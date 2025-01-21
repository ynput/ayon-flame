from typing import Any


def _convert_collect_shots_plugins_1_1_0(
    overrides: dict[str, Any]
):
    """Report settings from "CollectTimelineInstances"
    to "CollectShot".

    1.0.0 is the latest version using the old way
    """
    if "CollectTimelineInstances" not in overrides["publish"]:
        # Legacy settings not found
        return

    if "CollectShot" in overrides["publish"]:
        # Already new settings
        return

    collect_shot_data = overrides["publish"].pop("CollectTimelineInstances")
    overrides["publish"]["CollectShot"] = collect_shot_data


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    _convert_collect_shots_plugins_1_1_0(overrides)
    return overrides
