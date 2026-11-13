# Pinned native archives

`scripts/native-manifest.json` declares a host entry for each native inventory
tool. A null URL/hash and `unverified` status mean no verified binary is available
through this manifest. Do not fill them with guessed values.

CIRCT and Sail entries use digests read from upstream GitHub release metadata
on 2026-11-13. No large archive was downloaded for this work. Metadata verification
is not native runtime or relocation qualification. Linux execution is untested.

```sh
python3 scripts/fetch-native.py --tool 'CIRCT/arcilator' --dry-run
python3 scripts/fetch-native.py --tool 'CIRCT/arcilator' --prefix "$HOME/.cache/rvw/native"
python3 scripts/fetch-native.py --tool 'CIRCT/arcilator' --check
```

The default prefix is outside the repository. The fetcher verifies the SHA-256
before extracting. It refuses unverified entries and existing destinations.
`--check` checks the archive receipt and payload presence. It does not rehash all
installed files or certify runtime dependencies. Find the archive's `bin` directory
and set `RVW_CIRCT` or `RVW_SAIL` as required by the consumer. Archive layouts are
preserved. Source notices and licences stay in the archive.

The existing `native-bundle.py` remains the private Actions artifact path. This
manifest does not replace its build identities or promise a complete offline
bundle. Python, JDK, runtime dependencies, redistribution review and native
relocation qualification remain open under #71 and #37.
