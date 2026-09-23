# Phase 0 Research: Flame Batch Workfile Host Foundation

**Note**: Working artifact (regenerate with `/speckit.plan` if needed; not
committed per `SPEC_KIT.md`).

## R1 — Does a workfile host already exist?

- **Finding**: No. Repo-wide grep for `IWorkfileHost` / workfile-host
  registration returns only a comment in
  `client/ayon_flame/api/pipeline.py` ("Flame can be used as a multi-workfile
  host"). Constitution Article 10 survey gate is satisfied: this is new work,
  not an existing feature.
- **Decision**: Add the first workfile host for this repo.

## R2 — What does `api/workio.py` provide today?

- **Finding** (`client/ayon_flame/api/workio.py`):
  - `file_extensions()` → `[".otoc"]`
  - `work_root(session)` → `os.path.normpath(session["AYON_WORKDIR"])`
  - `has_unsaved_changes()`, `save_file()`, `open_file()`, `current_file()`
    → all raise `NotImplementedError("Flame uses native workfile management")`
- **Decision**: Keep `api/workio.py` as the single workfile API seam. The new
  host delegates to it for extensions/work root and layers the Batch
  consolidated-JSON behaviour on top, leaving publish/version callers of the
  `NotImplementedError` methods untouched.

## R3 — What is the consolidated-JSON batch format?

- **Finding** (`client/ayon_flame/api/batch_utils.py`):
  - `save_batch_as_consolidated_json(batch, filepath, temporary_folder=None)`
    saves the native batch setup to a temp dir and writes one JSON dict keyed
    by relative path; binary files are base64-encoded with `"__b64__:"`.
  - `load_batch_from_consolidated_json(filepath, name=None, temporary_folder=None)`
    reconstitutes files, loads the `.batch` setup, restores the group name.
  - Helpers: `get_current_batch()`, `get_batch_from_workspace(name, workspace)`,
    `get_metadata_node(batch=None, create=False)`,
    `read_node_metadata`/`write_node_metadata`/`clear_node_metadata`,
    `edit_batch_group_content`, `create_batch`, `update_batch`.
- **Decision**: Reuse these functions verbatim; add no new serialization.

## R4 — How is the Batch context identified today?

- **Finding**: `CTX.context` (singleton in `api/lib.py`) is set to
  `"FlameMenuBatch"` in `scripts/publish_current_batch_content.py` and read in
  `api/pipeline.py:get_current_context`, `plugins/create/create_batch.py`,
  `create_batch_render.py`, and publish collectors.
- **Decision**: `CTX.context` is **not** the selection mechanism for this
  feature (spec FR-002 requires `flame.get_current_tab()`). `CTX.context` is
  left untouched so existing publish/creator behaviour does not change.

## R5 — Where can the host be installed safely?

- **Finding**: `startup/AYON_in_flame.py` calls `install_host(FlameHost())` in
  each `get_*_custom_ui_actions` hook. `FlameHost` (`api/pipeline.py`) already
  subclasses `HostBase, ILoadHost, IPublishHost`.
  `client/ayon_flame/addon.py` imports no Flame API.
- **Decision**: Add `IWorkfileHost` to `FlameHost`'s bases; the existing
  `install_host(FlameHost())` call remains the only installation point.

## R6 — Exact `IWorkfileHost` surface (verified in `ayon-core`)

Verified against `/Users/jakub/CODE/__YNPUT/ayon-core/client/ayon_core`
(`host/interfaces/workfiles.py`, `host/abstract.py`, `host/host.py`):

```python
class IWorkfileHost(AbstractHost):                     # workfiles.py:830
    change_context_before_workfile_open = True         # class attribute

    @abstractmethod
    def save_workfile(self, dst_path: Optional[str] = None) -> None: ...

    @abstractmethod
    def open_workfile(self, filepath: str) -> None: ...

    @abstractmethod
    def get_current_workfile(self) -> Optional[str]: ...

    def workfile_has_unsaved_changes(self) -> Optional[bool]:  # default None
        return None

    def get_workfile_extensions(self) -> list[str]:            # default []
        return []
```

- **Only three methods are abstract**: `save_workfile`, `open_workfile`,
  `get_current_workfile`. Everything else has a working base implementation.
- **Core-provided (do not re-implement)**: `save_workfile_with_context`,
  `open_workfile_with_context`, `list_workfiles`,
  `list_published_workfiles`, `copy_workfile`,
  `copy_workfile_representation`, and all `_before_*`/`_after_*` hooks.
  These drive template/path resolution, `AYON_WORKDIR`, workfile entities and
  events; they call `self.save_workfile(filepath)` /
  `self.open_workfile(filepath)` internally.
- **Deprecated aliases still present** (workfiles.py:1422-1468):
  `file_extensions()`, `save_file()`, `open_file()`, `current_file()`,
  `has_unsaved_changes()`. Each delegates to the new name. Implement the new
  names only.
- **No `work_root` in the interface**: it is *not* an `IWorkfileHost` method.
  Nuke/Resolve declare it as a plain extra method on the host class; core
  uses `AYON_WORKDIR` instead (`pipeline/context_tools.py:548`).
- **`AbstractHost` abstracts** (already satisfied by `HostBase`): `log`,
  `name`, `get_app_information`, `get_current_context`,
  `set_current_context`, `get_current_project_name`,
  `get_current_folder_path`, `get_current_task_name`, `get_context_title`.

**Registration (answers the "yes it is" clarification)**: there is **no**
separate workfile-host registry. Core discovers capability by
`isinstance(host, IWorkfileHost)` against the single host returned by
`registered_host()`, which is the object passed to `install_host(...)`
(`host/host.py`, `pipeline/create/context.py:644`,
`tools/workfiles/control.py:160`, `plugins/publish/validate_file_saved.py:45`).
Therefore the workfile host **must** be wired into `FlameHost` itself; a
second, separately registered host object is not possible.

**Reference implementations verified locally**:
- `ayon-nuke/client/ayon_nuke/api/pipeline.py:99-126` —
  `NukeHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost)` delegating
  `open_workfile`/`save_workfile`/`get_current_workfile`/
  `workfile_has_unsaved_changes`/`get_workfile_extensions` to `api/workio.py`
  functions (plus an extra `work_root`).
- `ayon-resolve/client/ayon_resolve/api/pipeline.py:60,112-132` — same shape.

## R7 — Flame Python API `get_current_tab()` (verified)

Verified against the community-generated Flame API stubs
`beatreichenbach/types-flame` (PyPI `types-flame`, versions 2024.2.0 and
2026.2.3; `flame-stubs/__init__.pyi`):

- **`def get_current_tab() -> str`** — *"Get the current tab name."*
  Present in **both** the 2024.2.0 and 2026.2.3 stubs
  (2024.2.0 line 4042, 2026.2.3 line 4979) → stable API.
- **`def set_current_tab(arg1: str) -> bool`** — *"Set the given tab as the
  active environment. Keyword arguments: tab -- The tab to set active
  (MediaHub, Conform, Timeline, Effects, Batch, Tools)"*. The tab list is
  **identical** in 2024.2.0 and 2026.2.3.
- **`def go_to(tab: str) -> bool`** — *"Deprecated / use set_current_tab()
  instead."*
- **Conclusion**: the Batch page value is the literal string **`"Batch"`**.
  BFX is a *render context*, not a tab (see `set_render_option`:
  "Timeline, Conform, Effects, BFX, Batch"), so it is intentionally out of
  scope for this feature.

### Flame 2026 → 2027 compliance

- `get_current_tab` / `set_current_tab` exist with identical semantics in the
  oldest (2024.2) and newest (2026.2) published stubs; the tab enumeration is
  unchanged. Flame 2027 stubs are not published yet, so 2027 support rests on
  the API's demonstrated stability. **Verify in-host on 2026 and 2027.**
- `get_current_tab()` may raise or return an unexpected value before a project
  is loaded, or during startup/shutdown. Treat any non-`"Batch"` value —
  including `None` and exceptions — as "not the Batch page" (fail closed).
- Do **not** depend on `flame.go_to()`; it is explicitly deprecated.

### `flame.batch` / `PyBatch` surface (verified, 2026.2.3)

- `flame.batch: PyBatch` module attribute exists (also in 2024.2.0).
- `PyBatch` attributes: `name`, `nodes`, `reels`, `shelf_reels`,
  `batch_iterations`, `current_iteration`, `current_iteration_number`,
  `opened`, `parent`, `contexts`, `node_types`.
- `PyBatch` methods used by existing code: `save_setup(setup_path)`,
  `load_setup(setup_path)`, `append_setup`, `replace_setup(iteration)`,
  `clear_setup`, `iterate(index=-1)`, `create_node`, `connect_nodes`,
  `organize`, `create_reel`, `create_shelf_reel`.
- **There is no setup-path attribute and no "current batch file" concept.**
  `save_setup` *requires* an explicit path; nothing records where a Batch
  Group was last saved. Consequence: `get_current_workfile()` for Batch
  **cannot** return a native path — it can only return a path AYON itself
  knows about, or `None`.

## R8 — HIGH RISK: implementing `IWorkfileHost` activates a core publish validator

- **Finding**: `ayon_core/plugins/publish/validate_file_saved.py`
  (`ValidateCurrentSaveFile`, `ContextPlugin`, order
  `ValidatorOrder - 0.1`) starts with:

  ```python
  host = registered_host()
  if not isinstance(host, IWorkfileHost):
      self.log.debug("Skipping file save validation because host does "
                     "not implement workfiles.")
      return
  current_file = context.data["currentFile"]
  if not current_file:
      raise PublishValidationError("Workfile is not saved. ...")
  ```

  Core publish plugins are registered for every host, including Flame
  (`ayon_core/addon/interfaces.py:IPluginPaths.get_publish_plugin_paths`,
  consumed by `pipeline/context_tools.py:192`). Today the validator
  **skips** for Flame precisely because `FlameHost` is not an
  `IWorkfileHost`.
- **Impact**: the moment `FlameHost` implements `IWorkfileHost`, every Flame
  publish (Timeline/clip **and** Batch) runs this validator. It fails unless
  `context.data["currentFile"]` is non-empty. `currentFile` is collected by
  core from the host's `get_current_workfile()` (also used at
  `pipeline/create/context.py:644` to populate the creator's
  `_current_workfile_path`).
