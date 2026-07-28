from __future__ import annotations

import logging
import os

from pprint import pformat
from typing import Any

from qtpy import QtWidgets

from ayon_core.pipeline import get_current_project_name
from ayon_core.settings import (
    get_current_project_settings,
)
from ayon_core.tools.utils import host_tools


logger = logging.getLogger(__name__)

menu_group_name = 'AYON'


def callback_selection(
    selection,
    function,
    context,
):
    import ayon_flame.api as ayfapi
    ayfapi.CTX.selection = selection
    ayfapi.CTX.context = context
    logger.debug("Hook Selection: \n\t{}".format(
        pformat({
            index: (type(item), item.name)
            for index, item in enumerate(ayfapi.CTX.selection)})
    ))
    function()


_MAIN_WINDOW = None


def _get_main_window():
    global _MAIN_WINDOW
    if _MAIN_WINDOW is None:
        _MAIN_WINDOW = next(
            (
                obj
                for obj in QtWidgets.QApplication.topLevelWidgets()
                if isinstance(obj, QtWidgets.QMainWindow)
            ),
            None
        )
    return _MAIN_WINDOW


class _FlameMenuApp(object):
    def __init__(self, framework):
        self.name = self.__class__.__name__
        self.framework = framework
        self.log = framework.log
        self.menu_group_name = menu_group_name

        # flame module is only available when a
        # flame project is loaded and initialized
        self.flame = None
        try:
            import flame
            self.flame = flame
            self.flame_project_name = flame.project.current_project.name

        except ImportError:
            self.flame = None
            self.flame_project_name = None

        self.prefs = self.framework.prefs.setdefault(self.name, {})
        self.prefs_user = self.framework.prefs_user.setdefault(self.name, {})
        self.prefs_global = self.framework.prefs_global.setdefault(
            self.name,
            {}
        )
        self.tools_helper = host_tools.HostToolsHelper(
            parent=_get_main_window()
        )

    def __getattr__(self, name):
        def method(*args, **kwargs):
            logger.debug('calling %s' % name)
        return method

    def rescan(self, *args, **kwargs):
        if not self.flame:
            try:
                import flame
                self.flame = flame
            except ImportError:
                self.flame = None

        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')
            self.log.info('Rescan Python Hooks')

    def refresh(self, *args, **kwargs):
        self.rescan()

    def build_menu(self) -> dict[str, Any]:
        project_name = get_current_project_name()
        return{
            "actions": [
                {
                    "name": f"0 - {project_name or 'project'}",
                    "isEnabled": False
                }
            ],
            "name": self.menu_group_name,
        }

    def build_script_menu_from_settings(self) -> dict[str, Any]:
        return {}


class FlameMenuProjectConnect(_FlameMenuApp):
    """ Takes care of the preferences dialog as well.
    """

    def build_menu(self) -> dict[str, Any]:
        if not self.flame:
            return {}

        menu = super().build_menu()
        menu['actions'].append({
            "name": "1 - Load...",
            "execute": lambda x: self.tools_helper.show_loader()
        })

        return menu


class _FlameMenuContext(_FlameMenuApp):
    """ Menu that appears in the timeline, batch and universal contexts.
    """

    def build_script_menu_from_settings(self) -> list[dict[str, Any]]:
        """ Load configuration of script menu from project settings.
        """
        project_settings = get_current_project_settings()

        custom_menu = project_settings["flame"]["custom_menu"]
        defs = custom_menu["definition"]
        menu_name = custom_menu["name"]
        enabled = custom_menu["enabled"]

        if not enabled:
            logger.info("Script menu settings is disabled.")
            return {}

        if not defs:
            logger.info("No script menu content, no definition found.")
            return {}

        def add_action(action_def: dict[str, Any]):
            """ Add an action to the menu based on the given definition.
            """

            def execute_action(action_def: dict[str, Any]):
                """ Execute the action.
                """
                if action_def["source_type"] == "python":
                    command = action_def["python"]
                else:
                    file_path = action_def["file"]
                    dirname = os.path.dirname(file_path)
                    basename = os.path.basename(file_path)
                    module_name, _ = os.path.splitext(basename)

                    command = f"""
import importlib.util
spec = importlib.util.spec_from_file_location(
"{module_name}",
"{dirname}/{module_name}.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
getattr(module, "{module_name}")()
"""

                exec(command, {})

            return {
                "name": action_def["title"],
                "execute": lambda x, d=action_def: callback_selection(
                    x,  # selection
                    lambda: execute_action(d),
                    context=self.__class__.__name__
                ),
            }

        def is_valid_action(action_def: dict[str, Any]) -> bool:
            """ Check if the action definition is valid for this menu context.
            """
            return (
                action_def["item_type"] == "action"
                and action_def["action"]["flame_context"] in (
                    self.__class__.__name__,
                    "ALL",
                )
            )

        menu_items = [
            {
                "name": menu_name,
                "actions": [
                    add_action(item["action"])
                    for item in defs
                    if is_valid_action(item)
                ],
                "hierarchy": []
            }
        ]
        for item in defs:
            if item["item_type"] == "menu":
                menu_items.append(
                    {
                        "name": item["menu"]["title"],
                        "actions": [
                            add_action(sitem["action"])
                            for sitem in item["menu"]["items"]
                            if is_valid_action(sitem)
                        ],
                        "hierarchy": [menu_name]
                    }
                )

        return menu_items


    def build_menu(self) -> dict[str, Any]:
        if not self.flame:
            return {}

        menu = super().build_menu()
        menu['actions'].append(
            {
                "name": "1 - Create...",
                "execute": lambda x: callback_selection(
                    x,
                    host_tools.show_publisher(
                        tab="create", parent=_get_main_window()
                    ),
                    context=self.__class__.__name__
                ),
            }
        )
        menu["actions"].append(
            {
                "name": "2 - Publish...",
                "execute": lambda x: callback_selection(
                    x,
                    host_tools.show_publisher(
                        tab="publish", parent=_get_main_window()
                    ),
                    context=self.__class__.__name__
                ),
            }
        )
        menu['actions'].append({
            "name": "3 - Load...",
            "execute": lambda x: self.tools_helper.show_loader()
        })
        return menu


class FlameMenuTimeline(_FlameMenuContext):
    """ Menu that appears in the timeline context.
    """


class FlameMenuBatch(_FlameMenuContext):
    """ Menu that appears in the batch context.
    """


class FlameMenuUniversal(_FlameMenuContext):
    """ Menu that appears in the universal context.
    """
