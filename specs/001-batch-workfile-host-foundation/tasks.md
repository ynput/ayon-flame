# Tasks: Flame Batch Workfile Host Foundation

**Feature**: `specs/001-batch-workfile-host-foundation/spec.md`
**Plan**: `specs/001-batch-workfile-host-foundation/plan.md`
**Branch**: `Batch-workfile-host-foundation`
**Prerequisites**: `spec.md` (done), `plan.md` (done), `research.md` (done)

**Blocking gate**: `T001` must be resolved (plan **D1**: whether `FlameHost`
gains the `IWorkfileHost` mixin in this milestone) before any task marked
`[GATED:D1]` may start. Phases 2 and the read-only parts of Phase 5/6 do not
depend on it.

**Conventions**

- `[P]` = parallelizable (different files, no dependency on in-flight edits).
- `[GATED:D1]` = blocked until the D1 decision is recorded.
- Every task that touches `client/ayon_flame/**` must keep `addon.py`
  importable without the `flame` module and must not modify anything under
  `client/ayon_flame/plugins/` or `server/`.
- The repository has **no test framework**; do not add one.

---

## Phase 1 — Setup & Decision Gate

- [x] **T001 [BLOCKING] Record the D1 decision** — **D1b requested
      (2026-09-23)**, but implementation revealed a larger blast radius than
      D1b assumed (research **R10**: no Flame `collect_current_file` collector →
      `ValidateCurrentSaveFile` KeyError; adding one activates
      `CollectSceneVersion` → `PublishError` on version-less paths and a
      same-`order` collision with `CollectBatchVersion` over
      `context.data["version"]`; non-Batch publishing becomes unsatisfiable
      because `workio.save_file` raises). D1b is therefore **deferred** and
      this milestone ships the D1a scope. Resolution, rationale and the
      ready-to-apply D1b flip checklist are recorded in `plan.md` D1.
      **No `FlameHost` change was made.**
- [x] **T002 Re-verify the `IWorkfileHost` surface against the installed core**
      — Verified against the local `ayon-core` checkout
      (`host/interfaces/workfiles.py:830`): exactly three abstract methods
      (`save_workfile`, `open_workfile`, `get_current_workfile`), defaults for
      `workfile_has_unsaved_changes`/`get_workfile_extensions`, no `work_root`
      in the interface, no separate registry (`isinstance` only). Recorded in
      `research.md` R6.
- [ ] **T003 [P] Confirm the Flame tab value for the target builds** — *Not
      done.* Requires Flame 2026/2027 in-host. Evidence so far: published API
      stubs for 2024.2 and 2026.2 both declare
      `flame.set_current_tab` with tabs `MediaHub, Conform, Timeline, Effects,
      Batch, Tools` → expected `flame.get_current_tab() == "Batch"`
      (`research.md` R7). Moved to the in-host gate T021/T025.

---

## Phase 2 — Batch workfile host module (no publish impact)

- [x] **T004 Create `client/ayon_flame/api/workfile.py` skeleton** — Created;
      module docstring states it is host-runtime-only (imports `flame`) and is
      not to be imported from `addon.py`. Imports `os`/`typing`, `flame`,
      `ayon_core.host.IWorkfileHost`, `ayon_core.lib.Logger`, and the sibling
      `batch_utils`/`workio`; module logger added.
- [x] **T005 [P] Implement `_is_batch_tab(tab)` predicate** — Implemented with
      `BATCH_TAB = "Batch"`; normalized (`strip().lower()`) comparison;
      non-`str`, `None`, and any other tab (including `"BFX"`) → `False`.
      Docstring documents the Flame tab set and the fail-closed rule.
- [x] **T006 Implement `FlameWorkfileHost(IWorkfileHost)`** — Implemented via a
      shared `_FlameWorkfileHostBase` (session path record +
      `workfile_has_unsaved_changes() -> None`). Delegates
      `save_workfile`→`workio.save_file`, `open_workfile`→`workio.open_file`,
      `get_current_workfile`→`workio.current_file()` **with a
      `NotImplementedError` fallback** to AYON's session record (never raises),
      `get_workfile_extensions`→`workio.file_extensions()`, plus the extra
      `work_root(session)`→`workio.work_root`. Deprecated aliases are not
      overridden.
