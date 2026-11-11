"""Flame project save rewrites the Batch workfile of the batch group.

`startup/AYON_in_flame.py` is a Flame Python hook, its `project_saved`
calls `pipeline.refresh_batch_workfile`.
"""

import os
import sys
import time

import flame
import pytest

from ayon_flame.api import batch_utils, pipeline

from helpers import add_note, batch_setup_text, wait_for


@pytest.fixture
def startup_hook():
    """The 'AYON_in_flame' hook module Flame loaded from this checkout."""
    import ayon_flame

    expected = os.path.join(
        os.path.dirname(ayon_flame.__file__), "startup", "AYON_in_flame.py"
    )
    for module in list(sys.modules.values()):
        module_file = getattr(module, "__file__", None) or ""
        if os.path.normpath(module_file) == os.path.normpath(expected):
            return module
    pytest.fail(f"Flame did not load the hook {expected}")


@pytest.fixture
def saved_batch(batch_group, tmp_path):
    """A batch group with a Batch workfile saved in this session."""
    path = str(tmp_path / "sh010_v001.flamebatch")
    pipeline.FlameBatchHost().save_workfile(path)
    return batch_group, path


def test_refresh_rewrites_session_workfile(flame_settings, saved_batch):
    batch, path = saved_batch
    add_note(batch, "after_save")

    pipeline.refresh_batch_workfile()

    assert "after_save" in batch_setup_text(path)


def test_refresh_follows_setting(flame_settings, saved_batch):
    batch, path = saved_batch
    flame_settings["flame"]["update_batch_workfile"]["enabled"] = False
    add_note(batch, "after_save")

    pipeline.refresh_batch_workfile()

    assert "after_save" not in batch_setup_text(path)


def test_refresh_without_session_workfile(flame_settings, batch_group):
    """A batch group never saved as a Batch workfile writes nothing."""
    assert pipeline.FlameBatchHost().get_current_workfile() is None

    pipeline.refresh_batch_workfile()

    assert not batch_utils._SESSION_BATCH_WORKFILES


def test_hook_skips_auto_save(flame_settings, saved_batch, startup_hook):
    batch, path = saved_batch
    add_note(batch, "after_save")

    startup_hook.project_saved(flame.projects.current_project.name, 0.1, True)
    assert "after_save" not in batch_setup_text(path)

    startup_hook.project_saved(flame.projects.current_project.name, 0.1, False)
    assert "after_save" in batch_setup_text(path)


def test_save_project_shortcut_rewrites_workfile(flame_settings, saved_batch):
    """The real Flame project save runs the hook."""
    batch, path = saved_batch
    add_note(batch, "after_project_save")
    saved_before = os.path.getmtime(path)
    time.sleep(1)

    flame.execute_shortcut("Save Project")

    assert wait_for(lambda: os.path.getmtime(path) > saved_before, 30), (
        "The Batch workfile was not written by the project save."
    )
    assert "after_project_save" in batch_setup_text(path)
