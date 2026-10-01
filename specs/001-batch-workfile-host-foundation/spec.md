# Feature Specification: Flame Batch Workfile Host Foundation

**Feature Branch**: `Batch-workfile-host-foundation`
**Created**: 2026-09-23
**Status**: Draft
**Input**: Implement `IWorkfileHost` for the Flame Batch page in
`client/ayon_flame`, reusing `api/workio.py` and the consolidated-JSON batch
format, selecting the workfile host by `flame.get_current_tab()`. Do not
change publish/version behavior yet.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use AYON workfile operations on the Batch page (Priority: P1)

As a Flame artist working in the Batch page, I want AYON's workfile
integration to operate on the active Batch group through the standard
`IWorkfileHost` contract, so that Batch workfiles can be handled by shared
AYON workfile tooling without a second implementation of Batch serialization.

**Why this priority**: The Batch page is the target host context and is the
foundation for future Batch workfile workflows.

**Independent Test**: In a Flame session with the Batch page active, install
the AYON host and verify that the registered workfile host is the Batch
implementation and that its workfile operations delegate to the existing
Flame workfile seam and Batch helpers.

**Acceptance Scenarios**:

1. **Given** Flame is displaying the Batch page, **when** AYON host/workfile
   integration is installed, **then** the Batch `IWorkfileHost` is selected
   using `flame.get_current_tab()`.
2. **Given** an active Batch group, **when** the Batch workfile host performs
   a supported save/export operation, **then** the existing consolidated JSON
   Batch representation is used through `client/ayon_flame/api/workio.py`
   and/or its existing Batch utility seam, without introducing another
   serialization format.
3. **Given** a consolidated JSON Batch workfile, **when** the Batch workfile
   host performs a supported open/import operation, **then** the existing
   Batch JSON loader is used and the resulting Batch group is restored in
   Flame.
4. **Given** the Batch workfile host is selected, **when** shared AYON code
   asks for the work root, **then** the existing `workio.work_root(session)`
   behavior is retained.
5. **Given** the active Flame tab is not the Batch page, **when** host/workfile
   integration is installed or queried, **then** the Batch workfile host is
   not selected for that tab.

### User Story 2 - Preserve existing non-workfile behavior (Priority: P1)

As a pipeline administrator, I want this foundation to leave existing
publishing and native Flame version/iteration behavior unchanged, so that the
feature can be introduced without altering current production publishing.

**Independent Test**: Review the diff and run the existing lint/package checks;
verify that publish/version plugins and their behavior are not modified.

**Acceptance Scenarios**:

1. **Given** existing publish plugins and version/iteration handling, **when**
   the Batch workfile host is added, **then** no publish plugin, publish
   registration, version collector, or version/iteration behavior is changed.
2. **Given** existing non-Batch Flame contexts, **when** the integration is
   loaded, **then** their current host behavior remains available and the new
   Batch selection logic does not import or require Batch GUI state outside
   the Flame runtime boundary.

### User Story 3 - Keep launcher-safe and host-runtime boundaries (Priority: P1)

As an AYON launcher user, I want the addon registration module to remain
importable without Flame installed, while Flame-specific tab selection and
workfile operations execute only inside Flame.

**Independent Test**: Import the launcher-facing addon module in a plain Python
environment without the Flame module, and inspect that Flame imports remain
in the API/startup integration boundary.

**Acceptance Scenarios**:

1. **Given** a plain Python interpreter without Flame's `flame` module, **when**
   `client/ayon_flame/addon.py` is imported, **then** the import succeeds as
   it does today.
2. **Given** Flame runtime is available, **when** the integration is started,
   **then** tab detection uses `flame.get_current_tab()` and registers the
   appropriate Batch workfile host through the existing AYON host/workfile
   installation path.

## Requirements

### Functional Requirements

- **FR-001**: The client SHALL provide a Flame Batch implementation of the
  shared `ayon_core` `IWorkfileHost` contract.
- **FR-002**: The Batch workfile host SHALL be selected based on the value
  returned by `flame.get_current_tab()`; it SHALL not use only the existing
  `CTX.context` marker as the selection mechanism.
- **FR-003**: The implementation SHALL identify the Flame Batch page using a
  single documented, maintainable tab predicate, including the behavior for
  missing, unexpected, or non-Batch tab values.
- **FR-004**: Batch workfile operations SHALL reuse the existing
  `client/ayon_flame/api/workio.py` seam rather than duplicating its public
  workfile API.
- **FR-005**: Batch serialization/deserialization SHALL use the existing
  consolidated JSON format and the existing helpers in
  `client/ayon_flame/api/batch_utils.py`; no new Batch file format or parallel
  conversion path SHALL be introduced.
- **FR-006**: The implementation SHALL preserve the existing work root
  behavior (`session["AYON_WORKDIR"]`) unless required by the
  `IWorkfileHost` contract, in which case the adapter SHALL delegate to
  `workio.work_root`.
- **FR-007**: The implementation SHALL be initialized from the Flame runtime
  integration (startup/API seam), not by importing `flame` from
  `client/ayon_flame/addon.py`.
- **FR-008**: The implementation SHALL define safe behavior for a Batch tab
  with no active Batch group and for unsupported `IWorkfileHost` operations;
  behavior SHALL be explicit rather than silently producing a different
  workfile.
