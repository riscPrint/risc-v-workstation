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
   (`abs-tudelft` on GitHub); GitLab `rameloni`.
3. SpinalHDL org (`github.com/SpinalHDL`): new repos, and SpinalHDL issues/PRs/discussions mentioning
   Tywaves, HGLDD, SpinalWaves, SpinalTrace.
4. TU Delft repository (repository.tudelft.nl) and arXiv/IEEE for new theses or papers that link code.
5. Web search for the project name plus "github", "release", "open source".

If something is found: note the URL, licence, what it covers (waves / trace / both), the Spinal version
it targets, and how it differs from our port (see each folder's `PORTING_NOTES.md`).

## Check log

- 2026-10-19: initial check (web search + GitHub `jarlb`/`rameloni` repos). No SpinalWaves/SpinalTrace
  code found. ChiselTrace is public at github.com/jarlb/chiseltrace (used as the port source).
