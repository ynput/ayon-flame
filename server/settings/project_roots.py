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
    label: str = SettingsField("", title="Label")
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


DEFAULT_PROJECT_ROOTS_SETTINGS = {
    "variants": [
        {
            "name": "",
            "label": "Default",
            "project_path": {
                "windows": [],
                "linux": ["/opt/Autodesk/project"],
                "darwin": ["/opt/Autodesk/project"],
            },
        },
    ],
}
