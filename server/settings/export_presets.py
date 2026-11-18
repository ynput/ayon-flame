from ayon_server.settings import SettingsField, BaseSettingsModel


class ExportPresetsModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        default=False,
        title="Enable Export Presets",
        description=(
            "Copy export presets from a central folder into the Flame "
            "project on each launch, so they appear under Project presets. "
            "Kept in sync: presets removed centrally are removed from the "
            "project, presets made in the project are kept."
        ),
    )
    source_dir: str = SettingsField(
        "",
        title="Central Presets Folder",
        description=(
            "One subfolder per Flame export type: audio_file, "
            "distribution_package, file_sequence, movie_file, "
            "sequence_publish. Presets can be grouped in folders inside "
            "these, e.g. movie_file/AYON. Template fields: 'root', 'project'."
        ),
    )


DEFAULT_EXPORT_PRESETS_SETTINGS = {
    "enabled": False,
    "source_dir": "",
}
