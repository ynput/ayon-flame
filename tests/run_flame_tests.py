"""Run the tests in `tests/flame` inside a Flame session.

Flame has no terminal mode, so the tests run in a normal Flame session
started through AYON (`ayon-applications`), with the AYON environment and
the prelaunch hooks of this checkout. A Flame window opens for the
duration of the run.

Usage:
    ayon run tests/run_flame_tests.py [--app flame/2026-2] [--project NAME]
        [--folder PATH] [--task NAME] [--core PATH] [-- PYTEST ARGS]

The tests run in a dedicated AYON project (`flame_tests` by default), which
is created when missing. See `tests/README.md`.
"""

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
CLIENT_DIR = os.path.join(REPO_ROOT, "client")
FLAME_TESTS_DIR = os.path.join(TESTS_DIR, "flame")
HOOK_DIR = os.path.join(FLAME_TESTS_DIR, "hook")
REQUIREMENTS = os.path.join(TESTS_DIR, "requirements-flame.txt")
DEPS_ROOT = os.path.join(TESTS_DIR, ".deps")
RESULTS_DIR = os.path.join(TESTS_DIR, ".results")

DEFAULT_APP = "flame/2026-2"
DEFAULT_PROJECT = "flame_tests"
DEFAULT_FOLDER = "/shots/sq01/sh010"
DEFAULT_TASK = "compositing"

# Folders and tasks of the test project: (path, folder type, tasks).
TEST_HIERARCHY = (
    ("/shots", "Folder", ()),
    ("/shots/sq01", "Sequence", ()),
    (
        "/shots/sq01/sh010",
        "Shot",
        (("compositing", "Compositing"), ("paint", "Paint")),
    ),
    ("/editorial", "Folder", (("edit", "Edit"),)),
)


def _log(message):
    print(f"[run_flame_tests] {message}", flush=True)


def _flame_pids(pattern):
    try:
        output = subprocess.run(
            # '--' as the pattern starts with '--start-project'
            ["pgrep", "-f", "--", pattern], capture_output=True, text=True
        ).stdout
    except FileNotFoundError:
        return []
    return [int(pid) for pid in output.split() if pid.strip().isdigit()]


def _running_flame_pids():
    try:
        output = subprocess.run(
            ["pgrep", "-x", "flame"], capture_output=True, text=True
        ).stdout
    except FileNotFoundError:
        return []
    return [int(pid) for pid in output.split() if pid.strip().isdigit()]


def setup_test_project(project_name):
    """Create the test project, its folders and tasks when missing."""
    import ayon_api
    from ayon_api.operations import OperationsSession

    if not ayon_api.get_project(project_name):
        code = "".join(c for c in project_name if c.isalnum())[:10]
        _log(f"Creating AYON project '{project_name}' ({code}).")
        ayon_api.create_project(project_name, code)

    folder_ids = {"": None}
    for path, folder_type, tasks in TEST_HIERARCHY:
        folder = ayon_api.get_folder_by_path(project_name, path)
        if folder is None:
            parent_path, name = path.rsplit("/", 1)
            session = OperationsSession()
            operation = session.create_entity(
                project_name,
                "folder",
                {
                    "name": name,
                    "folderType": folder_type,
                    "parentId": folder_ids[parent_path],
                },
            )
            session.commit()
            folder_id = operation.entity_id
            _log(f"Created folder {path}")
        else:
            folder_id = folder["id"]
        folder_ids[path] = folder_id

        existing = {
            task["name"]
            for task in ayon_api.get_tasks(
                project_name, folder_ids=[folder_id], fields={"name"}
            )
        }
        for task_name, task_type in tasks:
            if task_name in existing:
                continue
            session = OperationsSession()
            session.create_entity(
                project_name,
                "task",
                {
                    "name": task_name,
                    "taskType": task_type,
                    "folderId": folder_id,
                },
            )
            session.commit()
            _log(f"Created task {path} {task_name}")


def _is_package_dir(path, package):
    return os.path.isfile(os.path.join(path, package, "__init__.py"))


def _prepend_python_path(path, package):
    """Put a client folder first, drop other folders of the same package.

    Applies to this process and to the 'PYTHONPATH' Flame inherits.
    """
    path = os.path.normpath(path)
    sys.path[:] = [
        p for p in sys.path
        if not (_is_package_dir(p, package) and os.path.normpath(p) != path)
    ]
    sys.path.insert(0, path)

    python_paths = [
        p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if p and not _is_package_dir(p, package)
    ]
    os.environ["PYTHONPATH"] = os.pathsep.join([path] + python_paths)