- **Consequences**:
  - Timeline/clip publishes risk a **new hard failure** ("Workfile is not
    saved") because `workio.current_file()` currently raises
    `NotImplementedError` — a real, user-visible publish behaviour change.
  - Batch publishes risk the same failure because Batch has no native file
    path (R7).
- **Decision**: This is a genuine conflict with spec FR-009/FR-010 ("no
  publish behaviour change yet") and is **not** silently solvable by
  implementation alone. The plan therefore:
  1. treats validator activation as an explicit, reviewed decision
     (see `plan.md` Decisions D1 and tasks T011/T012);
  2. requires an in-host verification that runs the publish validation for
     Flame on both a Batch tab and a non-Batch tab;
  3. forbids changing Flame's own publish plugins/versioning to work around
     it (that is the "later" work the request defers).

## R9 — `ayon_core` availability

- **Finding**: `ayon_core` is not importable in the agent session; the source
  is available at `/Users/jakub/CODE/__YNPUT/ayon-core/client/ayon_core` and
  was read directly. `package.py` requires `core >=1.8.0`.
- **Decision**: All interface facts above are taken from the local checkout,
  not from memory. Anyone implementing must re-verify against the *installed*
  core version if it is older than this checkout's tip.

## R10 — D1b blast radius is larger than assumed (blocking finding)

Discovered while implementing the D1b wiring. Three independent problems:

### R10.1 — `context.data["currentFile"]` is not populated by the host

`ValidateCurrentSaveFile` reads the key with `[]`:

```python
current_file = context.data["currentFile"]   # KeyError if unset
```

`currentFile` is **not** derived from `host.get_current_workfile()` by core.
Every host addon ships its own collector, e.g.
`ayon-hiero/client/ayon_hiero/plugins/publish/collect_current_file.py`:

```python
class CollectCurrentFile(pyblish.api.ContextPlugin):
    hosts = ["hiero"]
    order = pyblish.api.CollectorOrder - 0.5
    def process(self, context):
        context.data["currentFile"] = registered_host().get_current_workfile()
```

Flame has no such collector (verified by grep across
`client/ayon_flame/plugins/publish/`). So simply wiring `IWorkfileHost` makes
`ValidateCurrentSaveFile` raise `KeyError` → **all Flame publishes break**.
A new Flame collector is mandatory, i.e. a publish change.

### R10.2 — a new collector activates `CollectSceneVersion` (version change)

`ayon_core/plugins/publish/collect_scene_version.py`:

```python
order = pyblish.api.CollectorOrder
hosts = ["*"]
...
if not context.data.get('currentFile'):
    self.log.error("Cannot get current workfile path. ...")
    return                       # today's Flame behaviour: version untouched
filename = os.path.basename(context.data.get('currentFile'))
version = get_version_from_path(filename)
if version is None:
    raise PublishError(f"Unable to retrieve version number from filename: ...")
context.data['version'] = int(version)
```

- `get_version_from_path` matches `[\._]v([0-9]+)`; a version-less AYON path
  (e.g. `{project}.workfile`) makes it **raise `PublishError`**.
- Flame already sets the version itself: `CollectBatchVersion`
  (`client/ayon_flame/plugins/publish/collect_batch_version.py`) runs at the
  same `order = CollectorOrder` and sets
  `context.data["version"] = batch.current_iteration_number`. Adding
  `currentFile` creates a **same-order collision** over
  `context.data["version"]` → version behaviour change, which the feature
  explicitly forbids.

### R10.3 — non-Batch publishing would be blocked with no way out

`FlameWorkfileHost.get_current_workfile()` cannot resolve a path:
`workio.current_file()` raises `NotImplementedError` and Flame has no native
scene path. With a collector installed, `currentFile` becomes `None` →
`ValidateCurrentSaveFile` fails with *"Workfile is not saved. Please save your
scene to continue."* — and `workio.save_file()` also raises, so a Timeline
artist **cannot** satisfy it. That is a hard regression for every existing
Flame workflow.

### R10 — conclusion

D1b requires, together: a new publish collector, an accepted change to
`context.data["version"]` collection, and a working Timeline workfile save —
the last of which is explicitly out of scope. D1b is therefore deferred; the
capability module ships unwired with the flip checklist in `plan.md` D1.

### R10 verification note

Flame cannot be executed in an agent session, so R10.1–R10.3 are derived from
reading `ayon-core` source (paths and orders cited above), not from a live
publish. They should be confirmed in-host before any D1b flip.

## R11 — Module-level verification performed (no test framework)

`api/workfile.py` was exercised in a throwaway harness (stubbed `flame`,
`ayon_core.host`, `ayon_core.lib`, and the `batch_utils`/`workio` siblings):
21 assertions covering `_is_batch_tab` (Batch/whitespace/case/Timeline/None/
non-str/BFX), selector dispatch on tab change, delegation of save/open to
`batch_utils`, `get_current_workfile()` before/after save and after open,
missing-`dst_path` and missing-Batch-Group errors, default-host delegation to
`workio`, `work_root`, and fallback when `flame.get_current_tab` is absent.
All passed (the one initial failure was a stub bug — the real
`workio.work_root` calls `os.path.normpath`). No test files were added to the
repository.

## Open Questions for the reviewer

1. Confirm `flame.get_current_tab() == "Batch"` on the target Flame 2026 and
   2027 builds (in-host).
2. Confirm R10.1–R10.3 in-host, then flip D1b using the checklist in
   `plan.md` D1 (or keep D1a until Timeline workfile save exists).
3. Decide what `get_current_workfile()` should return for the **non-Batch**
   Flame tab once publishing depends on it (see R10.3).
