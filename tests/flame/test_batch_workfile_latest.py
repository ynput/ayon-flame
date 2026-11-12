"""Batch group on an older Batch workfile: save warning, Save As question
and `ValidateBatchWorkfileLatest`."""

import os

import flame
import pyblish.api
import pytest
from ayon_core.pipeline.publish import PublishValidationError
from qtpy import QtWidgets

from ayon_flame.api import CTX, batch_utils, pipeline

from helpers import (
    SHOT_OTHER_TASK,
    SHOT_PATH,
    SHOT_TASK,
    add_note,
    batch_product_data,
    load_plugin_module,
    workfile_path,
)


@pytest.fixture
def batch_host():
    return pipeline.FlameBatchHost()


@pytest.fixture
def console(monkeypatch):
    """Messages of the Flame console."""
    messages = []
    monkeypatch.setattr(
        flame.messages, "show_in_console",
        lambda text, *args, **kwargs: messages.append(text),
    )
    return messages


@pytest.fixture
def question(monkeypatch):
    """Answer of the Save As question, the calls are listed in 'asked'."""

    class Question:
        answer = QtWidgets.QMessageBox.No
        asked = []

    def _ask(parent, title, text, *args, **kwargs):
        Question.asked.append(text)
        return Question.answer

    Question.asked = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", _ask)
    return Question


@pytest.fixture
def saved_batch(batch_host, batch_group, shot_context):
    """A batch group saved as the v001 Batch workfile of the shot task."""
    folder_entity, task_entity = shot_context
    path = workfile_path(batch_host, folder_entity, task_entity, 1)
    batch_host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )
    return batch_group, path


@pytest.fixture
def newer_version(batch_host, shot_context):
    """Another artist saved v002 of the shot task, it is on disk."""
    folder_entity, task_entity = shot_context
    path = workfile_path(batch_host, folder_entity, task_entity, 2)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("{}")
    return path


def add_products(batch, task_name=SHOT_TASK):
    add_note(
        batch, batch_utils._METADATA_NODE_NAME,
        batch_product_data(SHOT_PATH, task_name, batch.name.get_value()),
    )


# --- get_batch_workfile_issue -----------------------------------------------


def test_no_issue_without_workfiles(batch_group):
    assert pipeline.get_batch_workfile_issue(
        batch_group, SHOT_PATH, SHOT_TASK
    ) is None


def test_issue_when_not_linked_to_a_workfile(batch_group, newer_version):
    issue = pipeline.get_batch_workfile_issue(
        batch_group, SHOT_PATH, SHOT_TASK
    )

    assert "is not linked to a workfile" in issue
    assert os.path.basename(newer_version) in issue


def test_issue_when_older_than_last(saved_batch, newer_version):
    batch, path = saved_batch

    issue = pipeline.get_batch_workfile_issue(batch, SHOT_PATH, SHOT_TASK)

    assert issue == (
        f"{os.path.basename(path)} is older than"
        f" {os.path.basename(newer_version)}."
    )


def test_no_issue_on_the_last_workfile(saved_batch):
    batch, _path = saved_batch

    assert pipeline.get_batch_workfile_issue(
        batch, SHOT_PATH, SHOT_TASK
    ) is None


# --- Warning on Flame project save ------------------------------------------


def test_save_warns_when_not_linked(flame_settings, batch_group, console):
    add_products(batch_group)

    pipeline.refresh_batch_workfile()

    assert any("is not linked to a workfile" in text for text in console)


def test_save_does_not_warn_without_products(
    flame_settings, batch_group, console
):
    """A batch group without AYON products is not an AYON workfile."""
    pipeline.refresh_batch_workfile()

    assert console == []


def test_save_warns_when_older(
    flame_settings, saved_batch, newer_version, console
):
    _batch, path = saved_batch

    pipeline.refresh_batch_workfile()

    assert f"AYON: saved {os.path.basename(path)}" in console
    assert any(
        "is older than" in text and "Open" in text for text in console
    )


def test_save_does_not_warn_on_the_last_workfile(
    flame_settings, saved_batch, console
):
    pipeline.refresh_batch_workfile()

    assert len(console) == 1
    assert "saved" in console[0]


def test_save_warning_follows_setting(
    flame_settings, saved_batch, newer_version, console
):
    flame_settings["flame"]["update_batch_workfile"]["enabled"] = False

    pipeline.refresh_batch_workfile()

    assert console == []


def test_failed_last_workfile_lookup_does_not_fail_save(
    flame_settings, saved_batch, console, monkeypatch
):
    def _fail(*args, **kwargs):
        raise OSError("workfiles unavailable")

    monkeypatch.setattr(pipeline, "get_last_batch_workfile", _fail)

    pipeline.refresh_batch_workfile()

    assert len(console) == 1
    assert "saved" in console[0]


