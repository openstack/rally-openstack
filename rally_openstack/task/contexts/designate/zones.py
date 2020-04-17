# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from rally.common import validation

from rally_openstack.common import consts
from rally_openstack.task.cleanup import manager as resource_manager
from rally_openstack.task import context
from rally_openstack.task.scenarios.designate import utils
from rally_openstack.task.scenarios.neutron import utils as neutron_utils


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="zones", platform="openstack", order=600)
class ZoneGenerator(context.OpenStackContext):
    """Context to add `zones_per_tenant` zones for each tenant."""

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "zones_per_tenant": {
                "type": "integer",
                "minimum": 1
            },
            "set_zone_in_network": {
                "type": "boolean",
                "description": "Update network with created DNS zone."
            }
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "zones_per_tenant": 1,
        "set_zone_in_network": False
    }

    def setup(self):
        for user, tenant_id in self._iterate_per_tenants(
                self.context["users"]):
            self.context["tenants"][tenant_id].setdefault("zones", [])
            designate_util = utils.DesignateScenario(
                {"user": user,
                 "task": self.context["task"],
                 "owner_id": self.context["owner_id"]})
            for i in range(self.config["zones_per_tenant"]):
                zone = designate_util._create_zone()
                self.context["tenants"][tenant_id]["zones"].append(zone)
        if self.config["set_zone_in_network"]:
            for user, tenant_id in self._iterate_per_tenants(
                    self.context["users"]):
                tenant = self.context["tenants"][tenant_id]

                network_update_args = {
                    "dns_domain": tenant["zones"][0]["name"]
                }
                body = {"network": network_update_args}
                scenario = neutron_utils.NeutronScenario(
                    context={"user": user, "task": self.context["task"],
                             "owner_id": self.context["owner_id"]}
                )
                scenario.clients("neutron").update_network(
                    tenant["networks"][0]["id"], body)

    def cleanup(self):
        resource_manager.cleanup(names=["designate.zones"],
                                 users=self.context.get("users", []),
                                 superclass=utils.DesignateScenario,
                                 task_id=self.get_owner_id())
