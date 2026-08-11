from __future__ import print_function  # noqa: UP010

import atexit
import os
import sys
import types
from pprint import pformat

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget  # noqa: F401
except ImportError:
    # https://github.com/ynput/ayon-flame/issues/120
    mock_module = types.ModuleType("PySide6.QtOpenGLWidgets")
    setattr(mock_module, "QOpenGLWidget", object())  # noqa: B010

    sys.modules["PySide6.QtOpenGLWidgets"] = mock_module
    from qtpy import QtWidgets
    sys.modules.pop("PySide6.QtOpenGLWidgets")

import traceback

import ayon_flame.api as flame_api
from ayon_core.lib import env_value_to_bool
from ayon_core.pipeline import get_global_context, install_host
from ayon_core.tools.utils import host_tools
from ayon_flame.api import FlameHost, batch_utils
from ayon_flame.api.menu import _get_main_window
from qtpy import QtWidgets


def ayon_flame_install():
    """Registering AYON in context
    """
    flame_host = FlameHost()
    install_host(flame_host)


def exception_handler(exctype, value, _traceback):
    """Exception handler for improving UX

    Args:
        exctype (str): type of exception
        value (str): exception value
        tb (str): traceback to show
    """
    msg = f"AYON: Python exception {value} in {exctype}"
    mbox = QtWidgets.QMessageBox()
    mbox.setText(msg)
    mbox.setDetailedText(
        pformat(traceback.format_exception(exctype, value, _traceback)))
    mbox.setStyleSheet("QLabel{min-width: 800px;}")
    mbox.exec_()
    sys.__excepthook__(exctype, value, _traceback)


# add exception handler into sys module
sys.excepthook = exception_handler


# register clean up logic to be called at Flame exit
def cleanup():
    """Cleaning up Flame framework context
    """
    if flame_api.CTX.flame_apps:
        print(
            f"`{__file__}` cleaning up flame_apps:\n "
            f"{pformat(flame_api.CTX.flame_apps)}\n"
        )
        while len(flame_api.CTX.flame_apps):
            app = flame_api.CTX.flame_apps.pop()
            print(f"`{__file__}` removing : {app.name}")
            del app
        flame_api.CTX.flame_apps = []

    if flame_api.CTX.app_framework:
        print(f"AYON\t: {flame_api.CTX.app_framework.bundle_name} cleaning up")
        flame_api.CTX.app_framework.save_prefs()
        flame_api.CTX.app_framework = None


atexit.register(cleanup)


def load_apps():
    """Load available flame_apps into Flame framework
    """
    flame_api.CTX.flame_apps.append(
        flame_api.FlameMenuProjectConnect(flame_api.CTX.app_framework))
    flame_api.CTX.flame_apps.append(
        flame_api.FlameMenuTimeline(flame_api.CTX.app_framework))
    flame_api.CTX.flame_apps.append(
        flame_api.FlameMenuBatch(flame_api.CTX.app_framework))
    flame_api.CTX.flame_apps.append(
        flame_api.FlameMenuUniversal(flame_api.CTX.app_framework))
    flame_api.CTX.app_framework.log.info("Apps are loaded")


def project_changed_dict(info):
    """Hook for project change action

    Args:
        info (str): info text
    """
    cleanup()


def _open_last_workfile():
    """Return the batch group holding this task's workfile, or None."""
    import flame

    if not env_value_to_bool("AVALON_OPEN_LAST_WORKFILE"):
        return None

    context = get_global_context()
    folder_path = context.get("folder_path")
    task_name = context.get("task_name")
    if not folder_path or not task_name:
        return None

    # each task its own batch group to avoid mixing with other tasks
    batch_name = batch_utils.get_task_batch_name(folder_path, task_name)

    # reuse an existing batch if it's already on the desktop
    existing_batch = batch_utils.get_batch_from_workspace(batch_name)
    if existing_batch is not None:
        print(f"AYON: reusing batch group '{batch_name}'")
        return existing_batch

    # load the last workfile into a task-specific batch group
    filepath = os.environ.get("AYON_LAST_WORKFILE")
    if filepath and os.path.exists(filepath):
        print(f"AYON: loading {filepath} into batch group '{batch_name}'")
        batch = flame.batch.create_batch_group(batch_name)

        batch_utils.set_current_batch(batch)
        try:
            batch = batch_utils.load_batch_from_consolidated_json(
                filepath, batch=batch
            )
        except Exception as error:
            print(
                f"!!!! AYON: could not load {filepath} into batch group "
                f"'{batch_name}': {error} !!!!"
            )
            flame_api.show_artist_message(
                f"could not open the last workfile. Batch group "
                f"'{batch_name}' is empty - delete it and open a version "
                "from the Work Files tool instead of saving over it.",
                "error",
                seconds=20,
            )
            return None
        return batch

    # start fresh batch group for this task
    print(f"AYON: no workfile yet, creating batch group '{batch_name}'")
    return flame.batch.create_batch_group(batch_name)


