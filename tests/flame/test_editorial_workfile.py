"""Editorial workfile host, `FlameHost` and `api.editorial_workfile`."""

import json
import os

import flame
import pytest

from ayon_flame.api import batch_utils, editorial_workfile, pipeline
from ayon_flame.api.lib import CTX

from helpers import (
    EDIT_TASK,
    SHOT_OTHER_TASK,
    SHOT_PATH,
    SHOT_TASK,
    add_note,
    batch_product_data,
    open_in_timeline,
    wait_for,
    workfile_path,
)


def _current_project_name():
    return flame.projects.current_project.name


def _read(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


@pytest.fixture
def no_project_save(monkeypatch):
    """Skip the native Flame project save, for tests about the file only."""
    monkeypatch.setattr(editorial_workfile, "save_flame_project", lambda: None)


def test_failed_project_save_fails_the_save(tmp_path, monkeypatch):
    """No editorial workfile claims a Flame project that was not saved."""

    def _fail(description):
        raise RuntimeError(f"no shortcut {description}")

    monkeypatch.setattr(flame, "execute_shortcut", _fail)
    path = tmp_path / "edit_v001.flameedit"

    with pytest.raises(RuntimeError, match="could not be saved"):
        pipeline.FlameHost().save_workfile(str(path))

    assert not path.exists()
    assert pipeline.FlameHost().get_current_workfile() is None


def test_save_writes_reference_to_timeline_sequence(make_sequence, tmp_path):
    sequence = make_sequence()
    open_in_timeline(sequence)
    path = str(tmp_path / "edit_v001.flameedit")

    pipeline.FlameHost().save_workfile(path)

    data = _read(path)
    assert data["flame_project"] == _current_project_name()
    assert data["flame_version"] == flame.get_version()
    assert data["sequence"] == {
        "name": sequence.name.get_value(),
        "uid": sequence.uid.get_value(),
    }
    assert data["context"] == {
        "project_name": os.environ["AYON_PROJECT_NAME"],
        "folder_path": SHOT_PATH,
        "task_name": SHOT_TASK,
    }
    assert pipeline.FlameHost().get_current_workfile() == path


def test_save_without_timeline_sequence(
    no_project_save, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        editorial_workfile, "get_timeline_sequence", lambda: None
    )
    path = str(tmp_path / "edit_v001.flameedit")

    pipeline.FlameHost().save_workfile(path)

    assert _read(path)["sequence"] is None


def test_save_without_workfile_asks_for_save_as():
    with pytest.raises(RuntimeError, match="use Save As"):
        pipeline.FlameHost().save_workfile()


def test_failed_save_keeps_previous_workfile(
    no_project_save, tmp_path, monkeypatch
):
    path = tmp_path / "edit_v001.flameedit"
    pipeline.FlameHost().save_workfile(str(path))
    previous = path.read_text()
    monkeypatch.setattr(
        editorial_workfile, "get_editorial_state", lambda context: {object()}
    )

    with pytest.raises(RuntimeError, match="Unable to save"):
        pipeline.FlameHost().save_workfile(str(path))

    assert path.read_text() == previous
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]


def test_current_workfile_belongs_to_task(
    no_project_save, tmp_path, monkeypatch
):
    path = str(tmp_path / "edit_v001.flameedit")
    host = pipeline.FlameHost()
    host.save_workfile(path)
    assert host.get_current_workfile() == path

    monkeypatch.setenv("AYON_TASK_NAME", SHOT_OTHER_TASK)

    assert host.get_current_workfile() is None


def test_save_with_context_uses_session_context(
    no_project_save, batch_group, edit_context
):
    """A Batch menu action left 'CTX.context' set, the editorial workfile
    still follows the session, not the batch group products."""
    add_note(
        batch_group, batch_utils._METADATA_NODE_NAME,
        batch_product_data(
            SHOT_PATH, SHOT_OTHER_TASK, batch_group.name.get_value()
        ),
    )
    CTX.context = "FlameMenuBatch"
    host = pipeline.FlameHost()
    folder_entity, task_entity = edit_context
    path = workfile_path(host, folder_entity, task_entity, 1)

    host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )

    context = _read(path)["context"]
    assert context["folder_path"] == folder_entity["path"]
    assert context["task_name"] == EDIT_TASK
    assert host.get_current_workfile() == path


def test_context_follows_batch_menu(batch_group):
    add_note(
        batch_group, batch_utils._METADATA_NODE_NAME,
        batch_product_data(
            SHOT_PATH, SHOT_OTHER_TASK, batch_group.name.get_value()
        ),
    )

    CTX.context = "FlameMenuTimeline"
    assert pipeline.FlameHost().get_current_context()["task_name"] == SHOT_TASK

    CTX.context = "FlameMenuBatch"
    assert pipeline.FlameHost().get_current_context()["task_name"] == (
        SHOT_OTHER_TASK
    )
    # The Workfiles tool of the main menu always uses the session.
    assert pipeline.FlameEditorialHost().get_current_context()[
        "task_name"
    ] == SHOT_TASK


def test_open_brings_sequence_back(no_project_save, make_sequence, tmp_path):
    saved = make_sequence()
    other = make_sequence()
    open_in_timeline(saved)
    path = str(tmp_path / "edit_v001.flameedit")
    pipeline.FlameHost().save_workfile(path)
    open_in_timeline(other)

    pipeline.FlameHost().open_workfile(path)

    uid = saved.uid.get_value()

    def _saved_is_open():
        opened = editorial_workfile.get_timeline_sequence()
        return opened is not None and opened.uid.get_value() == uid

    assert wait_for(_saved_is_open), "The saved sequence is not open."
    assert pipeline.FlameHost().get_current_workfile() == path


def test_open_prefers_sequence_with_same_uid(make_sequence):
    first = make_sequence()
    name = first.name.get_value()
    second = make_sequence(name)

    found = editorial_workfile._find_sequence(name, second.uid.get_value())

    assert found.uid.get_value() == second.uid.get_value()
    assert editorial_workfile._find_sequence(name, "missing uid") is not None
    assert editorial_workfile._find_sequence(f"{name}_missing", None) is None


def test_open_missing_sequence_keeps_workfile(tmp_path):
    path = tmp_path / "edit_v001.flameedit"
    path.write_text(json.dumps({
        "flame_project": "another_project",
        "sequence": {"name": "ayon_test_missing_sequence", "uid": "none"},
    }))

    pipeline.FlameHost().open_workfile(str(path))

    assert pipeline.FlameHost().get_current_workfile() == str(path)


def test_open_workfile_without_sequence(tmp_path):
    path = tmp_path / "edit_v001.flameedit"
    path.write_text(json.dumps({
        "flame_project": _current_project_name(), "sequence": None,
    }))

    pipeline.FlameHost().open_workfile(str(path))

    assert pipeline.FlameHost().get_current_workfile() == str(path)
