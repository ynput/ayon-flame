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

### Launch

The core settings that open the last workfile and the Workfiles tool on
start apply to Flame too, once per Flame session. Opening the last
workfile is on by default for every host (core `last_workfile_on_startup`
profiles), add a profile for `flame` to turn it off.

- The last workfile of the task is opened by the host of its extension: a
  `.flamebatch` as a new batch group on the Batch page, a `.flameedit` as
  its sequence on the Timeline page when the sequence is in the Flame
  project. It is the highest version across both extensions, the most
  recently modified one on a tie, or the workfile selected in the
  launcher. Each kind numbers its own versions, so a task with both kinds
  opens the one with the higher number, not the most recent one.
- Like opening it from the Workfiles tool, every launch adds a batch
  group, batch groups of earlier sessions stay on the desktop.
- A task without any workfile opens nothing, its first workfile is saved
  from the Workfiles tool.
- The Workfiles tool on start is the tool of that workfile kind. For a
  task without any workfile it is the editorial one, the first workfile
  extension of the addon.

### Publish source

The version source of a publish is the saved AYON workfile, not the Flame
placeholder:

- Batch publish: the Batch workfile saved or opened for the published batch
  group in the current Flame session, when it belongs to the task of the
  batch group's products. Without one (Flame was restarted, the batch group
  was renamed, it was never saved, its products moved to another task) it is
  the last saved Batch workfile of that task.
- Editorial publish: the editorial workfile saved or opened for the current
  task. It is not used for another task, e.g. after the context was changed
  in the Publisher.
