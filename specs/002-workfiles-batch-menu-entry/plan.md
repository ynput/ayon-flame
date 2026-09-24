# Implementation Plan: Workfiles Menu Entry (Flame Batch Menu)

**Branch**: `workfile-entry-batch-menu` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from
`specs/002-workfiles-batch-menu-entry/spec.md`

## Summary

Add a `4 - Workfiles...` action to the Flame Batch AYON menu. The action will
use the existing `callback_selection` and `_get_main_window` helpers and call
`host_tools.show_workfiles(parent=_get_main_window())`, matching the existing
Create/Publish callback pattern. To keep the action Batch-only, override
`FlameMenuBatch.build_menu()` and append the action after the inherited Create,
Publish, and Load actions. No shared context-menu action, startup hook, host
wiring, publish plugin, settings, or launcher module changes are required.

The workfile-host capability from feature 001 remains a documented runtime
dependency. Its deferred `FlameHost`/`IWorkfileHost` wiring is not included in
this plan because feature 001 established that wiring changes publish
validation and version collection behavior. The menu entry must not introduce
that side effect.

## Technical Context

**Language/Version**: Python 3.9+; Flame embedded Python runtime

**Primary Dependencies**: `ayon_core.tools.utils.host_tools`, `qtpy`,
Flame Python API through the existing menu runtime seam

**Storage**: None; menu action is transient. Workfile storage and
serialization remain owned by existing AYON Core/Flame workfile components.

**Testing**: No test framework exists. Use targeted Ruff checks, package
build, code inspection, and manual validation inside Flame.

**Target Platform**: Autodesk Flame supported by this addon, with the Batch
menu available and AYON Core's `host_tools` module installed.

**Project Type**: AYON host integration addon

**Performance Goals**: No measurable overhead beyond one menu action
construction and the existing workfiles UI invocation.

**Constraints**:

- Repository Ruff configuration is authoritative: line length 79, double
  quotes, lint selection `E`, `F`, `W`.
- `client/ayon_flame/addon.py` must remain importable without Flame.
- Do not modify `client/ayon_flame/plugins/**`, `server/**`, settings, or
  publish/version behavior.
- Do not wire `IWorkfileHost` into `FlameHost` as an incidental part of the
  menu change.
- Preserve existing action labels and order.

**Scale/Scope**: One existing client menu module plus feature documentation;
no new runtime modules, models, settings, or APIs.

## Constitution Check

*GATE: Must pass before Phase 0 research and re-check after Phase 1 design.*

| Gate | Status | Notes |
| --- | --- | --- |
| Article 1 — addon anatomy | PASS | Change stays under `client/ayon_flame/api/`; no new top-level runtime structure. |
| Article 2 — pipeline contracts | PASS | No identifiers, hosts, families, representations, or plugin orders change. |
| Article 3 — settings contract | PASS | No settings model, field, default, or override migration changes. |
| Article 4 — compatibility imports | PASS | Uses the already imported `host_tools` API; no compatibility branch is removed or added. |
| Article 5 — Ruff style | PASS | Implementation follows root `ruff.toml` (79 columns, double quotes). |
| Article 6 — vendor isolation | PASS | No vendor tree is touched. |
| Article 7 — host runtime boundary | PASS | Menu code remains in the existing Flame runtime API seam; `addon.py` is untouched. |
| Article 8 — verification ladder | PASS | Targeted Ruff, format, package build, then manual Flame validation; no test framework added. |
| Article 10 — survey first | PASS | Survey found no existing Workfiles action; existing Create/Publish/Load actions were preserved. |

**Post-design re-check**: PASS. The selected design modifies only the existing
menu seam and has no constitution violations or complexity exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/002-workfiles-batch-menu-entry/
├── spec.md                    # Feature requirements and acceptance criteria
├── plan.md                    # This implementation plan
├── research.md                # Existing menu and dependency findings
├── data-model.md              # Transient menu/callback model
├── quickstart.md              # Static and manual validation instructions
└── contracts/
    └── menu-action.md         # Menu shape and callback contract
```

`tasks.md` will be generated separately by `/speckit.tasks` and is not part of
this plan output.

### Source Code (repository root)

```text
client/ayon_flame/api/
└── menu.py                    # Modify FlameMenuBatch.build_menu only

client/ayon_flame/
└── addon.py                   # Explicitly unchanged; launcher-safe boundary