def use_checkout_addon():
    """Make AYON use the Flame addon of this checkout.

    The bundle may point the addon to another folder (a dev path or a
    downloaded version). The addon modules are imported from this checkout
    before the addons are loaded again, so the addon class, its launch
    hooks and the Flame startup hooks come from here.
    """
    for name in list(sys.modules):
        if name == "ayon_flame" or name.startswith("ayon_flame."):
            del sys.modules[name]
    _prepend_python_path(CLIENT_DIR, "ayon_flame")
    importlib.import_module("ayon_flame")

    from ayon_core.addon import AddonsManager
    from ayon_core.addon.base import load_addons

    load_addons(force=True)
    addon = AddonsManager().get("flame")
    if addon is None:
        raise RuntimeError("The Flame addon is not in the AYON bundle.")
    addon_file = os.path.normpath(inspect.getfile(addon.__class__))
    if not addon_file.startswith(os.path.normpath(CLIENT_DIR) + os.sep):
        raise RuntimeError(
            f"Flame addon is loaded from '{addon_file}', not this checkout."
        )
    _log(f"Flame addon: {addon_file}")


def use_core(core_path):
    """Make Flame use another ayon-core client (Flame only)."""
    client = os.path.join(os.path.abspath(core_path), "client")
    if not _is_package_dir(client, "ayon_core"):
        raise RuntimeError(f"No ayon-core client in '{core_path}'.")
    python_paths = [
        p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if p and not _is_package_dir(p, "ayon_core")
    ]
    os.environ["PYTHONPATH"] = os.pathsep.join([client] + python_paths)
    _log(f"Flame uses ayon-core from {client}")


def _flame_python_executable(application):
    executable = application.environment.get("AYON_FLAME_PYTHON_EXEC")
    if isinstance(executable, dict):
        executable = executable.get(sys.platform.replace("win32", "windows"))
    if not executable:
        raise RuntimeError(
            f"'{application.full_name}' has no AYON_FLAME_PYTHON_EXEC."
        )
    return os.path.expandvars(executable)


