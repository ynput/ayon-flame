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

- [ ] **T011 [GATED:D1] Add `IWorkfileHost` to `FlameHost`** — **DEFERRED, not
      performed.** Blocked by R10; applying it without a Flame
      `collect_current_file` collector breaks every Flame publish, and adding
      that collector changes `context.data["version"]` and blocks non-Batch
      publishing. Exact flip steps recorded in `plan.md` D1. This is the
      deliberate deviation from the D1b instruction.
- [ ] **T012 [GATED:D1] Confirm `startup/AYON_in_flame.py` needs no change** —
      **Deferred with T011.** Read and confirmed the file already calls
      `install_host(FlameHost())` in each `get_*_custom_ui_actions` hook, so
      no change would be required once T011 is applied.
- [ ] **T013 [P][GATED:D1] Confirm `addon.py` is unchanged** — **Confirmed
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
- [ ] **T015 [GATED:D1] Verify `ValidateCurrentSaveFile` behaviour** —
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
- [ ] **T019 `python create_package.py --skip-zip`** — *Not run*: it would
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
| DV-1 | **T011/T012/T015 not performed** — `IWorkfileHost` was **not** wired into `FlameHost` despite the D1b decision. | Wiring breaks every Flame publish without a new host collector, and adding that collector changes `context.data["version"]` and blocks non-Batch publishing — violating the feature's "no publish/version change yet" constraint. | `research.md` R10.1–R10.3; `plan.md` D1 flip checklist |
| DV-2 | `FlameWorkfileHost.get_current_workfile()` **catches `NotImplementedError`** from `workio.current_file()` and returns AYON's session record (or `None`) instead of propagating. | The plan required "never raise", because the return value feeds core publish validation once wired. | `api/workfile.py`; T010 |
| DV-3 | Batch workfile paths are tracked in a **module-level session map** (`_WORKFILE_PATHS`) rather than persisted in the Batch metadata Note node. | Writing into the Note node would leak into instance data published by `CreateBatchWorkfile` (`data_to_store()`), changing collected publish data. Persistence is a follow-up concern. | `api/workfile.py`; `plugins/create/create_batch.py` |
| DV-4 | Module tested with a **throwaway stubbed harness** in `/tmp`, not committed. | The repository has no test framework and must not gain one. | `research.md` R11 |
| DV-5 | Pre-existing repo-wide `ruff check .` `E501` in unmodified `agentic_setup.py:141` left unfixed. | Outside this feature's scope; unrelated file. | T017 |
