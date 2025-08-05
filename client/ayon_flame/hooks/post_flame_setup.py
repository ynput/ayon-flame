from copy import deepcopy
import os
import json
from typing import List

from ayon_applications import PostLaunchHook, LaunchTypes
from ayon_core.pipeline import Anatomy


class FlamePostLaunch(PostLaunchHook):

    app_groups = {"flame"}
    order = 1
    launch_types = {LaunchTypes.local}

    def _create_bookmarks(
        self, project_name:str, bookmark_paths: List[str]
    ) -> None:
        """Create bookmarks for project.

        As multiple roots can be defined, this will create a bookmark for each
        root respectively.

        This will respect previously set up bookmarks, only removing duplicate
        bookmarked paths in favour of the new ones.

        Args:
            project_name (str): Name of the project
            bookmark_paths (list[str]): Bookmark paths
        """
        bookmarks_path = os.path.join(
            "/opt/Autodesk/project",
            project_name,
            "status",
            "cf_bookmarks.json"
        )
        if os.path.exists(bookmarks_path):
            with open(bookmarks_path, "r") as bookmark_file:
                data = json.load(bookmark_file)
        else:
            # this is the default bookmark data
            data = {
                "DlBookmark": {
                    "Version": 1,
                    "Sections": [
                        {
                            "Section": "Project",
                            "Bookmarks": [
                                {
                                    "Bookmark": "Project Home",
                                    "Path": "<project home>",
                                    "Visibility": "Global"
                                }
                            ]
                        }
                    ]
                }
            }
        bookmarks = []
        for path in bookmark_paths:
            name = path.rstrip(os.path.sep)
            bookmarks.append(
                {
                    "Bookmark": (
                        name
                        if len(bookmark_paths) > 1
                        else os.path.basename(name)
                    ),
                    "Path": path,
                    "Visibility": "Global"
                }
            )
        for section in data["DlBookmark"]["Sections"]:
            if section["Section"] == "Project":
                for bookmark in deepcopy(section["Bookmarks"]):
                    if bookmark["Path"] in bookmark_paths:
                        section["Bookmarks"].remove(bookmark)
                # insert directly after the default "Project Home" bookmark
                section["Bookmarks"] = section[
                    "Bookmarks"
                ][:1] + bookmarks + section["Bookmarks"][1:]
                break
        os.makedirs(os.path.dirname(bookmarks_path), exist_ok=True)
        with open(bookmarks_path, "w") as bookmark_file:
            json.dump(data, bookmark_file, ensure_ascii=True, indent=4)

    def execute(self) -> None:
        """Collects the project root paths (multiple can be defined in ayon)
        and sets up the bookmarks for flame to point to them.
        """
        project_entity = self.data["project_entity"]
        project_name = project_entity["name"]
        anatomy = Anatomy(project_name, project_entity=project_entity)
        bookmark_paths = [
            os.path.join(str(root), project_name, "")  # for trailing '/' to match flame
            for root in anatomy.roots.values()
            if os.path.isdir(str(root))
        ]
        self._create_bookmarks(project_name, bookmark_paths)
