import logging
from copy import deepcopy
from pprint import pformat

from qtpy import QtWidgets

from ayon_core.pipeline import get_current_project_name
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

        project_name = get_current_project_name()
        self.menu = {
            "actions": [
                {
                    "name": f"0 - {project_name or 'project'}",
                    "isEnabled": False
                }
            ],
            "name": self.menu_group_name,
        }
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


class FlameMenuProjectConnect(_FlameMenuApp):
    """ Takes care of the preferences dialog as well.
    """

    def build_menu(self):
        if not self.flame:
            return []

        menu = deepcopy(self.menu)

        menu['actions'].append({
            "name": "1 - Load...",
            "execute": lambda x: self.tools_helper.show_loader()
        })
        menu['actions'].append({
            "name": "2 - Library...",
            "execute": lambda x: self.tools_helper.show_library_loader()
        })

        return menu


class FlameMenuTimeline(_FlameMenuApp):
    """ Menu that appears in the timeline context.
    """

    def build_menu(self):
        if not self.flame:
            return []

        menu = deepcopy(self.menu)

        menu['actions'].append(
            {
                "name": "1 - Create...",
                "execute": lambda x: callback_selection(
                    x,
                    host_tools.show_publisher(
                        tab="create", parent=_get_main_window()
                    ),
                    context="FlameMenuTimeline"
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
                    context="FlameMenuTimeline"
                ),
            }
        )
        menu['actions'].append({
            "name": "3 - Load...",
            "execute": lambda x: self.tools_helper.show_loader()
        })
        # TODO: enable once scene inventory is ready
        # menu['actions'].append({
        #     "name": "Manage...",
        #     "execute": lambda x: self.tools_helper.show_scene_inventory()
        # })
        menu['actions'].append({
            "name": "4 - Library...",
            "execute": lambda x: self.tools_helper.show_library_loader()
        })

        return menu


class FlameMenuUniversal(_FlameMenuApp):
    """ Menu that appears in the universal context.
    """

    def build_menu(self):
        if not self.flame:
            return []

        menu = deepcopy(self.menu)
        menu['actions'].append(
            {
                "name": "1 - Create...",
                "execute": lambda x: callback_selection(
                    x,
                    host_tools.show_publisher(
                        tab="create", parent=_get_main_window()
                    ),
                    context="FlameMenuUniversal"
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
                    context="FlameMenuUniversal"
                ),
            }
        )
        menu['actions'].append({
            "name": "3 - Load...",
            "execute": lambda x: callback_selection(
                x,
                self.tools_helper.show_loader,
                context="FlameMenuUniversal"
            )
        })
        menu['actions'].append({
            "name": "4 - Library...",
            "execute": lambda x: self.tools_helper.show_library_loader()
        })

        return menu