# --- Save As from an older batch group --------------------------------------


def test_save_as_from_older_batch_group_asks(
    batch_host, saved_batch, newer_version, shot_context, question
):
    batch, _path = saved_batch
    folder_entity, task_entity = shot_context
    question.answer = QtWidgets.QMessageBox.Yes
    new_path = workfile_path(batch_host, folder_entity, task_entity, 3)

    batch_host.save_workfile_with_context(
        new_path, folder_entity, task_entity, version=3
    )

    assert len(question.asked) == 1
    assert "is older than" in question.asked[0]
    assert os.path.exists(new_path)
    assert batch_host.get_current_workfile() == new_path


def test_save_as_canceled_saves_nothing(
    batch_host, saved_batch, newer_version, shot_context, question
):
    folder_entity, task_entity = shot_context
    question.answer = QtWidgets.QMessageBox.No
    new_path = workfile_path(batch_host, folder_entity, task_entity, 3)

    with pytest.raises(RuntimeError, match="Save As canceled"):
        batch_host.save_workfile_with_context(
            new_path, folder_entity, task_entity, version=3
        )

    assert not os.path.exists(new_path)
    assert batch_host.get_current_workfile() != new_path


def test_save_as_from_the_last_workfile_does_not_ask(
    batch_host, saved_batch, shot_context, question
):
    folder_entity, task_entity = shot_context
    new_path = workfile_path(batch_host, folder_entity, task_entity, 2)

    batch_host.save_workfile_with_context(
        new_path, folder_entity, task_entity, version=2
    )

    assert question.asked == []
    assert os.path.exists(new_path)


def test_save_as_to_another_task_does_not_ask(
    batch_host, saved_batch, newer_version, other_task_context, question
):
    folder_entity, task_entity = other_task_context
    new_path = workfile_path(batch_host, folder_entity, task_entity, 1)

    batch_host.save_workfile_with_context(
        new_path, folder_entity, task_entity, version=1
    )

    assert task_entity["name"] == SHOT_OTHER_TASK
    assert question.asked == []
    assert os.path.exists(new_path)


# --- ValidateBatchWorkfileLatest --------------------------------------------


@pytest.fixture
def validator(monkeypatch):
    module = load_plugin_module("publish", "validate_batch_workfile_latest.py")
    plugin_class = module.ValidateBatchWorkfileLatest
    # 'enabled' exists only once 'apply_settings' ran, it is removed again.
    for attribute in ("enabled", "optional", "active"):
        monkeypatch.setattr(
            plugin_class, attribute, getattr(plugin_class, attribute, True),
            raising=False,
        )
    return plugin_class


def make_context(batch):
    context = pyblish.api.Context()
    context.data["currentFile"] = "Flame/flame_tests"
    instance = context.create_instance(batch.name.get_value())
    instance.data.update(
        batch_product_data(SHOT_PATH, SHOT_TASK, batch.name.get_value())
    )
    instance.data["family"] = "workfile"
    instance.data["families"] = ["workfile"]
    return context


def test_validator_passes_on_the_last_workfile(validator, saved_batch):
    batch, _path = saved_batch

    validator().process(make_context(batch))


def test_validator_fails_for_older_workfile(
    validator, saved_batch, newer_version
):
    batch, path = saved_batch

    with pytest.raises(PublishValidationError) as error:
        validator().process(make_context(batch))

    assert os.path.basename(path) in str(error.value)
    assert os.path.basename(newer_version) in str(error.value)


def test_validator_fails_for_batch_without_workfile(
    validator, batch_group, newer_version
):
    add_products(batch_group)

    with pytest.raises(PublishValidationError, match="not linked"):
        validator().process(make_context(batch_group))


def test_validator_passes_without_any_workfile(validator, batch_group):
    add_products(batch_group)

    validator().process(make_context(batch_group))


def test_validator_skips_missing_batch_group(
    validator, saved_batch, newer_version
):
    batch, _path = saved_batch
    context = make_context(batch)
    context[0].data["batch_name"] = "ayon_test_not_on_desktop"

    validator().process(context)


def test_validator_only_for_batch_menu(validator, project_settings):
    CTX.context = "FlameMenuBatch"
    validator.apply_settings(project_settings)
    assert validator.enabled is True

    CTX.context = "FlameMenuPublisher"
    validator.apply_settings(project_settings)
    assert validator.enabled is False


def test_validator_follows_settings(validator, project_settings):
    CTX.context = "FlameMenuBatch"
    project_settings["flame"]["publish"]["ValidateBatchWorkfileLatest"] = {
        "enabled": False, "optional": False, "active": False,
    }

    validator.apply_settings(project_settings)

    assert validator.enabled is False
    assert validator.optional is False
    assert validator.active is False
