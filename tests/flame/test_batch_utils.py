"""Batch group helpers of `ayon_flame.api.batch_utils`."""

import json
import os

import flame
import pytest

from ayon_flame.api import batch_utils

from helpers import (
    SHOT_OTHER_TASK,
    SHOT_PATH,
    SHOT_TASK,
    FakeInstance,
    add_note,
    add_write_node,
    batch_product_data,
    batch_setup_text,
    get_batch_group_names,
    get_node,
    read_consolidated,
)


# --- Node metadata ----------------------------------------------------------


def test_node_metadata_roundtrip(batch_group):
    node = add_note(batch_group, "meta")
    batch_utils.write_node_metadata(node, {"folderPath": SHOT_PATH})

    data = batch_utils.read_node_metadata(node)

    assert data["folderPath"] == SHOT_PATH
    assert data[batch_utils.AYON_NOTE_MARKER] is True


def test_node_metadata_ignores_other_notes(batch_group):
    node = add_note(batch_group, "artist_note")
    node.note = "plain text from an artist"
    assert batch_utils.read_node_metadata(node) is None

    node.note = json.dumps({"folderPath": SHOT_PATH})
    assert batch_utils.read_node_metadata(node) is None, (
        "JSON without the AYON marker is not AYON data"
    )


def test_clear_node_metadata(batch_group):
    node = add_note(batch_group, "meta", {"folderPath": SHOT_PATH})

    batch_utils.clear_node_metadata(node)

    assert batch_utils.read_node_metadata(node) is None


def test_metadata_node_is_created_once(batch_group):
    assert batch_utils.get_metadata_node(batch_group) is None

    node = batch_utils.get_metadata_node(batch_group, create=True)
    again = batch_utils.get_metadata_node(batch_group, create=True)

    assert node.name.get_value() == batch_utils._METADATA_NODE_NAME
    assert again.name.get_value() == node.name.get_value()
    names = [n.name.get_value() for n in batch_group.nodes]
    assert names.count(batch_utils._METADATA_NODE_NAME) == 1


# --- Batch group names ------------------------------------------------------


def test_task_batch_name():
    assert (
        batch_utils.get_task_batch_name("/shots/sq01/sh010", "compositing")
        == "shots_sq01_sh010_compositing"
    )


def test_unique_batch_name(make_batch_group):
    batch = make_batch_group()
    name = batch.name.get_value()
    assert batch_utils.get_unique_batch_name(f"{name}_free") == f"{name}_free"
    assert batch_utils.get_unique_batch_name(name) == f"{name} (2)"

    make_batch_group(f"{name} (2)")
    assert batch_utils.get_unique_batch_name(name) == f"{name} (3)"


def test_batch_from_workspace(batch_group):
    name = batch_group.name.get_value()

    found = batch_utils.get_batch_from_workspace(name)

    assert found is not None
    assert found.uid.get_value() == batch_group.uid.get_value()
    assert batch_utils.get_batch_from_workspace(f"{name}_missing") is None


# --- Consolidated JSON ------------------------------------------------------


def test_consolidated_json_roundtrip(batch_group, tmp_path):
    name = batch_group.name.get_value()
    data = batch_product_data(SHOT_PATH, SHOT_TASK, name)
    add_note(batch_group, batch_utils._METADATA_NODE_NAME, data)
    add_write_node(batch_group, "ayon_write")
    path = str(tmp_path / "roundtrip.flamebatch")

    batch_utils.save_batch_as_consolidated_json(batch_group, path)

    # Flame names the setup '<name>_batch.batch', any '.batch' is loaded.
    content = read_consolidated(path)
    assert any(key.endswith(".batch") for key in content)
    assert "ayon_write" in batch_setup_text(path)

    loaded_name = f"{name}_loaded"
    flame.batch.create_batch_group(loaded_name)
    loaded = batch_utils.load_batch_from_consolidated_json(
        path, name=loaded_name
    )

    assert loaded.name.get_value() == loaded_name
    assert get_node(loaded, "ayon_write") is not None
    assert batch_utils.get_batch_product_data(loaded)["task"] == SHOT_TASK


def test_consolidated_json_keeps_binary_files(batch_group, tmp_path):
    """Files that are not UTF-8 are kept as base64."""
    folder = tmp_path / "export"
    folder.mkdir()
    (folder / "preset.bin").write_bytes(b"\xff\xfe\x00binary")
    path = str(tmp_path / "binary.flamebatch")

    batch_utils.save_batch_as_consolidated_json(
        batch_group, path, temporary_folder=str(folder)
    )

    content = read_consolidated(path)
    assert content["preset.bin"].startswith("__b64__:")
    assert any(key.endswith(".batch") for key in content)


def test_load_refuses_paths_outside_its_folder(tmp_path):
    outside = tmp_path / "outside.batch"
    path = tmp_path / "evil.flamebatch"
    path.write_text(json.dumps({"../outside.batch": "<batch/>"}))
    extract = tmp_path / "extract"
    extract.mkdir()

    with pytest.raises(ValueError, match="outside of its folder"):
        batch_utils.load_batch_from_consolidated_json(
            str(path), temporary_folder=str(extract)
        )
    assert not outside.exists()


def test_load_refuses_absolute_paths(tmp_path):
    target = tmp_path / "absolute.batch"
    path = tmp_path / "evil.flamebatch"
    path.write_text(json.dumps({str(target): "<batch/>"}))
    extract = tmp_path / "extract"
    extract.mkdir()

    with pytest.raises(ValueError):
        batch_utils.load_batch_from_consolidated_json(
            str(path), temporary_folder=str(extract)
        )
    assert not target.exists()


