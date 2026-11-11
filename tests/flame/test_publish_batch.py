"""Publish a batch group from the Batch menu and load it back, end to end.

The Batch product is created by saving a Batch workfile, then published
with the publish plugins of the bundle into the test project, as the
Publisher of the Batch menu does, and loaded with the Batch loader.
"""

import os

import ayon_api
import flame
import pytest

from ayon_core.pipeline import Anatomy, registered_host
from ayon_core.pipeline.create import CreateContext
from ayon_core.pipeline.load import (
    get_representation_context,
    load_with_repre_context,
)

import ayon_flame.api as flame_api
from ayon_flame.api import batch_utils, pipeline
from ayon_flame.api.lib import CTX

from helpers import (
    SHOT_TASK,
    add_note,
    batch_setup_text,
    get_batch_group_names,
    get_node,
    load_plugin_module,
    workfile_path,
)

pytestmark = pytest.mark.publish

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".results"
)


@pytest.fixture
def publish_logic():
    try:
        from ayon_core.pipeline.publish import PublishLogic
    except ImportError:
        pytest.skip("ayon-core without 'PublishLogic'")
    return PublishLogic(reset=False)


def _errors(logic):
    return [
        f"{info.title}: {info.message}"
        for info in logic.iter_all_error_info()
    ]


def test_batch_publish(
    publish_logic, batch_group, shot_context, project_name, project_settings,
    flame_settings, monkeypatch,
):
    # 'Iterate Batch After Publish' iterates the batch group, a Flame
    # project save that rewrites the Batch workfile too. Off here, so the
    # workfile holds the change only when the publish saved it.
    monkeypatch.setattr(flame_api, "refresh_batch_workfile", lambda: None)
    CTX.context = "FlameMenuBatch"
    folder_entity, task_entity = shot_context
    batch_host = pipeline.FlameBatchHost()
    path = workfile_path(batch_host, folder_entity, task_entity, 1)
    batch_host.save_workfile_with_context(
        path, folder_entity, task_entity, version=1
    )
    add_note(batch_group, "unsaved_at_publish")
    product = batch_utils.get_batch_product_data(batch_group)
    product_name = product["productName"]
    last_version = ayon_api.get_last_version_by_product_name(
        project_name, product_name, folder_entity["id"], fields={"version"}
    )

    create_context = CreateContext(registered_host(), headless=True)
    instances = [
        instance for instance in create_context.instances
        if instance.get("batch_name") == batch_group.name.get_value()
    ]
    assert len(instances) == 1, "The Batch product is not collected."
    publish_logic.reset_from_create_context(create_context)
    publish_logic.set_comment("In-Flame test publish")
    publish_logic.publish()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    publish_logic.store_publish_report(
        os.path.join(RESULTS_DIR, "publish_batch_report.json")
    )

    assert not publish_logic.has_failed(), _errors(publish_logic)

    # The Batch workfile is saved by the publish, it is the source.
    assert "unsaved_at_publish" in batch_setup_text(path)

    version = ayon_api.get_last_version_by_product_name(
        project_name, product_name, folder_entity["id"]
    )
    assert version is not None, f"{product_name} was not published."
    follow_workfile_version = (
        project_settings["core"]["publish"]["CollectAnatomyInstanceData"]
        ["follow_workfile_version"]
    )
    if follow_workfile_version:
        assert version["version"] == 1
    elif last_version:
        assert version["version"] == last_version["version"] + 1
    assert version["taskId"] == task_entity["id"]
    assert version["data"]["batch_name"] == batch_group.name.get_value()

    representations = list(ayon_api.get_representations(
        project_name, version_ids=[version["id"]]
    ))
    batch_repre = next(
        (r for r in representations if r["name"] == "batch"), None
    )
    assert batch_repre is not None, [r["name"] for r in representations]
    published = Anatomy(project_name).fill_root(batch_repre["attrib"]["path"])
    assert published.endswith(".flamebatch")
    assert "unsaved_at_publish" in batch_setup_text(published)
    assert not any(r["name"] == "otio" for r in representations)
    assert product["task"] == SHOT_TASK

    # Load it back, twice: the second batch group gets a free name.
    LoadBatchgroup = load_plugin_module(
        "load", "load_batch.py"
    ).LoadBatchgroup
    dialogs = []
    monkeypatch.setattr(
        flame.messages, "show_in_dialog",
        lambda *args, **kwargs: dialogs.append(args),
    )
    repre_context = get_representation_context(project_name, batch_repre)
    batch_name = batch_group.name.get_value()

    load_with_repre_context(LoadBatchgroup, repre_context)

    assert flame.batch.name.get_value() == f"{batch_name} (2)"
    assert get_node(flame.batch, "unsaved_at_publish") is not None
    assert flame.batch.batch_iterations, "Versions load as iterations."

    load_with_repre_context(LoadBatchgroup, repre_context)

    assert f"{batch_name} (3)" in get_batch_group_names()
    assert len(dialogs) == 2
