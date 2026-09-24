"""
Retrieval layer: turns a natural-language query into a ranked list of chunks.

Backends:
  bm25    - sparse lexical (default, always available)
  tfidf   - vector-space cosine
  hybrid  - reciprocal-rank fusion of bm25 + tfidf  (default for `ask`)
  dense / hybrid-dense - if sentence-transformers + a DenseIndex are supplied

Features layered on top of the raw index:
  * query expansion for broad/cheatsheet queries (see taxonomy.expand_query)
  * optional OS filtering (a "Windows privesc" query drops Linux chunks)
  * de-duplication so one machine cannot swamp the top-k
"""
from __future__ import annotations

from dataclasses import dataclass

from .ingest import Chunk
from .index import Corpus, DenseIndex
from . import taxonomy


@dataclass
class Hit:
    chunk: Chunk
    score: float
    rank: int


def reciprocal_rank_fusion(rankings: list[list[int]], k: int,
                           constant: int = 60) -> list[tuple[int, float]]:
    """Merge several ranked lists into one.

    Each list votes for a chunk with a weight of 1 / (constant + position), so a
    chunk ranked highly by more than one retriever rises to the top. This is how
    the 'hybrid' backend combines BM25 and TF-IDF.
    """
    fused: dict[int, float] = {}
    for ranking in rankings:
        for position, chunk_id in enumerate(ranking):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (constant + position + 1)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)[:k]


class Retriever:
    def __init__(self, corpus: Corpus, dense: DenseIndex | None = None):
        self.corpus = corpus
        self.chunks = corpus.chunks
        self.dense = dense

    def _os_ok(self, chunk: Chunk, os_filter: str | None) -> bool:
        if not os_filter:
            return True
        # keep matching OS plus Unknown (don't over-filter on missing metadata)
        return chunk.os == os_filter or chunk.os == "Unknown"

    def search(
        self,
        query: str,
        k: int = 12,
        backend: str = "hybrid",
        expand: bool = True,
        os_filter: str | None = "auto",
        per_machine_cap: int | None = None,
        pool: int = 200,
    ) -> list[Hit]:
        q = taxonomy.expand_query(query) if expand else query
        if os_filter == "auto":
            os_filter = taxonomy.detect_os(query)

        bm25 = self.corpus.bm25
        tfidf = self.corpus.tfidf

        if backend == "bm25" or (backend in ("hybrid", "tfidf") and tfidf is None):
            ranked = bm25.search(q, k=pool)
        elif backend == "tfidf":
            ranked = tfidf.search(q, k=pool)
        elif backend == "dense":
            if not self.dense:
                raise ValueError("dense backend requested but no DenseIndex loaded")
            ranked = self.dense.search(q, k=pool)
        elif backend in ("hybrid", "hybrid-dense"):
            lists = [[d for d, _ in bm25.search(q, k=pool)]]
            if tfidf is not None:
                lists.append([d for d, _ in tfidf.search(q, k=pool)])
            if backend == "hybrid-dense" and self.dense is not None:
                lists.append([d for d, _ in self.dense.search(q, k=pool)])
            ranked = reciprocal_rank_fusion(lists, k=pool)
        else:
            raise ValueError(f"unknown backend: {backend}")

        hits: list[Hit] = []
        seen_per_machine: dict[str, int] = {}
        for did, score in ranked:
            chunk = self.chunks[did]
            if not self._os_ok(chunk, os_filter):
                continue
            if per_machine_cap is not None:
                n = seen_per_machine.get(chunk.machine_slug, 0)
                if n >= per_machine_cap:
                    continue
                seen_per_machine[chunk.machine_slug] = n + 1
            hits.append(Hit(chunk=chunk, score=float(score), rank=len(hits)))
            if len(hits) >= k:
                break
        return hits