def test_load_without_batch_document(tmp_path):
    path = tmp_path / "empty.flamebatch"
    path.write_text(json.dumps({"notes.txt": "nothing"}))

    with pytest.raises(ValueError, match="No valid batch"):
        batch_utils.load_batch_from_consolidated_json(str(path))


# --- Context of the batch group products -----------------------------------


def test_products_context_prefers_batch_product(batch_group):
    name = batch_group.name.get_value()
    add_write_node(
        batch_group, "render",
        {"folderPath": SHOT_PATH, "task": SHOT_OTHER_TASK},
    )
    add_note(
        batch_group, batch_utils._METADATA_NODE_NAME,
        batch_product_data(SHOT_PATH, SHOT_TASK, name),
    )

    assert batch_utils.get_batch_products_context(batch_group) == {
        "folder_path": SHOT_PATH,
        "task_name": SHOT_TASK,
    }


def test_products_context_from_render_products(batch_group):
    add_write_node(
        batch_group, "render",
        {"folderPath": SHOT_PATH, "task": SHOT_OTHER_TASK},
    )

    assert batch_utils.get_batch_products_context(batch_group) == {
        "folder_path": SHOT_PATH,
        "task_name": SHOT_OTHER_TASK,
    }


def test_products_context_without_products(batch_group):
    add_note(batch_group, "artist_note")

    assert batch_utils.get_batch_products_context(batch_group) is None


def test_set_products_context(batch_group):
    name = batch_group.name.get_value()
    add_note(
        batch_group, batch_utils._METADATA_NODE_NAME,
        batch_product_data(SHOT_PATH, SHOT_TASK, name),
    )
    add_write_node(
        batch_group, "render", {"folderPath": SHOT_PATH, "task": SHOT_TASK}
    )
    add_note(batch_group, "artist_note")

    changed = batch_utils.set_batch_products_context(
        batch_group, SHOT_PATH, SHOT_OTHER_TASK
    )

    assert changed == 2
    assert batch_utils.get_batch_products_context(batch_group) == {
        "folder_path": SHOT_PATH,
        "task_name": SHOT_OTHER_TASK,
    }
    render = batch_utils.read_node_metadata(get_node(batch_group, "render"))
    assert render["task"] == SHOT_OTHER_TASK
    assert batch_utils.set_batch_products_context(
        batch_group, SHOT_PATH, SHOT_OTHER_TASK
    ) == 0


def test_set_instances_batch_name(batch_group):
    name = batch_group.name.get_value()
    add_note(
        batch_group, batch_utils._METADATA_NODE_NAME,
        batch_product_data(SHOT_PATH, SHOT_TASK, "old name"),
    )
    add_write_node(
        batch_group, "render", {"folderPath": SHOT_PATH, "task": SHOT_TASK}
    )

    batch_utils.set_instances_batch_name(batch_group, f"{name} (2)")

    assert batch_utils.get_batch_product_data(batch_group)["batch_name"] == (
        f"{name} (2)"
    )
    render = batch_utils.read_node_metadata(get_node(batch_group, "render"))
    assert "batch_name" not in render


# --- Session Batch workfiles -----------------------------------------------


def test_session_workfile_belongs_to_its_task(batch_group, tmp_path):
    path = str(tmp_path / "a" / ".." / "work_v001.flamebatch")

    batch_utils.set_session_batch_workfile(
        batch_group, path, SHOT_PATH, SHOT_TASK
    )

    assert batch_utils.get_session_batch_workfile(
        batch_group, SHOT_PATH, SHOT_TASK
    ) == os.path.normpath(path)
    assert batch_utils.get_session_batch_workfile(
        batch_group, SHOT_PATH, SHOT_OTHER_TASK
    ) is None


def test_session_workfile_follows_batch_group_uid(make_batch_group, tmp_path):
    batch = make_batch_group()
    other = make_batch_group()
    path = str(tmp_path / "work_v001.flamebatch")
    batch_utils.set_session_batch_workfile(batch, path, SHOT_PATH, SHOT_TASK)

    batch.name = f"{batch.name.get_value()}_renamed"

    assert batch_utils.get_session_batch_workfile(
        batch, SHOT_PATH, SHOT_TASK
    ) == path
    assert batch_utils.get_session_batch_workfile(
        other, SHOT_PATH, SHOT_TASK
    ) is None


def test_instances_batches(make_batch_group):
    first = make_batch_group()
    second = make_batch_group()
    first_name = first.name.get_value()
    second_name = second.name.get_value()
    instances = [
        FakeInstance(flame_context="FlameMenuBatch", batch_name=first_name),
        FakeInstance(flame_context="FlameMenuBatch", batch_name=first_name),
        FakeInstance(
            flame_context="FlameMenuBatch", batch_name=second_name,
            publish=False,
        ),
        FakeInstance(
            flame_context="FlameMenuBatch", batch_name=second_name,
            active=False,
        ),
        FakeInstance(
            flame_context="FlameMenuTimeline", batch_name=second_name
        ),
        FakeInstance(flame_context="FlameMenuBatch", batch_name="missing"),
        FakeInstance(flame_context="FlameMenuBatch"),
    ]

    batches = batch_utils.get_instances_batches(instances)

    assert list(batches) == [first_name]
    assert batches[first_name].uid.get_value() == first.uid.get_value()
    assert "missing" not in get_batch_group_names()
