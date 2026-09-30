from pydantic import validator
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    ensure_unique_names,
)


_DEFAULT_FLAME_OCIO_CONFIG = (
    "/opt/Autodesk/colour_mgmt/configs/legacy_configs/syncolor_aces1.1_config/config.ocio"
)


class ImageIOFileRuleModel(BaseSettingsModel):
    name: str = SettingsField("", title="Rule name")
    pattern: str = SettingsField("", title="Regex pattern")
    colorspace: str = SettingsField("", title="Colorspace name")
    ext: str = SettingsField("", title="File extension")


class ImageIOFileRulesModel(BaseSettingsModel):
    activate_host_rules: bool = SettingsField(False)
    rules: list[ImageIOFileRuleModel] = SettingsField(
        default_factory=list,
        title="Rules"
    )

    @validator("rules")
    def validate_unique_outputs(cls, value):
        ensure_unique_names(value)
        return value


class ImageIORemappingRulesModel(BaseSettingsModel):
    host_native_name: str = SettingsField(
        title="Application native colorspace name"
    )
    ocio_name: str = SettingsField(title="OCIO colorspace name")


class ImageIORemappingModel(BaseSettingsModel):
    rules: list[ImageIORemappingRulesModel] = SettingsField(
        default_factory=list
    )


class ProfileNamesMappingInputsModel(BaseSettingsModel):
    _layout = "expanded"

    flameName: str = SettingsField("", title="Flame name")
    ocioName: str = SettingsField("", title="OCIO name")


class ProfileNamesMappingModel(BaseSettingsModel):
    _layout = "expanded"

    inputs: list[ProfileNamesMappingInputsModel] = SettingsField(
        default_factory=list,
        title="Profile names mapping"
    )


class ImageIOProjectModel(BaseSettingsModel):
    colourPolicy: str = SettingsField(
        "ACES 1.1",
        title="SyncColor Policy (name or path)",
        description=(
            "Define SynColor preset to use when creating a new project "
            "(Flame < 2026)."
        )
    )
    defaultOcioConfig: str = SettingsField(
        _DEFAULT_FLAME_OCIO_CONFIG,
        title="OCIO default config",
        description=(
            "Path to a default OCIO config to use when creating a new project "
            "(Flame >= 2026)\n"
            "Only used if **no global OCIO environment variable is set**"
        ),
    )
    frameDepth: str = SettingsField(
        "16-bit fp",
        title="Image Depth"
    )
    fieldDominance: str = SettingsField(
        "PROGRESSIVE",
        title="Field Dominance"
    )


class FlameImageIOModel(BaseSettingsModel):
    _isGroup = True
    activate_host_color_management: bool = SettingsField(
        True, title="Enable Color Management"
    )
    remapping: ImageIORemappingModel = SettingsField(
        title="Remapping colorspace names",
        default_factory=ImageIORemappingModel
    )
    file_rules: ImageIOFileRulesModel = SettingsField(
        default_factory=ImageIOFileRulesModel,
        title="File Rules"
    )
    # NOTE 'project' attribute was expanded to this model but that caused
    #   inconsistency with v3 settings and harder conversion handling
    #   - it can be moved back but keep in mind that it must be handled in v3
    #       conversion script too
    project: ImageIOProjectModel = SettingsField(
        default_factory=ImageIOProjectModel,
        title="Project"
    )
    profilesMapping: ProfileNamesMappingModel = SettingsField(
        default_factory=ProfileNamesMappingModel,
        title="Profile names mapping"
    )


DEFAULT_IMAGEIO_SETTINGS = {
    "project": {
        "colourPolicy": "ACES 1.1",
        "defaultOcioConfig": _DEFAULT_FLAME_OCIO_CONFIG,
        "frameDepth": "16-bit fp",
        "fieldDominance": "PROGRESSIVE"
    },
    "profilesMapping": {
        "inputs": [
            {
                "flameName": "ACEScg",
                "ocioName": "ACES - ACEScg"
            },
            {
                "flameName": "Rec.709 video",
                "ocioName": "Output - Rec.709"
            }
        ]
    }
}
