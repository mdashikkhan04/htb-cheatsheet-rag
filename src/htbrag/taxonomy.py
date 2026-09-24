"""
A small, curated taxonomy of offensive-security techniques.

Used for THREE things (never for the gold answer key, which is derived
independently by grepping the raw files):

  1. Query expansion  - a broad "cheatsheet" query is expanded with the seed
                        terms of the relevant category so retrieval pulls a
                        diverse set of techniques, not just one.
  2. OS routing        - decide whether a query is Windows- or Linux-flavoured.
  3. Offline grouping  - the no-API-key fallback synthesizer buckets retrieved
                        chunks into these groups to produce a grouped, cited
                        cheatsheet.

Each pattern is a compiled, case-insensitive regex with word-ish boundaries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Technique:
    key: str
    name: str
    os: str            # "Windows" | "Linux" | "Any"
    blurb: str         # one-line explanation used by the offline synthesizer
    seeds: list[str]   # query-expansion seed terms
    patterns: list[str]  # regexes that mark a chunk as demonstrating this


def _c(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns]


WINDOWS_PRIVESC: list[Technique] = [
    Technique(
        "sam_dump", "SAM / SYSTEM hive dump", "Windows",
        "Dump the SAM and SYSTEM registry hives (or LSASS) and extract local "
        "account hashes offline with secretsdump/samdump2.",
        ["SAM SYSTEM hive", "secretsdump", "reg save SAM", "lsass dump", "hashes"],
        [r"\breg\s+save\b.*\bsam\b", r"\bsam\b.*\bsystem\b.*hive", r"secretsdump",
         r"samdump2", r"lsass(\.dmp)?", r"sekurlsa::logonpasswords"],
    ),
    Technique(
        "potato", "Potato family (SeImpersonate abuse)", "Windows",
        "Abuse SeImpersonate/SeAssignPrimaryToken with a potato tool "
        "(JuicyPotato, PrintSpoofer, GodPotato, RoguePotato) to impersonate "
        "SYSTEM.",
        ["SeImpersonate", "PrintSpoofer", "JuicyPotato", "GodPotato",
         "RoguePotato", "potato token impersonation"],
        [r"seimpersonate", r"seassignprimarytoken", r"printspoofer",
         r"juicypotato", r"godpotato", r"roguepotato", r"sweetpotato",
         r"\bpotato\b"],
    ),
    Technique(
        "adcs", "ADCS certificate abuse", "Windows",
        "Abuse Active Directory Certificate Services (ESC1-ESC8) with "
        "Certipy to obtain a certificate and authenticate as a privileged user.",
        ["ADCS", "certipy", "ESC1", "ESC8", "vulnerable certificate template",
         "certificate abuse"],
        [r"\badcs\b", r"certipy", r"\besc\d{1,2}\b", r"certificate template",
         r"\bntlmrelayx\b.*\badcs\b", r"pkinit"],
    ),
    Technique(
        "acl_bloodhound", "ACL / BloodHound abuse", "Windows",
        "Enumerate Active Directory with BloodHound and abuse dangerous ACLs "
        "(GenericAll, GenericWrite, WriteDACL, WriteOwner, AddSelf).",
        ["BloodHound", "GenericAll", "GenericWrite", "WriteDACL", "WriteOwner",
         "ACL abuse", "ForceChangePassword"],
        [r"bloodhound", r"genericall", r"genericwrite", r"writedacl",
         r"writeowner", r"forcechangepassword", r"\baddself\b", r"\bacl\b abuse"],
    ),
    Technique(
        "dcsync", "DCSync / credential replication", "Windows",
        "With replication rights (or Domain Admin), use DCSync to pull the "
        "krbtgt/administrator hashes from the domain controller.",
        ["DCSync", "GetChanges", "replication rights", "krbtgt", "secretsdump dcsync"],
        [r"dcsync", r"drsuapi", r"get-?changes", r"\bkrbtgt\b", r"replicating directory"],
    ),
    Technique(
        "kerberos_roast", "Kerberoast / AS-REP roast", "Windows",
        "Request SPN tickets (Kerberoast) or roast accounts without "
        "pre-auth (AS-REP) and crack the returned hashes offline.",
        ["Kerberoast", "AS-REP roast", "GetUserSPNs", "GetNPUsers", "SPN ticket"],
        [r"kerberoast", r"as-?rep", r"getuserspns", r"getnpusers", r"\bspn\b.*ticket"],
    ),
    Technique(
        "shadow_cred", "Shadow Credentials / key trust", "Windows",
        "Abuse write access to msDS-KeyCredentialLink (Whisker/pywhisker) to "
        "add a shadow credential and authenticate as the target.",
        ["shadow credential", "msDS-KeyCredentialLink", "Whisker", "pywhisker"],
        [r"shadow\s*cred", r"keycredentiallink", r"whisker", r"pywhisker"],
    ),
    Technique(
        "token_priv", "Dangerous token privileges", "Windows",
        "Abuse SeBackup/SeRestore, SeDebug, or SeManageVolume style privileges "
        "to read protected files or escalate.",
        ["SeBackupPrivilege", "SeRestore", "SeDebug", "SeManageVolume", "whoami /priv"],
        [r"sebackup", r"serestore", r"sedebugprivilege", r"semanagevolume",
         r"whoami\s*/priv"],
    ),
    Technique(
        "runas_cred", "Stored credentials / runas", "Windows",
        "Reuse credentials found in files, the registry, or the Credential "
        "Manager (cmdkey/runas, unattend.xml, PowerShell history).",
        ["runas", "cmdkey", "unattend.xml", "credential manager", "powershell history"],
        [r"\bcmdkey\b", r"runas\s*/", r"unattend\.xml", r"credential manager",
         r"consolehost_history"],
    ),
]

LINUX_PRIVESC: list[Technique] = [
    Technique(
        "sudo", "sudo misconfiguration / GTFOBins", "Linux",
        "Abuse sudo rights (sudo -l) on a binary that can spawn a shell or "
        "read files, per GTFOBins.",
        ["sudo -l", "GTFOBins", "sudo NOPASSWD", "sudo exploit"],
        [r"sudo\s+-l", r"gtfobins", r"nopasswd", r"\(root\)\s*NOPASSWD"],
    ),
    Technique(
        "suid", "SUID / SGID binaries", "Linux",
        "Find and abuse SUID/SGID binaries that run as root to escalate.",
        ["SUID", "SGID", "find perm 4000", "setuid binary"],
        [r"\bsuid\b", r"\bsgid\b", r"perm\s*-?[0-7]*4000", r"setuid"],
    ),
    Technique(
        "cron", "Cron job abuse", "Linux",
        "Hijack a writable script or wildcard run by a root cron job.",
        ["cron", "crontab", "pspy", "cron wildcard"],
        [r"\bcron\b", r"crontab", r"\bpspy\b"],
    ),
    Technique(
        "capabilities", "Linux capabilities", "Linux",
        "Abuse file capabilities (e.g. cap_setuid) via getcap to gain root.",
        ["getcap", "cap_setuid", "capabilities"],
        [r"getcap", r"cap_setuid", r"cap_dac_read"],
    ),
    Technique(
        "kernel", "Kernel / sudo CVE exploit", "Linux",
        "Exploit a vulnerable kernel or sudo version (e.g. DirtyPipe, "
        "PwnKit/pkexec, Baron Samedit).",
        ["DirtyPipe", "PwnKit", "pkexec", "Baron Samedit", "kernel exploit"],
        [r"dirtypipe", r"dirty\s*cow", r"pwnkit", r"pkexec", r"baron samedit",
         r"cve-\d{4}-\d+"],
    ),
    Technique(
        "path_env", "PATH / env hijack", "Linux",
        "Abuse a relative binary call in a root-run program by hijacking PATH "
        "or LD_PRELOAD.",
        ["PATH hijack", "LD_PRELOAD", "LD_LIBRARY_PATH", "relative path"],
        [r"path\s*hijack", r"ld_preload", r"ld_library_path"],
    ),
    Technique(
        "container_group", "docker / lxd group abuse", "Linux",
        "Abuse membership of the docker/lxd group to mount the host filesystem "
        "as root.",
        ["docker group", "lxd group", "container escape"],
        [r"\bdocker\b\s*group", r"\blxd\b", r"lxc\s+", r"container escape"],
    ),
]

ALL_TECHNIQUES = WINDOWS_PRIVESC + LINUX_PRIVESC
_COMPILED = {t.key: _c(t.patterns) for t in ALL_TECHNIQUES}
BY_KEY = {t.key: t for t in ALL_TECHNIQUES}


def matches(technique_key: str, text: str) -> bool:
    return any(p.search(text) for p in _COMPILED[technique_key])


def detect_os(query: str) -> str | None:
    q = query.lower()
    if re.search(r"\b(windows|active directory|\bad\b|domain controller|ntlm|kerbero)", q):
        return "Windows"
    if re.search(r"\b(linux|unix|sudo|suid|gtfobins|bash|cron)\b", q):
        return "Linux"
    return None


def is_cheatsheet(query: str) -> bool:
    return bool(re.search(r"cheat\s*sheet|cheatsheet|overview|all the ways|"
                          r"techniques for|ways to|summary of", query.lower()))


def expand_query(query: str) -> str:
    """Append category seed terms for broad/cheatsheet queries so retrieval
    surfaces diverse techniques instead of a single dominant one."""
    q = query.lower()
    extra: list[str] = []
    os_hint = detect_os(query)
    privesc = bool(re.search(r"privilege escalation|privesc|escalat|to (root|system|administrator)", q))
    if is_cheatsheet(query) or privesc:
        pool = ALL_TECHNIQUES
        if os_hint == "Windows":
            pool = WINDOWS_PRIVESC
        elif os_hint == "Linux":
            pool = LINUX_PRIVESC
        for t in pool:
            extra.extend(t.seeds[:3])
    if not extra:
        return query
    return query + " " + " ".join(extra)
