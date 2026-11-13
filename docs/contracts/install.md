# Installation and release diagnostics

## Optional tool inventory

`rvw.tool-inventory/1` lives in `rvw/src/rvw/doctor/tools.json`.
`profiles` maps profile names to installer flag suffixes. Each `tools` row
records a name, area, executable probes, flag suffix, command areas,
environment variables, source pin and per-OS install recipe. `discovery`
records source lookup locations. It includes dynamic lookups for review.
Linux recipes with `linux_status: untested` are not execution evidence.

Doctor adds `tool_inventory` rows to `rvw.doctor/1`. Each row gives `name`,
`area`, `paths`, presence `status`, `install_flag`, `install_command` and
`qualification`. Presence does not establish version or runtime support.
Existing native version and adapter conformance records remain separate.

## Native archive manifest

`rvw.native-archives/1` in `scripts/native-manifest.json` holds `archives`
keyed by tool and host. `unverified` entries have null URL and SHA-256.
`verified_metadata` records a fixed release URL, SHA-256, version and evidence
source. This status refers to upstream metadata, not native execution.
The fetcher refuses unverified entries. A receipt stores the selected row.
Receipt checks establish neither full installed-file integrity nor relocation.

## Bounded release scan

`scripts/scan-release.py` emits `rvw.release-scan/1`. `tracked_findings` gives
file, line and finding class without credential values. `changed_personal_paths`
is its personal-path subset for files touched since `since` in local history.
`metadata_findings` reports locally reachable commit/tag message findings.
`identity_counts` reports distinct author, committer and tagger counts.
Identity publication approval is a separate owner decision. No approval is
inferred from a zero-finding report. Archives and remote caches are outside scope.

## Presence probes

Inventory `probes` are executable, module or file checks. Each has a display
name. Executable/file probes can select an `env` value, a `root_env` plus relative
path, or ordered `candidates`. Explicit selectors are authoritative. A file
probe can locate a relative file beside `relative_executable`. Plugin file
presence does not prove ABI compatibility or native load success.
