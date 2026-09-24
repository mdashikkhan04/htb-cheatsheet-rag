# HTB Cheatsheet Assistant (RAG)

A Retrieval-Augmented Generation system that answers natural-language questions
about offensive-security techniques by **retrieving** passages from the
[htb-wiki](https://github.com/0xh7ml/htb-wiki) corpus of Hack The Box write-ups
(by 0xdf) and **synthesizing a grounded, cited answer** — grouped by technique,
with the specific machines that demonstrate each one, e.g. `(seen on: Absolute,
APT)`. Answers come from the retrieved text, not the model's own memory.

```
Reference query:  "Provide me the Windows privilege escalation cheatsheet."
→ SAM/SYSTEM hive dump · Potato family (SeImpersonate) · ADCS abuse ·
  ACL/BloodHound abuse · DCSync · Kerberoast/AS-REP · Shadow Credentials …
  each with a one-line explanation and (seen on: <machines>).
```

## Highlights

- **Heading-aware chunking** that preserves each technique section and its
  machine/OS/heading provenance (513 files → 32,442 chunks).
- **Three retrievers**: BM25 (sparse lexical, zero-dependency, default),
  TF-IDF cosine (vector space), and a reciprocal-rank-fusion **hybrid**; an
  optional neural dense path if `sentence-transformers` is installed.
- **Grounded synthesis** with a strict "answer only from retrieved passages"
  prompt for Anthropic/OpenAI, **plus a deterministic offline synthesizer** that
  produces grouped, cited cheatsheets with **no API key** — so the system, and
  its evaluation, run fully offline.
- **Hand-derived evaluation**: 15-question test set + gold answer key built by
  reading the raw files; retrieval recall/precision and a synthesis
  grounding/hallucination check. **0 hallucinated citations; MRR 0.95 on
  specific questions.**

## Install & build (Windows / macOS / Linux)

The project is a standard pip-installable package, so the commands are identical
on every OS. Installing it (`pip install -e .`) puts an `htbrag` command on your
PATH — no `PYTHONPATH` or activation tricks needed.

```bash
# 1. get the code + the dataset (side by side)
git clone <this-repo>
cd htb-cheatsheet-rag
git clone https://github.com/0xh7ml/htb-wiki.git ../htb-wiki

# 2. install (creates the `htbrag` command). Use `python` on Windows, `python3` on mac/Linux.
python -m pip install -e .          # deps: numpy + scikit-learn only

# 3. build & cache the index, then ask
htbrag build --raw ../htb-wiki/raw
htbrag ask "Provide me the Windows privilege escalation cheatsheet." --k 60
```

> Notes · Python 3.10+ required. · If the `htbrag` command isn't found, use the
> equivalent `python -m htbrag ...` form. · BM25 retrieval and the offline
> synthesizer need no scikit-learn at all; scikit-learn only powers the
> TF-IDF/hybrid retriever. · A virtual environment is optional but recommended
> (`python -m venv .venv`; then `.venv\Scripts\activate` on Windows or
> `source .venv/bin/activate` on mac/Linux).

## Ask a question

```bash
# Offline, grouped, cited (no API key needed):
htbrag ask "Provide me the Windows privilege escalation cheatsheet." --k 60

# Specific question, BM25 only, show the sources behind the answer:
htbrag ask "How does PrintSpoofer abuse SeImpersonatePrivilege and which machines use it?" \
  --backend bm25 --show-sources

# Use a real LLM for synthesis (retrieval stays the same). Set the key first:
#   Windows PowerShell:  $env:ANTHROPIC_API_KEY="..."
#   macOS / Linux:       export ANTHROPIC_API_KEY=...
htbrag ask "Give me a Linux privilege escalation cheatsheet." --synth auto
```

Key flags: `--backend {bm25,tfidf,hybrid,dense,hybrid-dense}` ·
`--synth {extractive,auto,anthropic,openai}` · `--k <n>` · `--show-sources`.

## Evaluate

```bash
python eval/evaluate.py                     # prints tables, writes eval/results.json
python tests/derive_gold.py --raw ../htb-wiki/raw > tests/gold_sets.json   # regen gold
```

(`eval/` and `tests/` scripts add `src/` to the path themselves, so they run
with or without the install.)

## How it works

```
raw/*.md ──ingest.py──► heading-aware chunks ──index.py──► BM25 + TF-IDF (+dense)
                                                              │
   query ──retrieve.py──► query expansion + OS filter + RRF ──► top-k chunks
                                                              │
                         synthesize.py ──► LLM (grounded prompt)  ── or ──►
                                           offline extractive grouping ──► cited answer
```

| Module | Responsibility |
|---|---|
| `src/htbrag/ingest.py` | load write-ups, extract machine/OS/difficulty, heading-aware chunking |
| `src/htbrag/index.py` | tokenizer (camelCase-aware), BM25 (from scratch), TF-IDF, optional dense |
| `src/htbrag/taxonomy.py` | technique taxonomy: query expansion, OS routing, offline grouping |
| `src/htbrag/retrieve.py` | backends, query expansion, OS filter, hybrid RRF, per-machine dedup |
| `src/htbrag/synthesize.py` | grounded LLM synthesis + offline extractive synthesizer |
| `src/htbrag/rag.py` / `cli.py` | pipeline orchestration + command line |
| `tests/` | test set, hand-derived gold + answer key, derivation script |
| `eval/` | evaluation harness + writeup |

## Deliverables map

- **Working code + README** — this repo (`src/`, CLI).
- **Test set + hand-derived answer key** — `tests/test_set.jsonl`,
  `tests/answer_key.md`, `tests/derive_gold.py`.
- **Evaluation writeup** — `eval/EVALUATION.md` (+ `eval/evaluate.py`,
  `eval/results.json`).
- **Design note** — `DESIGN_NOTE.md`.

## Credits & disclaimer

Write-ups by **0xdf** (https://0xdf.gitlab.io), reorganised into the
`htb-wiki` corpus (credit: original *llm-wiki* by Andrej Karpathy). This project
only indexes that **publicly available educational** content for retrieval; it
adds no exploit code of its own.
