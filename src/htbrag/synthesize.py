"""
Synthesis: turn retrieved chunks into a grounded, cited answer.

Two synthesizers, selected by `backend`:

  * LLMSynthesizer       - calls Anthropic or OpenAI. A strict system prompt
                           forces the model to answer ONLY from the numbered
                           passages and to cite machines as "(seen on: X, Y)".
  * ExtractiveSynthesizer- NO API key needed. Buckets retrieved chunks into the
                           technique taxonomy and emits a grouped cheatsheet
                           with machine citations pulled straight from the
                           retrieved chunks. Guarantees a grounded, cited answer
                           offline, and is used for deterministic evaluation.

Both take the same (query, hits) and return an `Answer` with the text plus the
set of cited machines, so the evaluator can check citation grounding.
"""
from __future__ import annotations

import os
import re
import textwrap
from dataclasses import dataclass, field

from .retrieve import Hit
from . import taxonomy


@dataclass
class Answer:
    text: str
    cited_machines: list[str] = field(default_factory=list)
    used_machines: list[str] = field(default_factory=list)   # machines in retrieved set
    backend: str = ""


def _context_block(hits: list[Hit], max_chars_each: int = 900) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        body = h.chunk.text.strip()
        if len(body) > max_chars_each:
            body = body[:max_chars_each] + " …"
        lines.append(
            f"[{i}] machine={h.chunk.machine} | os={h.chunk.os} | "
            f"section={h.chunk.heading_path}\n{body}"
        )
    return "\n\n".join(lines)


SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are an offensive-security assistant that answers ONLY from the retrieved
    passages provided by the user. These passages come from Hack The Box
    write-ups.

    Rules:
    - Use only information present in the numbered passages. If something is not
      in them, do not state it. Never use outside/training knowledge to add
      techniques, machines, commands, or CVEs.
    - For a "cheatsheet"/overview question, GROUP the techniques (e.g. SAM/SYSTEM
      hive dump, potato-family SeImpersonate abuse, ADCS certificate abuse,
      ACL/BloodHound abuse, Kerberoast/AS-REP, DCSync). Give each group a one- or
      two-line explanation.
    - After each technique, cite the specific machine(s) that demonstrate it,
      using the passage metadata, in the form "(seen on: Absolute, APT)".
    - Prefer precision over breadth. If passages are thin on a technique, say so
      rather than inventing detail.
    - Keep it tight and practical, like a cheatsheet.
    """
)


class LLMSynthesizer:
    def __init__(self, backend: str = "auto", model: str | None = None):
        self.backend = backend
        self.model = model

    def _resolve(self) -> str:
        if self.backend in ("anthropic", "openai"):
            return self.backend
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        raise RuntimeError("No LLM API key found (ANTHROPIC_API_KEY / OPENAI_API_KEY).")

    def synthesize(self, query: str, hits: list[Hit]) -> Answer:
        provider = self._resolve()
        context = _context_block(hits)
        user = f"Question: {query}\n\nRetrieved passages:\n\n{context}\n\nAnswer:"
        if provider == "anthropic":
            import anthropic  # lazy

            client = anthropic.Anthropic()
            msg = client.messages.create(
                model=self.model or "claude-3-5-sonnet-latest",
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(b.text for b in msg.content if b.type == "text")
        else:
            from openai import OpenAI  # lazy

            client = OpenAI()
            resp = client.chat.completions.create(
                model=self.model or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                max_tokens=1200,
            )
            text = resp.choices[0].message.content or ""
        used = _unique([h.chunk.machine for h in hits])
        cited = _machines_mentioned(text, used)
        return Answer(text=text, cited_machines=cited, used_machines=used, backend=provider)


class ExtractiveSynthesizer:
    """Deterministic, offline, grounded. Groups retrieved chunks by taxonomy."""

    def synthesize(self, query: str, hits: list[Hit]) -> Answer:
        used = _unique([h.chunk.machine for h in hits])
        os_hint = taxonomy.detect_os(query)
        if taxonomy.is_cheatsheet(query) or re.search(
            r"privilege escalation|privesc|escalat", query.lower()
        ):
            text, cited = self._cheatsheet(query, hits, os_hint)
        else:
            text, cited = self._specific(query, hits)
        return Answer(text=text, cited_machines=cited, used_machines=used,
                      backend="extractive")

    def _cheatsheet(self, query, hits, os_hint):
        pool = taxonomy.ALL_TECHNIQUES
        if os_hint == "Windows":
            pool = taxonomy.WINDOWS_PRIVESC
        elif os_hint == "Linux":
            pool = taxonomy.LINUX_PRIVESC

        buckets: dict[str, list[Hit]] = {t.key: [] for t in pool}
        for h in hits:
            blob = f"{h.chunk.heading_path}\n{h.chunk.text}"
            for t in pool:
                if taxonomy.matches(t.key, blob):
                    buckets[t.key].append(h)

        out = [f"# {os_hint or 'Offensive-security'} cheatsheet",
               f"_Grounded in {len(_unique([h.chunk.machine for h in hits]))} "
               f"retrieved write-up sections._\n"]
        cited: list[str] = []
        n = 0
        for t in pool:
            b = buckets[t.key]
            if not b:
                continue
            n += 1
            machines = _unique([h.chunk.machine for h in b])[:8]
            cited.extend(machines)
            out.append(f"## {n}. {t.name}")
            out.append(t.blurb)
            out.append(f"(seen on: {', '.join(machines)})\n")
        if n == 0:
            return self._specific(query, hits)
        return "\n".join(out), _unique(cited)

    def _specific(self, query, hits):
        q_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        out = [f"## Answer (grounded in retrieved write-ups)\n"]
        cited: list[str] = []
        for h in hits[:6]:
            snippet = _best_sentences(h.chunk.text, q_terms)
            cited.append(h.chunk.machine)
            out.append(f"**{h.chunk.machine}** — _{h.chunk.heading_path}_")
            out.append(f"{snippet}")
            out.append(f"(seen on: {h.chunk.machine})\n")
        return "\n".join(out), _unique(cited)


def _best_sentences(text: str, q_terms: set[str], max_len: int = 320) -> str:
    sents = re.split(r"(?<=[.!?])\s+|\n", text)
    scored = []
    for s in sents:
        toks = set(re.findall(r"[a-z0-9]+", s.lower()))
        overlap = len(toks & q_terms)
        if overlap:
            scored.append((overlap, s.strip()))
    scored.sort(reverse=True)
    if not scored:
        return text[:max_len].strip() + (" …" if len(text) > max_len else "")
    picked, total = [], 0
    for _, s in scored:
        if total + len(s) > max_len:
            break
        picked.append(s)
        total += len(s)
    return " ".join(picked) if picked else scored[0][1][:max_len]


def _unique(items) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _machines_mentioned(text: str, candidates: list[str]) -> list[str]:
    found = []
    for m in candidates:
        if re.search(rf"\b{re.escape(m)}\b", text, re.I):
            found.append(m)
    return _unique(found)


def get_synthesizer(backend: str):
    if backend in ("extractive", "offline", "none"):
        return ExtractiveSynthesizer()
    return LLMSynthesizer(backend=backend)
