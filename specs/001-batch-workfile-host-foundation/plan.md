# Implementation Plan: Flame Batch Workfile Host Foundation

**Branch**: `Batch-workfile-host-foundation` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-batch-workfile-host-foundation/spec.md`

## Summary

Add an `IWorkfileHost` implementation for Flame's Batch page by introducing a
small, host-runtime-only workfile seam in `client/ayon_flame/api/`. A
tab-aware selector reads `flame.get_current_tab()` (Batch page value:
`"Batch"`), returns the Batch implementation when Batch is active, and
delegates Batch read/write to the existing `api/workio.py` seam and
`api/batch_utils.py` consolidated-JSON helpers. The capability is wired into
`FlameHost` in `api/pipeline.py`, which is already the object passed to
`install_host(FlameHost())` from `startup/AYON_in_flame.py`; `addon.py` stays
launcher-safe. Publish plugins, publish registration, and Flame native
version/iteration behaviour are untouched — with one **explicitly flagged
consequence** (see Decision D1) that requires a design choice before coding.

## Technical Context

**Language/Version**: Python 3.9+ (host runtime); Flame's embedded Python API
**Primary Dependencies**: `ayon_core` (`ayon_core.host.HostBase`,
`ayon_core.host.IWorkfileHost`, `ayon_core.lib.Logger`), Flame `flame` Python
API, `pyblish` (existing registrations only)
**Storage**: Existing consolidated-JSON Batch workfile format
(`api/batch_utils.save_batch_as_consolidated_json` /
`load_batch_from_consolidated_json`); no new format
**Testing**: No test framework in this repository. Validation =
`ruff check .`, `ruff format --check .`,
`python create_package.py --skip-zip`, plus documented manual Flame runs
**Target Platform**: Autodesk Flame 2026–2027 on macOS/Linux (no Windows)
**Project Type**: AYON host addon (client host integration + server settings)
**Performance Goals**: Negligible; host selection is a constant-time tab
lookup; Batch export/load is bounded by Flame's own save/load
**Constraints**: `addon.py` must stay importable without the `flame` module;
Flame tab access stays in `api/`/`startup/`; no settings rename or conversion;
Flame's own publish/version code unchanged
**Scale/Scope**: One new client module plus small edits to `api/__init__.py`
and `api/pipeline.py`; no server changes

### Verified interface surface (`ayon_core` local checkout)

`IWorkfileHost` (`host/interfaces/workfiles.py:830`) has exactly **three**
abstract methods — `save_workfile(dst_path=None)`, `open_workfile(filepath)`,
`get_current_workfile()` — and two useful defaults —
`workfile_has_unsaved_changes()` → `None`, `get_workfile_extensions()` → `[]`.
Context/template/path/entity handling, `AYON_WORKDIR` management, events, and
`list_workfiles`/`list_published_workfiles`/`copy_workfile*` are all
implemented by the interface and must **not** be re-implemented. Deprecated
aliases (`file_extensions`, `save_file`, `open_file`, `current_file`,
`has_unsaved_changes`) exist but must not be overridden. There is no
`work_root` in the interface, and **no separate workfile-host registry**:
core detects the host via `isinstance(host, IWorkfileHost)` on
`registered_host()`, so the capability must be mixed into `FlameHost` itself.

### Verified Flame API facts

- `flame.get_current_tab() -> str` exists and is unchanged in the published
  Flame API stubs for **2024.2** and **2026.2**.
- `flame.set_current_tab(tab)` documents the tab set as
  `MediaHub, Conform, Timeline, Effects, Batch, Tools`; the Batch page value
  is therefore **`"Batch"`**.
- `flame.go_to()` is deprecated — do not use it.
- `flame.batch` is a `PyBatch`; `PyBatch` exposes `save_setup(path)`,
  `load_setup(path)`, `iterate()`, `batch_iterations`, `name`, `nodes`, etc.
- **`PyBatch` has no setup-path attribute** — Flame does not record where a
  Batch Group was last saved, so a native "current workfile path" does not
  exist for Batch.

## Constitution Check

*GATE: must pass before Phase 0 research and re-checked after Phase 1 design.*

| Gate | Status | Notes |
| --- | --- | --- |
| Reuse shared helpers; no parallel formats | PASS | Reuses `api/workio.py`, `api/batch_utils.py`; JSON format unchanged |
| Preserve pipeline contracts (identifiers/families/hosts) | PASS | No identifier, family, or host-name change |
| Keep client settings aligned with server models | PASS | No settings change; no `_convert_*` needed |
| Preserve compatibility imports per `package.py` (`core >=1.8.0`) | PASS | Interface read from the local core checkout; re-verify against installed core |
| Keep GUI/headless boundaries (Article 7) | PASS | Tab access stays in `api/`; `addon.py` untouched |
| Do not add a test framework where none exists | PASS | Manual in-host validation only |
| Survey first; stop if feature exists (Article 10) | PASS | No `IWorkfileHost`/workfile host exists today |

**GATE NOTE**: the constitution gate passes. Decision **D1** is resolved above:
D1b was requested but is blocked by research R10, so this milestone ships the
D1a scope (the capability module) and the `FlameHost` wiring is deferred.

## Project Structure

### Documentation (this feature)

```text
specs/001-batch-workfile-host-foundation/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 findings (working artifact)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
client/ayon_flame/
├── addon.py                     # UNCHANGED — stays launcher-safe
├── api/
│   ├── __init__.py              # export the new workfile-host seam
│   ├── workfile.py              # NEW — IWorkfileHost impls + tab selector
│   ├── workio.py                # UNCHANGED surface; reused
│   ├── batch_utils.py           # UNCHANGED; reused
│   └── pipeline.py              # FlameHost gains the workfile capability
└── startup/
    └── AYON_in_flame.py         # UNCHANGED install path (install_host)

