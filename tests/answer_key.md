# Answer Key — hand-derived ground truth

**Method.** Gold machine sets were derived by reading the *raw* write-up files with explicit rules (`tests/derive_gold.py`), independently of the RAG system. Each rule is a case-insensitive regex over the raw Markdown; `cron` is heading-gated to drop incidental mentions; composite/broad sets are unions of atomic technique sets. Two false positives were removed during review: `ouija` (the string `2021-4034` was a prefix of CVE-2021-40346) and `haystack` (ships a log4j *jar* but predates Log4Shell). Regenerate with:

```bash
python3 tests/derive_gold.py --raw ../htb-wiki/raw > tests/gold_sets.json
```

Relevance is scored at the **machine** level: a retrieved chunk is relevant if its machine is in the gold set for that question.

## Q01 · BROAD — Provide me the Windows privilege escalation cheatsheet.
- **Technique key:** `windows_privesc`  ·  **Gold machines:** 89
- **Derivation rule:** union of: potato, adcs, dcsync, acl_bloodhound, sam_dump, kerberoast, asrep, shadow_cred
- **Gold set:** absolute, active, acute, administrator, anubis, apt, authority, axlle, baby, babytwo, blackfield, blazorized, bounty, breach, bruno, cereal, certificate, certified, cicada, coder, conceal, control, darkcorp, darkzero, delegate, dropzone, eighteen, escape, escapetwo, fighter  … (+59 more)

## Q02 · BROAD — Give me a Linux privilege escalation cheatsheet.
- **Technique key:** `linux_privesc`  ·  **Gold machines:** 298
- **Derivation rule:** union of: sudo_gtfobins, suid, cron, pwnkit, lxd_docker
- **Gold set:** abducted, academy, admirer, agile, ai, airtouch, alert, altered, ambassador, antique, aragog, ariekei, armageddon, artificial, awkward, backdoor, backend, backendtwo, backfire, bagel, bamboo, bank, barrier, bashed, beep, bigbang, bitlab, blockblock, blocky, blunder  … (+268 more)

## Q03 · BROAD — What are the common ways these boxes attack Active Directory?
- **Technique key:** `ad_attack`  ·  **Gold machines:** 69
- **Derivation rule:** union of: kerberoast, asrep, dcsync, acl_bloodhound, adcs, shadow_cred
- **Gold set:** absolute, active, administrator, anubis, apt, authority, axlle, babytwo, blackfield, blazorized, breach, bruno, certificate, certified, coder, control, darkcorp, darkzero, delegate, eighteen, escape, escapetwo, flight, fluffy, forest, freelancer, ghost, hathor, haze, hospital  … (+39 more)

## Q04 · BROAD — Show me how sudo misconfigurations and GTFOBins are abused for root.
- **Technique key:** `sudo_gtfobins`  ·  **Gold machines:** 191
- **Derivation rule:** regex: gtfobins | sudo -l | nopasswd
- **Gold set:** abducted, academy, admirer, agile, airtouch, alert, ariekei, armageddon, artificial, awkward, backendtwo, backfire, bagel, bamboo, barrier, bashed, beep, bigbang, bitlab, blockblock, blocky, blunder, blurry, boardlight, bookworm, bountyhunter, brainfuck, broker, broscience, browsed  … (+161 more)

## Q05 · BROAD — Give an overview of ADCS certificate abuse (ESC1-ESC8) across the boxes.
- **Technique key:** `adcs`  ·  **Gold machines:** 28
- **Derivation rule:** regex: certipy | \bESC[1-8]\b | certificate template | \badcs\b
- **Gold set:** absolute, administrator, anubis, authority, certificate, certified, coder, darkcorp, darkzero, escape, escapetwo, fluffy, haze, infiltrator, manager, mirage, mist, puppy, rebound, retro, rustykey, scepter, sendai, shibuya, tombwatcher, vintage, voleur, vulncicada

## Q06 · SPECIFIC — How does the PrintSpoofer / potato attack abuse SeImpersonatePrivilege, and which machines use it?
- **Technique key:** `potato`  ·  **Gold machines:** 28
- **Derivation rule:** regex: printspoofer|juicypotato|god ?potato|rogue ?potato|sweet ?potato|rotten ?potato|lonely ?potato
- **Gold set:** apt, bounty, breach, bruno, cereal, conceal, darkzero, fighter, ghost, hackback, haze, job, json, mailing, media, mirage, perspective, pivotapi, proper, rebound, scrambled, sendai, shibuya, signed, silo, tally, visual, worker

