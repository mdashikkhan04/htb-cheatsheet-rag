"""HTB Cheatsheet Assistant (RAG) — retrieval-augmented answers over the
0xdf Hack The Box write-up corpus."""
from .rag import RAGPipeline
from .retrieve import Retriever, Hit
from .synthesize import Answer

__all__ = ["RAGPipeline", "Retriever", "Hit", "Answer"]
__version__ = "1.0.0"
