# Design Note

## Chunking strategy

Each write-up is split **along its Markdown headings**, and every chunk carries
its full heading path (e.g. `Shell as SYSTEM > SeImpersonate > PrintSpoofer`)
plus its machine, OS and difficulty. Headings are the author's own semantic
boundaries — one technique per section — so heading chunks keep a technique
intact instead of splitting it mid-thought. Sections longer than ~1,400
characters are window-split on paragraph boundaries with a 180-char overlap so a
command and its explanation are not severed. Fenced code blocks are detected so
that `#` lines inside pasted shell output are never mistaken for headings. The
machine name and heading path are folded into the indexed text, which lets a
query naming a machine or a phase ("privesc", "foothold") match directly, and —
crucially — gives every chunk the provenance the synthesizer needs to cite
`(seen on: <machine>)`. Result: 513 files → 32,442 chunks.

## Lexical vs. embedding retrieval

I chose **BM25 (sparse lexical) as the primary retriever**, with a TF-IDF
vector retriever and a reciprocal-rank-fusion **hybrid** alongside, and an
optional neural dense path (sentence-transformers) behind a lazy import.

Reasoning: this domain is unusually **keyword-exact**. The signal lives in tool
names (`PrintSpoofer`, `secretsdump`, `certipy`), technique tags (`ESC1`,
`GenericAll`) and CVE numbers (`CVE-2021-4034`) — tokens where an approximate
semantic match is a *liability*: dense embeddings happily blur `ESC1` into
`ESC8`, or `CVE-2021-4034` (PwnKit) into a neighbouring CVE. BM25 rewards the
exact rare term. It is also deterministic, needs no model download or GPU, and
runs in-process — so the grader can reproduce every number offline. The one
place naive lexical retrieval hurts is compound tokens, so the shared tokenizer
splits camelCase/snake_case (`SeImpersonatePrivilege` → `se`, `impersonate`,
`privilege`) while keeping the original compound, which recovers most of what an
embedding model would give here. The evaluation bears this out: BM25 is within
~2 points of TF-IDF and the hybrid on specific questions and has the best
specific-question recall (R@20 0.70), at zero dependencies. The hybrid is the
recommended production default — it is the most robust across query phrasings
without giving up lexical precision.

## Why no vector database (e.g. Pinecone)

Deliberately none. A vector DB earns its keep at scale — millions of dense
vectors needing approximate-nearest-neighbour search, hosted and sharded. This
corpus is 32,442 chunks: brute-force cosine over it is milliseconds in-process,
so a hosted store (Pinecone/Weaviate) would only add an external service, API
keys, network latency and cost for zero retrieval benefit — over-engineering for
the size. The primary retriever is lexical (BM25), which isn't a dense-vector
workload at all. If the corpus grew by orders of magnitude, the scale-appropriate
step is a local ANN index (FAISS / Chroma) first, and a managed vector DB only
when it must be distributed — the retriever interface is small, so swapping the
backend is a contained change.

## One improvement with another week

Add a **retrieve → rerank → group** stage. Keep BM25/hybrid as a high-recall
first pass (top ~100), then apply a cross-encoder reranker (e.g.
`ms-marco-MiniLM`) to reorder by true query–passage relevance, and cluster the
survivors by technique before synthesis. This directly targets the two weak
spots the eval exposed — broad-query precision (ADCS pulled adjacent AD boxes)
and cheatsheet grouping quality — by letting a relevance model, rather than
lexical overlap, decide the final ordering, and by making the technique buckets
data-driven instead of relying on the hand-curated taxonomy. I would also add a
lightweight **claim-level citation check** at answer time (verify each sentence's
cited machine actually contains the claimed tool/technique) to push synthesis
precision toward the 1.0 the grounding check already guarantees for fabrication.
