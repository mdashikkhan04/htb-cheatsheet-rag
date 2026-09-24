"""
RAGPipeline: ties ingestion -> indexing -> retrieval -> synthesis together and
provides a small on-disk cache so the index is built once.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .ingest import build_chunks
from .index import Corpus, DenseIndex
from .retrieve import Retriever, Hit
from .synthesize import get_synthesizer, Answer

DEFAULT_CACHE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "corpus.pkl")


@dataclass
class RAGPipeline:
    corpus: Corpus
    retriever: Retriever

    @staticmethod
    def build(raw_dir: str, cache: str | None = DEFAULT_CACHE,
              with_tfidf: bool = True, **chunk_kw) -> "RAGPipeline":
        chunks = build_chunks(raw_dir, **chunk_kw)
        corpus = Corpus.build(chunks, with_tfidf=with_tfidf)
        if cache:
            os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
            corpus.save(cache)
        return RAGPipeline(corpus=corpus, retriever=Retriever(corpus))

    @staticmethod
    def load(cache: str = DEFAULT_CACHE, dense: bool = False) -> "RAGPipeline":
        corpus = Corpus.load(cache)
        dense_idx = DenseIndex(corpus.chunks) if dense else None
        return RAGPipeline(corpus=corpus, retriever=Retriever(corpus, dense=dense_idx))

    def retrieve(self, query: str, k: int = 12, backend: str = "hybrid",
                 **kw) -> list[Hit]:
        return self.retriever.search(query, k=k, backend=backend, **kw)

    def answer(self, query: str, k: int = 12, retrieval_backend: str = "hybrid",
               synth_backend: str = "extractive", **kw) -> tuple[Answer, list[Hit]]:
        hits = self.retrieve(query, k=k, backend=retrieval_backend, **kw)
        synth = get_synthesizer(synth_backend)
        ans = synth.synthesize(query, hits)
        return ans, hits

    @property
    def stats(self) -> dict:
        chunks = self.corpus.chunks
        machines = {c.machine_slug for c in chunks}
        by_os: dict[str, int] = {}
        for c in chunks:
            by_os[c.os] = by_os.get(c.os, 0) + 1
        return {"chunks": len(chunks), "machines": len(machines), "by_os": by_os}
