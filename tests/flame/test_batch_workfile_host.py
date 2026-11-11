"""Batch workfile host, `ayon_flame.api.pipeline.FlameBatchHost`."""

import json
import os

import flame
import pytest

from ayon_flame.api import batch_utils, pipeline
from ayon_flame.constants import (
    BATCH_WORKFILE_EXTENSION,
    EDITORIAL_WORKFILE_EXTENSION,
)

from helpers import (
    SHOT_OTHER_TASK,
    SHOT_PATH,
    SHOT_TASK,
    add_note,
    add_write_node,
    batch_product_data,
    batch_setup_text,
    get_batch_group_names,
    get_node,
    workfile_path,
)


@pytest.fixture
def batch_host():
    return pipeline.FlameBatchHost()


def test_workfile_extensions(batch_host):
    assert batch_host.get_workfile_extensions() == [BATCH_WORKFILE_EXTENSION]
    assert pipeline.FlameHost().get_workfile_extensions() == [
        EDITORIAL_WORKFILE_EXTENSION
    ]
    assert batch_host.name == pipeline.FlameHost.name


def test_save_without_workfile_asks_for_save_as(batch_host, batch_group):
    assert batch_host.get_current_workfile() is None

    with pytest.raises(RuntimeError, match="use Save As"):
        batch_host.save_workfile()


def test_save_writes_workfile_and_remembers_it(
    batch_host, batch_group, tmp_path
):
    add_note(batch_group, "saved_node")
    path = str(tmp_path / "work" / "sh010_v001.flamebatch")

    batch_host.save_workfile(path)

    assert "saved_node" in batch_setup_text(path)
    assert batch_host.get_current_workfile() == os.path.normpath(path)


def test_save_again_writes_current_workfile(
    batch_host, batch_group, tmp_path
):
    path = str(tmp_path / "sh010_v001.flamebatch")
    batch_host.save_workfile(path)
    add_note(batch_group, "added_later")

    batch_host.save_workfile()

    assert "added_later" in batch_setup_text(path)


def test_failed_save_keeps_previous_workfile(
    batch_host, batch_group, tmp_path, monkeypatch
):
    path = tmp_path / "sh010_v001.flamebatch"
    batch_host.save_workfile(str(path))
    previous = path.read_text()

    def _fail(batch, filepath, *args, **kwargs):
        with open(filepath, "w") as stream:
            stream.write("{partial")
        raise OSError("disk full")

    monkeypatch.setattr(batch_utils, "save_batch_as_consolidated_json", _fail)

    with pytest.raises(RuntimeError, match="disk full"):
        batch_host.save_workfile(str(path))

    assert path.read_text() == previous
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]


def test_save_with_context_creates_batch_product(
    batch_host, batch_group, shot_context
):
    folder_entity, task_entity = shot_context
    path = workfile_path(batch_host, folder_entity, task_entity, 1)

    batch_host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )

    product = batch_utils.get_batch_product_data(batch_group)
    assert product["folderPath"] == SHOT_PATH
    assert product["task"] == SHOT_TASK
    assert product["batch_name"] == batch_group.name.get_value()
    assert batch_host.get_current_workfile() == path
    # The product note is part of the saved content.
    assert batch_utils._METADATA_NODE_NAME in batch_setup_text(path)


def test_save_with_context_moves_products_to_task(
    batch_host, batch_group, other_task_context
):
    name = batch_group.name.get_value()
    add_note(
        batch_group, batch_utils._METADATA_NODE_NAME,
        batch_product_data(SHOT_PATH, SHOT_TASK, name),
    )
    add_write_node(
        batch_group, "render", {"folderPath": SHOT_PATH, "task": SHOT_TASK}
    )
    folder_entity, task_entity = other_task_context
    path = workfile_path(batch_host, folder_entity, task_entity, 1)

    batch_host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )

    assert batch_utils.get_batch_products_context(batch_group) == {
        "folder_path": SHOT_PATH,
        "task_name": SHOT_OTHER_TASK,
    }
    render = batch_utils.read_node_metadata(get_node(batch_group, "render"))
    assert render["task"] == SHOT_OTHER_TASK
    assert os.environ["AYON_TASK_NAME"] == SHOT_OTHER_TASK
    assert batch_host.get_current_workfile() == path