- [x] **T007 Implement `FlameBatchWorkfileHost(IWorkfileHost)`** — Implemented:
      `save_workfile` raises `RuntimeError` on a falsy `dst_path` and otherwise
      calls `batch_utils.save_batch_as_consolidated_json`;
      `open_workfile` calls `batch_utils.load_batch_from_consolidated_json`;
      `get_current_workfile` returns only the recorded AYON path (never a
      fabricated native path); `workfile_has_unsaved_changes() -> None`;
      `get_workfile_extensions() -> [".json"]`. Missing Batch Group surfaces as
      a clear `RuntimeError` (never a silent wrong group).
- [x] **T008 Implement `get_flame_workfile_host()` selector** — Implemented;
      reads `flame.get_current_tab()` inside `try/except`, logs and falls back
      to `FlameWorkfileHost` on any error, returns
      `FlameBatchWorkfileHost` only when `_is_batch_tab(tab)`. No caching.
- [x] **T009 Export the new seam from `api/__init__.py`** — Added the
      `workfile` import block and `__all__` entries for
      `FlameWorkfileHost`, `FlameBatchWorkfileHost`,
      `get_flame_workfile_host`, matching the file's existing style.
- [x] **T010 Verify `FlameWorkfileHost` cannot regress publishes** — Done by
      construction: `get_current_workfile()` catches `NotImplementedError` and
      returns `None` instead of raising; no publish path is touched while the
      mixin is unwired. The residual publish risk is exactly R10 and is
      deferred to the D1b flip (blocked).

---

## Phase 3 — Host wiring (GATED:D1) — NOT APPLIED

- [x] **T011 [GATED:D1 → SUPERSEDED by T033, Amendment 1] Add `IWorkfileHost` to `FlameHost`** — **DEFERRED, not
      performed.** Blocked by R10; applying it without a Flame
      `collect_current_file` collector breaks every Flame publish, and adding
      that collector changes `context.data["version"]` and blocks non-Batch
      publishing. Exact flip steps recorded in `plan.md` D1. This is the
      deliberate deviation from the D1b instruction.
- [x] **T012 [GATED:D1 → SUPERSEDED by T033, Amendment 1] Confirm `startup/AYON_in_flame.py` needs no change** —
      **Deferred with T011.** Read and confirmed the file already calls
      `install_host(FlameHost())` in each `get_*_custom_ui_actions` hook, so
      no change would be required once T011 is applied.
- [x] **T013 [P][GATED:D1] Confirm `addon.py` is unchanged** — **Confirmed
      unchanged** (`git status` shows no modification); `addon.py` still
      returns `[".otoc"]` from its launcher-time `get_workfile_extensions()`
      and contains no `flame` import. Reported here rather than blocked,
      because it is true regardless of T011.

---

## Phase 4 — Publish-impact containment

- [x] **T014 [GATED:D1] Confirm no publish plugin or registration changed** —
      Confirmed: `client/ayon_flame/plugins/**`, `server/**`,
      `api/menu.py`, and `api/pipeline.py` are all unmodified. Change set is
      `api/workfile.py` (new), `api/__init__.py` (exports), plus `specs/`.
- [ ] **T015 [GATED:D1 → SUPERSEDED by T027/T039/T042, Amendment 1] Verify `ValidateCurrentSaveFile` behaviour** —
      **Deferred with T011** (nothing to verify while the mixin is unwired).
      Expected behaviour if D1b is flipped: R10.1–R10.3.
- [x] **T016 Confirm `CTX.context` and creators/loaders are untouched** —
      Confirmed by `git status`: no changes under `plugins/create`,
      `plugins/publish`, `scripts/`, or the `CTX.context` readers in
      `api/pipeline.py`. The new selection does not use `CTX.context`.

---

## Phase 5 — Static validation

- [x] **T017 `ruff check .`** — `python3 -m ruff check` **passes for the
      changed files** (`api/workfile.py`, `api/__init__.py`). The repo-wide run
      reports **one pre-existing** `E501` in unmodified `agentic_setup.py:141`
      (`ruff 0.16.0`, line 92 > 79), unrelated to this change and left alone.
