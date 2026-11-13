# MCP replay inputs

`calls.json` has 60 reviewed calls. The slow test replays them over stdio.
It uses the existing GCD SQL fixture and the hand-written VCD and RTL here.
It writes outputs under pytest's temporary project. It fetches each completed
background result again. This replay does not run a native build. Other tools
remain outside this replay. New families need reviewed call arguments.

Run from the checkout root:

```sh
nice -n 15 rvw/.venv/bin/python -m pytest rvw/tests/test_mcp_surface_replay.py -q
```

The external native driver must use a private core, private locks, two native
jobs at most, and a separate output directory. Its artifact rows cannot use
these fixture inputs as native evidence.