def _show_workfiles_tool():
    if not env_value_to_bool("AYON_WORKFILE_TOOL_ON_START"):
        return

    host_tools.show_workfiles(parent=_get_main_window())


def _run_launch_workfile_actions():
    """Open this task's workfile and bring it in front of the artist."""
    try:
        batch = _open_last_workfile()
        if batch is not None:
            batch_utils.set_current_batch(batch)
            # Flame opens on the Timeline page
            batch_utils.show_batch_page()
    except Exception as error:
        print(f"!!!! AYON: could not open last workfile: {error} !!!!")

    try:
        _show_workfiles_tool()
    except Exception as error:
        print(f"!!!! AYON: could not show workfiles tool: {error} !!!!")


def app_initialized(project_name=None):
    """Flame hook: the application is fully initialized, project loaded."""
    flame_api.CTX.app_framework = flame_api.FlameAppFramework()

    print(f"{flame_api.CTX.app_framework.bundle_name} initializing")

    load_apps()

    if not project_name:
        return

    try:
        import flame
        flame.schedule_idle_event(_run_launch_workfile_actions)
    except Exception as error:
        print(f"!!!! AYON: could not run project load actions: {error} !!!!")


"""
Initialization of the hook is starting from here

First it needs to test if it can import the flame module.
This will happen only in case a project has been loaded.
Then `app_initialized` will load main Framework which will load
all menu objects as flame_apps.
"""

try:
    import flame  # noqa
except ImportError:
    print("!!!! not able to import flame module !!!!")

try:
    app_initialized()
except Exception as error:
    print(f"!!!! not able to initialize the app: {error} !!!!")


def rescan_hooks():
    import flame  # noqa
    flame.execute_shortcut("Rescan Python Hooks")


def _build_app_menu(app_name):
    """Flame menu object generator

    Args:
        app_name (str): name of menu object app

    Returns:
        list: menu object
    """
    menu = []

    # first find the relative appname
    app = None
    for _app in flame_api.CTX.flame_apps:
        if _app.__class__.__name__ == app_name:
            app = _app

    if app:
        menu.append(app.build_menu())

    if flame_api.CTX.app_framework:
        menu_auto_refresh = flame_api.CTX.app_framework.prefs_global.get(
            "menu_auto_refresh", {})
        if menu_auto_refresh.get("timeline_menu", True):
            try:
                import flame  # noqa
                flame.schedule_idle_event(rescan_hooks)
            except ImportError:
                print("!-!!! not able to import flame module !!!!")

    return menu


""" Flame hooks are starting here
"""


def project_saved(project_name, save_time, is_auto_save):
    """Hook to activate when project is saved

    Args:
        project_name (str): name of project
        save_time (str): time when it was saved
        is_auto_save (bool): autosave is on or off
    """

    if flame_api.CTX.app_framework:
        flame_api.CTX.app_framework.save_prefs()

    # ignore Flame's periodic auto-save
    if is_auto_save:
        return

    flame_api.refresh_workfile()


def batch_setup_iterated_post(info, userData):
    """Hook to activate after a batch group iteration.
    A Flame iterate makes a new AYON workfile version"""

    if isinstance(info, dict) and info.get("abort"):
        # the AYON workfile still has to be attempted: its versions do not
        # come from Flame's iteration backups
        print(
            "!!!! AYON: Flame could not back up the iteration natively "
            f"({info.get('abortMessage')}). AYON versions its workfiles "
            "separately !!!!"
        )

    flame_api.bump_workfile_version()


def batch_setup_saved(setupPath):
    """Hook to activate when a batch setup is saved to disk."""
    flame_api.refresh_workfile()


def get_main_menu_custom_ui_actions():
    """Hook to create submenu in start menu

    Returns:
        list: menu object
    """
    # install AYON and the host
    ayon_flame_install()

    return _build_app_menu("FlameMenuProjectConnect")


def get_timeline_custom_ui_actions():
    """Hook to create submenu in timeline

    Returns:
        list: menu object
    """
    # install AYON and the host
    ayon_flame_install()

    return _build_app_menu("FlameMenuTimeline")


def get_batch_custom_ui_actions():
    """Hook to create submenu in batch

    Returns:
        list: menu object
    """
    # install AYON and the host
    ayon_flame_install()

    return _build_app_menu("FlameMenuBatch")


def get_media_panel_custom_ui_actions():
    """Hook to create submenu in desktop

    Returns:
        list: menu object
    """
    # install AYON and the host
    ayon_flame_install()

    return _build_app_menu("FlameMenuUniversal")
