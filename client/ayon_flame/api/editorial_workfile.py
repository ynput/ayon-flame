"""Editorial workfile of the Flame host.

Flame keeps timelines in its project database and offers no simple way to
dump a project, library or sequence into a file and restore it (no
Python project export, 'flame_archive' needs formatted archives and
Wiretap addressing). The editorial workfile is therefore a small JSON
reference: saving it saves the Flame project natively and records which
Flame project and sequence the AYON task version points to. Opening it
brings that sequence back into the Timeline when it still exists.
"""
import json
import os
from typing import Any, Dict, Optional

import flame

from ayon_core.lib import Logger

from .utils import get_flame_version

log = Logger.get_logger(__name__)

EDITORIAL_WORKFILE_EXTENSION = ".flame"

# Shortcut description of Flame's native project save.
_SAVE_PROJECT_SHORTCUT = "Save Project"

# The host object is re-created by every Flame menu hook, so the current
# workfile lives at module level for the whole Flame session.
_CURRENT_WORKFILE = None


def _get_value(attribute: Any) -> Any:
    """Return the value of a Flame PyAttribute or of a plain value."""
    if hasattr(attribute, "get_value"):
        return attribute.get_value()
    return attribute


def get_current_editorial_workfile() -> Optional[str]:
    return _CURRENT_WORKFILE


def set_current_editorial_workfile(filepath: Optional[str]):
    global _CURRENT_WORKFILE
    _CURRENT_WORKFILE = os.path.normpath(filepath) if filepath else None


def get_timeline_sequence() -> Optional["flame.PySequence"]:
    """Return the sequence opened in the Timeline, if any."""
    clip = flame.timeline.clip
    if isinstance(clip, flame.PySequence):
        return clip
    return None


def save_flame_project():
    """Save the Flame project natively, as the artist would."""
    try:
        flame.execute_shortcut(_SAVE_PROJECT_SHORTCUT)
    except Exception:
        log.warning(
            "Flame project could not be saved with the '%s' shortcut.",
            _SAVE_PROJECT_SHORTCUT,
            exc_info=True,
        )


def get_editorial_state(context: Dict[str, Any]) -> Dict[str, Any]:
    """Collect what the editorial workfile refers to.

    Args:
        context (dict[str, Any]): AYON context with 'project_name',
            'folder_path' and 'task_name'.
    """
    sequence_data = None
    sequence = get_timeline_sequence()
    if sequence is not None:
        sequence_data = {
            "name": _get_value(sequence.name),
            "uid": _get_value(sequence.uid),
        }

    return {
        "flame_project": flame.project.current_project.name,
        "flame_version": get_flame_version()["full"],
        "sequence": sequence_data,
        "context": {
            "project_name": context["project_name"],
            "folder_path": context["folder_path"],
            "task_name": context["task_name"],
        },
    }


def save_editorial_workfile(filepath: str, context: Dict[str, Any]):
    """Save the Flame project and write the editorial workfile.

    The file is written next to the destination and moved into place, so
    a failure never leaves a partial workfile behind.
    """
    save_flame_project()
    data = get_editorial_state(context)

    dirpath = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(dirpath, exist_ok=True)
    tmp_path = os.path.join(
        dirpath, ".{}.{}.tmp".format(os.path.basename(filepath), os.getpid())
    )
    try:
        with open(tmp_path, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=4)
        os.replace(tmp_path, filepath)
    except Exception as error:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError(
            f"Unable to save Flame editorial workfile '{filepath}': {error}"
        ) from error

    set_current_editorial_workfile(filepath)


def _find_sequence(name: str, uid: Optional[str]):
    """Find a sequence of the current project, preferring the same uid."""
    sequences = [
        item
        for item in flame.find_by_name(name)
        if isinstance(item, flame.PySequence)
    ]
    for sequence in sequences:
        if uid and _get_value(sequence.uid) == uid:
            return sequence
    return sequences[0] if sequences else None


def open_editorial_workfile(filepath: str):
    """Open the sequence referenced by the editorial workfile."""
    with open(filepath, "r", encoding="utf-8") as stream:
        data = json.load(stream)

    set_current_editorial_workfile(filepath)

    project_name = flame.project.current_project.name
    if data.get("flame_project") != project_name:
        log.warning(
            "Workfile '%s' was saved in Flame project '%s', the current "
            "Flame project is '%s'.",
            filepath, data.get("flame_project"), project_name,
        )

    sequence_data = data.get("sequence")
    if not sequence_data:
        log.info("Workfile '%s' does not reference a sequence.", filepath)
        return

    sequence = _find_sequence(sequence_data["name"], sequence_data.get("uid"))
    if sequence is None:
        log.warning(
            "Sequence '%s' referenced by '%s' was not found in the Flame "
            "project.", sequence_data["name"], filepath,
        )
        return

    sequence.open()
    flame.set_current_tab("Timeline")