client/ayon_flame/plugins/    # Explicitly unchanged
server/                        # Explicitly unchanged
```

**Structure Decision**: Extend the existing menu class hierarchy instead of
creating a new menu helper or module. `_FlameMenuContext` remains the shared
implementation for Create/Publish/Load, while `FlameMenuBatch` owns the
Batch-specific Workfiles action.

## Design Decisions

### D1 — Keep host wiring out of this feature

Do not modify `FlameHost` or add `IWorkfileHost` to its bases. Feature 001's
D1b wiring was deferred because it activates core validators/collectors and
would change Flame publish/version behavior. The menu action can be added
without silently reopening that decision. A future implementation may wire the
host after the feature 001 follow-up resolves those effects.

### D2 — Override only `FlameMenuBatch.build_menu`

Do not append the action in `_FlameMenuContext.build_menu()`, because that
would expose Workfiles on Timeline and Universal menus. The subclass override
calls `super()`, checks the inherited result, appends one action, and returns
it. This preserves the current guard that returns `{}` when Flame is not
available.

### D3 — Reuse the existing callback pattern

Use the already imported `host_tools` object and existing helpers:

```python
menu["actions"].append({
    "name": "4 - Workfiles...",
    "execute": lambda x: callback_selection(
        x,
        host_tools.show_workfiles(parent=_get_main_window()),
        context=self.__class__.__name__,
    ),
})
```

This keeps selection/context propagation consistent with Create and Publish,
uses the same main-window parent, and avoids adding a wrapper abstraction.

### D4 — Preserve numbering and labels

The new label is `4 - Workfiles...`, appended after `3 - Load...`. Existing
items are not reordered or renamed. The project indicator remains inherited.

### D5 — No new error handling in the menu layer

The menu action delegates to `show_workfiles` and does not catch or reinterpret
workfile-host errors. Missing Batch groups and host capability behavior remain
owned by the workfile tool/host layer. Menu construction must remain safe under
the existing `self.flame` guard.

## Implementation Steps

1. Add a `build_menu` override to `FlameMenuBatch` in
   `client/ayon_flame/api/menu.py`.
2. Call `super().build_menu()` and return `{}` unchanged if the inherited menu
   is empty.
3. Append the `4 - Workfiles...` action using
   `host_tools.show_workfiles(parent=_get_main_window())` through
   `callback_selection`.
4. Do not modify `FlameMenuTimeline`, `FlameMenuUniversal`, startup hooks,
   `FlameHost`, `addon.py`, plugins, server settings, or workfile host code.
5. Run static/package validation and inspect the final diff.
6. Perform the manual Flame menu and workfiles-tool validation described in
   `quickstart.md`, including recording the feature 001 host-wiring dependency.

## Verification Plan

### Static checks

```bash
ruff check client/ayon_flame/api/menu.py
ruff format --check client/ayon_flame/api/menu.py
python create_package.py --skip-zip
```

Also inspect:

- Batch menu action order and exact label.
- Timeline and Universal menu code remains unchanged.
- `git diff --name-only` contains only the intended menu source and feature
  artifacts.
- No `addon.py`, plugin, server, or pipeline changes.

### Manual in-host checks

1. Open Flame with an AYON project and navigate to Batch.
2. Build/open the AYON Batch menu and confirm actions are ordered
   `Create...`, `Publish...`, `Load...`, `Workfiles...` after the project row.
3. Select Workfiles and verify the AYON workfiles UI opens with the Flame main
   window parent.
4. Verify the current registered-host behavior, and record whether the
   feature 001 `IWorkfileHost` wiring is still deferred.
5. Check Timeline and Universal/Media Panel menus: Workfiles must be absent,
   and existing actions must remain unchanged.
6. Confirm no publish/version behavior changed as a result of this feature.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| `show_workfiles` signature differs in the runtime AYON Core | Action could fail when selected | Confirm the installed Core callback contract before in-host validation; adapt only the call signature if necessary. |
| `IWorkfileHost` remains unwired | Workfiles UI may not offer a usable Flame workfile host | Keep this dependency explicit; do not activate publish validators/collectors as a workaround. |
| Action added to shared builder accidentally | Workfiles appears in unsupported contexts | Implement only on `FlameMenuBatch`; manually inspect Timeline/Universal menus. |
| Missing main window | Workfiles receives `None` parent | Reuse existing `_get_main_window()` behavior exactly; no new window assumptions. |
| Existing menu order changes | User-facing regression | Append after inherited actions and validate exact labels/order. |

## Complexity Tracking

No constitution violations. No complexity exception is required.
