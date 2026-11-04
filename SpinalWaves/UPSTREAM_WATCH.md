# Upstream watch: TU Delft "SpinalWaves & SpinalTrace"

TU Delft has a funded project, **SpinalWaves & SpinalTrace** (start: April 2026), with the same goals as
this local port: keep SpinalHDL types in the waveform viewer (Tywaves for Spinal) and trace signal
behaviour back to SpinalHDL source (ChiselTrace for Spinal). As of 2026-10-19 there is **no public
code or release**. The folders `SpinalWaves/` and `SpinalTrace/` here are our own port, built from the
open-source Tywaves and ChiselTrace code (Apache-2.0) while we wait.

Use the checklist below to check for upstream code and releases. Record public
source links when reporting a change.

## Checklist for each check

1. GitHub search: repos named/described `SpinalWaves`, `SpinalTrace`, `spinal-waves`, `spinal-trace`,
   `tywaves spinal`, `chiseltrace spinal`; code search for `SpinalWaves`.
2. Known authors/orgs: `rameloni` (Raffaele Meloni, Tywaves), `jarlb` (Jarl Brand, ChiselTrace),
   Christiaan Cromjongh, H. Peter Hofstee, Zaid Al-Ars; TU Delft CE / Accelerated Big Data Systems
   (`abs-tudelft` on GitHub); GitLab `rameloni`. Also `ccromjongh` (Christiaan Cromjongh, the TU Delft
   developer): `ccromjongh/SpinalHDL` branch `spinaltrace` and `ccromjongh/sigtrail` (SigTrail = their
   renamed ChiselTrace fork). Check new commits/branches there and any release or merge into upstream.
3. SpinalHDL org (`github.com/SpinalHDL`): new repos, and SpinalHDL issues/PRs/discussions mentioning
   Tywaves, HGLDD, SpinalWaves, SpinalTrace, SigTrail. Status updates are posted in SpinalHDL issue #1882.
4. TU Delft repository (repository.tudelft.nl) and arXiv/IEEE for new theses or papers that link code.
5. Web search for the project name plus "github", "release", "open source".

If something is found: note the URL, licence, what it covers (waves / trace / both), the Spinal version
it targets, and how it differs from our port (see each folder's `PORTING_NOTES.md`).

## Check log

- 2026-10-19: initial check (web search + GitHub `jarlb`/`rameloni` repos). No SpinalWaves/SpinalTrace
  code found. ChiselTrace is public at github.com/jarlb/chiseltrace (used as the port source).
- 2026-11-02: **UPSTREAM FOUND (work in progress, no release).** TU Delft (Christiaan Cromjongh) posts
  status in SpinalHDL issue #1882 (https://github.com/SpinalHDL/SpinalHDL/issues/1882). Code:
  - https://github.com/ccromjongh/SpinalHDL/tree/spinaltrace — fork of SpinalHDL; PDG phase in
    `core/src/main/scala/spinal/core/pdg_analysis/` (~1600 lines) plus small hooks in Bool/Bits/UInt/SInt,
    when, Statement, idsl plugin. Last commit 2026-08-27 (binary mux and Vec-index support, probe dedup).
  - https://github.com/ccromjongh/sigtrail (Apache-2.0) — ChiselTrace fork renamed SigTrail, Chisel + Spinal
    language mode, switch/case multi-fork. Last push 2026-08-25.
  SpinalTrace side only. No SpinalWaves (HGLDD/type info) output yet: they borrow Chisel HGLDD files for
  testing. Public since about 2026-08-13; the 2026-10-19 check missed it because it searched project names only.
