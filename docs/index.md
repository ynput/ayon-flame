# AYON Flame Addon API Reference

--8<-- "README.md:2"

## Workfiles

Flame has more than one kind of workfile, and AYON matches files and
workfile hosts by file extension. Every kind therefore owns a unique,
explicit extension and never a generic one such as `.json`:

| Workfile | Extension | Opened from |
| --- | --- | --- |
| Batch group, a consolidated JSON document | `.flamebatch` | Batch menu > AYON > 4 - Work Files... |
| Editorial, a JSON reference to the Flame project and sequence | `.flameedit` | Flame main menu > AYON > 2 - Work Files... |

The workfile hosts (`FlameBatchHost`, `FlameEditorialHost`) have the same
host name as the registered `FlameHost` (`flame`): workfile templates and
settings are found by host name. Each Workfiles tool is built with
its own host instance. Each Workfiles tool lists only the files of its own
extension, so the version stacks of different kinds do not mix. A new kind
of workfile needs a new extension and a new entry in
`ayon_flame/constants.py`.

The published Batch workfile has the same `.flamebatch` extension, so it is
listed among the published workfiles of the task. Batch workfiles published
before this change are `.json` and stay loadable with the Batch loader.
