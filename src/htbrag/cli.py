"""
Command-line interface.

  python -m htbrag.cli build  --raw ../htb-wiki/raw
  python -m htbrag.cli ask    "Provide me the Windows privilege escalation cheatsheet."
  python -m htbrag.cli ask    "..." --backend bm25 --synth anthropic --k 40 --show-sources
  python -m htbrag.cli eval   --test tests/test_set.jsonl --k 10
"""
from __future__ import annotations

import argparse
import os
import sys

from .rag import RAGPipeline, DEFAULT_CACHE


def _ensure_pipeline(args) -> RAGPipeline:
    if os.path.exists(args.cache) and not getattr(args, "rebuild", False):
        return RAGPipeline.load(args.cache, dense=getattr(args, "dense", False))
    if not getattr(args, "raw", None):
        sys.exit(f"No index at {args.cache}. Run: python -m htbrag.cli build --raw <raw_dir>")
    print(f"[build] indexing corpus from {args.raw} ...", file=sys.stderr)
    return RAGPipeline.build(args.raw, cache=args.cache)


def cmd_build(args):
    pipe = RAGPipeline.build(args.raw, cache=args.cache)
    print("[build] done:", pipe.stats)


def cmd_ask(args):
    pipe = _ensure_pipeline(args)
    try:
        ans, hits = pipe.answer(
            args.question, k=args.k,
            retrieval_backend=args.backend, synth_backend=args.synth,
        )
    except RuntimeError as exc:
        sys.exit(f"[synth] {exc}\n"
                 f"       Set ANTHROPIC_API_KEY / OPENAI_API_KEY, or use "
                 f"--synth extractive to run fully offline.")
    print("=" * 78)
    print(ans.text)
    print("=" * 78)
    print(f"[retrieval={args.backend} synth={ans.backend} k={args.k}] "
          f"cited machines: {', '.join(ans.cited_machines) or '(none)'}")
    if args.show_sources:
        print("\n--- retrieved passages ---")
        for i, h in enumerate(hits, 1):
            print(f"[{i}] {h.chunk.machine} ({h.chunk.os}) :: {h.chunk.heading_path} "
                  f"score={h.score:.3f}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="htbrag", description="HTB Cheatsheet Assistant (RAG)")
    p.add_argument("--cache", default=DEFAULT_CACHE, help="index cache path")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build + cache the index")
    b.add_argument("--raw", required=True, help="path to htb-wiki/raw")
    b.set_defaults(func=cmd_build)

    a = sub.add_parser("ask", help="answer a question")
    a.add_argument("question")
    a.add_argument("--raw", help="raw dir (only needed if no cache yet)")
    a.add_argument("--k", type=int, default=12)
    a.add_argument("--backend", default="hybrid",
                   choices=["bm25", "tfidf", "hybrid", "dense", "hybrid-dense"])
    a.add_argument("--synth", default="extractive",
                   help="extractive | auto | anthropic | openai")
    a.add_argument("--dense", action="store_true", help="load dense index")
    a.add_argument("--rebuild", action="store_true")
    a.add_argument("--show-sources", action="store_true")
    a.set_defaults(func=cmd_ask)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
