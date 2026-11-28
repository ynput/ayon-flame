"""Batch workfile saved elsewhere since AYON saved or opened it: by another
batch group, another Flame or another machine. No Flame project save or
publish writes over it, a Flame save shows one dialog."""

import types

import flame
import pyblish.api
import pytest

from ayon_flame.api import batch_utils, pipeline

from helpers import (
    SHOT_PATH,
    SHOT_TASK,
    add_note,
    batch_product_data,
    batch_setup_text,
    load_plugin_module,
    workfile_path,
)


@pytest.fixture
def messages(monkeypatch):
    """Lines of the Flame console and dialogs, a dialog does not block."""
    shown = types.SimpleNamespace(console=[], dialogs=[])
    monkeypatch.setattr(
        flame.messages, "show_in_console",
        lambda text, *args, **kwargs: shown.console.append(text),
    )
    monkeypatch.setattr(
        flame.messages, "show_in_dialog",
        lambda title, text, *args, **kwargs: shown.dialogs.append(text),
    )
    return shown


@pytest.fixture
def saved_batch(batch_group, shot_context):
    """A batch group saved as the v001 Batch workfile of the shot task."""
    host = pipeline.FlameBatchHost()
    folder_entity, task_entity = shot_context
    path = workfile_path(host, folder_entity, task_entity, 1)
    host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )
    return batch_group, path


@pytest.fixture
def extract_workfile_save(monkeypatch):
    module = load_plugin_module("publish", "extract_batch_workfile_save.py")
    plugin_class = module.ExtractBatchWorkfileSave
    monkeypatch.setattr(plugin_class, "update_batch_workfile", True)
    return plugin_class


def save_elsewhere(path):
    """Another Flame or machine saves the Batch workfile."""
    with open(path, "a", encoding="utf-8") as stream:
        stream.write("\n")


def publish_context(batch, path):
    """Pyblish context of a Batch menu publish of the batch group."""
    context = pyblish.api.Context()
    context.data["currentFile"] = path
    instance = context.create_instance(batch.name.get_value())
    instance.data.update(
        batch_product_data(SHOT_PATH, SHOT_TASK, batch.name.get_value())
    )
    instance.data["family"] = "workfile"
    instance.data["families"] = ["workfile"]
    return context


# --- Flame project save -----------------------------------------------------


def test_own_saves_keep_the_link(flame_settings, saved_batch, messages):
    batch, path = saved_batch

    for note_name in ("first_save", "second_save"):
        add_note(batch, note_name)
        pipeline.refresh_batch_workfile()
        assert note_name in batch_setup_text(path)

    assert messages.dialogs == []


def test_save_does_not_overwrite_save_of_another_batch_group(
    flame_settings, saved_batch, messages
):
    """v001 open in two batch groups: the other one saves it, the current
    one does not write over that save."""
    other, path = saved_batch
    pipeline.FlameBatchHost().open_workfile(path)
    current = flame.batch
    assert current.uid.get_value() != other.uid.get_value()

    # The other batch group saves v001 like its Flame save does
    # ('FlameBatchHost.save_workfile'). It is not made current: Flame
    # switches batch groups only after the test returns.
    add_note(other, "saved_by_other")
    pipeline.write_batch_workfile(other, path)
    batch_utils.set_session_batch_workfile(other, path, SHOT_PATH, SHOT_TASK)

    add_note(current, "unsaved_in_current")
    pipeline.refresh_batch_workfile()

    setup = batch_setup_text(path)
    assert "saved_by_other" in setup
    assert "unsaved_in_current" not in setup
    assert len(messages.dialogs) == 1
    assert "was saved elsewhere" in messages.dialogs[0]

    # The batch group is unlinked: the next save only warns in the console.
    pipeline.refresh_batch_workfile()

    assert len(messages.dialogs) == 1
    assert any("is not linked" in text for text in messages.console)
    assert "unsaved_in_current" not in batch_setup_text(path)


def test_save_does_not_overwrite_save_from_elsewhere(
    flame_settings, saved_batch, messages
):
    batch, path = saved_batch
    save_elsewhere(path)
    add_note(batch, "unsaved_change")

    pipeline.refresh_batch_workfile()

    assert "unsaved_change" not in batch_setup_text(path)
    assert len(messages.dialogs) == 1


# --- Publish ----------------------------------------------------------------


def test_publish_does_not_overwrite_save_from_elsewhere(
    extract_workfile_save, saved_batch
):
    batch, path = saved_batch
    save_elsewhere(path)
    add_note(batch, "unsaved_change")

    extract_workfile_save().process(publish_context(batch, path))

    assert "unsaved_change" not in batch_setup_text(path)


def test_publish_keeps_the_link_for_the_next_save(
    flame_settings, extract_workfile_save, saved_batch, messages
):
    batch, path = saved_batch
    add_note(batch, "published")
    extract_workfile_save().process(publish_context(batch, path))
    assert "published" in batch_setup_text(path)

    add_note(batch, "saved_after_publish")
    pipeline.refresh_batch_workfile()

    assert "saved_after_publish" in batch_setup_text(path)
    assert messages.dialogs == []