def test_context_comes_from_batch_products(batch_host, batch_group):
    name = batch_group.name.get_value()
    assert batch_host.get_current_context()["task_name"] == SHOT_TASK

    add_note(
        batch_group, batch_utils._METADATA_NODE_NAME,
        batch_product_data(SHOT_PATH, SHOT_OTHER_TASK, name),
    )

    context = batch_host.get_current_context()
    assert context["folder_path"] == SHOT_PATH
    assert context["task_name"] == SHOT_OTHER_TASK


def test_open_workfile_creates_task_batch_group(
    batch_host, batch_group, shot_context
):
    folder_entity, task_entity = shot_context
    add_note(batch_group, "opened_node")
    path = workfile_path(batch_host, folder_entity, task_entity, 1)
    batch_host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )
    task_batch_name = batch_utils.get_task_batch_name(SHOT_PATH, SHOT_TASK)

    batch_host.open_workfile_with_context(path, folder_entity, task_entity)

    opened = flame.batch
    assert opened.name.get_value() == task_batch_name
    assert opened.uid.get_value() != batch_group.uid.get_value()
    assert get_node(opened, "opened_node") is not None
    assert batch_utils.get_batch_product_data(opened)["batch_name"] == (
        task_batch_name
    )
    assert batch_host.get_current_workfile() == path

    # A second open does not replace the first one.
    batch_host.open_workfile_with_context(path, folder_entity, task_entity)

    assert flame.batch.name.get_value() == f"{task_batch_name} (2)"
    names = get_batch_group_names()
    assert task_batch_name in names
    assert f"{task_batch_name} (2)" in names


def test_open_moves_products_to_session_task(
    batch_host, batch_group, shot_context, other_task_context
):
    folder_entity, task_entity = shot_context
    path = workfile_path(batch_host, folder_entity, task_entity, 1)
    batch_host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )
    other_folder, other_task = other_task_context

    batch_host.open_workfile_with_context(path, other_folder, other_task)

    assert batch_utils.get_batch_products_context(flame.batch) == {
        "folder_path": SHOT_PATH,
        "task_name": SHOT_OTHER_TASK,
    }
    assert flame.batch.name.get_value() == batch_utils.get_task_batch_name(
        SHOT_PATH, SHOT_OTHER_TASK
    )
    assert os.environ["AYON_TASK_NAME"] == SHOT_OTHER_TASK
    assert batch_host.get_current_workfile() == path


def test_failed_open_leaves_no_batch_group(batch_host, batch_group, tmp_path):
    path = tmp_path / "broken.flamebatch"
    path.write_text(json.dumps({"notes.txt": "no batch setup"}))
    names = get_batch_group_names()

    with pytest.raises(ValueError):
        batch_host.open_workfile(str(path))

    assert get_batch_group_names() == names


def test_open_needs_task_context(batch_host, tmp_path, monkeypatch):
    monkeypatch.delenv("AYON_TASK_NAME")

    with pytest.raises(RuntimeError, match="only in a task context"):
        batch_host.open_workfile(str(tmp_path / "any.flamebatch"))


def test_last_batch_workfile(
    batch_host, batch_group, shot_context, other_task_context
):
    folder_entity, task_entity = shot_context
    for version in (1, 2):
        path = workfile_path(batch_host, folder_entity, task_entity, version)
        batch_host.save_workfile_with_context(
            path, folder_entity, task_entity, version=version
        )

    assert pipeline.get_last_batch_workfile(SHOT_PATH, SHOT_TASK) == path
    assert pipeline.get_last_batch_workfile(
        SHOT_PATH, SHOT_OTHER_TASK
    ) is None
    assert pipeline.get_last_batch_workfile("/missing", SHOT_TASK) is None
