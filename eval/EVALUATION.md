# Evaluation

**Setup.** 513 write-ups → 32,442 heading-aware chunks. Test set: 15 questions
(5 broad "cheatsheet", 10 specific "which machines / how"), scored against a
hand-derived answer key (`tests/answer_key.md`). Relevance is at the **machine**
level — a chunk counts if its machine is in the question's gold set. Reproduce
with `python eval/evaluate.py`.

## Retrieval (macro-averaged)

| Split | Backend | P@5 | P@10 | R@10 | R@20 | MRR |
|---|---|---|---|---|---|---|
| Specific (10) | bm25 | 0.86 | 0.79 | 0.53 | **0.70** | 0.95 |
| | tfidf | 0.88 | 0.74 | 0.51 | 0.66 | 0.95 |
| | hybrid | 0.88 | 0.77 | 0.52 | 0.69 | 0.95 |
| Broad (5) | bm25 | 0.72 | 0.74 | 0.07 | 0.15 | 0.75 |
| | tfidf | 0.84 | 0.82 | 0.09 | 0.16 | 0.87 |
| | hybrid | 0.84 | 0.76 | 0.08 | 0.14 | 0.80 |

**Reading it.** On specific questions the first hit is almost always a correct
machine (MRR 0.95) and ~70% of gold machines are found within 20 hits (R@20).
Broad-question recall looks low only by arithmetic: gold sets run 89–298
machines, so R@10 is capped near 10/|gold| — there the right lens is precision
(0.74–0.82 P@10) plus grouped coverage. The backends are close, so BM25 alone
(zero-dependency) is competitive and hybrid is the safe default. Perfect P@10 on
potato, Kerberoast, DCSync and AS-REP; weakest is ADCS (P@10 0.40), where query
expansion pulls in adjacent AD boxes.

## Synthesis quality

Scored with the deterministic offline synthesizer so results reproduce without an
API key. The LLM backend uses the same "answer only from the retrieved passages"
grounding, so these checks apply to both.

- **Citation correctness — mean precision 0.86** (1.00 on 9 of 15 questions).
- **Hallucination — 0 across all 15**: every cited machine appears in a
  retrieved chunk, by construction; no invented techniques, machines or CVEs.
- Citations slip only where grouping is broad (ADCS, SAM) — never as fabrication.

**Reference query.** "Windows privilege escalation cheatsheet" returns a grouped,
cited answer (SAM/SYSTEM dump, potato, ADCS, ACL/BloodHound, DCSync,
Kerberoast/AS-REP, shadow credentials), each with a one-line explanation and a
`(seen on: …)` citation — e.g. ACL/BloodHound → Absolute, which its write-up
confirms. This is grounded output, not model memory.

**Takeaway.** The system is strong on the qualities a cheatsheet must have —
precision and grounding — and honest about recall on very broad queries. Hybrid
retrieval is the recommended default.
