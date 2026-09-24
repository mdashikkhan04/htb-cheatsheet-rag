#!/usr/bin/env python3
"""
Hand-derive the gold (ground-truth) machine sets for the test set by reading
the RAW write-up files directly — NOT by trusting the RAG system.

Each technique is a rule over the raw text (case-insensitive regex, with a
couple of heading-aware rules for noisy techniques like cron). Run:

    python3 tests/derive_gold.py --raw ../htb-wiki/raw > tests/gold_sets.json

The printed JSON maps technique_key -> sorted list of machine slugs, and is the
single source of truth the evaluation scores against. Counts + a few examples
are printed to stderr so a human can sanity-check the derivation.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# --- atomic technique rules ------------------------------------------------
# Each value is (compiled_regex, requires_heading_regex_or_None).
RULES: dict[str, str] = {
    "potato": r"printspoofer|juicypotato|god\s?potato|rogue\s?potato|"
              r"sweet\s?potato|rotten\s?potato|lonely\s?potato",
    "adcs": r"certipy|\besc[1-8]\b|certificate template|\badcs\b",
    "dcsync": r"\bdcsync\b|drsuapi|--just-dc|-just-dc-user",
    "acl_bloodhound": r"genericall|genericwrite|writedacl|writeowner|"
                      r"forcechangepassword|addself|writespn",
    "sam_dump": r"\breg(\.exe)?\s+save|samdump2|hklm\\sam|"
                r"sam\s+and\s+system|system\s+and\s+sam|sam\s*&\s*system|"
                r"dumping\s+(the\s+)?sam|from\s+the\s+sam\s+hive",
    "kerberoast": r"kerberoast|getuserspns|get-?userspns",
    "asrep": r"as-?rep\s*roast|getnpusers|asrep(roast)?|dont_req_preauth|"
             r"do not require kerberos pre",
    # log4j jar mentions alone are incidental; require the exploit signal.
    "log4shell": r"log4shell|jndi:(ldap|rmi)|cve-2021-44228|"
                 r"log4j.{0,40}(rce|exploit|vuln|jndi|shell|inject)",
    # 2021-4034 must not be the prefix of another CVE (e.g. 2021-40346).
    "pwnkit": r"pwnkit|2021-4034(?!\d)",
    "lxd_docker": r"\blxd\b|lxc\s+image|docker\s+group|/var/run/docker\.sock|"
                  r"docker\.sock|member of the docker",
    "sudo_gtfobins": r"gtfobins|sudo\s+-l|nopasswd",
    "suid": r"\bsuid\b|find\s+/\s+-perm|-perm\s+-?[0-7]*4000",
    "shadow_cred": r"shadow\s*cred|keycredentiallink|\bwhisker\b|pywhisker",
}
# Cron is heading-gated to avoid the ~100 incidental mentions.
CRON_HEADING = re.compile(r"^#{1,6}.*\bcron", re.I | re.M)
CRON_BODY = re.compile(r"\bpspy\b|writable.*cron|cron.*\broot\b|cronjob|cron job", re.I)

COMPILED = {k: re.compile(v, re.I) for k, v in RULES.items()}

# --- composite (broad "cheatsheet") gold sets ------------------------------
WINDOWS_PRIVESC_KEYS = ["potato", "adcs", "dcsync", "acl_bloodhound", "sam_dump",
                        "kerberoast", "asrep", "shadow_cred"]
LINUX_PRIVESC_KEYS = ["sudo_gtfobins", "suid", "cron", "pwnkit", "lxd_docker"]
AD_ATTACK_KEYS = ["kerberoast", "asrep", "dcsync", "acl_bloodhound", "adcs",
                  "shadow_cred"]


def slug(path: str) -> str:
    b = os.path.basename(path)
    return re.sub(r"^htb-", "", re.sub(r"\.md$", "", b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.raw, "*.md")))
    gold: dict[str, set[str]] = {k: set() for k in list(RULES) + ["cron"]}

    for path in files:
        s = slug(path)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for key, rx in COMPILED.items():
            if rx.search(text):
                gold[key].add(s)
        if CRON_HEADING.search(text) or (CRON_BODY.search(text) and "cron" in text.lower()):
            gold["cron"].add(s)

    # composites
    def union(keys):
        out: set[str] = set()
        for k in keys:
            out |= gold[k]
        return out

    gold_out = {k: sorted(v) for k, v in gold.items()}
    gold_out["windows_privesc"] = sorted(union(WINDOWS_PRIVESC_KEYS))
    gold_out["linux_privesc"] = sorted(union(LINUX_PRIVESC_KEYS))
    gold_out["ad_attack"] = sorted(union(AD_ATTACK_KEYS))

    print(json.dumps(gold_out, indent=2))

    # human sanity-check to stderr
    print("\n=== derivation summary (machines per technique) ===", file=sys.stderr)
    for k, v in gold_out.items():
        ex = ", ".join(v[:6])
        print(f"{k:18} {len(v):4d}   e.g. {ex}", file=sys.stderr)


if __name__ == "__main__":
    main()
