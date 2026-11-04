# Public release procedure

The acceptance list is [#78](https://github.com/riscPrint/risc-v-workstation/issues/78).
Keep the repository private until the owner approves publication. This procedure
does not authorize publication. Put measured results in issues or the release PR.
Do not commit validation reports to the source tree.

1. Select the exact release revision after integration. Record its commit SHA.
2. Check the supported command scope in the root README. Keep known-failure
   waivers, stored-folder gates, statistical performance acceptance, mutation
   testing and generated-check runtime triage experimental until their close
   rules are met. Keep unqualified GUI cases experimental under #83. IDE scope
   remains with the owner under #77.
3. Record each advertised command, platform and tool combination in the release
   PR. Link native results at this revision. Use the public VexRiscv example for
   public core setup. State the optional private BOOM dependency separately.
   State C8's stable-input and result-identity limits. A passing selected test
   does not establish whole-core correctness.
4. Run `python3 scripts/qualify-install.py` for every advertised install case.
   See [the native qualification command](../scripts/README.md#native-install-qualification).
   Use fresh macOS, Ubuntu and Fedora hosts for clean-install claims under #17.
   Record untested flags and combinations as NOT RUN. Existing-host reuse,
   dry-run output and tool probes do not establish clean installs.
5. Check [tool versions](TOOL_VERSIONS.md) against the measured results under #40.
   Preserve locked Python and Rust installs and native source pins. Record
   package-manager drift and warnings. Do not call a version probe a tested flow.
6. Check community setup, security reporting, issue/PR templates, package
   metadata and dated advisory triage under #38. Check public setup and upstream
   provenance under #81. Preserve upstream attribution.
7. Run the bounded release scan with
   `rvw/.venv/bin/python -m pytest rvw/tests/test_release_hygiene.py -q`.
   Inspect the metadata report with
   `rvw/.venv/bin/python rvw/tests/test_release_hygiene.py`.
   Report scan scope and limits. This does not clear the owner identity gate #79.
8. Require passing root CI at the final revision under #16 and #41. Link the
   actual run and exact pass/skip counts. Hosted Linux workflows are disabled.
   Local tests cannot establish an Actions result. Run the native qualification
   command on a Linux host without Actions when needed.
9. Review every other P1 acceptance list for the advertised release scope.
   Record done, experimental, blocked or NOT RUN with a reason. Priority alone
   does not make later features a release requirement.
10. Inspect final source and binary archives. Check ELK license text and source
    availability notices in both the VSIX and standalone viewer. Check all
    inherited component obligations under #37. Source archives and native
    bundles have separate terms and qualification needs.
11. Obtain the owner's license decision under #37. Resolve the SpinalTrace EUPL
    copied block, f128 permission evidence and all other component obligations.
    A root license does not replace inherited terms. Redistribution stays
    blocked while applicable permission evidence is missing.
12. Obtain the GitHub Support outcome for old cached commits and objects under
    #39. A tree scan, squash or force-push cannot establish removal.
13. Obtain the owner's explicit acceptance of published author, committer and
    tag identities under #79. Do not rewrite identity or remove attribution as
    an implementation choice.
14. Record the approved tag, final SHA, package names and SHA-256 hashes. Link
    license and identity decisions, GitHub Support's outcome, install results
    and the final CI run in #78. Keep unresolved gates unchecked.

Do not create a public release while #37, #39 or #79 remains blocked. The owner
also retains integration/distribution choices under #34 and native bundle scope
under #71. Container work #59 and IDE scope #77 are not implicit release gates.
