#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

from __future__ import absolute_import
import os
import sys
import subprocess
import json
import xml.dom.minidom as minidom
from copy import deepcopy
import datetime
from adsk.libwiretapPythonClientAPI import (  # noqa
    WireTapClientInit,
    WireTapClientUninit,
    WireTapNodeHandle,
    WireTapServerHandle,
    WireTapInt,
    WireTapStr
)


class WireTapCom(object):
    """
    Comunicator class wrapper for talking to WireTap db.

    This way we are able to set new project with settings and
    correct colorspace policy. Also we are able to create new user
    or get actual user with similar name (users are usually cloning
    their profiles and adding date stamp into suffix).
    """

    def __init__(self, host_name=None, volume_name=None, group_name=None):
        """Initialisation of WireTap communication class

        Args:
            host_name (str, optional): Name of host server. Defaults to None.
            volume_name (str, optional): Name of volume. Defaults to None.
            group_name (str, optional): Name of user group. Defaults to None.
        """
        self._flame_version = None

        # wiretap tools dir path
        self.wiretap_tools_dir = os.getenv("AYON_WIRETAP_TOOLS")
        self.host_name = host_name or "localhost"

        # initialize WireTap client
        WireTapClientInit()
        self._server = WireTapServerHandle("{}:IFFFS".format(self.host_name))
        if not self._server.ping():
            raise RuntimeError(
                "Failed to ping WireTap server, check host: {}".format(
                    self.host_name
                )
            )

        print("WireTap connected at '{}'...".format(self.host_name))

        # Stone+Wire (Flame < 2026)
        # Default to installation values.
        if self._get_flame_version()[0] < 2026:
            self.volume_name = volume_name or "stonefs"
            self.group_name = group_name or "staff"
        else:
            self.volume_name = None  # no volumes in Flame>2026
            self.group_name = group_name  # current user group if None

    def close(self):
        self._server = None
        WireTapClientUninit()
        print("WireTap closed...")

    def get_launch_args(
            self, project_name, project_data, user_name, **kwargs):
        """Return Flame launch arguments to be used by AYON launcher.

        Args:
            project_name (str): name of project
            project_data (dict): Flame compatible project data
            user_name (str): name of user

        Returns:
            list: arguments
        """
        flame_major_version, _ = self._get_flame_version()
        workspace_name = kwargs.get("workspace_name")

        project_exists = self._project_prep(project_name)
        if not project_exists:
            if flame_major_version < 2026:
                self._set_project_syncolor_colorspace(
                    project_name,
                    sync_color_policy=kwargs.get("syncolor_policy")
                )
            else:
                self._set_project_ocio_config(
                    project_data,
                    kwargs.get("ocio_config"),
                    default_config=kwargs.get("default_ocio_config")
                )
            self._set_project_settings(project_name, project_data)

        launch_args = [
            "--start-project={}".format(project_name),
            "--create-workspace",
        ]

        # user profiles have been removed in flame 2025
        if flame_major_version < 2025:
            user_name = self._user_prep(user_name)
            launch_args.append("--start-user={}".format(user_name))

        if workspace_name is None:
            # default workspace
            print("Using a default workspace")
            return launch_args

        else:
            print("Using a custom workspace '{}'".format(workspace_name))
            self._workspace_prep(project_name, workspace_name)
            launch_args.append("--start-workspace={}".format(workspace_name))
            return launch_args

    def _get_flame_version(self):
        """Get the flame version.

        Returns:
            int: The flame year, e.g. 2025
            int: The flame minor version, e.g. 2

        Raises:
            AttributeError: unable to retrieve the flame version.
        """
        if self._flame_version is not None:
            return self._flame_version

        version_major = WireTapInt(0)
        version_minor = WireTapInt(0)
        version_exists = self._server.getVersion(version_major, version_minor)

        # Note: this usually happens when the wiretap server is broken
        # due to conflicting installations. Best re-install Flame from scratch.
        if not version_exists:
            raise AttributeError(
                    "Cannot get flame version details: {}".format(
                        self._server.lastError()
                    )
                )

        self._flame_version = int(version_major), int(version_minor)
        return self._flame_version

    def _workspace_prep(self, project_name, workspace_name):
        """Prepare a workspace, create it if needed.

        Args:
            project_name (str): project name
            workspace_name (str): workspace name

        Raises:
            AttributeError: unable to create workspace
        """
        workspace_exists = self._child_is_in_parent_path(
            "/projects/{}".format(project_name), workspace_name, "WORKSPACE"
        )
        if not workspace_exists:
            project = WireTapNodeHandle(
                self._server, "/projects/{}".format(project_name))

            workspace_node = WireTapNodeHandle()
            created_workspace = project.createNode(
                workspace_name, "WORKSPACE", workspace_node)

            if not created_workspace:
                raise AttributeError(
                    "Cannot create workspace `{}` in "
                    "project `{}`: `{}`".format(
                        workspace_name, project_name, project.lastError())
                )

        print(
            "Workspace `{}` is successfully created".format(workspace_name)
        )

    def _project_prep(self, project_name):
        """Prepare a project, create it needed.

        Args:
            project_name (str): project name

        Returns:
            bool: True if the project already existed

        Raises:
            AttributeError: unable to create project
            RuntimeError: project creation command failed
        """
        # test if project exists
        project_exists = self._child_is_in_parent_path(
            "/projects", project_name, "PROJECT")

        if project_exists:
            print("Project '{}' already exists.".format(project_name))
            return True

        # Flame < 2025: Stone+Wire,
        # create project in provided volume name
        if self._get_flame_version()[0] < 2026:
            volumes = self._get_all_volumes()

            if len(volumes) == 0:
                raise AttributeError(
                    "Not able to create new project: no volumes available."
                    "Do create a volume '{}' in Flame.".format(
                        self.volume_name
                    )
                )

            # check if volumes exists
            if self.volume_name not in volumes:
                raise AttributeError(
                    (
                        "Not able to create new project: volume '{}' does not "
                        "exist in Flame. Available volumes are: {}"
                    ).format(self.volume_name, volumes)
                )

            parent_args = ["-n", os.path.join("/volumes", self.volume_name)]

        # Flame >= 2026: Postgres + filesystem
        else:
            parent_args = ["-n", "/projects", "-t", "PROJECT"]

        # form cmd arguments
        project_create_cmd_args = [
            os.path.join(self.wiretap_tools_dir, "wiretap_create_node")
        ]
        project_create_cmd_args.extend(parent_args)
        project_create_cmd_args.extend(["-d", project_name])

        if self.group_name:
            project_create_cmd_args.extend(["-g", self.group_name])

        print(
            "Project creation cmd line: {}".format(
                " ".join(project_create_cmd_args)
            )
        )
        process = subprocess.Popen(
            project_create_cmd_args,
            cwd=os.path.expanduser('~'),
            preexec_fn=_subprocess_preexec_fn,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        output, stderr = process.communicate()

        if process.returncode != 0:
            message = (
                (
                    "Cannot create project '{}' (project_group: {}) "
                    "in Flame: {}, {}"
                ).format(
                    project_name,
                    self.group_name,
                    output.strip(),
                    stderr.strip()
                )
            )
            raise RuntimeError(message)

        print("New project '{}' is created.".format(project_name))
        return False

    def _get_all_volumes(self):
        """Request all available volumens from WireTap

        Returns:
            list: all available volumes in server

        Rises:
            AttributeError: unable to get any volumes children from server
        """
        root = WireTapNodeHandle(self._server, "/volumes")
        children_num = WireTapInt(0)

        get_children_num = root.getNumChildren(children_num)
        if not get_children_num:
            raise AttributeError(
                "Cannot get number of volumes: {}".format(root.lastError())
            )

        volumes = []

        # go through all children and get volume names
        child_obj = WireTapNodeHandle()
        for child_idx in range(children_num):

            # get a child
            if not root.getChild(child_idx, child_obj):
                raise AttributeError(
                    "Unable to get child: {}".format(root.lastError()))

            node_name = WireTapStr()
            get_children_name = child_obj.getDisplayName(node_name)

            if not get_children_name:
                raise AttributeError(
                    "Unable to get child name: {}".format(
                        child_obj.lastError())
                )

            volumes.append(node_name.c_str())

        return volumes

    def _user_prep(self, user_name):
        """Ensuring user does exists in user's stack

        Args:
            user_name (str): name of a user

        Raises:
            AttributeError: unable to create user
        """

        # get all used usernames in db
        used_names = self._get_usernames()
        print(">> used_names: {}".format(used_names))

        # filter only those which are sharing input user name
        filtered_users = [user for user in used_names if user_name in user]

        if filtered_users:
            # TODO: need to find lastly created following regex pattern for
            # date used in name
            return filtered_users.pop()

        # create new user name with date in suffix
        now = datetime.datetime.now()  # current date and time
        date = now.strftime("%Y%m%d")
        new_user_name = "{}_{}".format(user_name, date)
        print(new_user_name)

        if not self._child_is_in_parent_path("/users", new_user_name, "USER"):
            # Create the new user
            users = WireTapNodeHandle(self._server, "/users")

            user_node = WireTapNodeHandle()
            created_user = users.createNode(new_user_name, "USER", user_node)
            if not created_user:
                raise AttributeError(
                    "User {} cannot be created: {}".format(
                        new_user_name, users.lastError())
                )

            print("User `{}` is created".format(new_user_name))
            return new_user_name

    def _get_usernames(self):
        """Requesting all available users from WireTap

        Returns:
            list: all available user names

        Raises:
            AttributeError: there are no users in server
        """
        root = WireTapNodeHandle(self._server, "/users")
        children_num = WireTapInt(0)

        get_children_num = root.getNumChildren(children_num)
        if not get_children_num:
            raise AttributeError(
                "Cannot get number of volumes: {}".format(root.lastError())
            )

        usernames = []

        # go through all children and get volume names
        child_obj = WireTapNodeHandle()
        for child_idx in range(children_num):

            # get a child
            if not root.getChild(child_idx, child_obj):
                raise AttributeError(
                    "Unable to get child: {}".format(root.lastError()))

            node_name = WireTapStr()
            get_children_name = child_obj.getDisplayName(node_name)

            if not get_children_name:
                raise AttributeError(
                    "Unable to get child name: {}".format(
                        child_obj.lastError())
                )

            usernames.append(node_name.c_str())

        return usernames

    def _child_is_in_parent_path(self, parent_path, child_name, child_type):
        """Checking if a given child is in parent path.

        Args:
            parent_path (str): db path to parent
            child_name (str): name of child
            child_type (str): type of child

        Raises:
            AttributeError: Not able to get number of children
            AttributeError: Not able to get children form parent
            AttributeError: Not able to get children name
            AttributeError: Not able to get children type

        Returns:
            bool: True if child is in parent path
        """
        parent = WireTapNodeHandle(self._server, parent_path)

        # iterate number of children
        children_num = WireTapInt(0)
        requested = parent.getNumChildren(children_num)
        if not requested:
            raise AttributeError((
                "Error: Cannot request number of "
                "children from the node {}. Make sure your "
                "wiretap service is running: {}").format(
                    parent_path, parent.lastError())
            )

        # iterate children
        child_obj = WireTapNodeHandle()
        for child_idx in range(children_num):
            if not parent.getChild(child_idx, child_obj):
                raise AttributeError(
                    "Cannot get child: {}".format(
                        parent.lastError()))

            node_name = WireTapStr()
            node_type = WireTapStr()

            if not child_obj.getDisplayName(node_name):
                raise AttributeError(
                    "Unable to get child name: %s" % child_obj.lastError()
                )
            if not child_obj.getNodeTypeStr(node_type):
                raise AttributeError(
                    "Unable to obtain child type: %s" % child_obj.lastError()
                )

            if (node_name.c_str() == child_name) and (
                    node_type.c_str() == child_type):
                return True

        return False

    def _set_project_settings(self, project_name, project_data):
        """Setting project attributes.

        Args:
            project_name (str): name of project
            project_data (dict): data with project attributes
                                 (flame compatible)

        Raises:
            AttributeError: Not able to set project attributes
        """
        flame_year, flame_minor = self._get_flame_version()

        # Flame 2026.0 has an inconsistent project creation
        # XML API (still uses SetupDir but no description field)
        if flame_year == 2026 and flame_minor == 0:
            project_data = project_data.copy()
            project_data.pop("Description", None)

        # No more SetupDir required from Flame 2026.1
        elif flame_year >= 2026:
            project_data = project_data.copy()
            project_data.pop("SetupDir", None)

        # generated xml from project_data dict
        _xml = "<Project>"
        for key, value in project_data.items():
            _xml += "<{}>{}</{}>".format(key, value, key)
        _xml += "</Project>"

        pretty_xml = minidom.parseString(_xml).toprettyxml()
        print("__ xml: {}".format(pretty_xml))

        # set project data to wiretap
        project_node = WireTapNodeHandle(
            self._server, "/projects/{}".format(project_name))

        if not project_node.setMetaData("XML", _xml):
            raise AttributeError(
                "Not able to set project attributes {}. Error: {}".format(
                    project_name, project_node.lastError())
            )

        print("Project settings successfully set.")


    def _set_project_ocio_config(
        self,
        project_data,
        ocio_config,
        default_config=None,
    ):
        """Set project's OCIO config (Flame >= 2026 only).

        Args:
            project_data (dict): project data,
            ocio_config (str or None): name of config
            default_config (str or None): optional path to default config
        """
        if ocio_config:
            if not os.path.exists(ocio_config):
                print(
                    "Ignored OCIO config (not found): {}".format(ocio_config)
                )
                return
        elif default_config:
            if not os.path.exists(default_config):
                print(
                    "Ignored default OCIO config (not found): {}".format(
                        default_config
                    )
                )
                return
            ocio_config = default_config

        if ocio_config:
            print("Set project OCIO config: {}".format(ocio_config))
            project_data["OCIOConfigFile"] = ocio_config


    def _set_project_syncolor_colorspace(
            self,
            project_name,
            sync_color_policy=None,
    ):
        """Set project's syncolor policy (Flame < 2026 only).

        Args:
            project_name (str): name of project
            sync_color_policy (str or None): name of policy

        Raises:
            RuntimeError: Not able to set colorspace policy
        """
        color_policy = sync_color_policy or "Legacy"

        # check if the colour policy in custom dir
        if "/" in color_policy:
            # if unlikely full path was used make it redundant
            color_policy = color_policy.replace("/syncolor/policies/", "")
            # expecting input is `Shared/NameOfPolicy`
            color_policy = "/syncolor/policies/{}".format(
                color_policy)
        else:
            color_policy = "/syncolor/policies/Autodesk/{}".format(
                color_policy)

        # ensure color policy exists
        try:
            subprocess.run(
                [
                    os.path.join(
                        self.wiretap_tools_dir,
                        "wiretap_resolve_path"
                    ),
                    "-p",
                    color_policy,
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            print(
                "Ignored invalid provided color policy: {}".format(
                    color_policy
                )
            )
            return

        # set color policy on project
        project_colorspace_cmd = [
            os.path.join(
                self.wiretap_tools_dir,
                "wiretap_duplicate_node"
            ),
            "-s",
            color_policy,
            "-n",
            "/projects/{}/syncolor".format(project_name)
        ]

        print(project_colorspace_cmd)

        exit_code = subprocess.call(
            project_colorspace_cmd,
            cwd=os.path.expanduser('~'),
            preexec_fn=_subprocess_preexec_fn
        )

        if exit_code != 0:
            RuntimeError("Cannot set colorspace {} on project {}".format(
                color_policy, project_name
            ))


def _subprocess_preexec_fn():
    """ Helper function

    Setting permission mask to 0777
    """
    os.setpgrp()
    os.umask(0o000)


if __name__ == "__main__":
    # get json exchange data
    json_path = sys.argv[-1]
    json_data = open(json_path).read()
    in_data = json.loads(json_data)
    out_data = deepcopy(in_data)

    # get main server attributes
    host_name = in_data.pop("host_name")
    volume_name = in_data.pop("volume_name")
    group_name = in_data.pop("group_name")

    # initialize class
    wiretap_handler = WireTapCom(host_name, volume_name, group_name)

    try:
        app_args = wiretap_handler.get_launch_args(
            project_name=in_data.pop("project_name"),
            project_data=in_data.pop("project_data"),
            user_name=in_data.pop("user_name"),
            **in_data
        )
    finally:
        wiretap_handler.close()

    # set returned args back to out data
    out_data.update({
        "app_args": app_args
    })

    # write it out back to the exchange json file
    with open(json_path, "w") as file_stream:
        json.dump(out_data, file_stream, indent=4)
