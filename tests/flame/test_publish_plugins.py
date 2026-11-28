"""Publish and create plugins of the Batch and editorial workfiles.

Each plugin runs on its own, on a pyblish context made by the test.
`test_publish_batch.py` runs them together in a real publish.
"""

import copy
import os
import types

import pyblish.api
import pytest

from ayon_core.pipeline.publish import PublishValidationError

import ayon_flame.api as flapi
from ayon_flame.api import batch_utils, editorial_workfile, pipeline
from ayon_flame.api.lib import CTX

from helpers import (
    SHOT_PATH,
    SHOT_TASK,
    add_note,
    add_write_node,
    batch_product_data,
    batch_setup_text,
    get_batch_group_names,
    load_plugin_module,
    read_consolidated,
    workfile_path,
)

def make_context(current_file="Flame/flame_tests"):
    context = pyblish.api.Context()
    context.data["currentFile"] = current_file
    return context


def add_batch_instance(context, batch, **data):
    instance = context.create_instance(batch.name.get_value())
    instance.data.update(
        batch_product_data(SHOT_PATH, SHOT_TASK, batch.name.get_value())
    )
    instance.data["family"] = "workfile"
    instance.data["families"] = ["workfile"]
    instance.data.update(data)
    return instance


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


# --- CollectCurrentWorkfile -------------------------------------------------


@pytest.fixture
def collect_current_workfile():
    module = load_plugin_module("publish", "collect_current_workfile.py")
    return module.CollectCurrentWorkfile()


def test_current_file_is_session_batch_workfile(
    collect_current_workfile, saved_batch
):
    batch, path = saved_batch
    context = make_context()
    add_batch_instance(context, batch)

    collect_current_workfile.process(context)

    assert context.data["currentFile"] == path


def test_current_file_falls_back_to_last_batch_workfile(
    collect_current_workfile, saved_batch, shot_context
):
    batch, _ = saved_batch
    host = pipeline.FlameBatchHost()
    folder_entity, task_entity = shot_context
    last = workfile_path(host, folder_entity, task_entity, 2)
    host.save_workfile_with_context(
        last, folder_entity, task_entity, version=2
    )
    # Flame restarted: the batch group has no workfile in this session.
    batch_utils._SESSION_BATCH_WORKFILES.clear()
    context = make_context()
    add_batch_instance(context, batch)

    collect_current_workfile.process(context)

    assert context.data["currentFile"] == last


def test_current_file_is_editorial_workfile(
    collect_current_workfile, tmp_path, monkeypatch
):
    monkeypatch.setattr(editorial_workfile, "save_flame_project", lambda: None)
    path = str(tmp_path / "edit_v003.flameedit")
    pipeline.FlameHost().save_workfile(path)
    context = make_context()

    collect_current_workfile.process(context)

    assert context.data["currentFile"] == path


def test_current_file_keeps_placeholder(collect_current_workfile, batch_group):
    context = make_context("Flame/flame_tests")
    add_batch_instance(context, batch_group)

    collect_current_workfile.process(context)

    assert context.data["currentFile"] == "Flame/flame_tests"


# --- CollectBatchVersion ----------------------------------------------------


@pytest.fixture
def collect_batch_version():
    module = load_plugin_module("publish", "collect_batch_version.py")
    return module.CollectBatchVersion()


def test_version_from_batch_workfile(collect_batch_version, batch_group):
    context = make_context("/work/fltst_sh010_compositing_v003.flamebatch")
    add_batch_instance(context, batch_group)

    collect_batch_version.process(context)

    assert context.data["version"] == 3


@pytest.mark.parametrize("current_file", [
    "Flame/flame_tests",
    "/work/fltst_sh010_compositing.flamebatch",
    "/work/fltst_sh010_compositing_v003.flameedit",
])
def test_no_version_without_versioned_batch_workfile(
    collect_batch_version, batch_group, current_file
):
    context = make_context(current_file)
    add_batch_instance(context, batch_group)

    collect_batch_version.process(context)

    assert "version" not in context.data


def test_no_version_without_batch_instance(collect_batch_version):
    context = make_context("/work/fltst_sh010_compositing_v003.flamebatch")
    context.create_instance("editorial").data["flame_context"] = (
        "FlameMenuTimeline"
    )

    collect_batch_version.process(context)

    assert "version" not in context.data


# --- ExtractBatchWorkfileSave -----------------------------------------------