def ensure_pytest(flame_python):
    """Return a folder with pytest for the Python of Flame, or None.

    pytest of this process is used when its Python version is the one of
    Flame and it is already on 'PYTHONPATH' (the launcher venv). Otherwise
    `uv` installs `requirements-flame.txt` into `tests/.deps/`.
    """
    version = subprocess.run(
        [
            flame_python,
            "-c",
            "import sys; print('%d.%d' % sys.version_info[:2])",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    spec = importlib.util.find_spec("pytest")
    current = "%d.%d" % sys.version_info[:2]
    if spec is not None and current == version:
        site_dir = os.path.dirname(os.path.dirname(spec.origin))
        python_paths = os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if site_dir in python_paths:
            return None
        return site_dir

    target = os.path.join(DEPS_ROOT, f"py{version}")
    with open(REQUIREMENTS, "rb") as stream:
        digest = hashlib.sha1(stream.read()).hexdigest()
    stamp = os.path.join(target, ".requirements.sha1")
    if os.path.exists(stamp):
        with open(stamp) as stream:
            if stream.read().strip() == digest:
                return target

    _log(f"Installing {REQUIREMENTS} for Python {version} into {target}")
    subprocess.run(
        [
            "uv", "pip", "install",
            "--python", flame_python,
            "--target", target,
            "-r", REQUIREMENTS,
        ],
        check=True,
    )
    with open(stamp, "w") as stream:
        stream.write(digest)
    return target


def _absolute_test_path(arg):
    """Return a test path argument ('path' or 'path::test') as absolute."""
    path, sep, rest = arg.partition("::")
    if arg.startswith("-") or not os.path.exists(path):
        return arg
    return os.path.abspath(path) + sep + rest


def _stream_log(log_path, position):
    if not os.path.exists(log_path):
        return position
    with open(log_path, "r", errors="replace") as stream:
        stream.seek(position)
        chunk = stream.read()
        position = stream.tell()
    if chunk:
        sys.stdout.write(chunk)
        sys.stdout.flush()
    return position


def _stop_flame(project_name):
    pattern = f"--start-project={project_name}"
    for sig in (signal.SIGTERM, signal.SIGKILL):
        pids = _flame_pids(pattern)
        if not pids:
            return
        for pid in pids:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        time.sleep(5)


def run(args, pytest_args):
    from ayon_applications import ApplicationManager

    if _running_flame_pids():
        _log("Flame is running, close it first: one Flame at a time.")
        return 4

    if not args.no_setup:
        setup_test_project(args.project)

    use_checkout_addon()
    if args.core:
        use_core(args.core)

    manager = ApplicationManager()
    application = manager.applications.get(args.app)
    if application is None:
        _log(f"Unknown application '{args.app}'.")
        return 4

    pytest_dir = ensure_pytest(_flame_python_executable(application))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix="ayon_flame_tests_")
    log_path = os.path.join(run_dir, "pytest.log")
    result_path = os.path.join(run_dir, "result.json")
    junit_path = os.path.join(RESULTS_DIR, "junit.xml")

    test_paths = [FLAME_TESTS_DIR]
    if pytest_dir:
        test_paths.append(pytest_dir)

    # Flame does not run in this folder, test paths must be absolute.
    pytest_args = [
        _absolute_test_path(arg) for arg in pytest_args
    ] or [FLAME_TESTS_DIR]
    full_pytest_args = [
        "-c", os.path.join(FLAME_TESTS_DIR, "pytest.ini"),
        "--rootdir", FLAME_TESTS_DIR,
        f"--junitxml={junit_path}",
    ] + pytest_args

    os.environ.update({
        "AYON_FLAME_TEST_RUN": "1",
        "AYON_FLAME_TEST_PROJECT": args.project,
        "AYON_FLAME_TEST_PATHS": os.pathsep.join(test_paths),
        "AYON_FLAME_TEST_PYTEST_ARGS": json.dumps(full_pytest_args),
        "AYON_FLAME_TEST_LOG": log_path,
        "AYON_FLAME_TEST_RESULT": result_path,
        "AYON_FLAME_TEST_EXIT_TIMEOUT": str(args.exit_timeout),
    })
    hook_paths = [
        p for p in os.environ.get("DL_PYTHON_HOOK_PATH", "").split(os.pathsep)
        if p
    ]
    os.environ["DL_PYTHON_HOOK_PATH"] = os.pathsep.join(
        hook_paths + [HOOK_DIR]
    )

    _log(
        f"Launching {args.app} for {args.project} {args.folder} {args.task}"
    )
    manager.launch(
        args.app,
        project_name=args.project,
        folder_path=args.folder,
        task_name=args.task,
        start_last_workfile=False,
    )

    pattern = f"--start-project={args.project}"
    deadline = time.time() + args.timeout
    position = 0
    started = False
    while True:
        position = _stream_log(log_path, position)
        running = bool(_flame_pids(pattern))
        started = started or running
        if os.path.exists(result_path) and not running:
            break
        if started and not running:
            _log("Flame exited without a test result.")
            break
        if time.time() > deadline:
            _log(f"Timed out after {args.timeout} s, stopping Flame.")
            _stop_flame(args.project)
            break
        time.sleep(1)
    _stream_log(log_path, position)

    if not os.path.exists(result_path):
        return 3
    with open(result_path) as stream:
        result = json.load(stream)
    _log(f"pytest exit code {result['exitcode']}, JUnit report {junit_path}")
    return int(result["exitcode"])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pytest_args = []
    if "--" in argv:
        index = argv.index("--")
        argv, pytest_args = argv[:index], argv[index + 1:]

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--app",
        default=os.environ.get("AYON_FLAME_TEST_APP", DEFAULT_APP),
        help=f"AYON application name (default {DEFAULT_APP})",
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--folder", default=DEFAULT_FOLDER)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument(
        "--core", help="ayon-core checkout for Flame (default: the bundle's)"
    )
    parser.add_argument(
        "--no-setup",
        action="store_true",
        help="do not create the test project, folders and tasks",
    )
    parser.add_argument(
        "--timeout", type=int, default=1800, help="seconds (default 1800)"
    )
    parser.add_argument(
        "--exit-timeout",
        type=int,
        default=120,
        help="seconds Flame gets to quit before it is killed (default 120)",
    )
    args = parser.parse_args(argv)
    return run(args, pytest_args)


if __name__ == "__main__":
    sys.exit(main())
