"""
Search indexes over the chunk corpus.

Three ways to rank chunks against a query, from simplest to heaviest:

  * BM25Index  - keyword (lexical) ranking, written from scratch with only the
                 standard library. This is the main retriever: no dependencies,
                 deterministic, and very good on the keyword-heavy questions this
                 corpus attracts (tool names like PrintSpoofer, tags like ESC1).
  * TfidfIndex - a vector-space cosine retriever built on scikit-learn. Used as
                 the "embedding-style" comparison and inside the hybrid.
  * DenseIndex - OPTIONAL neural embeddings (sentence-transformers). Only loaded
                 if that library is installed; everything works without it.

The `tokenize` function below is shared by all of them and is the single most
important lever for lexical quality: it splits camelCase / snake_case so that a
compound tool name like "SeImpersonate" also matches its parts ("impersonate"),
while still keeping the original word for exact matches.
"""
from __future__ import annotations

import math
import pickle
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence

from .ingest import Chunk

# Regexes that find the boundary inside a camelCase word:
#   "godPotato"  -> "god Potato"      (lower/digit followed by upper)
#   "ADCSAbuse"  -> "ADCS Abuse"      (run of uppers followed by Upper+lower)
_CAMEL_BOUNDARY_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_BOUNDARY_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_WORD = re.compile(r"[a-z0-9]+")

# Extremely common words that carry no search signal; dropped from every token list.
_STOPWORDS = set(
    "the a an and or of to in on for with is are be this that it as at by from "
    "i we you he she they can will would should could into out up down over "
    "then than so if not no yes do does did done have has had was were which "
    "what when where who why how there here their his her its our your my me".split()
)


def _return_unchanged(text: str) -> str:
    """Identity preprocessor for TfidfVectorizer (must be a named, picklable func)."""
    return text


def tokenize(text: str) -> list[str]:
    """Turn text into search tokens, splitting compound tool names apart.

    Examples:
        "SeImpersonatePrivilege" -> ["se", "impersonate", "privilege", "seimpersonateprivilege"]
        "GodPotato"              -> ["god", "potato", "godpotato"]
        "ESC1"                   -> ["esc1"]
    """
    # 1) break camelCase words into separate words, and treat _ and - as spaces
    spaced = _CAMEL_BOUNDARY_1.sub(r"\1 \2", text)
    spaced = _CAMEL_BOUNDARY_2.sub(r"\1 \2", spaced)
    spaced = spaced.replace("_", " ").replace("-", " ")

    tokens = [w for w in _WORD.findall(spaced.lower())
              if w not in _STOPWORDS and len(w) > 1]

    # 2) also keep each original (un-split) word, so exact tool names still match
    for word in _WORD.findall(text.lower()):
        if word not in _STOPWORDS and len(word) > 1 and word not in tokens:
            tokens.append(word)
    return tokens


class BM25Index:
    """Okapi BM25 keyword ranking over the chunks. Pure Python, no dependencies.

    BM25 scores a chunk by how many of the query's words it contains, weighting
    rare words more (idf) and not over-rewarding very long chunks (the b term).
    """

    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = list(chunks)
        self.k1 = k1          # how fast repeated words stop adding score
        self.b = b            # how strongly to correct for chunk length

        # tokenize every chunk once
        tokenized = [tokenize(c.index_text()) for c in self.chunks]
        self.doc_len = [len(t) for t in tokenized]
        self.n_docs = len(self.chunks)
        self.avg_len = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0

        # term frequency per chunk, and document frequency across the corpus
        self.term_freq = [Counter(t) for t in tokenized]
        doc_freq: Counter = Counter()
        for counter in self.term_freq:
            doc_freq.update(counter.keys())

        # inverse document frequency: rarer words score higher
        self.idf = {
            term: math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
            for term, df in doc_freq.items()
        }

        # inverted index: term -> list of (chunk_id, times it appears there)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for doc_id, counter in enumerate(self.term_freq):
            for term, freq in counter.items():
                self.postings[term].append((doc_id, freq))

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        """Return the top-k (chunk_id, score) for the query, best first."""
        query_terms = [t for t in tokenize(query) if t in self.idf]
        scores: dict[int, float] = defaultdict(float)
        for term in query_terms:
            idf = self.idf[term]
            for doc_id, freq in self.postings.get(term, []):
                length = self.doc_len[doc_id]
                denominator = freq + self.k1 * (1 - self.b + self.b * length / self.avg_len)
                scores[doc_id] += idf * (freq * (self.k1 + 1)) / denominator
        return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:k]


class TfidfIndex:
    """Vector-space cosine retriever using scikit-learn's TF-IDF."""

    def __init__(self, chunks: Sequence[Chunk]):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.chunks = list(chunks)
        # Reuse our tokenizer for a fair comparison with BM25; add bi-grams so the
        # vector model captures a little word-pair context that BM25 does not.
        self.vectorizer = TfidfVectorizer(
            tokenizer=tokenize,
            preprocessor=_return_unchanged,
            token_pattern=None,
            ngram_range=(1, 2),
            min_df=2,
            sublinear_tf=True,
        )
        self.matrix = self.vectorizer.fit_transform(c.index_text() for c in self.chunks)

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        from sklearn.metrics.pairwise import linear_kernel

        query_vec = self.vectorizer.transform([query])
        similarities = linear_kernel(query_vec, self.matrix).ravel()
        top = similarities.argsort()[::-1][:k]
        return [(int(i), float(similarities[i])) for i in top if similarities[i] > 0]


class DenseIndex:
    """OPTIONAL neural dense retriever (sentence-transformers).

    Behind a lazy import so the system runs without it. Enable with
    `pip install sentence-transformers` and pass backend 'dense' / 'hybrid-dense'.
    """

    def __init__(self, chunks: Sequence[Chunk], model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        import numpy as np

        self.chunks = list(chunks)
        self.model = SentenceTransformer(model_name)
        embeddings = self.model.encode(
            [c.index_text() for c in self.chunks],
            batch_size=64, show_progress_bar=False, normalize_embeddings=True,
        )
        self.embeddings = np.asarray(embeddings, dtype="float32")

    def search(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        import numpy as np

        query_vec = self.model.encode([query], normalize_embeddings=True)
        similarities = (self.embeddings @ np.asarray(query_vec).T).ravel()
        top = similarities.argsort()[::-1][:k]
        return [(int(i), float(similarities[i])) for i in top]


@dataclass
class Corpus:
    """The chunks plus their built indexes. Picklable, so we build once and cache."""

    chunks: list[Chunk]
    bm25: BM25Index
    tfidf: TfidfIndex | None = None

    def save(self, path: str) -> None:
        with open(path, "wb") as fh:
            pickle.dump(self, fh)

    @staticmethod
    def load(path: str) -> "Corpus":
        with open(path, "rb") as fh:
            return pickle.load(fh)

    @staticmethod
    def build(chunks: list[Chunk], with_tfidf: bool = True) -> "Corpus":
        bm25 = BM25Index(chunks)
        tfidf = None
        if with_tfidf:
            try:
                tfidf = TfidfIndex(chunks)
            except Exception as exc:
                print(f"[index] TF-IDF unavailable ({exc}); using BM25 only.")
        return Corpus(chunks=chunks, bm25=bm25, tfidf=tfidf)
