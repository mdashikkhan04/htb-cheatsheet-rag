# Evaluation

**System:** HTB Cheatsheet Assistant (RAG). **Corpus:** 513 write-ups → 32,442
heading-aware chunks. **Test set:** 15 questions (5 broad "cheatsheet", 10
specific "which machines / how"), scored against a hand-derived answer key
(`tests/answer_key.md`, gold in `tests/gold_sets.json`). Reproduce with
`PYTHONPATH=src python3 eval/evaluate.py`.

Relevance is scored at the **machine** level: a retrieved chunk counts as
relevant when its machine is in the question's gold set. Metrics are macro-
averaged; retrieval uses one chunk per machine so top-*k* means *k* distinct
machines.

## 1. Retrieval — recall / precision

| Split | Backend | P@5 | P@10 | R@10 | R@20 | MRR |
|---|---|---|---|---|---|---|
| **Specific (10 Q)** | bm25 | 0.86 | 0.79 | 0.53 | **0.70** | 0.95 |
| | tfidf | 0.88 | 0.74 | 0.51 | 0.66 | 0.95 |
| | hybrid | 0.88 | 0.77 | 0.52 | 0.69 | 0.95 |
| **Broad (5 Q)** | bm25 | 0.72 | 0.74 | 0.07 | 0.15 | 0.75 |
| | tfidf | 0.84 | 0.82 | 0.09 | 0.16 | 0.87 |
| | hybrid | 0.84 | 0.76 | 0.08 | 0.14 | 0.80 |

**Reading the numbers.** On specific questions the system is accurate: the first
result is almost always a correct machine (MRR 0.95) and roughly 70 % of all gold
machines are recovered within 20 hits (R@20). The three backends are close;
BM25 alone — zero dependencies — is within a couple of points of the vector and
hybrid retrievers, and gives the best specific-question recall.

**Why broad-question recall looks low (and why that is expected).** The broad
gold sets are huge — Linux privesc = 298 machines, sudo/GTFOBins = 191, Windows
privesc = 89. Recall@10 is mechanically capped at `10/|gold|` (≈ 0.03 for Linux
privesc), so a low value is arithmetic, not a miss. The right lens for these is
precision — 0.74–0.82 P@10 means the cheatsheet is built from correct,
on-topic machines — plus the *grouped coverage* the synthesizer produces (the
Windows-privesc answer surfaces 8 distinct technique groups across 22 machines).

**Per-question highlights (hybrid).** Perfect P@10 on potato (Q06), Kerberoast
(Q08), DCSync (Q09), AS-REP (Q13). Log4Shell (Q07) and PwnKit (Q10) reach
R@10 = 1.0 (all gold machines found); their P@10 of 0.2–0.4 is only because the
gold set has 2–4 machines, so slots 5–10 cannot be filled with gold. The weakest
case is ADCS (Q05, P@10 0.40): the query expansion pulls broadly-related AD boxes
that are not in the narrow `adcs` gold set.

## 2. Synthesis quality

Scored with the deterministic offline (extractive) synthesizer so results are
reproducible without an API key; the same grounding checks apply to the LLM
backend.

- **Citation correctness — mean precision 0.86.** Of the machines the answer
  cites, 86 % are in the gold set. It is 1.00 on 9 of 15 questions (potato,
  Kerberoast, DCSync, AS-REP, shadow-cred, docker/lxd, sudo, ACL, Linux-privesc).
- **Hallucination — 0 across all 15 questions.** Every cited machine appears in
  a retrieved chunk; the synthesizer cannot name a machine it did not retrieve,
  by construction. No invented techniques, machines, or CVEs were observed.
- **Where citations slip.** ADCS (0.32) and the Windows/SAM cheatsheets mix in a
  few adjacent-but-not-gold machines — a *precision of grouping* issue driven by
  broad pattern matching, not fabrication.

**Qualitative note on the reference query.** "Provide me the Windows privilege
escalation cheatsheet" returns a grouped, cited answer — SAM/SYSTEM dump, potato
family, ADCS, ACL/BloodHound, DCSync, Kerberoast/AS-REP, shadow credentials,
token privileges — each with a one-line explanation and `(seen on: …)` machine
citations (e.g. ACL/BloodHound → Absolute, which its write-up confirms). This is
the intended behaviour and it is grounded, not model-memory recall.

## 3. Takeaways

The system is strong on precision and grounding (the qualities that matter for a
cheatsheet you would actually trust) and honest about recall on very broad
queries. BM25 is a genuinely competitive, dependency-free default; the hybrid
retriever is the safest all-round choice and the recommended production setting.
