# Feature Specification: Workfiles Menu Entry (Flame Batch Menu)

**Feature Branch**: `workfile-entry-batch-menu`
**Created**: 2026-09-24
**Status**: Draft
**Input**: User description: "Add a Workfiles menu action to the Flame Batch menu using `ayon_core host_tools.show_workfiles`, matching the existing menu action pattern."

## Summary

Add a **Workfiles** action to the AYON menu shown on the Flame **Batch** page
so artists can open AYON's workfiles tool from the Batch context menu. The
action must follow the same declarative menu-action pattern already used by the
Create / Publish / Load entries in `client/ayon_flame/api/menu.py`
(`_FlameMenuContext.build_menu()`), and it must call
`ayon_core.tools.utils.host_tools.show_workfiles`.

### Context / dependency (survey result)

This feature is the **menu-visible front door** for the workfile capability
added in feature `001-batch-workfile-host-foundation`
(`client/ayon_flame/api/workfile.py`: `FlameWorkfileHost`,
`FlameBatchWorkfileHost`, `get_flame_workfile_host`).

That capability is **not yet wired into `FlameHost`** — spec 001 deferred the
`IWorkfileHost` mixin (decision D1b blocked; task T011; deviation DV-1),
because flipping it activates ayon-core's `ValidateCurrentSaveFile` and
`CollectSceneVersion` in ways that change publish/version behaviour. The AYON
workfiles tool opens against the **registered host** and requires the host to
implement the `IWorkfileHost` contract, so today the host is not the target for
`show_workfiles`.

Consequence (recorded as an explicit decision for planning, not silently
assumed): this feature's in-scope deliverable is the **menu action wiring
itself**. Whether the action is usable-end-to-end depends on wiring the host
either in this milestone (if the user accepts the spec-001 D1b blast radius)
or in the separate follow-up tracked by spec 001. The spec below options this
as the primary open question for `/speckit.plan`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the AYON workfiles tool from the Batch page (Priority: P1)

As a Flame artist working on the Batch page, I want a **Workfiles** entry in
the AYON Batch context menu so that I can open AYON's workfiles browser from
the same surface as Create / Publish / Load.

**Why this priority**: This is the direct user-visible feature; without it the
Batch workfile capability (001) has no in-app entry point.

**Independent Test**: In Flame on the Batch page, expand the AYON menu and
verify a **Workfiles** action is present alongside Create / Publish / Load and
that selecting it invokes `host_tools.show_workfiles`. If the host is wired,
the workfiles tool opens; otherwise (deliberately unwired) record that it is
present but inert, and test the resulting behaviour explicitly.

**Acceptance Scenarios**:

1. **Given** the AYON menu is open on the Flame Batch page, **when** the menu is
   built, **then** the menu contains a **Workfiles** action alongside the
   existing Create / Publish / Load actions.
2. **Given** the Batch menu **Workfiles** action, **when** it is triggered,
   **then** it calls `ayon_core.tools.utils.host_tools.show_workfiles()` with a
   Flame `QMainWindow` parent, matching the pattern used by the existing
   Create / Publish (via `host_tools`) and Load (via `tools_helper`) actions.
3. **Given** the user running a menu action in Batch, **when** the action
   executes, **then** any Batch selection is propagated through the same
   `callback_selection` path used by the existing context actions, and no
   `flame` import is added to launcher-safe modules (`client/ayon_flame/addon.py`).

### User Story 2 - Workfiles appears only on the Batch menu (Priority: P1)

As a pipeline owner, I want the Workfiles action scoped to the **Batch** menu
only (per the request), leaving the Timeline/Universal context menus unchanged,
so the entry is added deliberately and does not unintentionally appear where
the workfile host is not the target.

**Why this priority**: The request is explicitly "Flame Batch menu". Keeping it
Batch-scoped also matches the fact that spec 001 delivered Batch-first workfile
support.

**Independent Test**: On the Timeline and Universal/Media-Panel menus, verify the
Workfiles action is **absent**, and that Create / Publish / Load behave exactly
as before.

**Acceptance Scenarios**:

1. **Given** the AYON menu on the Timeline or Universal context, **when** the
   menu is built, **then** no **Workfiles** action appears.
2. **Given** the existing shared menu builder, **when** the feature is added,
   **then** the Batch menu's existing Create / Publish / Load actions and their
   ordering/labels are preserved.

### User Story 3 - No regression and clean static validation (Priority: P2)

As a maintainer, I want the change confined to the menu layer and passing the
repository's existing checks, so it lands safely without altering publish,
version, or settings behaviour.

**Why this priority**: Matches the addon's "no publish/version change yet"
constraint from spec 001 and the repo's no-test-framework rule.

**Independent Test**: Run `ruff check .`, `ruff format --check .` on the changed
files and confirm no import of `flame` is added to `addon.py`. Confirm via
`git diff` that only the intended menu file (and this spec) are changed.

**Acceptance Scenarios**:

1. **Given** the repository's lint rules, **when** the menu change is added,
   **then** `ruff check` passes on the changed files and no publish plugin,
   `plugins/**`, or `server/**` file is modified.
