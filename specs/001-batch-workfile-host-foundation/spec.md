# Feature Specification: Flame Batch Workfile Host Foundation

**Feature Branch**: `Batch-workfile-host-foundation`
**Created**: 2026-09-23
**Amended**: 2026-10-01 (see "Amendment 1")
**Status**: Draft
**Input**: Implement `IWorkfileHost` for the Flame Batch page in
`client/ayon_flame`, reusing `api/workio.py` and the consolidated-JSON batch
format, selecting the workfile host by `flame.get_current_tab()`. Do not
change publish/version behavior yet.

## Clarifications

### Session 2026-10-01

- Q: When the Batch workfile host is switched on so the Workfiles widget can
  save, should the amendment also include the smallest publish-side change
  that keeps Flame publishing working and version numbers unchanged? → A:
  Yes (Option A) — include the minimal publish-side change (current workfile
  path supplied to publishing; existing Batch version still wins), keeping
  publish and version results identical (FR-A10 to FR-A12).
- Q: If an artist publishes a Batch that has never been saved as an AYON
  workfile, should publishing proceed as today or be blocked until they save?
  → A: Blocked, but by a publish **validator** with a clear, actionable
  message; its **Repair** action saves the Batch as the next available
  workfile version without opening the Workfiles tool (FR-A13 to FR-A17).
  This is the one deliberate exception to "publish results identical" in
  FR-A11.
- Q: After Flame is restarted, how should the validator know a Batch was
  already saved as an AYON workfile earlier? → A: Ask AYON Core for existing
  workfiles of the current context (Option B); if at least one exists the
  Batch counts as saved. No saved-path state is persisted by the addon
  (FR-A18).

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
  unchanged by this feature, except the minimal change in FR-A10 to FR-A12.
- **FR-010**: Existing Flame native version and Batch iteration behavior SHALL
  remain unchanged by this feature (FR-A11 makes this testable).
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
  beyond the minimum in FR-A10 to FR-A12,
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

## Amendment 1 (2026-10-01) — Save the active Batch from the Workfiles widget

**Input**: Implement workfile save in `api/workio.py` so the AYON Workfiles
widget persists the active Flame batch group as consolidated JSON, letting
`ayon_core` allocate the version number.

**Why this amends 001**: Article 10 survey found that the Batch save
capability already exists unwired (`FlameBatchWorkfileHost.save_workfile`) and
that the blocker is `workio.save_file()` plus the host wiring tracked in
DV-1. This amendment completes that remaining work instead of opening a new
feature. Where it conflicts with "do not change publish/version behaviour
yet" (original Input, FR-009, FR-010) the narrower rules below apply and the
conflict is resolved by Clarification Q1 (FR-A10 to FR-A12).

### User Story 4 - Save the current Batch from the Workfiles widget (Priority: P1)

As a Flame artist on the Batch page, I want to press **Save** in the AYON
Workfiles widget and have my active Batch group stored as an AYON workfile,
so that I can return to that exact Batch state later without managing files
or version numbers by hand.

**Why this priority**: This is the first user-visible capability of the Batch
workfile host; without it the host from User Story 1 cannot be used.

**Independent Test**: In Flame with an active Batch group, open the Workfiles
widget, save, and confirm a new consolidated JSON workfile appears in the
work area. Save again and confirm a second file with the next version.

**Acceptance Scenarios**:

1. **Given** an active Batch group on the Batch page, **when** the artist
   saves from the Workfiles widget, **then** a consolidated JSON file
   representing that Batch is written at the path chosen by the widget and
   the widget lists it as a workfile.
2. **Given** a Batch workfile already exists at version N, **when** the artist
   saves a new version, **then** the file is written at the version number
   that AYON Core allocated and the addon neither computes, increments nor
   rewrites that number.
3. **Given** a saved Batch workfile, **when** it is opened through the
   existing open path (User Story 1), **then** the Batch group is restored
   as saved.
4. **Given** the Batch page is active but no Batch group is open, **when**
   the artist saves, **then** nothing is written and the artist sees a clear
   "no active Batch group" error.
5. **Given** the target path cannot be written (missing permission, full
   disk), **when** the artist saves, **then** the error is surfaced, no
   partial or empty workfile is left in the work area, and the Batch group in
   Flame is unchanged.

### User Story 5 - Other tabs behave as before (Priority: P2)

As an artist on a non-Batch tab, I want save to fail explicitly rather than
write a Batch file, so that the wrong context is never stored as a workfile.

**Independent Test**: Trigger a workfile save while a non-Batch tab is
active and confirm no Batch JSON is written.

**Acceptance Scenarios**:

1. **Given** a non-Batch tab is active, **when** a workfile save is requested,
   **then** it behaves as it does today (explicitly unsupported) and no file
   is written.

### User Story 6 - Publish requires a saved Batch workfile (Priority: P2)

