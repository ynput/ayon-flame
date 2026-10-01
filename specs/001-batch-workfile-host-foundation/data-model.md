# Data Model: Batch workfile save (Amendment 1)

No new persisted format and no new addon-owned state.

| Entity | Source of truth | Notes |
| --- | --- | --- |
| Allocated workfile path | `ayon_core` (`save_workfile_with_context` / `save_next_version`) | Opaque to the addon; version, name, dir never derived here (FR-A02) |
| Saved Batch workfile | Consolidated JSON file (`batch_utils`) | Written atomically via temp sibling + `os.replace` (FR-A04) |
| Workfile entity | AYON server, created by Core after `save_workfile` returns | Addon does not create it |
| "Has saved workfile" | `host.list_workfiles(project, folder, task)` non-empty (FR-A18) | Context-level; restart-safe; not matched to a specific Batch |
| Session path record (`_WORKFILE_PATHS`) | In-memory, original milestone (DV-3) | Only feeds `get_current_workfile()`; NOT used by the validator |
| Publish `currentFile` | Flame collector | Latest existing workfile path for Batch context, else `None` (key always present) |

State transitions (validator): `no workfile` --Repair/Save--> `workfile exists`
(terminal for the publish session; the validator never reverts).