2. **Given** the launcher-safe boundary, **when** the menu module is loaded,
   **then** `client/ayon_flame/addon.py` remains importable without the `flame`
   module (the menu imports `host_tools`, which is launcher-safe; any `flame`
   import stays in the `api/`/`startup/` boundary as it is today).

### Edge Cases

- **Host not wired (dependency)**: If the `IWorkfileHost` mixin (spec 001
  D1b) is still unwired, `show_workfiles` opens against a host that is not an
  `IWorkfileHost`. The action should not raise on menu build; the tool's
  behaviour (and whether it is even shown) with an unwired host must be
  verified in-host and recorded, and **must not** break menu construction or
  the other actions.
- **No active Batch group**: The Batch workfile host raises a clear error when
  no Batch group is active (spec 001 T007/D4). The menu action itself opens the
  tool regardless; any in-tool failure is surfaced by the existing workfile
  host, not by the menu entry.
- **Project not loaded / `flame` unavailable**: `_FlameMenuContext.build_menu()`
  already returns `{}` when `self.flame` is falsy; the Workfiles action must
  inherit that guard and never be built in that state.
- **`_get_main_window()` returns `None`**: As with the existing Create/Publish
  actions, the Workfiles action passes `parent=_get_main_window()`; behaviour
  with no top-level `QMainWindow` must match the existing actions (no new
  failure introduced).
- **Menu label collision / numbering**: The action must use a label and
  position consistent with the existing numbered actions and not shadow or
  reorder Create / Publish / Load.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The AYON menu on the Flame **Batch** page MUST include a
  **Workfiles** action.
- **FR-002**: The Workfiles action MUST invoke
  `ayon_core.tools.utils.host_tools.show_workfiles()`, passing a Flame
  `QMainWindow` parent following the existing `host_tools.show_publisher` /
  `host_tools.show_loader` pattern in `_FlameMenuContext.build_menu()`.
- **FR-003**: The Workfiles action MUST NOT appear on the Timeline or Universal
  (Media-Panel) context menus; it is scoped to the Batch menu only.
- **FR-004**: The Workfiles action MUST only be added when the menu builder has
  a live `self.flame` (the existing guard), matching the current actions.
- **FR-005**: Existing Create / Publish / Load actions, their labels, and their
  ordering MUST be preserved.
- **FR-006**: The implementation MUST NOT modify `client/ayon_flame/plugins/**`,
  `server/**`, or any publish/version code, and MUST NOT add a settings field or
  a `_convert_*` migration.
- **FR-007**: `client/ayon_flame/addon.py` MUST remain importable without the
  `flame` module; the change MUST NOT add a `flame` import to launcher-safe
  code.
- **FR-008**: If the host `IWorkfileHost` mixin (spec 001 D1b) is not wired in
  this milestone, the feature MUST NOT activate or alter validator/collector
  behaviour (FR-009 of spec 001 still holds); the dependency MUST be recorded
  as an explicit decision, not silently relied upon.

### Key Entities

- **Batch context menu**: The menu built for the Flame Batch page by
  `_FlameMenuContext.build_menu()` / the `FlameMenuBatch` app.
- **Menu action**: The declarative `{"name": ..., "execute": lambda selection: ...}`
  entry pattern used by the existing Create / Publish / Load actions.
- **Workfiles tool**: AYON's `host_tools.show_workfiles` surface for the
  registered host's `IWorkfileHost`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A **Workfiles** action is present on the Flame Batch AYON menu and
  absent from Timeline/Universal menus (verifiable by menu-build inspection).
- **SC-002**: Selecting the action calls `host_tools.show_workfiles` with a
  `QMainWindow` parent (verifiable by code inspection and an in-host run).
- **SC-003**: `ruff check .` passes on changed files and `git diff` shows no
  change outside the intended menu file and this spec.
- **SC-004**: `client/ayon_flame/addon.py` imports without `flame` (launcher
  boundary intact).

## Assumptions

- **Scope is menu-entry-only by default**: The primary deliverable is the
  Batch-menu Workfiles action. Whether to also wire `FlameHost` as an
  `IWorkfileHost` (spec 001 D1b flip) in this milestone is an **open decision**
  for `/speckit.plan`; the default assumption here is that wiring stays in the
  spec-001 follow-up unless the user explicitly opts in, because flipping it
  changes publish/version behaviour (spec 001 R10/D1).
- **Label/position**: "Workfiles..." placed as the next numbered action (after
  the existing `3 - Load...`), consistent with the current labels.
- **Placement implementation**: Implemented by overriding `build_menu` on
  `FlameMenuBatch` (calling `super().build_menu()` then appending the
  Workfiles action) so the entry is Batch-scoped without disturbing the shared
  `_FlameMenuContext` actions. Alternative (adding to the shared builder and
  exposing on every context) is noted and rejected by default per the request.
- **Dependency on spec 001**: This feature consumes
  `client/ayon_flame/api/workfile.py`; that module already exists and is
  unmodified here.