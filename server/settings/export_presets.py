from ayon_server.settings import SettingsField, BaseSettingsModel


class ExportPresetsModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        default=False,
        title="Enable Export Presets",
        description=(
            "Copy export presets from a central folder into the Flame "
            "project on each launch, so they appear under Project presets"
        ),
    )
    source_dir: str = SettingsField(
        "",
        title="Central Presets Folder",
        description=(
            "Folder with one subfolder per export type, like Flame's shared "
            "export presets (file_sequence, movie_file, sequence_publish...). "
            "Presets removed from it are also removed from projects; presets "
            "made in the project are kept. Available template fields are "
            "'root' and 'project' only."
        ),
    )


DEFAULT_EXPORT_PRESETS_SETTINGS = {
    "enabled": False,
    "source_dir": "",
}
