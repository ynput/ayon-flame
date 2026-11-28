"""Run pytest inside Flame, started by `tests/run_flame_tests.py`.

A Flame Python hook: the runner adds this folder to `DL_PYTHON_HOOK_PATH`.
Nothing happens unless `AYON_FLAME_TEST_RUN` is set. Once the project is
loaded (`app_initialized` with a project name), pytest runs from an idle
event, then Flame quits.

Settings come from the environment:

    AYON_FLAME_TEST_PATHS         paths added to `sys.path`
    AYON_FLAME_TEST_PYTEST_ARGS   JSON list of pytest arguments
    AYON_FLAME_TEST_LOG           file pytest writes its output to
    AYON_FLAME_TEST_RESULT        JSON file with the pytest exit code
    AYON_FLAME_TEST_EXIT_TIMEOUT  seconds before Flame is killed when the
                                  'Program Exit' shortcut does not close it
"""

import json
import os
import sys
import threading
import time
import traceback

_STATE = {"started": False}


def _hard_exit_later(exitcode):
    """Kill Flame when it does not quit, e.g. a dialog asks to save."""
    timeout = float(os.environ.get("AYON_FLAME_TEST_EXIT_TIMEOUT") or 120)

    def _target():
        time.sleep(timeout)
        os._exit(exitcode)

    threading.Thread(target=_target, daemon=True).start()


def _run_tests():
    exitcode = 3
    log_stream = None
    stdout, stderr = sys.stdout, sys.stderr
    log_path = os.environ.get("AYON_FLAME_TEST_LOG")
    if log_path:
        log_stream = open(log_path, "w", buffering=1)
        sys.stdout = log_stream
        sys.stderr = log_stream

    try:
        paths = os.environ.get("AYON_FLAME_TEST_PATHS", "").split(os.pathsep)
        for path in reversed(paths):
            if path and path not in sys.path:
                sys.path.insert(0, path)

        import pytest

        args = json.loads(
            os.environ.get("AYON_FLAME_TEST_PYTEST_ARGS") or "[]"
        )
        # Test ids relative to the tests folder, Flame's folder is restored.
        cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            exitcode = int(pytest.main(args + ["-p", "no:cacheprovider"]))
        finally:
            os.chdir(cwd)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout, sys.stderr = stdout, stderr
        if log_stream:
            log_stream.close()
        result_path = os.environ.get("AYON_FLAME_TEST_RESULT")
        if result_path:
            with open(result_path, "w") as stream:
                json.dump({"exitcode": exitcode}, stream)
        _quit(exitcode)


def _quit(exitcode):
    _hard_exit_later(exitcode)
    try:
        import flame

        flame.execute_shortcut("Program Exit")
    except Exception:
        traceback.print_exc()
        os._exit(exitcode)


def app_initialized(project_name=None):
    if (
        not os.environ.get("AYON_FLAME_TEST_RUN")
        or not project_name
        or _STATE["started"]
    ):
        return
    _STATE["started"] = True

    import flame

    flame.schedule_idle_event(_run_tests)
