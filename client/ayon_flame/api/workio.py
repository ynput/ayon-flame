"""Host API required Work Files tool"""
import os
import tempfile

import flame

from . import batch_utils

exported_project_ext = ".otoc"

# Value returned by 'flame.get_current_tab()' for the Batch page.
# 'flame.set_current_tab' documents the full tab list as
# "MediaHub, Conform, Timeline, Effects, Batch, Tools".
BATCH_TAB = "Batch"


def _is_batch_tab(tab: object) -> bool:
    """Return whether the given value is the Flame Batch page.

    'MediaHub', 'Conform', 'Timeline', 'Effects', 'Batch' and 'Tools' are
    the tabs documented by 'flame.set_current_tab'. BFX is a render context,
    not a tab, and is therefore not matched here.

    Any unexpected value - including 'None' - is treated as "not Batch" so
    that workfile operations never target the wrong context.
    """
    if not isinstance(tab, str):
        return False
    return tab.strip().lower() == BATCH_TAB.lower()


def is_batch_tab() -> bool:
    """Return whether the Batch page is the active Flame tab.

    A failure to read the tab is treated as "not Batch".
    """
    try:
        tab = flame.get_current_tab()
    except Exception:
        return False
    return _is_batch_tab(tab)


def file_extensions():
    return [exported_project_ext]


def has_unsaved_changes():
    raise NotImplementedError("Flame uses native workfile management")


def save_file(filepath):
    """Save the active Batch group as consolidated JSON to 'filepath'.

    The path (and therefore the version) is allocated by AYON Core and is
    used as given. The file is written to a temporary sibling first and moved
    into place, so a failure never leaves a partial file at 'filepath'.

    Raises:
        NotImplementedError: When the Batch page is not the active tab.
        RuntimeError: When there is no active Batch group or the file cannot
            be written.
    """
    if not is_batch_tab():
        raise NotImplementedError("Flame uses native workfile management")

    if not filepath:
        raise RuntimeError(
            "Cannot save a Flame Batch workfile without a destination path."
        )

    try:
        batch = batch_utils.get_current_batch()
    except RuntimeError as error:
        raise RuntimeError(
            "No active Flame Batch Group to work with."
        ) from error

    dirpath = os.path.dirname(os.path.abspath(filepath))
    temp_path = None
    try:
        os.makedirs(dirpath, exist_ok=True)
        handle, temp_path = tempfile.mkstemp(
            prefix=".ayon_batch_", suffix=".tmp", dir=dirpath
        )
        os.close(handle)
        batch_utils.save_batch_as_consolidated_json(batch, temp_path)
        os.replace(temp_path, filepath)
        temp_path = None
    except Exception as error:
        raise RuntimeError(
            f"Unable to save Flame Batch workfile '{filepath}': {error}"
        ) from error
    finally:
        if temp_path is not None and os.path.exists(temp_path):
            os.remove(temp_path)


def open_file(filepath):
    raise NotImplementedError("Flame uses native workfile management")


def current_file():
    raise NotImplementedError("Flame uses native workfile management")


def work_root(session):
    return os.path.normpath(session["AYON_WORKDIR"])
