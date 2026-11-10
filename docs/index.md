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

Flame follows the core settings to open the last workfile and the
Workfiles tool on start. It does it once per launch from AYON, not again
after a Flame project switch. Opening the last workfile is on by default
for every host (core `last_workfile_on_startup`). Add a profile for
`flame` to turn it off.

- A `.flamebatch` opens as a new batch group on the Batch page. A
  `.flameedit` opens its sequence on the Timeline page, if the sequence
  is in the Flame project.
- The launcher picks the highest version across both extensions, or the
  workfile selected in the launcher. Each kind has its own version
  numbers, so a task with both kinds opens the higher number, not the
  most recent file.
- Each launch adds a batch group, like opening from the Workfiles tool.
  Batch groups of earlier sessions stay on the desktop.
- A task without a workfile opens nothing. Save its first workfile from
  the Workfiles tool.
- The Workfiles tool on start matches the workfile kind. For a task
  without a workfile it is the editorial one. The Batch tool opens on
  the task of the current batch group, like from the Batch menu.

### Flame save

After a Save As or an Open from Work Files, or the workfile opened at
launch, each Flame project save rewrites the Batch workfile of the
current batch group. It keeps the same version. Save As in Work Files
makes a new version.

Project saves are control+S, the Save Project menu and every iteration
(Iterate button, command+S on the Batch schematic). A Batch publish
saves too while "Iterate Batch After Publish" is on. Auto-saves are
skipped. The Batch Save button and Save Desktop do not save the project.

Save before switching to another batch group: only the current one is
written. Nothing is written for a batch group without a Batch workfile
in this Flame session: after a Flame restart or a project switch, for a
group from the Batch loader, or after a Batch Load And Replace.

Work Files selects the Batch workfile of the current batch group, and
Save As proposes its comment.

Setting: `flame/update_batch_workfile`, on by default.

### Publish source

The version source of a publish is the saved AYON workfile, not the Flame
placeholder:

- Batch publish: the Batch workfile saved or opened for the published batch
  group in the current Flame session, when it belongs to the task of the
  batch group's products. Without one (Flame was restarted, it was never
  saved, its products moved to another task) it is the last saved Batch
  workfile of that task.
- Editorial publish: the editorial workfile saved or opened for the current
  task. It is not used for another task, e.g. after the context was changed
  in the Publisher.