- [x] **T018 `ruff format --check .`** — `api/workfile.py` is written to the
      repo's dominant style and passes `ruff check`; note that repo-wide
      `ruff format --check` already reports many pre-existing files (including
      untouched `docs/*.md` and `api/__init__.py`) as needing reformatting
      under `ruff 0.16.0`, so repo-wide format drift is pre-existing.
- [x] **T019 `python create_package.py --skip-zip`** — *Passed in Amendment 1 (T044); originally not run*: it would
      touch generated package artifacts unrelated to this change. Run by the
      reviewer/CI.
- [x] **T020 Verify launcher-safe import** — Confirmed `addon.py` contains no
      `flame` import and was not modified, so the launcher path is unaffected.
      Note `ayon_flame.api` already imported `flame` (via `api/pipeline.py`)
      before this change, so adding `api/workfile.py` does not alter the
      launcher import graph.
      **Extra (beyond plan): module-level verification.** `api/workfile.py` was
      exercised in a throwaway stubbed harness with 21 assertions (tab
      predicate, selector dispatch, save/open delegation, current-workfile
      before/after save and after open, missing-path and missing-Batch errors,
      default-host delegation, fallback when the tab API is absent) — all
      passed. See `research.md` R11.

---

## Phase 6 — Manual Flame validation (reviewer, in-host)

Flame cannot be executed from an agent session; a human reviewer must run
these inside Flame via the studio launcher wrapper (`README.md`).

- [ ] **T021 Verify tab selection on Flame 2026** — On the Batch page,
      `flame.get_current_tab()` returns `"Batch"` and
      `get_flame_workfile_host()` returns `FlameBatchWorkfileHost`; on the
      Timeline and Media Panel it returns `FlameWorkfileHost`.
- [ ] **T022 Verify Batch workfile round-trip on Flame 2026** — Save a Batch
      group through the host and confirm the output is exactly the
      `save_batch_as_consolidated_json` shape (relative-path keys, `__b64__:`
      for binaries); open it back and confirm the Batch Group is restored.
      Record whether open *replaces* or *merges into* the current group
      (plan risk) and whether any Batch Group existed beforehand.
- [ ] **T023 Verify Batch tab with no Batch Group** — On the Batch page with
      no active Batch Group, save/open must raise the explicit error from
      T007 — never silently target another group.
- [ ] **T024 Verify Batch iteration behaviour unchanged** — Confirm the
      publish-driven iteration flow (`integrate_batch_iteration.py`,
      `flame.batch.iterate()`) and the loader's iteration handling
      (`plugins/load/load_batch.py`) behave exactly as before.
- [ ] **T025 Repeat T021–T024 on Flame 2027** — Required for the
      "compliant with Flame 2026 to 2027" goal; note any API drift in
      `research.md` R7.
- [ ] **T026 Record results** — Append observed values (tab strings, error
      messages, round-trip outcomes) to `research.md` open questions and, if
      the D1 decision needs adjusting, note it in `plan.md` Decisions.

---

## Amendment 1 tasks (2026-10-01)

**Spec**: Amendment 1 (FR-A01–A18, US4–US6). **Plan**: "Amendment 1 plan"
(D6–D11, Open items). **Design**: `data-model.md`,
`contracts/internal-seams.md`, `quickstart.md`.

**Overrides to the Conventions above (for Amendment 1 tasks only)**: the
original ban on editing `client/ayon_flame/plugins/` is lifted for exactly the
two new publish plugins and the host-scoped Core-plugin handling listed in
FR-A12 / plan "Source layout delta"; every other publish plugin, `server/`,
`package.py` and `addon.py` stay unchanged. No test framework is added.

**Ship gate**: T033 (host becomes an `IWorkfileHost`) MUST NOT be merged or
released without T038–T041 (collector, Core-plugin handling, validator,
repair) — activating the host alone breaks Flame publishing (R10).

**Task format**: `- [ ] Txxx [P?] [Story?] description with file path`.

### Phase A1 — Gates and verification (no story label)

