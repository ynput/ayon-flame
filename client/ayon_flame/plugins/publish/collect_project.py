import pyblish.api
from pprint import pformat

import ayon_flame.api as ayfapi


class CollecFlameProject(pyblish.api.ContextPlugin):
    """Inject the current project data into current context."""

    label = "Collect Flame project"
    order = pyblish.api.CollectorOrder - 0.492

    def process(self, context):
        # update context with main project attributes
        project = ayfapi.get_current_project()
        project_data = {
            "flameProject": project,
            "currentFile": f"Flame/{project.name}"
        }

        self.log.debug(f">>> Project data: {pformat(project_data)}")
        context.data.update(project_data)
