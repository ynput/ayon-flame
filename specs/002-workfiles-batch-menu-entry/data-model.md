# Data Model: Workfiles Menu Entry

This feature introduces no persisted data, settings fields, entities, or
pipeline metadata. It adds one transient menu action to the existing Flame
menu structure.

## Menu model

### Batch menu

- `name`: existing AYON menu group name (`"AYON"`)
- `actions`: existing ordered action list, extended with:
  - `name`: `"4 - Workfiles..."`
  - `execute`: callback accepting Flame's selection argument

The action is created only when the existing `_FlameMenuContext` Flame-runtime
guard succeeds.

## Callback context

When invoked, the callback receives the Flame menu selection and routes it
through the existing `callback_selection` helper. That helper stores:

- `ayon_flame.api.CTX.selection`: the received selection
- `ayon_flame.api.CTX.context`: the menu app class name (`"FlameMenuBatch"`)

It then invokes the callable returned by `host_tools.show_workfiles(...)`.
No new state is persisted and no existing context fields are renamed.

## External dependency

`host_tools.show_workfiles` owns the workfiles UI state and operates on the
currently registered AYON host. This feature does not duplicate or wrap its
workfile entities, paths, or serialization data.
