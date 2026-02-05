from typing import Any


def _convert_collect_shots_plugins_1_3_1(
    overrides: dict[str, Any]
):
    """Converts settings from "ExtractProductResources".

    1.3.0 is the latest version using the old way
    """
    publish_overrides = overrides.get("publish", {})
    if not publish_overrides:
        # Legacy settings not found
        return

    extract_product_resources = publish_overrides["ExtractProductResources"]
    legacy_keep_original_representation = extract_product_resources.get(
        "keep_original_representation", None)
    legacy_export_presets_mapping = extract_product_resources.get(
        "export_presets_mapping", None)
    if (
        legacy_keep_original_representation is None or
        legacy_export_presets_mapping is None
    ):
        # Legacy settings not found
        return

    legacy_export_presets_mapping = extract_product_resources.pop(
        "export_presets_mapping")
    legacy_keep_original_representation = extract_product_resources.pop(
        "keep_original_representation")
    additional_representation_export = (
        overrides["publish"]["ExtractProductResources"].setdefault(
            "additional_representation_export", {})
    )
    additional_representation_export["export_presets_mapping"] = (
        legacy_export_presets_mapping)
    additional_representation_export["keep_original_representation"] = (
        legacy_keep_original_representation)


def _convert_collect_shots_plugins_1_1_0(
    overrides: dict[str, Any]
):
    """Report settings from "CollectTimelineInstances"
    to "CollectShot".

    1.0.0 is the latest version using the old way
    """
    publish_overrides = overrides.get("publish", {})
    if "CollectTimelineInstances" not in publish_overrides:
        # Legacy settings not found
        return

    collect_shot_data = overrides["publish"].pop("CollectTimelineInstances")
    overrides["publish"]["CollectShot"] = collect_shot_data


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    _convert_collect_shots_plugins_1_1_0(overrides)
    _convert_collect_shots_plugins_1_3_1(overrides)
    return overrides
