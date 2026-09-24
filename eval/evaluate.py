#!/usr/bin/env python3
"""
Evaluate retrieval + synthesis against the hand-derived answer key.

Retrieval (machine-level, gold from tests/gold_sets.json):
    Precision@5, Precision@10, Recall@10, Recall@20, MRR
    compared across backends: bm25 / tfidf / hybrid.

Synthesis (offline extractive backend, deterministic):
    - citation precision  = |cited ∩ gold| / |cited|      (did it cite correctly)
    - citation recall     = |cited ∩ gold| / |gold|
    - hallucinated cites  = machines cited but NOT in any retrieved chunk
                            (grounding violation — should always be 0)

Usage:
    PYTHONPATH=src python3 eval/evaluate.py --raw ../htb-wiki/raw \
        --test tests/test_set.jsonl --gold tests/gold_sets.json --out eval/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# let this script find the package whether or not it was pip-installed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from htbrag.rag import RAGPipeline
from htbrag.synthesize import ExtractiveSynthesizer


def unique_machines(hits):
    """The machines behind a ranked list of chunks, in order, each once."""
    seen, machines = set(), []
    for hit in hits:
        if hit.chunk.machine_slug not in seen:
            seen.add(hit.chunk.machine_slug)
            machines.append(hit.chunk.machine_slug)
    return machines


def precision_recall_at_k(retrieved, gold, k):
    """Precision and recall of the top-k retrieved machines against the gold set."""
    top_k = retrieved[:k]
    correct = [m for m in top_k if m in gold]
    precision = len(correct) / len(top_k) if top_k else 0.0
    recall = len(correct) / len(gold) if gold else 0.0
    return precision, recall


def reciprocal_rank(retrieved, gold):
    """1 / rank of the first correct machine (0 if none). Averaged, this is MRR."""
    for rank, machine in enumerate(retrieved, 1):
        if machine in gold:
            return 1.0 / rank
    return 0.0


def evaluate(pipe, tests, gold_sets, backends):
    rows = []
    for t in tests:
        gold = set(gold_sets[t["technique_key"]])
        row = {"id": t["id"], "type": t["type"], "q": t["question"],
               "gold_n": len(gold), "backends": {}}
        for b in backends:
            hits = pipe.retrieve(t["question"], k=20, backend=b, per_machine_cap=1)
            machines = unique_machines(hits)
            p5, _ = precision_recall_at_k(machines, gold, 5)
            p10, r10 = precision_recall_at_k(machines, gold, 10)
            _, r20 = precision_recall_at_k(machines, gold, 20)
            row["backends"][b] = {
                "P@5": round(p5, 3), "P@10": round(p10, 3),
                "R@10": round(r10, 3), "R@20": round(r20, 3),
                "MRR": round(reciprocal_rank(machines, gold), 3),
                "top10": machines[:10],
            }
        rows.append(row)
    return rows


def synth_eval(pipe, tests, gold_sets):
    synth = ExtractiveSynthesizer()
    out = []
    for t in tests:
        gold = set(gold_sets[t["technique_key"]])
        hits = pipe.retrieve(t["question"], k=40, backend="hybrid", per_machine_cap=2)
        retrieved_machines = {h.chunk.machine for h in hits}
        ans = synth.synthesize(t["question"], hits)
        cited = ans.cited_machines
        cited_slug = [c.lower().replace(" ", "") for c in cited]
        gold_slug = {g.replace("-", "") for g in gold}
        hit = [c for c in cited_slug if c in gold_slug]
        halluc = [c for c in cited if c not in retrieved_machines]
        out.append({
            "id": t["id"], "type": t["type"], "n_cited": len(cited),
            "cite_precision": round(len(hit) / len(cited), 3) if cited else 0.0,
            "cite_recall": round(len(hit) / len(gold), 3) if gold else 0.0,
            "hallucinated": halluc,
        })
    return out


METRICS = ["P@5", "P@10", "R@10", "R@20", "MRR"]


def macro_average(rows, backends, question_type=None):
    """Average each metric across questions (optionally only 'broad'/'specific')."""
    selected = [r for r in rows if question_type is None or r["type"] == question_type]
    averages: dict[str, dict[str, float]] = {}
    for backend in backends:
        averages[backend] = {}
        for metric in METRICS:
            values = [r["backends"][backend][metric] for r in selected]
            averages[backend][metric] = round(sum(values) / len(values), 3) if values else 0.0
    return averages


def format_table(averages, backends):
    """Render the averaged metrics as a small Markdown table."""
    lines = ["| backend | " + " | ".join(METRICS) + " |",
             "|" + "---|" * (len(METRICS) + 1)]
    for backend in backends:
        cells = " | ".join(f"{averages[backend][m]:.3f}" for m in METRICS)
        lines.append(f"| {backend} | {cells} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="../htb-wiki/raw")
    ap.add_argument("--cache", default=os.path.join(os.path.dirname(__file__), "..", "data", "corpus.pkl"))
    ap.add_argument("--test", default=os.path.join(os.path.dirname(__file__), "..", "tests", "test_set.jsonl"))
    ap.add_argument("--gold", default=os.path.join(os.path.dirname(__file__), "..", "tests", "gold_sets.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results.json"))
    args = ap.parse_args()

    backends = ["bm25", "tfidf", "hybrid"]
    if os.path.exists(args.cache):
        pipe = RAGPipeline.load(args.cache)
    else:
        pipe = RAGPipeline.build(args.raw, cache=args.cache)

    tests = [json.loads(l) for l in open(args.test) if l.strip()]
    gold_sets = json.load(open(args.gold))

    rows = evaluate(pipe, tests, gold_sets, backends)
    synth = synth_eval(pipe, tests, gold_sets)

    result = {
        "n_questions": len(tests),
        "macro_all": macro_average(rows, backends),
        "macro_broad": macro_average(rows, backends, "broad"),
        "macro_specific": macro_average(rows, backends, "specific"),
        "per_question": rows,
        "synthesis": synth,
    }
    json.dump(result, open(args.out, "w"), indent=2)

    print(f"# Retrieval — macro over {len(tests)} questions (machine-level)\n")
    print("ALL:\n" + format_table(result["macro_all"], backends))
    print("\nBROAD:\n" + format_table(result["macro_broad"], backends))
    print("\nSPECIFIC:\n" + format_table(result["macro_specific"], backends))
    print("\n# Per-question (hybrid): P@10 / R@10 / MRR")
    for r in rows:
        h = r["backends"]["hybrid"]
        print(f"  {r['id']} [{r['type'][:4]}] gold={r['gold_n']:3d}  "
              f"P@10={h['P@10']:.2f} R@10={h['R@10']:.2f} MRR={h['MRR']:.2f}  {r['q'][:52]}")
    print("\n# Synthesis (extractive) — citation precision / recall / hallucinations")
    hall_total = 0
    for s in synth:
        hall_total += len(s["hallucinated"])
        print(f"  {s['id']} cited={s['n_cited']:2d}  cite_P={s['cite_precision']:.2f} "
              f"cite_R={s['cite_recall']:.2f}  halluc={s['hallucinated'] or 0}")
    cp = sum(s["cite_precision"] for s in synth) / len(synth)
    print(f"\n  mean citation precision = {cp:.3f}   total hallucinated citations = {hall_total}")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
