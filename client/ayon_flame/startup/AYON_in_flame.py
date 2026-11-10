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

import ayon_api
import ayon_flame.api as flame_api
from ayon_core.lib import env_value_to_bool
from ayon_core.pipeline import get_global_context, install_host
from ayon_flame.api import FlameHost
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


def check_project_ocio_config():
    """Warn if Flame project OCIO config and AYON OCIO config differs.

    Flame project OCIO config is only set at project creation,
    so it can differ from the current config set in AYON (used at publish).
    """
    import flame
    from ayon_core.pipeline.context_tools import get_current_project_settings

    # Flame < 2026 projects use SynColor not OCIO.
    if int(flame.get_version_major()) < 2026:
        return

    # No OCIO config set.
    ayon_ocio_config = os.getenv("OCIO")
    if not ayon_ocio_config:
        return

    project_name = flame_api.get_current_project().name
    try:
        # Color management is disabled.
        imageio_flame = get_current_project_settings()["flame"]["imageio"]
        if imageio_flame.get("activate_host_color_management") is False:
            return

        project_ocio_config = flame_api.get_project_ocio_config(project_name)

    except Exception as error:
        print(f"!!!! not able to check project OCIO config: {error} !!!!")
        return

    if (
        project_ocio_config
        and os.path.realpath(project_ocio_config)
        == os.path.realpath(ayon_ocio_config)
    ):
        return

    message = (
        f"Flame project '{project_name}' OCIO config does not match "
        "AYON OCIO config, published colorspaces might be wrong.\n\n"
        f"- Flame project: {project_ocio_config}\n"
        f"- AYON: {ayon_ocio_config}"
    )
    print(f"AYON: {message}")
    flame.messages.show_in_dialog(
        "AYON: OCIO config mismatch",
        message,
        "warning",
        ["OK"],
    )


def open_launch_workfile():
    """Open the last workfile of the launch task and show the Workfiles tool.

    Follows the core Workfiles settings: last workfile on startup, and
    Workfiles tool on startup. The workfile extension picks the host and
    the tool. A task without a workfile opens nothing.

    Runs from an idle event, so errors show in the Flame message bar, not
    in a blocking dialog.
    """
    # Run once per launch. A project change starts a new Flame process
    # with this environment, and 'app_initialized' runs again.
    open_last_workfile = env_value_to_bool(
        value=os.environ.pop("AVALON_OPEN_LAST_WORKFILE", None)
    )
    show_workfiles_tool = env_value_to_bool(
        value=os.environ.pop("AYON_WORKFILE_TOOL_ON_START", None)
    )
    if not open_last_workfile and not show_workfiles_tool:
        return

    context = get_global_context()
    if not context["folder_path"] or not context["task_name"]:
        return

    # The launcher sets it even for a task without a workfile. It then
    # ends with the first extension of the addon, '.flameedit'.
    filepath = os.environ.get("AYON_LAST_WORKFILE", "")
    if filepath.endswith(flame_api.BATCH_WORKFILE_EXTENSION):
        host_class = flame_api.FlameBatchHost
        show_workfiles = flame_api.show_batch_workfiles
    else:
        host_class = flame_api.FlameEditorialHost
        show_workfiles = flame_api.show_editorial_workfiles

    # Two steps, so the tool still shows when the workfile fails to open.
    try:
        # Only the menu hooks install the host, they may not have run yet.
        ayon_flame_install()

        if open_last_workfile and os.path.exists(filepath):
            project_name = context["project_name"]
            folder_entity = ayon_api.get_folder_by_path(
                project_name, context["folder_path"]
            )
            task_entity = ayon_api.get_task_by_name(
                project_name, folder_entity["id"], context["task_name"]
            )
            host_class().open_workfile_with_context(
                filepath, folder_entity, task_entity
            )
    except Exception as error:
        _show_error("open the launch workfile", error)

    if show_workfiles_tool:
        try:
            show_workfiles()
        except Exception as error:
            _show_error("show the Workfiles tool", error)


def _show_error(action, error):
    import flame

    print(f"!!!! AYON: not able to {action}: {error} !!!!")
    traceback.print_exc()
    flame.messages.show_in_console(
        f"AYON: not able to {action}: {error}", "error", 20
    )


def app_initialized(project_name=None):
    """Inicialization of Framework

    Args:
        project_name (str, optional): Flame project. Flame passes it after
            each project load. Defaults to None.
    """
    flame_api.CTX.app_framework = flame_api.FlameAppFramework()

    print(f"{flame_api.CTX.app_framework.bundle_name} initializing")

    load_apps()
    check_project_ocio_config()

    if project_name:
        import flame

        flame.schedule_idle_event(open_launch_workfile)


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

    # Append specific app_name menu(s) if any.
    for _app in flame_api.CTX.flame_apps:
        if _app.__class__.__name__ == app_name:
            app_menu = _app.build_menu()
            if app_menu:
                menu.append(app_menu)
            app_custom_menu = _app.build_custom_menu_from_settings()
            if app_custom_menu:
                menu.extend(app_custom_menu)

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
