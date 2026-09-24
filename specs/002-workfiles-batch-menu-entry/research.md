# Research: Workfiles Menu Entry (Flame Batch Menu)

## R1 — Existing Flame menu architecture

`client/ayon_flame/api/menu.py` defines `_FlameMenuContext.build_menu()` for
Timeline, Batch, and Universal contexts. It returns a menu dictionary with
numbered actions and currently appends:

1. `1 - Create...`
2. `2 - Publish...`
3. `3 - Load...`

`FlameMenuBatch` subclasses `_FlameMenuContext` but currently has no override,
so the shared actions appear in all three context menus.

The menu hook in `startup/AYON_in_flame.py` calls
`_build_app_menu("FlameMenuBatch")` from `get_batch_custom_ui_actions()`, so an
override on `FlameMenuBatch.build_menu()` is sufficient to scope the new action
to the Batch menu without changing the startup hook.

## R2 — Existing action callback pattern

The menu module imports:

```python
from ayon_core.tools.utils import host_tools
```

Create and Publish construct an executable callback using a `host_tools`
function and pass it through `callback_selection`:

```python
"execute": lambda x: callback_selection(
    x,
    host_tools.show_publisher(
        tab="create", parent=_get_main_window()
    ),
    context=self.__class__.__name__
),
```

The Workfiles entry will follow the same pattern, using
`host_tools.show_workfiles(parent=_get_main_window())`. It will preserve the
selection/context handoff even though the workfiles tool itself is not
selection-driven today.

## R3 — Batch-only placement

Adding the action to `_FlameMenuContext.build_menu()` would expose it on the
Timeline and Universal menus, violating FR-003. The selected design is:

```python
class FlameMenuBatch(_FlameMenuContext):
    def build_menu(self):
        menu = super().build_menu()
        if menu:
            menu["actions"].append({...})
        return menu
```

The action is appended after `3 - Load...` as `4 - Workfiles...`, preserving
existing action labels and ordering.

## R4 — Main-window parent

`_get_main_window()` already finds the first `QtWidgets.QMainWindow` among
application top-level widgets and is passed to the existing publisher action.
The Workfiles action will pass the same parent helper and will not introduce a
second Qt-window lookup or alternate parent policy.

If no main window exists, the helper returns `None`, matching the behavior
already accepted by the existing Create/Publish actions.

## R5 — Host workfile capability dependency

Feature 001 added `client/ayon_flame/api/workfile.py`, but intentionally did
not mix `IWorkfileHost` into `FlameHost`. Its plan records that doing so would
activate ayon-core publish validation and scene-version collection, changing
Flame publish/version behavior. This feature therefore does not modify
`api/pipeline.py`, publish plugins, or settings.

The menu action is still valid as the user-facing entry point and can be
implemented independently. End-to-end opening of the workfiles UI must be
validated against the registered host in Flame and coordinated with the
follow-up that resolves the feature 001 D1b wiring decision.

## R6 — Scope and compatibility

No settings, package compatibility constraints, identifiers, representations,
publish orders, or host registration paths are changed. `addon.py` is not
imported or modified by the menu change. The implementation remains within the
existing host-runtime GUI seam.

## Open validation item

The exact callback contract of `host_tools.show_workfiles` should be checked
against the AYON Core version used by the Flame runtime before manual
validation. The implementation follows the established `show_publisher`
parent-call pattern and assumes `show_workfiles(parent=...)` returns the
callable expected by the Flame menu framework. If the installed core exposes a
different signature, adapt only the call shape while preserving the same menu
and callback structure.
