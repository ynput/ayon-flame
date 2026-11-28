"""The Publisher keeps its instances when the artist opens another batch
group: the Batch and Batch Render creators refuse to save or remove the
instances of a batch group that is not the current one."""

import flame
import pytest

from ayon_core.pipeline.create import CreatorError

from ayon_flame.api import batch_utils

from helpers import (
    SHOT_PATH,
    SHOT_TASK,
    add_note,
    add_write_node,
    batch_product_data,
    get_node,
    load_plugin_module,
)

METADATA_NODE = batch_utils._METADATA_NODE_NAME


class FakeCreatedInstance:
    """'CreatedInstance' without a create context: the data and the
    transient data the creators use."""

    def __init__(self, data=None, **_kwargs):
        self.data = dict(data or {})
        self.transient_data = {}

    def data_to_store(self):
        return dict(self.data)


def make_creator(monkeypatch, filename, class_name):
    """The creator of the plugin file without a create context. Collected
    and removed instances are listed in 'collected' and 'removed'."""
    module = load_plugin_module("create", filename)
    monkeypatch.setattr(module, "CreatedInstance", FakeCreatedInstance)
    creator_class = getattr(module, class_name)
    creator = creator_class.__new__(creator_class)
    creator.collected = []
    creator.removed = []
    creator._add_instance_to_context = creator.collected.append
    creator._remove_instance_from_context = creator.removed.append
    return creator


@pytest.fixture
def batch_creator(monkeypatch):
    return make_creator(monkeypatch, "create_batch.py", "CreateBatchWorkfile")


@pytest.fixture
def render_creator(monkeypatch):
    return make_creator(
        monkeypatch, "create_batch_render.py", "CreateBatchRender"
    )


def new_current_batch(make_batch_group):
    """A new batch group, the current one: the artist opens another batch
    group while the Publisher is open. (Flame switches back to an older
    batch group only after the test returns, the tests do not.)"""
    batch = make_batch_group()
    assert flame.batch.uid.get_value() == batch.uid.get_value()
    return batch


def collect_batch_instance(creator, batch):
    """Collect the Batch product of the batch group, as the Publisher does
    when it opens or refreshes."""
    add_note(
        batch, METADATA_NODE,
        batch_product_data(SHOT_PATH, SHOT_TASK, batch.name.get_value()),
    )
    creator.collect_instances()
    (instance,) = creator.collected
    return instance


def stored_batch_data(batch):
    return batch_utils.read_node_metadata(get_node(batch, METADATA_NODE))


# --- Batch product ----------------------------------------------------------


def test_batch_instance_saved_in_its_batch_group(
    batch_creator, make_batch_group
):
    batch = new_current_batch(make_batch_group)
    instance = collect_batch_instance(batch_creator, batch)
    instance.data["comment"] = "saved"

    batch_creator.update_instances([(instance, None)])

    assert stored_batch_data(batch)["comment"] == "saved"


def test_batch_instance_of_another_batch_group_refused(
    batch_creator, make_batch_group
):
    first = new_current_batch(make_batch_group)
    instance = collect_batch_instance(batch_creator, first)
    second = new_current_batch(make_batch_group)
    instance.data["comment"] = "wrong batch group"

    with pytest.raises(CreatorError):
        batch_creator.update_instances([(instance, None)])
    with pytest.raises(CreatorError):
        batch_creator.remove_instances([instance])

    assert get_node(second, METADATA_NODE) is None
    assert "comment" not in stored_batch_data(first)
    assert batch_creator.removed == []


def test_batch_instance_saved_after_publisher_refresh(
    batch_creator, make_batch_group
):
    """The refused artist refreshes the Publisher: the instances of the
    current batch group show and save."""
    first = new_current_batch(make_batch_group)
    collect_batch_instance(batch_creator, first)
    second = new_current_batch(make_batch_group)

    batch_creator.collected.clear()
    instance = collect_batch_instance(batch_creator, second)
    instance.data["comment"] = "after refresh"
    batch_creator.update_instances([(instance, None)])

    assert stored_batch_data(second)["comment"] == "after refresh"
    assert "comment" not in stored_batch_data(first)


# --- Batch Render products --------------------------------------------------


def test_render_instance_of_another_batch_group_refused(
    render_creator, make_batch_group
):
    first = new_current_batch(make_batch_group)
    data = {
        "productName": "renderMain",
        "folderPath": SHOT_PATH,
        "task": SHOT_TASK,
    }
    node = add_write_node(first, "ayon_test_render", data)
    render_creator.collect_instances()
    (instance,) = render_creator.collected
    # The uid kept at collect is the one of the current batch group.
    batch_utils.check_instances_batch([instance], flame.batch)

    new_current_batch(make_batch_group)

    with pytest.raises(CreatorError):
        render_creator.update_instances([(instance, None)])
    with pytest.raises(CreatorError):
        render_creator.remove_instances([instance])

    assert batch_utils.read_node_metadata(node).items() >= data.items()