As a pipeline supervisor, I want a Batch to be saved as an AYON workfile before
it is published, so that every published Batch version can be traced to the
workfile it came from; and as an artist I want a one-click fix when I forgot.

**Independent Test**: Publish a Batch that has never been saved: validation
fails with the message. Click Repair: a new workfile version is saved and
validation passes. Publish again unchanged: no failure.

**Acceptance Scenarios**:

1. **Given** a Batch with no saved AYON workfile, **when** the artist
   publishes, **then** validation fails with the clear message from FR-A14 and
   nothing is published.
2. **Given** that failure, **when** the artist clicks Repair, **then** the
   Batch is saved as the next available version without the Workfiles tool
   opening, and re-validation passes.
3. **Given** the current context already has an AYON workfile (saved earlier,
   including before a Flame restart, via the Workfiles widget or Repair),
   **when** the artist publishes, **then** the validator
   passes and publish proceeds exactly as before.
4. **Given** Repair cannot save (for example an unwritable work area),
   **when** the artist clicks Repair, **then** a cause-naming error is shown,
   no partial file exists, and validation still fails.

### Edge Cases (amendment)

- Save is requested while the destination file already exists at the same
  path: the widget/Core decides overwrite policy; the addon writes only to
  the path it is given and never picks a different one.
- The Batch contains very large or binary embedded files: the existing
  consolidated JSON encoding is used unchanged; save either completes fully
  or fails without leaving a partial file.
- Batch name contains characters unsuitable for file names: naming is owned
  by AYON Core templates; the addon does not derive file names.
- Two Batch groups are open: only the active Batch group is saved.
- The current tab cannot be read: the save fails explicitly and does not
  assume Batch.

### Functional Requirements (amendment)

- **FR-A01**: `workio.save_file(filepath)` SHALL, when the Batch page is the
  active tab, persist the active Batch group to `filepath` in the existing
  consolidated JSON format, using the existing `batch_utils` helpers and the
  same code path as `FlameBatchWorkfileHost.save_workfile`; there SHALL be one
  Batch save implementation, not two.
- **FR-A02**: The addon SHALL write to exactly the `filepath` supplied by AYON
  Core and SHALL NOT compute, allocate, parse, increment or alter the version
  number, file name, or directory. The only other save path is the validator
  Repair action (FR-A15), which SHALL obtain the next version and path from
  AYON Core's workfile allocation and never compute them in the addon.
- **FR-A03**: Saving SHALL NOT mutate the Batch group in Flame, its iteration
  number, or its metadata.
- **FR-A04**: On any failure (no active Batch, unreadable tab, serialisation
  or write error) the save SHALL raise an error with an actionable message
  and SHALL NOT leave a partial or empty file at `filepath`.
- **FR-A05**: On non-Batch tabs `workio.save_file` SHALL keep today's explicit
  "unsupported" behaviour and SHALL NOT write a Batch file.
- **FR-A06**: The Workfiles widget SHALL be able to reach the save path, which
  requires the Batch workfile host to be active in `FlameHost` (DV-1).
- **FR-A10**: Activating the host SHALL include the minimum publish-side
  change needed so that Flame publishing keeps working: the publish context
  SHALL receive the current workfile path (R10.1) and the existing Batch
  version from `CollectBatchVersion` SHALL remain the value used for
  publishing, never a version parsed from the workfile name (R10.2).
- **FR-A11**: With the host active, the collected publish version, Batch
  iteration number and publish validation outcome for the same Batch SHALL be
  identical to those before activation for a Batch that has a saved AYON
  workfile, including when the saved name carries no version. The sole
  deliberate difference is the validator in FR-A13 for a never-saved Batch.
- **FR-A12**: The publish-side change SHALL be limited to what FR-A10 and
  FR-A11 require, plus the validator and repair in FR-A13 to FR-A17, and SHALL
  be listed explicitly in the plan; no other publish
  plugin, registration, extraction or integration behaviour SHALL change.
- **FR-A13**: Publishing a Batch SHALL be checked by a publish validator that
  FAILS when AYON Core reports no workfile for the current context
  (FR-A18). It applies only to Batch publishing and SHALL NOT run for other
  tabs/contexts.
- **FR-A14**: The failure message SHALL state the problem, why it matters,
  and the two ways out, in plain language, and SHALL name the Batch group.
  Proposed wording (final text settled in planning, same content): title
  "Batch has no saved workfile"; body "The Batch group '<name>' has not been
  saved as an AYON workfile, so this publish cannot be linked to a workfile
  version. Save the Batch from the Workfiles tool, or click Repair to save it
  now as the next available version."
- **FR-A15**: The validator SHALL provide a Repair action that saves the
  active Batch group as the next available workfile version for the current
  context, as consolidated JSON through the same save path as FR-A01, without
  requiring the artist to open or interact with the Workfiles tool. Version,
  file name and directory SHALL be obtained from AYON Core (FR-A02).
