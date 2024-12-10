from copy import deepcopy
from pprint import pformat

from qtpy import QtWidgets

from ayon_core.pipeline import get_current_project_name
from ayon_core.tools.utils import host_tools

menu_group_name = 'AYON'

default_flame_export_presets = {
    'Publish': {
        'PresetVisibility': 2,
        'PresetType': 0,
        'PresetFile': 'OpenEXR/OpenEXR (16-bit fp PIZ).xml'
    },
    'Preview': {
        'PresetVisibility': 3,
        'PresetType': 2,
        'PresetFile': 'Generate Preview.xml'
    },
    'Thumbnail': {
        'PresetVisibility': 3,
        'PresetType': 0,
        'PresetFile': 'Generate Thumbnail.xml'
    }
}    


def callback_selection(selection, function):
    import ayon_flame.api as ayfapi
    ayfapi.CTX.selection = selection
    print("Hook Selection: \n\t{}".format(
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
        self.dynamic_menu_data = {}

        # flame module is only available when a
        # flame project is loaded and initialized
        self.flame = None
        try:
            import flame
            self.flame = flame
        except ImportError:
            self.flame = None

        self.flame_project_name = flame.project.current_project.name
        self.prefs = self.framework.prefs_dict(self.framework.prefs, self.name)
        self.prefs_user = self.framework.prefs_dict(
            self.framework.prefs_user, self.name)
        self.prefs_global = self.framework.prefs_dict(
            self.framework.prefs_global, self.name)

        self.mbox = QtWidgets.QMessageBox()
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
            print('calling %s' % name)
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


class FlameMenuProjectConnect(_FlameMenuApp):

    # flameMenuProjectconnect app takes care of the preferences dialog as well

    def __init__(self, framework):
        _FlameMenuApp.__init__(self, framework)

    def __getattr__(self, name):
        def method(*args, **kwargs):
            project = self.dynamic_menu_data.get(name)
            if project:
                self.link_project(project)
        return method

    def build_menu(self):
        if not self.flame:
            return []

        menu = deepcopy(self.menu)

        # menu['actions'].append({
        #     "name": "Workfiles...",
        #     "execute": lambda x: self.tools_helper.show_workfiles()
        # })
        menu['actions'].append({
            "name": "1 - Load...",
            "execute": lambda x: self.tools_helper.show_loader()
        })
        # menu['actions'].append({
        #     "name": "Manage...",
        #     "execute": lambda x: self.tools_helper.show_scene_inventory()
        # })
        menu['actions'].append({
            "name": "2 - Library...",
            "execute": lambda x: self.tools_helper.show_library_loader()
        })

        return menu

    def refresh(self, *args, **kwargs):
        self.rescan()

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


class FlameMenuTimeline(_FlameMenuApp):

    # flameMenuProjectconnect app takes care of the preferences dialog as well

    def __init__(self, framework):
        _FlameMenuApp.__init__(self, framework)

    def __getattr__(self, name):
        def method(*args, **kwargs):
            project = self.dynamic_menu_data.get(name)
            if project:
                self.link_project(project)
        return method

    def build_menu(self):
        if not self.flame:
            return []

        menu = deepcopy(self.menu)

        menu['actions'].append(
            {
                "name": "1 - Create...",
                "execute": lambda x: callback_selection(
                    x, host_tools.show_publisher(
                        tab="create", parent=_get_main_window()
                    )
                ),
            }
        )
        menu["actions"].append(
            {
                "name": "2 - Publish...",
                "execute": lambda x: callback_selection(
                    x, host_tools.show_publisher(
                        tab="publish", parent=_get_main_window()
                    )
                ),
            }
        )
        menu['actions'].append({
            "name": "3 - Load...",
            "execute": lambda x: self.tools_helper.show_loader()
        })
        # menu['actions'].append({
        #     "name": "Manage...",
        #     "execute": lambda x: self.tools_helper.show_scene_inventory()
        # })
        menu['actions'].append({
            "name": "4 - Library...",
            "execute": lambda x: self.tools_helper.show_library_loader()
        })

        return menu

    def refresh(self, *args, **kwargs):
        self.rescan()

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


class FlameMenuUniversal(_FlameMenuApp):

    # flameMenuProjectconnect app takes care of the preferences dialog as well

    def __init__(self, framework):
        _FlameMenuApp.__init__(self, framework)

    def __getattr__(self, name):
        def method(*args, **kwargs):
            project = self.dynamic_menu_data.get(name)
            if project:
                self.link_project(project)
        return method

    def build_menu(self):
        if not self.flame:
            return []

        menu = deepcopy(self.menu)

        menu['actions'].append({
            "name": "1 - Load...",
            "execute": lambda x: callback_selection(
                x, self.tools_helper.show_loader)
        })
        # menu['actions'].append({
        #     "name": "Manage...",
        #     "execute": lambda x: self.tools_helper.show_scene_inventory()
        # })
        menu['actions'].append({
            "name": "2 - Library...",
            "execute": lambda x: self.tools_helper.show_library_loader()
        })

        return menu

    def refresh(self, *args, **kwargs):
        self.rescan()

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