@pytest.fixture
def extract_workfile_save(monkeypatch):
    module = load_plugin_module("publish", "extract_batch_workfile_save.py")
    plugin_class = module.ExtractBatchWorkfileSave
    monkeypatch.setattr(plugin_class, "update_batch_workfile", True)
    return plugin_class


def test_publish_saves_session_workfile(extract_workfile_save, saved_batch):
    batch, path = saved_batch
    add_note(batch, "unsaved_change")
    context = make_context(path)
    add_batch_instance(context, batch)

    extract_workfile_save().process(context)

    assert "unsaved_change" in batch_setup_text(path)


def test_publish_never_writes_fallback_workfile(
    extract_workfile_save, saved_batch
):
    batch, path = saved_batch
    batch_utils._SESSION_BATCH_WORKFILES.clear()
    add_note(batch, "unsaved_change")
    context = make_context(path)
    add_batch_instance(context, batch)

    extract_workfile_save().process(context)

    assert "unsaved_change" not in batch_setup_text(path)


def test_publish_save_follows_setting(
    extract_workfile_save, saved_batch, project_settings
):
    batch, path = saved_batch
    settings = copy.deepcopy(project_settings)
    settings["flame"]["update_batch_workfile"]["enabled"] = False
    extract_workfile_save.apply_settings(settings)
    add_note(batch, "unsaved_change")
    context = make_context(path)
    add_batch_instance(context, batch)

    extract_workfile_save().process(context)

    assert "unsaved_change" not in batch_setup_text(path)


def test_publish_save_skips_other_source(extract_workfile_save, saved_batch):
    batch, path = saved_batch
    add_note(batch, "unsaved_change")
    context = make_context("Flame/flame_tests")
    add_batch_instance(context, batch)

    extract_workfile_save().process(context)

    assert "unsaved_change" not in batch_setup_text(path)


# --- ExtractBatchWorkfile ---------------------------------------------------


def test_extract_batch_workfile(batch_group, tmp_path):
    module = load_plugin_module("publish", "extract_batch_workfile.py")
    add_note(batch_group, "published_node")
    context = make_context()
    instance = add_batch_instance(context, batch_group)
    instance.data["stagingDir"] = str(tmp_path)
    name = batch_group.name.get_value()

    module.ExtractBatchWorkfile().process(instance)

    representation = instance.data["representations"][-1]
    assert representation["ext"] == "flamebatch"
    assert representation["files"] == f"{name}.flamebatch"
    path = os.path.join(representation["stagingDir"], representation["files"])
    assert "published_node" in batch_setup_text(path)
    assert read_consolidated(path)
    assert instance.data["versionData"]["batch_name"] == name


def test_extract_otio_skips_batch_product(batch_group):
    module = load_plugin_module("publish", "extract_otio_file.py")
    context = make_context()
    instance = add_batch_instance(context, batch_group)

    module.ExtractOTIOFile().process(instance)

    assert "representations" not in instance.data


def test_extract_otio_for_editorial_workfile(tmp_path):
    import opentimelineio as otio

    module = load_plugin_module("publish", "extract_otio_file.py")
    context = make_context()
    context.data["otioTimeline"] = otio.schema.Timeline(name="edit")
    instance = context.create_instance("workfileMain")
    instance.data.update({
        "name": "workfileMain",
        "creator_identifier": flapi.EDITORIAL_WORKFILE_CREATOR,
        "stagingDir": str(tmp_path),
    })

    module.ExtractOTIOFile().process(instance)

    representation = instance.data["representations"][-1]
    assert representation["ext"] == "otio"
    path = os.path.join(representation["stagingDir"], representation["files"])
    assert otio.adapters.read_from_file(path).name == "edit"


# --- ValidateEditorialWorkfileSaved -----------------------------------------


@pytest.fixture
def validate_editorial(monkeypatch):
    module = load_plugin_module(
        "publish", "validate_editorial_workfile_saved.py"
    )
    plugin_class = module.ValidateEditorialWorkfileSaved
    # 'enabled' exists only once 'apply_settings' ran, it is removed again.
    for attribute in ("enabled", "optional", "active"):
        monkeypatch.setattr(
            plugin_class, attribute, getattr(plugin_class, attribute, True),
            raising=False,
        )
    return plugin_class


def test_validate_editorial_workfile_missing(validate_editorial):
    with pytest.raises(PublishValidationError):
        validate_editorial().process(make_context())


def test_validate_editorial_workfile_saved(
    validate_editorial, tmp_path, monkeypatch
):
    monkeypatch.setattr(editorial_workfile, "save_flame_project", lambda: None)
    pipeline.FlameHost().save_workfile(str(tmp_path / "edit_v001.flameedit"))

    validate_editorial().process(make_context())


