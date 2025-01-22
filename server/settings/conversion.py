from typing import Any


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
    return overrides
