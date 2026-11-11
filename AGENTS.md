# Flame addon

Guidance for AI coding agents working in this repository. It only records
facts an agent cannot cheaply derive from the code. Keep it short and keep it
true: when a fact here changes, update this file in the same PR.

## What this addon is

AYON host integration for Autodesk Flame (`package.py`; `README.md`): it
registers the `flame` host with the AYON launcher, ships Flame-side
create/load/publish plugins, and provides the server-side settings model.

- **Client host integration** — [`client/ayon_flame/`](client/ayon_flame);
  `FlameAddon` registration (`addon.py`), the Flame-API seam (`api/`:
  `pipeline.py`, `lib.py`, `menu.py`, `plugin.py`, `batch_utils.py`),
  plugins (`plugins/create`, `plugins/load`, `plugins/publish`), launcher
  hooks (`hooks/`), OpenTimelineIO export (`otio/`), and the Flame startup
  hook (`startup/AYON_in_flame.py`, injected via `DL_PYTHON_HOOK_PATH`).
- **Server addon + settings** — [`server/`](server); `FlameAddon` in
  `server/__init__.py`, settings model `FlameSettings` in
  `server/settings/main.py` with per-concern modules beside it.
- **Docs** — `docs/` built with `mkdocs.yml`.

## Repo facts

- Addon name `flame`; title `Flame`; client code dir `ayon_flame`
  (`package.py`).
- The server addon class is `FlameAddon` in **`server/__init__.py`** — this
  repo has no `server/addon.py`.
- **IMPORTANT:** `client/ayon_flame/addon.py` is loaded at launcher/hook time,
  so it must stay importable without Flame's Python API. Never import the
  Flame `flame` module, Qt, or any menu state from `addon.py` or `hooks/`;
  that code belongs in `api/` or `startup/`.
- `package.py` holds the `ayon_server_version` / `ayon_required_addons` /
  `ayon_compatible_addons` constraints — read them there before relying on a
  newer `ayon-core` API.
- `FlameSettings` (`server/settings/main.py`) is exposed under the category
  **`flame`**; client code reads it as
  `get_current_project_settings()["flame"]`.
- Settings override migrations live in `server/settings/conversion.py`
  (`_convert_*` helpers) and are chained through
  `FlameAddon.convert_settings_overrides` (`server/__init__.py`). Never rename
  or move a settings field without adding a conversion there.
- `client/ayon_flame/version.py` is regenerated from `package.py:version` by
  `create_package.py` (`update_client_version`); treat `package.py` as
  authoritative and never hand-edit the version.
- Style: `ruff.toml` at repo root — line length 79, lint selects `E`, `F`,
  `W`. Match the surrounding code; do not reformat untouched files.
- Tests: none — there is no `tests/` directory. Do not add a test framework;
  validate with the checks below and in Flame.

## Flame specifics

- The menus are built by `startup/AYON_in_flame.py` hooks:
  `get_main_menu_custom_ui_actions` → `FlameMenuProjectConnect`,
  `get_timeline_custom_ui_actions` → `FlameMenuTimeline`,
  `get_batch_custom_ui_actions` → `FlameMenuBatch`,
  `get_media_panel_custom_ui_actions` → `FlameMenuUniversal`
  (classes in `api/menu.py`). Every action that depends on the selection must
  go through `callback_selection(...)`, which records `CTX.selection` and
  `CTX.context` (the menu class name) before running the callback.
- `CTX.context == "FlameMenuBatch"` is how plugins know an action came from
  the Batch schematic; batch instances are stored as JSON in Note nodes
  (`batch_utils.read_node_metadata` / `write_node_metadata`).
- A Batch group is serialised to/from a single "consolidated JSON" file by
  `batch_utils.save_batch_as_consolidated_json` /
  `load_batch_from_consolidated_json`; reuse it instead of a new format.
- `flame.get_current_tab()` returns one of `MediaHub`, `Conform`,
  `Timeline`, `Effects`, `Batch`, `Tools`.
- Flame Python hooks run on Flame's UI thread: never block them (no modal
  dialogs from `flame.schedule_idle_event` callbacks, no long loops).
- The Flame project name is the AYON project name, so every task of a
  project shares one Flame project.
- Lambdas in menu `execute` entries must defer the call
  (`lambda x: callback_selection(x, lambda: tool(...), ...)`), never call the
  tool while the menu is being built.

## Development checks

```bash
ruff check .
python create_package.py --skip-zip   # use python3 if python is not on PATH
```

`ruff` must be installed locally (CI runs it via `chartboost/ruff-action` in
`.github/workflows/pr_linting.yml`). Flame cannot be executed from an agent
session — host behaviour must be validated by a person inside Flame started
through the AYON launcher. Say so in the PR testing notes instead of claiming
it works.

## Pull requests

- Target `develop`. One concern per PR; stack dependent PRs (base the next PR
  on the previous branch) instead of growing one big PR.
- Every PR needs exactly one `type: ...` label (`type: bug`,
  `type: enhancement`, `type: feature`, `type: maintenance`); CI validates it.
- PR body sections: `## Changelog Description`, `## Additional info`,
  `## Testing notes:` (numbered, reproducible in Flame).
- Keep `## Additional info` to the bare minimum: a few one-line bullets
  with what a reviewer needs and cannot read from the changelog or diff
  (stack position, merge note, known limitation, open risk). No
  file-by-file change lists, no rationale or research write-ups.