- **FR-A16**: After a successful Repair the validator SHALL pass on
  re-validation, the session SHALL record the new path as the current
  workfile, and the new file SHALL be listed by the Workfiles widget.
- **FR-A17**: If Repair fails (no active Batch, no resolvable context, write
  error) it SHALL report the cause, leave no partial file, and leave the
  validator failing; it SHALL NOT overwrite an existing workfile.
- **FR-A18**: "Has a saved workfile" SHALL mean AYON Core lists at least one
  workfile for the current project/folder/task context; this check SHALL work
  identically before and after a Flame restart and SHALL NOT depend on any
  session-only record or on state the addon persists. A Batch is not matched
  to a specific workfile, so an older workfile in the same context satisfies
  the validator.
- **FR-A07**: `workio.save_file` SHALL remain importable only from the Flame
  API seam; `addon.py` SHALL NOT import it or `flame` (NFR-001 unchanged).
- **FR-A08**: Existing `open_file`, `current_file`, `has_unsaved_changes`
  contracts SHALL NOT change except where unavoidable for FR-A06 or FR-A10, and any
  such change SHALL be listed in the plan.
- **FR-A09**: No settings, settings migration, or compatibility constraint
  SHALL change (FR-011, FR-012 hold).

### Key Entities (amendment)

- **Allocated workfile path**: The full destination path (directory, name,
  version, extension) produced by AYON Core and handed to the save request;
  treated as opaque by the addon.
- **Saved Batch workfile**: The consolidated JSON file written for the active
  Batch group; round-trips through the existing open path.

### Success Criteria (amendment)

- **SC-A01**: An artist can save the active Batch from the Workfiles widget in
  one action and see the new workfile listed immediately.
- **SC-A02**: Ten consecutive saves produce ten distinct workfiles with
  consecutive version numbers, none assigned by the addon.
- **SC-A03**: 100% of saved workfiles reopen to a Batch equivalent to the one
  saved (same nodes, reels and settings) in manual in-host checks.
- **SC-A04**: In every induced failure (no Batch, unwritable path), zero
  partial files remain and the artist sees a message naming the cause.
- **SC-A05**: Saving on a non-Batch tab produces zero files.
- **SC-A06**: For a Batch with a saved workfile, publish and Batch iteration/
  version results are identical before and after the amendment (FR-A10 to
  FR-A12).
- **SC-A07**: Publishing a never-saved Batch fails validation 100% of the
  time, and one Repair click turns it into a passing publish with a new
  workfile version, with zero Workfiles tool interaction.
- **SC-A08**: In a usability check, 9 of 10 artists can say from the message
  alone what is wrong and what to do.

### Assumptions (amendment)

- AYON Core's Workfiles tool resolves the path and version and then calls the
  host's save with the final path; the addon supplies no template logic.
- The Batch tab predicate and consolidated JSON helpers from the original
  milestone are correct and reused as delivered.
- Non-Batch workfile save remains unsupported; Timeline save is a separate
  future feature (DV-1 prerequisite noted in tasks).
- "Has a saved workfile" is defined by FR-A18 (context-level, via AYON
  Core); workfiles saved outside AYON are not detected. The in-memory path
  record from the original milestone (DV-3) remains only for
  `get_current_workfile()` and is not used by the validator.
- AYON Core exposes a way to resolve the next workfile version/path for a
  context; planning must confirm it exists in the declared `core` version
  (`>=1.8.0`) before adopting FR-A15.
- Verification is manual in Flame plus `ruff` and package-build checks; no
  test framework is added.

## Implementation Status — Amendment 1 (2026-10-01)

**Delivered (code)**: atomic Batch save in `workio.save_file` (FR-A01–A05);
`FlameHost` is now an `IWorkfileHost` (FR-A06, resolves DV-1); new
`CollectCurrentFile` collector (FR-A10); Core's `ValidateCurrentSaveFile` and
`CollectSceneVersion` are kept inactive for the Flame host through a pyblish
discovery filter (FR-A10–A12); new `ValidateBatchWorkfileSaved` validator whose
Repair calls Core's `save_next_version()` (FR-A13–A17); the existence check uses
the context's workfiles from AYON Core (FR-A18). `CollectBatchVersion`,
`addon.py`, `startup/`, `server/` and `package.py` are unchanged.

**Not verified — needs a reviewer inside Flame**: all acceptance scenarios and
`SC-A01`–`SC-A08` (see `quickstart.md`); code paths were verified only with
stubbed harnesses and static checks (tasks.md DV-8).

**Open — needs a decision**: the Workfiles tool has no entry in Flame's AYON
menus, so artists cannot open it from Flame (tasks.md T029 / DV-9). Adding a
menu control is out of the stated scope here; it is tracked and implemented by
spec 002 (`specs/002-workfiles-batch-menu-entry`, branch
`workfile-entry-batch-menu`).

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