- [x] T027 Prove the D9 mechanism with a throwaway harness in `/tmp` (not
      committed): show which pyblish approach disables Core's
      `ValidateCurrentSaveFile` and `CollectSceneVersion` for host `flame`
      only and survives publish-time plugin discovery. Record the result and
      chosen mechanism in `specs/001-batch-workfile-host-foundation/research.md`
      as **R13**. **GATE for T039**; if no mechanism preserves FR-A11, stop and
      report to the user — do not edit Core or settings.
- [x] T028 [P] Confirm `save_next_version`, `host.list_workfiles` and
      `RepairContextAction` exist with the signatures in R12 on the lowest
      supported core (`core >=1.8.0` from `package.py`, not only the
      `1.9.14+dev` checkout at `/Users/jakub/CODE/__YNPUT/ayon-core`); amend
      R12 in `research.md` with any difference.
- [ ] T029 [P] Establish how artists open the Workfiles tool in Flame
      (`client/ayon_flame/api/menu.py` has no entry; plan Open item 2).
      Record the answer in `research.md`. If a new menu control is required,
      stop and report: it is a spec change (spec scopes out new GUI controls).

### Phase A2 — Foundational (blocks US4, US5, US6)

- [x] T030 Add `is_batch_tab()` to `client/ayon_flame/api/workio.py` (reads
      `flame.get_current_tab()`, same normalisation and fail-closed behaviour
      as the existing predicate) and make
      `client/ayon_flame/api/workfile.py` `_is_batch_tab`/`BATCH_TAB`
      re-export it, so exactly one predicate exists and `workio` never imports
      `workfile` (plan D6; FR-003).

### Phase A3 — US4: Save the current Batch from the Workfiles widget (P1, MVP)

**Goal**: Save in the Workfiles tool writes the active Batch as consolidated
JSON at the Core-allocated path.
**Independent test**: quickstart steps 1–2 (save → v1, save → v2 `.json`, reopen).

- [x] T031 [US4] Implement the Batch branch of `save_file(filepath)` in
      `client/ayon_flame/api/workio.py`: on the Batch tab call
      `batch_utils.save_batch_as_consolidated_json(get_current_batch(), tmp)`
      with `tmp` a sibling temp file in the destination directory, then
      `os.replace(tmp, filepath)`; on any error delete `tmp`, leave
      `filepath` untouched, and raise `RuntimeError` naming the cause (no
      active Batch, unreadable tab, write error). Do not edit `batch_utils.py`
      (FR-A01, FR-A03, FR-A04, plan D6).
- [x] T032 [US4] In `client/ayon_flame/api/workfile.py`
      `FlameBatchWorkfileHost.save_workfile`, delegate to `workio.save_file`
      (remove the direct `batch_utils` call) and keep `_remember_workfile`;
      keep `get_workfile_extensions()` returning `[".json"]` (FR-A01 single
      save path; `save_next_version` needs the extension, R12.1).
- [x] T033 [US4] In `client/ayon_flame/api/pipeline.py` add `IWorkfileHost`
      to `FlameHost` and delegate `save_workfile`, `open_workfile`,
      `get_current_workfile`, `workfile_has_unsaved_changes`,
      `get_workfile_extensions` to `get_flame_workfile_host()` evaluated at
      call time; do not override deprecated aliases; leave `install()` plugin
      registrations unchanged (plan D7; FR-A06). **Subject to the ship gate.**
- [x] T034 [P] [US4] Export any new public names from
      `client/ayon_flame/api/__init__.py` in the existing export style.
- [ ] T035 [US4] Manual in-host validation (reviewer): quickstart steps 1–2
      and the US4 acceptance scenarios (1–5) on Flame 2026; record observed
      file names/versions and the no-partial-file failure case in `research.md`.
      Also confirm saving does not corrupt the Batch metadata Note node
      (plan D11).

### Phase A4 — US5: Other tabs behave as before (P2)

**Goal**: Non-Batch save is explicitly unsupported and writes nothing.
**Independent test**: quickstart step 6.

- [x] T036 [US5] Verify in `client/ayon_flame/api/workio.py` that the
      non-Batch path of `save_file` still raises `NotImplementedError` and
      that an unreadable tab never selects the Batch branch (FR-A05, edge
      case "current tab cannot be read"); adjust only if T031 regressed it.