plugins/                         # UNCHANGED (publish/create/load)
server/                          # UNCHANGED (settings)
```

**Structure Decision**: add one new module, `client/ayon_flame/api/workfile.py`,
inside the existing host-API seam. It is the only place that reads
`flame.get_current_tab()` for workfile selection. `FlameHost` in
`api/pipeline.py` gains `IWorkfileHost` and delegates the three abstract
methods to the tab-selected implementation, so the existing
`install_host(FlameHost())` in `startup/AYON_in_flame.py` remains the single
installation point and `addon.py` is untouched.

## Phase 0 — Research

Full findings in [research.md](./research.md). Headlines:

1. No workfile host exists yet (grep-verified).
2. `api/workio.py` is a thin seam: `work_root(session)` returns
   `session["AYON_WORKDIR"]`; `file_extensions()` returns `[".otoc"]`;
   `save/open/current/unsaved` raise `NotImplementedError`.
3. Batch serialization already exists in `api/batch_utils.py` (consolidated
   JSON with the `__b64__:` binary convention).
4. Selection must use `flame.get_current_tab()`; `CTX.context`
   (`"FlameMenuBatch"`) is **not** the selection mechanism and stays untouched.
5. `IWorkfileHost` verification is in Technical Context above.
6. Flame API verification (2024.2 + 2026.2 stubs) is in Technical Context
   above; 2027 must be confirmed in-host.
7. **HIGH RISK / D1**: enabling `IWorkfileHost` flips ayon-core's
   `ValidateCurrentSaveFile` publish validator from "skip" to "enforce" for
   Flame (`plugins/publish/validate_file_saved.py:45`).

## Phase 1 — Design

### Decisions

**D1 — RESOLVED (2026-09-23): D1b requested, but blocked by research R10.**
**Implementation status: the D1b decision was taken; wiring `FlameHost` was
then found to be unsafe to ship in this milestone and is deliberately NOT
applied (see below). `api/workfile.py` is complete and verified and is
identical under D1a/D1b; flipping to D1b is a two-file change.**

Decision taken: **D1b** — wire `IWorkfileHost` into `FlameHost` now.

Blocker discovered while implementing (research R8/R10): the blast radius of
wiring is larger than D1b assumed. Making `FlameHost` an `IWorkfileHost`:

1. activates ayon-core `ValidateCurrentSaveFile`, which reads
   `context.data["currentFile"]` with `[]` (KeyError, not `.get()`). That key
   is populated only by a **host-specific collector plugin**; Flame has none,
   so **every** Flame publish would fail unless a new collector is added;
2. adding that collector turns on ayon-core `CollectSceneVersion`
   (`order = CollectorOrder`, `hosts = ["*"]`), which parses a version out of
   the workfile filename and **raises `PublishError` when the filename has no
   `v\d` token** — and which competes, at the same `order`, with Flame's own
   `CollectBatchVersion` for `context.data["version"]` → **version behaviour
   change**;
3. blocks non-Batch publishing entirely: `FlameWorkfileHost` cannot save
   (delegates to `workio.save_file`, which raises `NotImplementedError`), so
   `get_current_workfile()` is `None`, so `ValidateCurrentSaveFile` fails with
   "Workfile is not saved" and the artist has no way to save.

Points 1–3 mean D1b cannot be delivered in this milestone without violating
the feature's own constraint "do not change publish/version behaviour yet".

Therefore this milestone delivers the **D1a scope** (the capability module),
which is byte-identical under both options, and defers the wiring.

**Ready flip for D1b (when timeline workfile save exists and version
collection is settled)**:
1. `api/pipeline.py`: add `IWorkfileHost` to `FlameHost`'s bases and implement
   `save_workfile` / `open_workfile` / `get_current_workfile` /
   `workfile_has_unsaved_changes` / `get_workfile_extensions` by delegating to
   `get_flame_workfile_host()`.
2. `plugins/publish/collect_current_file.py`: new collector,
   `order = pyblish.api.CollectorOrder - 0.5`, `hosts = ["flame"]`, mirroring
   `ayon-hiero`'s `CollectCurrentFile`:
   `context.data["currentFile"] = registered_host().get_current_workfile()`.
3. Verify R10 items 1–3 in-host and confirm `context.data["version"]` is
   unchanged for Batch publishes.

### D1(a/b) — original analysis (kept for the record)

**D1 — `ValidateCurrentSaveFile` activation (RESOLVED, see above).**

Making `FlameHost` an `IWorkfileHost` is the only supported way to expose the
workfile host (core uses `isinstance`, not a registry). That same `isinstance`
check turns on ayon-core's `ValidateCurrentSaveFile` context validator for
**every** Flame publish — not just Batch. Two viable paths, to be chosen with
the user before T0xx that edits `api/pipeline.py`:

- **D1a (recommended, no publish change)**: keep the *capability* landing in
  `api/workfile.py` (pure, testable, not yet mixed in) as this milestone's
  deliverable, and mix `IWorkfileHost` into `FlameHost` only in the follow-up
  milestone that also settles `currentFile`/`currentFile` semantics for
  Timeline and Batch. This satisfies "Do not change publish/version behavior
  yet" literally, at the cost of the host not being *active* through the
  workfiles tool in this milestone.
- **D1b (active host now)**: mix `IWorkfileHost` into `FlameHost` immediately
  and accept the validator becoming active, requiring `get_current_workfile()`
  to return a stable, non-empty AYON-known path (Batch: the AYON workfile path
  recorded for the batch; non-Batch: the existing
  `{AYON_WORKDIR}/{project}.workfile` convention from
  `plugins/create/create_workfile.py`). This **does** change publish behaviour
  for Flame and therefore conflicts with spec FR-009 unless the user
  explicitly accepts it.

**Everything below assumes D1a vs D1b only affects *when* `FlameHost` gains the
mixin** — `api/workfile.py` is designed identically either way, and was
implemented as such.

**D2 — Tab predicate.** `_is_batch_tab(tab) -> bool` compares the normalized
result of `flame.get_current_tab()` to `"Batch"`. `None`, unexpected strings,
and exceptions → `False` ("not Batch"), i.e. fail closed to the default host.
Swift pessimism is intentional: a wrong "Batch" answer would operate on the
wrong workfile.

**D3 — Batch workfile path.** Batch has no native path (verified). The Batch
host therefore:
- `save_workfile(dst_path)`: when `dst_path` is provided (core always passes
  one from `save_workfile_with_context`) → write via
  `batch_utils.save_batch_as_consolidated_json(flame.batch, dst_path)`; if
  `None`, raise a clear `RuntimeError` (never a silent no-op).
- `open_workfile(filepath)`: `batch_utils.load_batch_from_consolidated_json(filepath)`.
- `get_current_workfile()`: return the AYON-known path when resolvable for the
  active batch group, else `None`. Never invent a path.
- `workfile_has_unsaved_changes()`: return `None` (Flame cannot tell) rather
  than raising.
- `get_workfile_extensions()`: `[".json"]` (the batch consolidated format);
  `api/workio.file_extensions()` keeps `[".otoc"]` for the native/non-Batch
  path. Documented as a deliberate, format-driven difference.

**D4 — Missing Batch group.** A Batch tab with no active Batch Group must not
silently save/open a different group. Reuse `get_current_batch()` and surface
its explicit `RuntimeError`, or a clearer Batch-specific error, at the point
of use.

**D5 — Context-change ordering.** Keep
`change_context_before_workfile_open = True` (the interface default) unless
in-host validation shows the Batch metadata Note node (read by
`FlameHost.get_current_context`) disagrees with the folder/task passed by the
workfiles tool. Record the observed behaviour; do not change it speculatively.

### Component design

1. **`api/workfile.py` (new)**
   - `FlameWorkfileHost(IWorkfileHost)` — default/non-Batch host; delegates to
     `api/workio.py` (`work_root` kept as an extra convenience method matching
     nuke/resolve, extensions from `workio.file_extensions()`).
   - `FlameBatchWorkfileHost(IWorkfileHost)` — Batch-page host implementing
     D3/D4 on top of `batch_utils`.
   - `get_flame_workfile_host()` — reads `flame.get_current_tab()` and returns
     the Batch host iff `_is_batch_tab(...)`, else the default host.
   - `_is_batch_tab(tab)` — the single centralized predicate.
   - `flame` is imported in this module; the module is therefore imported only
     from the host-runtime path.

2. **`api/pipeline.py` (`FlameHost`)** — changes gated by D1:
   - Optionally add `IWorkfileHost` to the bases and implement
     `save_workfile`/`open_workfile`/`get_current_workfile` (plus
     `workfile_has_unsaved_changes`/`get_workfile_extensions`) by delegating
     to `get_flame_workfile_host()`.
   - `install()`/`uninstall()` and all registered plugin paths stay identical.

3. **`api/__init__.py`** — re-export the new public names consistently with the
   existing export style.

4. **`startup/AYON_in_flame.py`** — no change expected (already installs
   `FlameHost()`).

### Contracts (internal seam)

```python
class FlameBatchWorkfileHost(IWorkfileHost):
    def save_workfile(self, dst_path: str | None = None) -> None: ...
    def open_workfile(self, filepath: str) -> None: ...
    def get_current_workfile(self) -> str | None: ...
    def workfile_has_unsaved_changes(self) -> bool | None: ...   # -> None
    def get_workfile_extensions(self) -> list[str]: ...          # -> [".json"]

