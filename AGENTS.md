# Flame addon

**Primary guidance:** the shared instructions in
[.agents-main/AGENTS.md](.agents-main/AGENTS.md) and
[.agents-main/fragments/host-integration.md](.agents-main/fragments/host-integration.md).
Agents that support `@` imports load them from the lines below. If their
content is not already in your context, open and read both files before
doing anything else. This file only adds repository-specific facts on top of
that shared guidance. It never replaces, overrides or contradicts it.

@./.agents-main/AGENTS.md
@./.agents-main/fragments/host-integration.md

## What this addon is

AYON host integration for Autodesk Flame (`package.py`; `README.md`): it
registers the `flame` host with the AYON launcher, ships Flame-side
create/load/publish plugins, and provides the server-side settings model.

- **Client host integration** — [`client/ayon_flame/`](client/ayon_flame);
  `FlameAddon` registration (`addon.py`), the Flame-API seam (`api/`:
  `pipeline.py`, `lib.py`, `menu.py`, `plugin.py`, `workio.py`), plugins
  (`plugins/create`, `plugins/load`, `plugins/publish`), launcher hooks
  (`hooks/`), OpenTimelineIO export (`otio/`), and the Flame startup hook
  (`startup/AYON_in_flame.py`, injected via `DL_PYTHON_HOOK_PATH`).
- **Server addon + settings** — [`server/`](server); `FlameAddon` in
  `server/__init__.py`, settings model `FlameSettings` in
  `server/settings/main.py` with per-concern modules beside it.

## Repo facts

- Addon name `flame`; title `Flame`; client code dir `ayon_flame`
  (`package.py`).
- The server addon class is `FlameAddon` in **`server/__init__.py`** — this
  repo has no `server/addon.py`.
- **IMPORTANT:** `client/ayon_flame/addon.py` is loaded at launcher/hook time,
  so it must stay importable without Flame's Python API. Never import the
  Flame `flame` module, or any GUI/menu state, from `addon.py`; that code
  belongs in `api/`, `startup/`, or `hooks/`.
- `package.py` holds the `ayon_server_version` / `ayon_required_addons` /
  `ayon_compatible_addons` constraints — read them there before touching any
  compatibility-import branch. Not restated here.
- `FlameSettings` (`server/settings/main.py`) is exposed under the category
  **`flame`**; client code reads it as
  `get_current_project_settings()["flame"]` (`client/ayon_flame/api/plugin.py`,
  `api/menu.py`).
- Settings override migrations live in `server/settings/conversion.py`
  (`_convert_*` helpers) and are chained through
  `FlameAddon.convert_settings_overrides` (`server/__init__.py`). Any settings
  rename must add a conversion there — never rename a settings field without
  one.
- `client/ayon_flame/version.py` is regenerated from `package.py:version` by
  `create_package.py` (`update_client_version`); treat `package.py` as
  authoritative and do not hand-edit the two out of sync.
- Style: `ruff.toml` at repo root — line length 79, lint selects `E`, `F`,
  `W`, formatter uses double quotes. No vendor directory exists to exclude.
- Tests: none — no `tests/` and no `pyproject.toml`. Do not add a test
  framework; validate with the lint and package-build checks below.

## Development checks

```bash
ruff check .
ruff format --check .
python create_package.py --skip-zip   # use python3 if python is not on PATH
```

`ruff` must be installed locally (CI runs it via `chartboost/ruff-action` in
`.github/workflows/pr_linting.yml`). Flame itself cannot be executed from an
agent session — a reviewer must validate host behaviour inside Flame via the
studio launcher wrapper described in `README.md`; see
`fragments/host-integration.md`.

## Spec Kit

Spec-driven development setup: [SPEC_KIT.md](SPEC_KIT.md). This repo is
harness-agnostic — no agent config is committed; each teammate installs their
own Spec Kit integration and links `.agents-main` via
`python agentic_setup.py install`. The AYON constitution is loaded only for
`/speckit.*` work; `.specify/memory/ayon-addon-constitution.md` is this
repository's tracked extension layer (it may only tighten the shared
constitution).