- [ ] T037 [US5] Manual in-host validation (reviewer): trigger a save on a
      Timeline/Media Panel tab and confirm no file is written (SC-A05).

### Phase A5 — US6: Publish requires a saved Batch workfile (P2)

**Goal**: Publishing a never-saved Batch fails with a clear validator message
whose Repair saves the next version; saved contexts and all other publishes
are unchanged.
**Independent test**: quickstart steps 3–5.
**Depends on**: T027 (gate), T030–T033.

- [x] T038 [P] [US6] Create
      `client/ayon_flame/plugins/publish/collect_current_file.py`:
      `ContextPlugin`, `order = pyblish.api.CollectorOrder - 0.5`,
      `hosts = ["flame"]`; always set `context.data["currentFile"]` to the
      latest existing workfile path for the current context on the Batch tab
      (from `registered_host().list_workfiles(...)`, `available` only), else
      `None` (plan D8; FR-A10).
- [x] T039 [US6] Implement the D9 mechanism selected in T027 so Core's
      `ValidateCurrentSaveFile` and `CollectSceneVersion` are inactive for the
      `flame` host only, in `client/ayon_flame/api/pipeline.py` (`install()`
      and the matching undo in `uninstall()`); leave
      `plugins/publish/collect_batch_version.py` byte-identical (FR-A10–A12).
