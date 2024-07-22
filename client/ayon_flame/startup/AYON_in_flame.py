from __future__ import print_function
import sys
from pprint import pformat
import atexit
from qtpy import QtWidgets
import traceback

import ayon_flame.api as flame_api
from ayon_core.pipeline import (
    install_host,
    registered_host,
)


def ayon_flame_install():
    """Registering AYON in context
    """
    install_host(flame_api)
    print("Registered host: {}".format(registered_host()))


# Exception handler
def exeption_handler(exctype, value, _traceback):
    """Exception handler for improving UX

    Args:
        exctype (str): type of exception
        value (str): exception value
        tb (str): traceback to show
    """
    msg = "AYON: Python exception {} in {}".format(value, exctype)
    mbox = QtWidgets.QMessageBox()
    mbox.setText(msg)
    mbox.setDetailedText(
        pformat(traceback.format_exception(exctype, value, _traceback)))
    mbox.setStyleSheet('QLabel{min-width: 800px;}')
    mbox.exec_()
    sys.__excepthook__(exctype, value, _traceback)


# add exception handler into sys module
sys.excepthook = exeption_handler


# register clean up logic to be called at Flame exit
def cleanup():
    """Cleaning up Flame framework context
    """
    if flame_api.CTX.flame_apps:
        print('`{}` cleaning up flame_apps:\n {}\n'.format(
            __file__, pformat(flame_api.CTX.flame_apps)))
        while len(flame_api.CTX.flame_apps):
            app = flame_api.CTX.flame_apps.pop()
            print('`{}` removing : {}'.format(__file__, app.name))
            del app
        flame_api.CTX.flame_apps = []

    if flame_api.CTX.app_framework:
        print('AYON\t: {} cleaning up'.format(
            flame_api.CTX.app_framework.bundle_name)
        )
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
        flame_api.FlameMenuUniversal(flame_api.CTX.app_framework))
    flame_api.CTX.app_framework.log.info("Apps are loaded")


def project_changed_dict(info):
    """Hook for project change action

    Args:
        info (str): info text
    """
    cleanup()

def app_initialized(parent=None):
    """Inicialization of Framework

    Args:
        parent (obj, optional): Parent object. Defaults to None.
    """
    print(">> init of framework")
    flame_api.CTX.app_framework = flame_api.FlameAppFramework()

    print("{} initializing".format(
        flame_api.CTX.app_framework.bundle_name))

    load_apps()


print(">>>>> initialisation of hooks")
"""
Initialisation of the hook is starting from here

First it needs to test if it can import the flame module.
This will happen only in case a project has been loaded.
Then `app_initialized` will load main Framework which will load
all menu objects as flame_apps.
"""

try:
    import flame  # noqa
    app_initialized(parent=None)
except ImportError:
    print("!!!! not able to import flame module !!!!")
print(">>>> app_initialised")

def rescan_hooks():
    import flame  # noqa
    flame.execute_shortcut('Rescan Python Hooks')
print(">>>> rescan_hooks")

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
            'menu_auto_refresh', {})
        if menu_auto_refresh.get('timeline_menu', True):
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

    return _build_app_menu("FlameMenuUniversal")


def get_media_panel_custom_ui_actions():
    """Hook to create submenu in desktop

    Returns:
        list: menu object
    """
    # install AYON and the host
    ayon_flame_install()

    return _build_app_menu("FlameMenuUniversal")
