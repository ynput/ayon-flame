# Contract: Batch Workfiles Menu Action

## Menu object

The `FlameMenuBatch.build_menu()` result MUST retain the inherited menu object
and append exactly one action with:

```python
{
    "name": "4 - Workfiles...",
    "execute": <callable>,
}
```

The inherited action order MUST remain:

```text
0 - <project>
1 - Create...
2 - Publish...
3 - Load...
4 - Workfiles...
```

## Execution

The action callable receives Flame's menu selection argument and MUST route
execution through:

```python
callback_selection(
    selection,
    host_tools.show_workfiles(parent=_get_main_window()),
    context="FlameMenuBatch",
)
```

The implementation may use the class-name expression already used by sibling
actions instead of the literal context value.

## Scope

- `FlameMenuTimeline.build_menu()` MUST NOT include this action.
- `FlameMenuUniversal.build_menu()` MUST NOT include this action.
- When `self.flame` is unavailable, the existing empty-menu behavior MUST be
  preserved.
- No host import or workfile serialization logic belongs in this menu action.
