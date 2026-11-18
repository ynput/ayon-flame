from pydantic import validator

from ayon_server.exceptions import BadRequestException
from ayon_server.settings import (
    SettingsField, BaseSettingsModel, ensure_unique_names
)


class BookmarkItem(BaseSettingsModel):
    name: str = SettingsField("", title="Name")
    bookmark_label: str = SettingsField(
        "",
        title="Label Template",
        min_length=1,
        description="Template for label of bookmark in mediahub",
    )
    path_template: str = SettingsField("", title="Path Template", min_length=1)


class BookmarksModel(BaseSettingsModel):
    enabled: bool = SettingsField(default=True, title="Enable Bookmarks")
    remove_default_bookmarks: bool = SettingsField(
        default=False,
        title="Remove Flame Default Bookmarks",
        description=(
            "Remove the default Autodesk bookmarks in Project category: "
            "Project Home and Project Setups"
        ),
    )
    bookmark_paths: list[BookmarkItem] = SettingsField(
        default_factory=list,
        title="Bookmark Paths",
        description="Available template fields are 'root' and 'project' only",
    )

    @validator("bookmark_paths")
    def validate_unique_name(cls, value):
        ensure_unique_names(value)
        return value

    @validator("bookmark_paths")
    def validate_unique_label(cls, value):
        bookmark_labels = []
        for obj in value:
            if not hasattr(obj, "bookmark_label"):
                raise BadRequestException(
                    "Object without bookmark_label provided"
                )
            if obj.bookmark_label not in bookmark_labels:
                bookmark_labels.append(obj.bookmark_label)
            else:
                raise BadRequestException(
                    f"Duplicate bookmark_label '{obj.bookmark_label}'"
                )
        return value


DEFAULT_BOOKMARK_SETTINGS = {
    "enabled": True,
    "remove_default_bookmarks": False,
    "bookmark_paths": [
        {
            "name": "Project Root",
            "bookmark_label": "{project[name]}",
            "path_template": "{root[work]}/{project[name]}",
        },
    ],
}
