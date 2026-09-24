# Quickstart: Workfiles Menu Entry

## Static validation

From the repository root:

```bash
ruff check client/ayon_flame/api/menu.py
ruff format --check client/ayon_flame/api/menu.py
python create_package.py --skip-zip
```

The repository has no test framework; do not add one for this menu action.

## Manual Flame validation

A reviewer with the supported Flame studio launcher should:

1. Start Flame with the AYON Flame addon installed.
2. Open a project and navigate to the Batch page.
3. Open the AYON Batch menu.
4. Confirm the existing actions remain ordered as Create, Publish, Load and
   the new `4 - Workfiles...` action follows them.
5. Activate Workfiles and confirm `host_tools.show_workfiles` opens the AYON
   workfiles UI with the Flame main window as its parent.
6. Confirm the workfiles UI behavior against the currently registered Flame
   host. If feature 001's `IWorkfileHost` wiring is still deferred, record that
   dependency rather than changing publish or collector behavior as a workaround.
7. On the Timeline and Universal/Media Panel menus, confirm that Workfiles is
   absent and that the existing actions are unchanged.
8. Repeat with no active top-level `QMainWindow` if practical; behavior should
   match the existing publisher action's `parent=None` fallback.

## Regression checks

Confirm that:

- `client/ayon_flame/addon.py` remains launcher-safe and has no Flame import.
- No files under `client/ayon_flame/plugins/` or `server/` changed.
- Flame publish and version/iteration behavior is unchanged.
