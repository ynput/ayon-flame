# Tests inside Flame

The tests in `tests/flame` run in a real Flame session: they create batch
groups and sequences, save and load Batch setups, run the Flame project save
and publish into AYON. Flame has no terminal mode, so a Flame window opens
while they run. They are not part of CI (Flame licence and a display
needed) and not part of the addon package.

## Run

Run it with the AYON launcher, so Flame starts like an artist's Flame: the
bundle's addons, the AYON environment and the prelaunch hooks.

```shell
/path/to/ayon run tests/run_flame_tests.py
/path/to/ayon run tests/run_flame_tests.py --app flame/2026-2
/path/to/ayon run tests/run_flame_tests.py -- tests/flame/test_batch_utils.py -k unique
/path/to/ayon run tests/run_flame_tests.py -- -m "not publish"
```

In a development workspace, `ayon` is
`<ayon-launcher>/.venv/bin/python <ayon-launcher>/start.py --use-dev`.

Arguments after `--` go to pytest. The exit code is pytest's, 3 when no
result came back from Flame, 4 when the run could not start (Flame already
running, unknown application, not a test project). A full run takes about
a minute, most of it Flame starting and quitting.

Options:

- `--app`: the AYON application, `flame/2026-2` by default (or
  `AYON_FLAME_TEST_APP`).
- `--test-project`, `--folder`, `--task`: the test context, `flame_tests`,
  `/shots/sq01/sh010`, `compositing` by default. The project name must
  start with `flame_tests`. (`--project` is taken by the AYON launcher.)
- `--core PATH`: an ayon-core checkout for Flame instead of the bundle's.
- `--no-setup`: do not create the test project.
- `--timeout`, `--start-timeout`, `--exit-timeout`: seconds for the whole
  run (1800), for Flame to start (300) and to quit after the tests (120).

## What the runner needs

- **AYON launcher**, logged in to the server whose bundle has the Flame
  addon and `ayon-applications` with the Flame application.
- **The test project.** The runner creates `flame_tests` with the default
  anatomy when it is missing, with `/shots/sq01/sh010` (tasks
  `compositing`, `paint`) and `/editorial` (task `edit`). The Flame
  project of the same name is created by the prelaunch hook. Never point
  the tests to a production project: they delete the workfiles of the test
  tasks and publish into it. They refuse to run unless the runner started
  them.
- **No Flame running.** One Flame at a time.
- **ayon-core with `PublishLogic`** for the end-to-end publish test, it is
  skipped with an older one (the skip and its reason show in the summary).
- **pytest** for the Python of Flame: the launcher's own when the Python
  versions match (development launcher), otherwise `uv` installs
  `requirements-flame.txt` into `tests/.deps/`.

## How it works

`run_flame_tests.py` runs in the AYON launcher process:

1. It creates the test project, folders and tasks when missing.
2. It loads the Flame addon from this checkout: the client folder goes
   first on `sys.path` and `PYTHONPATH`, the addons are loaded again. The
   bundle may point to another folder (dev path or downloaded version).
3. It adds `tests/flame/hook` to `DL_PYTHON_HOOK_PATH` and launches Flame
   through `ayon-applications`, without opening the last workfile.
4. `hook/ayon_flame_tests_hook.py` is a Flame Python hook. Once the project
   is loaded (`app_initialized`), it runs pytest from an idle event,
   writes the output to a log the runner prints, writes the exit code to a
   JSON file, then closes Flame with the `Program Exit` shortcut. Flame is
   killed when it does not quit within the exit timeout.

A run first deletes batch groups and sequences left by a killed run. Each
test deletes the batch groups and sequences it made, restores the
AYON session and the module state of the host (current workfiles). The
workfiles of the test tasks are deleted before each test, the ones of the
last test stay for a look after a failure. Published versions stay in the
test project.

Results go to `tests/.results/`: `junit.xml` and the publish report of the
end-to-end test (`publish_batch_report.json`).

## Tests

| File | Covers |
| --- | --- |
| `test_batch_utils.py` | node metadata, batch group names, consolidated JSON save and load, products context, session Batch workfiles |
| `test_batch_workfile_host.py` | `FlameBatchHost`: save, save with context (Batch product, products moved to the task), open, last workfile |
| `test_editorial_workfile.py` | `FlameHost` editorial workfiles: save, open, current workfile per task, Batch menu context |
| `test_project_saved_hook.py` | `project_saved` hook and the real `Save Project` shortcut rewriting the Batch workfile |
| `test_publish_plugins.py` | publish and create plugins of the Batch and editorial workfiles, one by one |
| `test_publish_batch.py` | a Batch menu publish end to end, then the Batch loader (`publish` marker) |
| `test_startup.py` | last workfile opened at launch (Batch or editorial), Workfiles tools of both menus |
