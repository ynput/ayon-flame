# Internal contracts (Amendment 1)

```python
# api/workio.py  — single Batch save implementation (FR-A01)
def is_batch_tab() -> bool: ...                 # one predicate (FR-003)
def save_file(filepath: str) -> None:
    """Batch tab: atomic consolidated-JSON save of the active Batch.
    Non-Batch tab: unchanged (NotImplementedError). Raises RuntimeError with
    an actionable message when no active Batch / unreadable tab / write error;
    never leaves a partial file at `filepath`."""

# api/workfile.py
class FlameBatchWorkfileHost:
    def save_workfile(self, dst_path=None) -> None: ...   # -> workio.save_file + remember path
    def get_workfile_extensions(self) -> list[str]: ...   # [".json"]

# api/pipeline.py
class FlameHost(HostBase, ILoadHost, IPublishHost, IWorkfileHost):
    def save_workfile(self, dst_path=None): ...           # delegate: get_flame_workfile_host()
    def open_workfile(self, filepath): ...
    def get_current_workfile(self): ...
    def workfile_has_unsaved_changes(self): ...           # -> None
    def get_workfile_extensions(self): ...                # tab-aware at call time

# plugins/publish/collect_current_file.py
class CollectCurrentFile(pyblish.api.ContextPlugin):      # order = CollectorOrder - 0.5, hosts=["flame"]
    # context.data["currentFile"] = latest workfile path or None (key always set)

# plugins/publish/validate_batch_workfile_saved.py
class ValidateBatchWorkfileSaved(pyblish.api.ContextPlugin):
    # hosts=["flame"], order=ValidatorOrder - 0.2, actions=[RepairContextAction]
    # runs only when a Batch instance is in context (same predicate as CollectBatchVersion)
    # fails when not host.list_workfiles(project, folder, task)       (FR-A13/A18)
    @classmethod
    def repair(cls, context) -> None: ...   # ayon_core.pipeline.workfile.save_next_version()
```

Error contract (FR-A14, final wording in tasks): title "Batch has no saved
workfile"; body names the Batch group, why it matters, and both ways out
(Workfiles tool or Repair).
