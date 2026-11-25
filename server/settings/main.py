from ayon_server.settings import BaseSettingsModel, SettingsField

from .project_roots import ProjectRoots, DEFAULT_PROJECT_ROOTS_SETTINGS
from .bookmarks import BookmarksModel, DEFAULT_BOOKMARK_SETTINGS
from .export_presets import ExportPresetsModel, DEFAULT_EXPORT_PRESETS_SETTINGS
from .imageio import FlameImageIOModel, DEFAULT_IMAGEIO_SETTINGS
from .create_plugins import CreatePluginsModel, DEFAULT_CREATE_SETTINGS
from .publish_plugins import PublishPluginsModel, DEFAULT_PUBLISH_SETTINGS
from .loader_plugins import LoaderPluginsModel, DEFAULT_LOADER_SETTINGS
from .custom_menu import CustomMenuSettings, DEFAULT_CUSTOM_MENU_SETTINGS


class InstallOpenTimelineIOToFlameModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        default=True,
        title="Enable"
    )


# hooks configurations
class FlameHooksModel(BaseSettingsModel):
    _layout = "expanded"
    InstallOpenTimelineIOToFlame: InstallOpenTimelineIOToFlameModel = \
        SettingsField(
            default_factory=InstallOpenTimelineIOToFlameModel,
            title="Install OpenTimelineIO to Flame"
        )
    project_setup: bool = SettingsField(
        default=True,
        title="Automated Project setup",
        description=(
            "Create and setup a Flame project matching AYON project."
        ),
    )


class FlameSettings(BaseSettingsModel):
    flame_projects_root: ProjectRoots = SettingsField(
        default_factory=ProjectRoots,
        title="Flame Project Management",
        description="Required for Project Bookmarks and Export Presets",
    )
    bookmarks: BookmarksModel = SettingsField(
        default_factory=BookmarksModel,
        title="Project Bookmarks",
    )
    export_presets: ExportPresetsModel = SettingsField(
        default_factory=ExportPresetsModel,
        title="Export Presets",
    )
    imageio: FlameImageIOModel = SettingsField(
        default_factory=FlameImageIOModel,
        title="Color Management (ImageIO)"
    )
    hooks: FlameHooksModel = SettingsField(
        default_factory=FlameHooksModel,
        title="Hooks"
    )
    create: CreatePluginsModel = SettingsField(
        default_factory=CreatePluginsModel,
        title="Create plugins"
    )
    publish: PublishPluginsModel = SettingsField(
        default_factory=PublishPluginsModel,
        title="Publish plugins"
    )
    load: LoaderPluginsModel = SettingsField(
        default_factory=LoaderPluginsModel,
        title="Loader plugins"
    )
    custom_menu: CustomMenuSettings = SettingsField(
        default_factory=CustomMenuSettings,
        title="Custom Menu"
    )


DEFAULT_VALUES = {
    "flame_projects_root": DEFAULT_PROJECT_ROOTS_SETTINGS,
    "bookmarks": DEFAULT_BOOKMARK_SETTINGS,
    "export_presets": DEFAULT_EXPORT_PRESETS_SETTINGS,
    "imageio": DEFAULT_IMAGEIO_SETTINGS,
    "create": DEFAULT_CREATE_SETTINGS,
    "publish": DEFAULT_PUBLISH_SETTINGS,
    "load": DEFAULT_LOADER_SETTINGS,
    "custom_menu": DEFAULT_CUSTOM_MENU_SETTINGS
}
