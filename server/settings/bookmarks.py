from pydantic import validator

from ayon_server.settings import (
    SettingsField, BaseSettingsModel, ensure_unique_names
)

class MultiplatformStrList(BaseSettingsModel):
    windows: list[str] = SettingsField(default_factory=list, title="Windows")
    linux: list[str] = SettingsField(default_factory=list, title="Linux")
    darwin: list[str] = SettingsField(default_factory=list, title="MacOS")


class AppVariant(BaseSettingsModel):
    name: str = SettingsField("", title="Name")
    project_path: MultiplatformStrList = SettingsField(
        default_factory=MultiplatformStrList,
        title="Path to Projects Folder",
    )


class ProjectRoots(BaseSettingsModel):
    variants: list[AppVariant] = SettingsField(
        default_factory=list,
        title="Variants",
        description=(
            "Where projects may be saved for different installations of Flame"
        ),
    )

    @validator("variants")
    def validate_unique_name(cls, value):
        ensure_unique_names(value)
        return value


class BookmarkItem(BaseSettingsModel):
    name: str = SettingsField("", title="Name")
    bookmark_label: str = SettingsField(
        "",
        title="Label Template",
        min_length=1,
        description="Template for label of bookmark in mediahub",
    )
    path_template: str = SettingsField("", title="Path Template", min_length=1)

    @validator("name")
    def validate_unique_name(cls, value):
        ensure_unique_names(value)
        return value

    @validator("bookmark_label")
    def validate_unique_label(cls, value):
        ensure_unique_names(value)
        return value


class BookmarksModel(BaseSettingsModel):
    enabled: bool = SettingsField(default=True, title="Enable Bookmarks")
    flame_projects_root: ProjectRoots = SettingsField(
        default_factory=ProjectRoots,
        title="Flame Projects' Location",
        description="Required for saving bookmarks",
    )
    bookmark_paths: list[BookmarkItem] = SettingsField(
        default_factory=list,
        title="Bookmark Paths",
        description="Available template fields are 'root' and 'project' only",
    )


DEFAULT_BOOKMARK_SETTINGS = {
    "enabled": True,
    "flame_projects_root": {
        "variants": [
            {
                "name": "",
                "project_path": {
                    "windows": [],
                    "linux": ["/opt/Autodesk/project"],
                    "darwin": ["/opt/Autodesk/project"],
                },
            },
        ],
    },
    "bookmark_paths": [
        {
            "name": "Project Root",
            "bookmark_label": "{project[name]}",
            "path_template": "{root[work]}/{project[name]}",
        },
    ],
}
