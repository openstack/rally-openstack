# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import io
import os
import zipfile

from rally.common import validation
from rally import exceptions

from rally_openstack.common import consts
from rally_openstack.common import osclients
from rally_openstack.task.cleanup import manager as resource_manager
from rally_openstack.task import context
from rally_openstack.task.scenarios.murano import utils as mutils


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="murano_packages", platform="openstack", order=401)
class PackageGenerator(context.OpenStackContext):
    """Context class for uploading applications for murano."""

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "app_package": {
                "type": "string",
            }
        },
        "required": ["app_package"],
        "additionalProperties": False
    }

    def setup(self):
        is_config_app_dir = False
        pckg_path = os.path.expanduser(self.config["app_package"])
        if zipfile.is_zipfile(pckg_path):
            zip_name = pckg_path
        elif os.path.isdir(pckg_path):
            is_config_app_dir = True
            zip_name = mutils.pack_dir(pckg_path)
        else:
            msg = "There is no zip archive or directory by this path: %s"
            raise exceptions.ContextSetupFailure(msg=msg % pckg_path,
                                                 ctx_name=self.get_name())

        for user, tenant_id in self._iterate_per_tenants():
            clients = osclients.Clients(user["credential"])
            self.context["tenants"][tenant_id]["packages"] = []
            if is_config_app_dir:
                self.context["tenants"][tenant_id]["murano_ctx"] = zip_name
            # TODO(astudenov): use self.generate_random_name()
            with open(zip_name, "rb") as f:
                file = io.BytesIO(f.read())
            package = clients.murano().packages.create(
                {"categories": ["Web"], "tags": ["tag"]},
                {"file": file})

            self.context["tenants"][tenant_id]["packages"].append(package)

    def cleanup(self):
        resource_manager.cleanup(names=["murano.packages"],
                                 users=self.context.get("users", []),
                                 superclass=self.__class__,
                                 task_id=self.get_owner_id())