def _is_batch_tab(tab: object) -> bool: ...      # tab == "Batch"
def get_flame_workfile_host() -> IWorkfileHost: ...
```

Behavioural contract:
- `save_workfile` produces exactly the existing consolidated JSON;
  `open_workfile` consumes exactly that format.
- Selection returns the Batch host iff `_is_batch_tab(flame.get_current_tab())`.
- No publish plugin, plugin path, or version/iteration code is modified.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| **D1**: `IWorkfileHost` activates core's `ValidateCurrentSaveFile` **and** `CollectSceneVersion`, and needs a new host collector | New hard publish failures and changed `context.data["version"]`; conflicts with FR-009 | D1b requested but blocked (research R10); wiring deferred, flip checklist recorded in D1. `api/workfile.py` shipped unwired |
| Non-Batch Flame has no native workfile path (`workio.current_file()` raises) | If D1b is chosen, Timeline publishes could fail validation | D3 `get_current_workfile()` must return a stable AYON-known path or nothing; never raise |
| `flame.get_current_tab()` value differs or raises on 2027 | Wrong/no host selection | Centralized `_is_batch_tab`, fail closed; verify on 2026 **and** 2027 in-host |
| Batch group absent on the Batch tab | Silent wrong-file operation | D4 explicit error from `get_current_batch()` |
| `load_batch_from_consolidated_json` loads *into* the current batch group | Opening a workfile may merge rather than replace | Document expected semantics; verify in-host; do not reimplement load |
| `CTX.context`-based context reading interacts with opened batch | Context mismatch in publish | D5: observe `change_context_before_workfile_open` behaviour in-host; no speculative change |
| Deprecated aliases overridden by mistake | Double-delegation / subtle breakage | Do not override `file_extensions`/`save_file`/`open_file`/`current_file`/`has_unsaved_changes` |

## Complexity Tracking

No constitution violations. One blocking design decision (D1) is tracked
above rather than as complexity.

## Verification Plan

1. `ruff check .`
2. `ruff format --check .`
3. `python create_package.py --skip-zip`
4. Import `client/ayon_flame/addon.py` in a plain interpreter **without** the
   `flame` module — must succeed.
5. In Flame 2026: open the Batch page, `flame.get_current_tab()` returns
   `"Batch"`, and `get_flame_workfile_host()` returns the Batch host.
6. In Flame 2026: save a Batch group through the host → byte-shape check that
   the output equals `save_batch_as_consolidated_json` output; open it back →
   Batch group restored.
7. In Flame 2026: on Timeline/Media Panel, confirm the Batch host is **not**
   selected.
8. Repeat 5–7 on Flame 2027.
9. Run a Flame publish on a Batch tab and on a non-Batch tab; record whether
   `ValidateCurrentSaveFile` runs, and confirm the D1 decision holds.
10. Confirm no change to Flame publish plugin registration, `CTX.context`,
    creators, loaders, or Batch iteration/version behaviour.