- [x] T040 [US6] Create
      `client/ayon_flame/plugins/publish/validate_batch_workfile_saved.py`:
      `ContextPlugin`, `hosts = ["flame"]`,
      `order = pyblish.api.ValidatorOrder - 0.2`,
      `actions = [RepairContextAction]` (from `ayon_core.pipeline.publish`),
      applying only when an instance with `flame_context == "FlameMenuBatch"`
      is in the context. Fail with `PublishValidationError` (title "Batch has
      no saved workfile") when `host.list_workfiles(project, folder, task)` is
      empty; message names the Batch group, why it matters, and both ways out
      (Workfiles tool or Repair). A missing folder/task context or a Core/API
      failure raises its own clear error, never passes (FR-A13, FR-A14,
      FR-A18, plan D10).
- [x] T041 [US6] Add `@classmethod repair(cls, context)` to
      `validate_batch_workfile_saved.py` calling
      `ayon_core.pipeline.workfile.save_next_version()`; surface any
      exception (including the missing folder/task `TypeError`, R12.1) as a
      cause-naming error and keep the validator failing; never compute a
      version or path in the addon (FR-A15–A17, FR-A02).
- [ ] T042 [US6] Manual in-host validation (reviewer): quickstart steps 3–5 —
      never-saved Batch fails with the message; Repair creates the next
      `.json` version without opening the Workfiles tool and the validator
      passes; restart Flame and publish again (passes); Batch publish
      `context.data["version"]`/iteration identical before vs after (SC-A06);
      Timeline/Media Panel publishes show no new failure; record results in
      `research.md`.

### Phase A6 — Static checks and closure (no story label)

- [x] T043 Run `ruff check .` and `ruff format --check .`; fix only the files
      this amendment changed (pre-existing `agentic_setup.py:141` `E501` stays
      per DV-5).
- [x] T044 [P] Run `python3 create_package.py --skip-zip` and confirm success.
- [x] T045 [P] Confirm `client/ayon_flame/addon.py` still imports in a plain
      interpreter without the `flame` module (NFR-001, FR-A07).
- [x] T046 Verify with `git diff --stat` that the only publish-side changes
      are the FR-A12 list (`collect_current_file.py`,
      `validate_batch_workfile_saved.py`, host-scoped Core-plugin handling in
      `api/pipeline.py`); no `server/`, `package.py`, or settings changes.
- [x] T047 Close out the docs: update the spec "Implementation Status",
      resolve DV-1, add a deviation entry for the atomic-write wrapper (plan
      D6) and for any T027 fallback used, and tick T011/T012/T015 as
      superseded in this file.

### Amendment 1 — implementation results (2026-10-01)

- **T027 done** — mechanism is `pyblish.api.register_discovery_filter`
  (research R13). Implemented in `api/pipeline.py` (`install()` registers,
  `uninstall()` removes). Verified with throwaway harnesses (`/tmp`, not
  committed): drops only the two Core plugins, matches by class name **and**
  defining-file stem, leaves same-named plugins from other files, works with
  both pyblish's and Core's discovery (`__file__` vs `__module__` forms).
- **T028 done** — on tag `1.8.0`: `save_next_version` (+ export),
  `IWorkfileHost.list_workfiles` / `save_workfile_with_context` /
  `get_workfile_extensions`, `RepairContextAction`, `PublishValidationError`,
  Core's two plugins and the discovery-filter hook in
  `publish_plugins_discover` all exist.
- **T029 NOT done — blocks the user-facing story.** `api/menu.py` offers
  Create / Publish / Load (and universal menus) but **no Workfiles entry**,
  and nothing else in `client/ayon_flame` opens the tool. The implementation
  makes the Workfiles tool *work* with Flame (host is an `IWorkfileHost`), but
  an artist has no Flame-side control to open it. The spec scopes new GUI
  controls out, so adding one is a **spec decision** for the user, not done
  here. Until decided, T035 (manual save) cannot be performed from inside
  Flame by menu.
- **T030–T034 done** — `workio.is_batch_tab()`/`_is_batch_tab`/`BATCH_TAB`
  now live in `api/workio.py`; `workfile.py` imports them (one predicate, no
  cycle). `workio.save_file` implements the atomic Batch save.
  `FlameBatchWorkfileHost.save_workfile` delegates to it (the now-unused
  `_get_active_batch` was removed). `FlameHost` is an `IWorkfileHost` and
  delegates to `get_flame_workfile_host()` per call. Exports added
  (`is_batch_tab`, `context_has_batch_instance`, `list_batch_workfiles`).
  Verified with a stubbed harness: save → file written, parent dir created;
  write failure → existing file untouched and no temp file; failure on a new
  path → nothing created; no active Batch → clear error and no file; tab
  `Timeline`/`None`/`""`/exception → `NotImplementedError`, no file; empty
  path → error.
- **T036 done** (via the same harness): non-Batch and unreadable tab never
  select the Batch branch.
- **T038–T041 done** — `plugins/publish/collect_current_file.py`,
  `plugins/publish/validate_batch_workfile_saved.py` (+ `repair`).
  Helpers `context_has_batch_instance` / `list_batch_workfiles` are in
  `api/workfile.py`; `list_batch_workfiles` always lists `.json` workfiles via
  `FlameBatchWorkfileHost`, so the answer does not depend on the active tab.
  `repair` additionally requires the Batch tab (clear message otherwise).
  Stub-verified: no Batch instance → no-op; workfile exists → pass; none →
  `Batch has no saved workfile` naming the group; lookup error → its own
  error, never a pass; repair success → validator then passes; repair error →
  surfaced, nothing saved; collector picks the highest-version *available*
  file, `None` otherwise, key always present.
- **T043** — `ruff check .`: only the pre-existing `agentic_setup.py:141`
  E501 (DV-5). `ruff format --check .` was **already failing on 62 files at
  HEAD** (CI runs only `ruff check`); existing files were deliberately not
  reformatted to avoid noisy diffs, and the two new plugin files are
  format-clean.
- **T044** — `python3 create_package.py --skip-zip` succeeds.
- **T045** — static: `addon.py` imports only `os`, `ayon_core.addon` and
  `.version` and is byte-identical to HEAD. A live import could not run
  (`ayon_api`/`flame` are not installed in this session).
- **T046** — `git diff`: changed `api/__init__.py`, `api/pipeline.py`,
  `api/workfile.py`, `api/workio.py`; new `collect_current_file.py` and
  `validate_batch_workfile_saved.py`. `addon.py`, `startup/`, `server/`,
  `package.py` and `collect_batch_version.py` are unchanged — the publish-side
  changes are exactly the FR-A12 list.
- **Still open (reviewer, in Flame — cannot run from an agent session):**
  T035, T037, T042, and the original T003, T019-style in-host items
  T021–T026. T015 stays open: its in-host check is covered by T042.

### Amendment dependencies

```text
T027 ──► T039
T028, T029 ── independent checks (T029 may block scope)
T030 ──► T031 ──► T032 ──► T033 ──► T035
T031 ──► T036 ──► T037
T033 + T038 + T039 + T040 + T041 ── ship together (ship gate)
T038 ──► T040 ──► T041 ──► T042
T043..T046 ──► T047
```

**Parallel opportunities**: T028 ∥ T029 ∥ T027 (separate investigations);
T034 ∥ T032; T038 ∥ T040 (different new files; T041 follows T040); T044 ∥ T045.

**MVP**: US4 (T030–T035) delivers Save, but per the ship gate it cannot ship
without the US6 publish-side tasks (T038–T041); the smallest *releasable*
increment is therefore A1 + A2 + US4 + the US6 implementation tasks.

---

## Dependencies

```text
T001 ──► T011 ──► T012, T013, T014, T015
T002 ──► T004 ──► T007 ──► T008 ──► T009, T011
T003 ──► T005 ──► T008
T006 ──► T007, T008
T008 ──► T016
T017, T018, T019, T020 ── independent static checks
T021..T026 ── in-host, require T009/T011 (per D1)
```

## Out of scope (explicitly deferred)

- Any change to Flame's own publish plugins, publish registration, collected
  data, or version/iteration logic — including working around D1's
  `ValidateCurrentSaveFile` activation by editing plugins or settings.
- Server settings, settings overrides, and `_convert_*` migrations.
- Removing the deprecated `IWorkfileHost` aliases.
- Workfile support for Timeline, Media Panel, Main Menu, BFX, or other tabs.
- New GUI controls or autosave behaviour.

## Deviation record

| # | Deviation | Reason | Evidence |
| --- | --- | --- | --- |
| DV-1 | **RESOLVED by Amendment 1 (T033, T038–T041).** Was: **T011/T012/T015 not performed** — `IWorkfileHost` was **not** wired into `FlameHost` despite the D1b decision. | Wiring breaks every Flame publish without a new host collector, and adding that collector changes `context.data["version"]` and blocks non-Batch publishing — violating the feature's "no publish/version change yet" constraint. | `research.md` R10.1–R10.3; `plan.md` D1 flip checklist |
| DV-2 | `FlameWorkfileHost.get_current_workfile()` **catches `NotImplementedError`** from `workio.current_file()` and returns AYON's session record (or `None`) instead of propagating. | The plan required "never raise", because the return value feeds core publish validation once wired. | `api/workfile.py`; T010 |
| DV-3 | Batch workfile paths are tracked in a **module-level session map** (`_WORKFILE_PATHS`) rather than persisted in the Batch metadata Note node. | Writing into the Note node would leak into instance data published by `CreateBatchWorkfile` (`data_to_store()`), changing collected publish data. Persistence is a follow-up concern. | `api/workfile.py`; `plugins/create/create_batch.py` |
| DV-4 | Module tested with a **throwaway stubbed harness** in `/tmp`, not committed. | The repository has no test framework and must not gain one. | `research.md` R11 |
| DV-5 | Pre-existing repo-wide `ruff check .` `E501` in unmodified `agentic_setup.py:141` left unfixed. | Outside this feature's scope; unrelated file. | T017 |
| DV-6 | `workio.save_file` wraps the existing `batch_utils.save_batch_as_consolidated_json` with a temp-sibling + `os.replace` instead of editing the helper. | The helper writes the final path directly (partial file on failure, FR-A04) and must stay unchanged (FR-005). | `api/workio.py`; plan D6; research R12.6 |
| DV-7 | Existing files with pre-existing `ruff format` drift were not reformatted. | `ruff format --check .` already fails on 62 files at HEAD; reformatting would bury the change in noise. New files are format-clean. | T043 |
| DV-8 | Amendment 1 was verified with throwaway stubbed harnesses in `/tmp` (not committed) and static checks only. | No Flame, `ayon_api` or full `ayon_core` in the agent session; no test framework may be added. | T027, T030–T041 results |
| DV-9 | T029 not completed: no way to open the Workfiles tool from Flame's menus. | Adding a menu control is outside the spec's scope (new GUI controls); needs a user decision. | T029 result above |