def test_validate_editorial_disabled_for_batch_menu(
    validate_editorial, project_settings
):
    CTX.context = "FlameMenuBatch"
    validate_editorial.apply_settings(project_settings)
    assert validate_editorial.enabled is False

    CTX.context = "FlameMenuTimeline"
    validate_editorial.apply_settings(project_settings)
    assert validate_editorial.enabled is True


# --- IncrementBatchRenderNextStagingDir -------------------------------------


@pytest.mark.parametrize(
    ("follow_workfile_version", "context_version", "expected"),
    [
        (True, 3, 3),
        (True, None, 4),
        (False, 3, 4),
    ],
)
def test_render_staging_dir_version(
    batch_group, monkeypatch, follow_workfile_version, context_version,
    expected,
):
    module = load_plugin_module(
        "publish", "increment_batch_render_next_staging_dir.py"
    )
    used = {}

    def _staging_dir_info(*args, **kwargs):
        used.update(kwargs["template_data"])
        return types.SimpleNamespace(
            directory=f"/staging/v{kwargs['template_data']['version']:03}"
        )

    monkeypatch.setattr(module, "get_staging_dir_info", _staging_dir_info)
    write_node = add_write_node(batch_group, "render")
    context = make_context("/work/fltst_sh010_compositing_v003.flamebatch")
    if context_version is not None:
        context.data["version"] = context_version
    context.data.update({
        "projectEntity": {}, "anatomy": None, "project_settings": {},
        "hostName": "flame", "user": "tester",
    })
    instance = context.create_instance("render")
    instance.data.update({
        "stagingDir_is_custom": True,
        "followWorkfileVersion": follow_workfile_version,
        "transientData": {"writeNode": write_node},
        "anatomyData": {"version": 3},
        "productType": "render",
        "productName": "renderMain",
    })

    module.IncrementBatchRenderNextStagingDir().process(instance)

    assert used["version"] == expected
    assert used["workfile_name"] == "fltst_sh010_compositing_v003"
    assert write_node.media_path.get_value() == f"/staging/v{expected:03}"


# --- IntegrateBatchGroup ---------------------------------------------------


def test_editorial_batch_group_named_like_work_files(make_batch_group):
    """The batch group of an editorial publish is the one Work Files use."""
    module = load_plugin_module("publish", "integrate_batch_group.py")
    plugin = module.IntegrateBatchGroup()
    context = make_context()
    instance = context.create_instance("plate")
    instance.data.update({
        "folderPath": SHOT_PATH,
        "frameStart": 1001,
        "frameEnd": 1010,
        "handleStart": 0,
        "handleEnd": 0,
    })
    expected = batch_utils.get_task_batch_name(SHOT_PATH, SHOT_TASK)

    batch = plugin._get_batch_group(instance, {"name": SHOT_TASK})
    again = plugin._get_batch_group(instance, {"name": SHOT_TASK})

    assert batch.name.get_value() == expected
    assert again.uid.get_value() == batch.uid.get_value()
    assert get_batch_group_names().count(expected) == 1


# --- Creators ---------------------------------------------------------------


@pytest.mark.parametrize(("batch_name", "expected"), [
    ("sh010_comp", "sh010_comp"),
    ("sh010_comp (2)", "sh010_comp_2"),
    ("sh010 comp", "sh010comp"),
    (".hidden.", "hidden"),
    ("(2)", "2"),
    ("%%%", "fallback"),
])
def test_batch_product_name(batch_name, expected):
    module = load_plugin_module("create", "create_batch.py")

    assert module.get_batch_product_name(batch_name, "fallback") == expected


def test_creators_follow_menu(project_settings):
    batch_module = load_plugin_module("create", "create_batch.py")
    workfile_module = load_plugin_module("create", "create_workfile.py")
    batch_creator = batch_module.CreateBatchWorkfile.__new__(
        batch_module.CreateBatchWorkfile
    )
    workfile_creator = workfile_module.CreateWorkfile.__new__(
        workfile_module.CreateWorkfile
    )

    CTX.context = "FlameMenuBatch"
    batch_creator.apply_settings(project_settings)
    workfile_creator.apply_settings(project_settings)
    assert batch_creator.enabled is True
    assert workfile_creator.enabled is False

    CTX.context = "FlameMenuTimeline"
    batch_creator.apply_settings(project_settings)
    workfile_creator.apply_settings(project_settings)
    assert batch_creator.enabled is False
    assert workfile_creator.enabled is True