## Q07 · SPECIFIC — Which machines are exploited via Log4Shell (CVE-2021-44228) and how?
- **Technique key:** `log4shell`  ·  **Gold machines:** 2
- **Derivation rule:** regex: log4shell | jndi:(ldap|rmi) | cve-2021-44228 | log4j.{0,40}(rce|exploit|vuln|jndi|shell|inject)
- **Gold set:** crafty, logforge

## Q08 · SPECIFIC — How is Kerberoasting performed and which machines use GetUserSPNs?
- **Technique key:** `kerberoast`  ·  **Gold machines:** 28
- **Derivation rule:** regex: kerberoast | getuserspns
- **Gold set:** absolute, active, administrator, blackfield, blazorized, breach, certified, delegate, escape, fluffy, forest, hathor, hospital, intelligence, jab, lustroustwo, mirage, object, pivotapi, puppy, rebound, sauna, scrambled, search, sizzle, tombwatcher, vintage, voleur

## Q09 · SPECIFIC — Which machines use a DCSync attack to dump domain hashes, and how?
- **Technique key:** `dcsync`  ·  **Gold machines:** 30
- **Derivation rule:** regex: \bdcsync\b | drsuapi | --just-dc
- **Gold set:** administrator, apt, authority, blazorized, coder, darkcorp, darkzero, delegate, eighteen, flight, forest, freelancer, ghost, hathor, mirage, mist, multimaster, overwatch, phantom, rebound, redelegate, retrotwo, rustykey, sauna, scepter, signed, sizzle, university, vintage, vulncicada

## Q10 · SPECIFIC — How is the PwnKit (pkexec, CVE-2021-4034) exploit used, and on which machines?
- **Technique key:** `pwnkit`  ·  **Gold machines:** 4
- **Derivation rule:** regex: pwnkit | 2021-4034(?!\d)
- **Gold set:** antique, paper, pressed, routerspace

## Q11 · SPECIFIC — Which machines use Shadow Credentials (msDS-KeyCredentialLink / Whisker) and how?
- **Technique key:** `shadow_cred`  ·  **Gold machines:** 13
- **Derivation rule:** regex: shadow ?cred | keycredentiallink | whisker | pywhisker
- **Gold set:** absolute, certified, darkcorp, delegate, escapetwo, fluffy, haze, infiltrator, mist, outdated, puppy, rebound, tombwatcher

## Q12 · SPECIFIC — How do machines abuse the docker or lxd group to get root?
- **Technique key:** `lxd_docker`  ·  **Gold machines:** 45
- **Derivation rule:** regex: \blxd\b | lxc image | docker group | docker.sock | member of the docker
- **Gold set:** ambassador, ariekei, backdoor, backend, backendtwo, book, bookworm, brainfuck, broker, bucket, cache, calamity, caption, carrier, chainsaw, clicker, corporate, data, ellingson, encoding, extension, feline, iclean, inception, intuition, jail, laboratory, mischief, monitorstwo, obscurity  … (+15 more)

## Q13 · SPECIFIC — Which machines use AS-REP roasting (GetNPUsers) and how does it work?
- **Technique key:** `asrep`  ·  **Gold machines:** 18
- **Derivation rule:** regex: as-?rep roast | getnpusers | asrep(roast)? | dont_req_preauth
- **Gold set:** absolute, active, anubis, blackfield, bruno, escape, forest, infiltrator, intelligence, jab, mantis, mist, multimaster, outdated, pivotapi, rebound, sauna, tentacle

## Q14 · SPECIFIC — How is BloodHound used to find GenericAll / WriteDACL ACL abuse paths, and on which machines?
- **Technique key:** `acl_bloodhound`  ·  **Gold machines:** 44
- **Derivation rule:** regex: genericall|genericwrite|writedacl|writeowner|forcechangepassword|addself|writespn
- **Gold set:** absolute, administrator, anubis, axlle, babytwo, blackfield, blazorized, certificate, certified, control, darkcorp, darkzero, delegate, escape, escapetwo, fluffy, forest, freelancer, haze, infiltrator, mirage, mist, multimaster, nanocorp, object, phantom, pivotapi, puppy, querier, rebound  … (+14 more)

## Q15 · SPECIFIC — Which machines dump the SAM and SYSTEM registry hives to extract local hashes?
- **Technique key:** `sam_dump`  ·  **Gold machines:** 10
- **Derivation rule:** regex: reg save | samdump2 | hklm\\sam | sam and system | dumping the sam
- **Gold set:** acute, baby, blackfield, cicada, control, darkcorp, dropzone, freelancer, mist, omni
