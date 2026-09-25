# Design Note

**Chunking.** Each write-up is split on Markdown headings, keeping the heading
path plus machine/OS metadata on every chunk (513 files → 32,442 chunks).
Headings are the author's own technique boundaries, so a chunk holds one
technique intact; sections over ~1,400 chars are window-split with 180-char
overlap so a command stays with its explanation. That per-chunk provenance is
what lets answers cite `(seen on: <machine>)`.

**Lexical vs. embedding.** BM25 (sparse lexical) is the primary retriever, with
a TF-IDF vector retriever and an RRF **hybrid** alongside; a neural dense option
(sentence-transformers) sits behind a flag. The domain is keyword-exact — tool
names (`PrintSpoofer`), technique tags (`ESC1`), CVE IDs — where semantic blur
hurts (dense models conflate `ESC1`/`ESC8`). BM25 rewards the exact rare term,
is deterministic, and needs no model or GPU; a camelCase-splitting tokenizer
recovers most of what embeddings would add. In evaluation BM25 stays within ~2
points of TF-IDF/hybrid on specific questions with the best specific recall
(R@20 0.70), at zero dependencies. **Hybrid is the production default.**

**No vector DB.** At 32k chunks brute-force cosine is milliseconds, so a hosted
store (Pinecone) adds ops, latency and cost for no gain. At larger scale:
FAISS/Chroma first, a managed DB only when it must be distributed.

**One week more.** Add retrieve → cross-encoder rerank → group, plus a
claim-level citation check (verify each cited machine actually contains the
claimed technique). This targets the two weak spots the eval shows — broad-query
precision and grouping quality.
