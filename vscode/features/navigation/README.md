# Design navigation

Start `rvw lsp` with the existing LSP command. Set `lsp.database` for the captured design.
Use the Scala editor context menu to list signals, query waves, focus blocks, or inspect drivers and loads.
Repeated instances require a choice. Missing mappings give a message. Rebuild after source changes.
Block diagram nodes provide the same drivers and loads actions through their source location.
Wave signal rows retain the existing checked Jump to Signal Source action.
The view uses captured declarations, not live elaboration.

`navigation.navigate` selects a signal at the current source line and opens
its `rvw query navigate` record. The record links the stored diagram endpoint,
wave path and dependency selector. Unmapped fields remain explicit.