- **FR-009**: Existing publish registration and publish plugins SHALL remain
  unchanged by this feature.
- **FR-010**: Existing Flame native version and Batch iteration behavior SHALL
  remain unchanged by this feature.
- **FR-011**: No settings field rename or settings schema migration SHALL be
  introduced by this feature.
- **FR-012**: The implementation SHALL preserve compatibility with the AYON
  Core version declared by `package.py` (`core >=1.8.0`).

### Non-Functional Requirements

- **NFR-001**: Host-runtime imports and GUI/tab access SHALL remain outside
  launcher-safe addon registration code.
- **NFR-002**: The implementation SHALL use the repository's existing style and
  pass `ruff check .` and `ruff format --check .`.
- **NFR-003**: Packaging SHALL continue to pass
  `python create_package.py --skip-zip`.
- **NFR-004**: The feature SHALL not add a test framework to this repository.
  Verification requiring Flame SHALL be documented as a manual in-host test.

## Key Entities

- **Batch workfile host**: Flame-specific adapter implementing AYON Core's
  `IWorkfileHost` contract for the Flame Batch page.
- **Current Flame tab**: The runtime value returned by
  `flame.get_current_tab()`, used to choose whether the Batch host applies.
- **Active Batch group**: The native Flame Batch object operated on by the
  existing Batch utility functions.
- **Consolidated JSON Batch workfile**: The existing JSON document containing
  the native Batch setup and referenced files, including the established
  `__b64__:` encoding for binary contents.
- **Work root**: The AYON work directory returned by the existing
  `workio.work_root(session)` contract.

## Scope Boundaries

### In scope

- Adding the Batch `IWorkfileHost` adapter and its runtime registration or
  selection path.
- Adapting the existing `api/workio.py` and consolidated JSON Batch helpers
  to the shared workfile-host contract as needed.
- Current-tab selection using `flame.get_current_tab()`.
- Explicit handling/documentation of unsupported operations and absent Batch
  context.
- Manual Flame validation instructions and static/package validation.

### Out of scope

- Changes to publish plugins, publish registration, extraction, integration,
  or collected publish data.
- Changes to Flame native version handling, Batch iterations, or loader version
  behavior.
- Replacing or redesigning the consolidated JSON format.
- Changes to server settings, settings overrides, or addon compatibility
  constraints.
- Workfile support for Timeline, Media Panel, Main Menu, or other Flame tabs.
- New GUI controls, autosave behavior, or native Flame project/workfile
  management beyond the `IWorkfileHost` adapter.

## Assumptions and Clarifications Needed During Planning

- The exact `IWorkfileHost` method surface and registration API are provided by
  the AYON Core version declared in `package.py`; implementation planning must
  verify those signatures before coding.
- The exact runtime value/name returned for the Flame Batch page by
  `flame.get_current_tab()` must be confirmed against the supported Flame API
  during in-host validation. The predicate must be centralized so this value
  can be corrected without changing workfile serialization.
- Flame's native workfile management currently raises
  `NotImplementedError` in `api/workio.py`; planning must decide which methods
  are true adapters to consolidated JSON and which remain explicitly
  unsupported, without changing publish/version behavior.

## Implementation Status (2026-09-23)

**Delivered in this milestone**: the workfile-host capability for the Flame
Batch page — `client/ayon_flame/api/workfile.py` with `_is_batch_tab`,
`FlameWorkfileHost`, `FlameBatchWorkfileHost` and `get_flame_workfile_host`
(selected via `flame.get_current_tab()`), exported from `api/__init__.py`.

**Not delivered**: the capability is **not yet wired into `FlameHost`**. The
D1b decision (wire now) was taken, but implementation showed wiring would
break the feature's own constraint "do not change publish/version behaviour
yet" — see `research.md` R10 and `plan.md` D1:

- `ayon_core`'s `ValidateCurrentSaveFile` reads `context.data["currentFile"]`,
  which only a host-specific collector sets; Flame has none, so every Flame
  publish would fail.
- Adding that collector activates `ayon_core`'s `CollectSceneVersion`, which
  raises `PublishError` for version-less workfile names and collides, at the
  same `order`, with Flame's own `CollectBatchVersion` over
  `context.data["version"]`.
- Non-Batch publishing would become unsatisfiable because
  `workio.save_file()` still raises `NotImplementedError`.

Consequently **FR-009 and FR-010 remain satisfied** (no publish or version
behaviour changed), FR-007 is satisfied (nothing added to `addon.py`), and
FR-001/FR-002/FR-004/FR-005/FR-006/FR-008/FR-011/FR-012 are satisfied by the
new module. The remaining work to activate the host — plus the prerequisite
Timeline workfile-save support — is tracked in `tasks.md` (DV-1) and the D1
checklist in `plan.md`.

## Verification Plan

1. Run `ruff check .`.
2. Run `ruff format --check .`.
3. Run `python create_package.py --skip-zip`.
4. In Flame, activate the Batch page, install AYON, and verify the selected
   workfile host and current-tab predicate.
5. In Flame, export/save a Batch group through the host and inspect that the
   output is the established consolidated JSON format.
6. Open/load that JSON through the host and verify the Batch group is restored.
7. Repeat on a non-Batch tab and verify the Batch host is not selected.
8. Confirm existing publish and native version/iteration workflows continue
   unchanged; this feature must not require a publish/version migration.
