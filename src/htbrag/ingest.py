"""
Ingestion + heading-aware chunking for the HTB write-up corpus.

Each raw file is one 0xdf Hack The Box write-up in Markdown. We:
  1. Parse light metadata (machine name, OS, difficulty) from the header.
  2. Split the document along Markdown headings, keeping the heading *path*
     (e.g. "Shell as svc > PrintSpoofer") as chunk context.
  3. Window-split oversized sections with overlap so no chunk is too large
     for the retriever / LLM context.

The chunk is the unit of retrieval. Every chunk keeps its provenance
(machine + section) so the synthesizer can cite "(seen on: <machine>)".
"""
from __future__ import annotations

import os
import re
import glob
import time
from dataclasses import dataclass, field, asdict
from typing import Iterable


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
# In this corpus the OS shows up as an icon image reference, e.g. "OS ![Windows]".
OS_RE = re.compile(r"OS\s*!\[(Windows|Linux|FreeBSD|OpenBSD|Android|Solaris)\]", re.I)
OS_ICON_RE = re.compile(r"/icons/(Windows|Linux|FreeBSD|OpenBSD|Android|Solaris)\.", re.I)
DIFF_RE = re.compile(r"\b(Easy|Medium|Hard|Insane)\b")


@dataclass
class Chunk:
    id: str
    machine: str          # display name, e.g. "Absolute"
    machine_slug: str     # e.g. "absolute"
    os: str               # "Windows" | "Linux" | "Unknown"
    difficulty: str       # "Easy" | ... | "Unknown"
    heading_path: str     # "Recon > nmap"
    text: str             # raw section text (no synthetic header)
    source: str           # relative file path

    def index_text(self) -> str:
        """Text fed to the retriever: body + machine + heading terms so that
        queries mentioning a machine or a section name can match."""
        return f"{self.machine} {self.heading_path} {self.text}"

    def cite(self) -> str:
        return self.machine

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Document:
    machine: str
    machine_slug: str
    os: str
    difficulty: str
    source: str
    text: str


def machine_from_filename(path: str) -> tuple[str, str]:
    base = os.path.basename(path)
    slug = re.sub(r"\.md$", "", base)
    slug = re.sub(r"^htb-", "", slug)
    # Display: keep it simple and readable; hyphens -> spaces, title-case.
    display = slug.replace("-", " ").title()
    return display, slug


def detect_os(text: str) -> str:
    head = "\n".join(text.splitlines()[:80])
    m = OS_RE.search(head) or OS_ICON_RE.search(head)
    if m:
        return m.group(1).capitalize()
    return "Unknown"


def detect_difficulty(text: str) -> str:
    head = "\n".join(text.splitlines()[:80])
    # Prefer a difficulty word that appears on its own short line in Box Info.
    for line in head.splitlines():
        s = line.strip()
        if s in ("Easy", "Medium", "Hard", "Insane"):
            return s
    m = DIFF_RE.search(head)
    return m.group(1) if m else "Unknown"


def _read_text(path: str, attempts: int = 4) -> str:
    """Read a file, retrying briefly on transient OS errors.

    On Windows, antivirus (e.g. Defender) can momentarily lock a freshly
    git-cloned file while it scans it, which surfaces as OSError 22 on the first
    open. A short retry lets the scan finish; we also fall back to a binary read
    if the text open keeps failing.
    """
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError as err:
            last_err = err
            time.sleep(0.25 * (i + 1))
    # final fallback: read raw bytes and decode leniently
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        raise last_err if last_err else OSError(f"could not read {path}")


def load_document(path: str) -> Document:
    text = _read_text(path)
    display, slug = machine_from_filename(path)
    return Document(
        machine=display,
        machine_slug=slug,
        os=detect_os(text),
        difficulty=detect_difficulty(text),
        source=os.path.relpath(path),
        text=text,
    )


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Return list of (heading_path, body). Splits on Markdown headings and
    tracks a heading stack so nested sections carry their parents' context.

    Lines that look like headings but sit *inside* fenced code blocks are
    ignored (many write-ups paste shell output containing '#')."""
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []   # (level, title)
    cur_heading = "Overview"
    buf: list[str] = []
    in_fence = False

    def flush(heading: str, body_lines: list[str]):
        body = "\n".join(body_lines).strip()
        if body:
            sections.append((heading, body))

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            buf.append(line)
            continue
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            # close current section
            flush(cur_heading, buf)
            buf = []
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            cur_heading = " > ".join(t for _, t in stack)
        else:
            buf.append(line)
    flush(cur_heading, buf)
    return sections


def _window_split(body: str, max_chars: int, overlap: int) -> list[str]:
    if len(body) <= max_chars:
        return [body]
    # Split on blank lines (paragraph / block boundaries) then greedily pack.
    blocks = re.split(r"\n\s*\n", body)
    windows: list[str] = []
    cur = ""
    for blk in blocks:
        if not cur:
            cur = blk
        elif len(cur) + len(blk) + 2 <= max_chars:
            cur = cur + "\n\n" + blk
        else:
            windows.append(cur)
            # start next window with a tail overlap of the previous one
            tail = cur[-overlap:] if overlap else ""
            cur = (tail + "\n\n" + blk) if tail else blk
    if cur:
        windows.append(cur)
    # Any single block still larger than max_chars: hard-split it.
    out: list[str] = []
    for w in windows:
        if len(w) <= max_chars:
            out.append(w)
        else:
            for i in range(0, len(w), max_chars - overlap):
                out.append(w[i : i + max_chars])
    return out


def chunk_document(doc: Document, max_chars: int = 1400, overlap: int = 180,
                   min_chars: int = 40) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    for heading_path, body in _split_sections(doc.text):
        for window in _window_split(body, max_chars, overlap):
            if len(window.strip()) < min_chars:
                continue
            chunks.append(
                Chunk(
                    id=f"{doc.machine_slug}::{idx}",
                    machine=doc.machine,
                    machine_slug=doc.machine_slug,
                    os=doc.os,
                    difficulty=doc.difficulty,
                    heading_path=heading_path,
                    text=window.strip(),
                    source=doc.source,
                )
            )
            idx += 1
    return chunks


def iter_raw_files(raw_dir: str) -> Iterable[str]:
    # Use absolute, OS-native paths (no "..") so open() never trips over
    # relative-path or separator quirks on Windows.
    pattern = os.path.join(os.path.abspath(raw_dir), "*.md")
    return sorted(os.path.abspath(p) for p in glob.glob(pattern))


def build_chunks(raw_dir: str, **kw) -> list[Chunk]:
    """Load every write-up and turn it into chunks.

    A file that cannot be read even after retries is skipped (not fatal) so one
    unreadable file never aborts the whole build; the count is reported.
    """
    files = list(iter_raw_files(raw_dir))
    if not files:
        raise FileNotFoundError(
            f"No .md files found in {os.path.abspath(raw_dir)} — is the dataset cloned? "
            f"Try: git clone https://github.com/0xh7ml/htb-wiki.git"
        )
    chunks: list[Chunk] = []
    skipped: list[str] = []
    for path in files:
        try:
            doc = load_document(path)
        except OSError as err:
            skipped.append(os.path.basename(path))
            print(f"[ingest] skipped {os.path.basename(path)} ({err})")
            continue
        chunks.extend(chunk_document(doc, **kw))
    if skipped:
        print(f"[ingest] {len(skipped)}/{len(files)} file(s) skipped after retries.")
    return chunks
