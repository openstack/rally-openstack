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

from rally.common import logging
from rally.common import validation

from rally_openstack.common import consts
from rally_openstack.common import osclients
from rally_openstack.common.services.network import neutron
from rally_openstack.task import context


LOG = logging.getLogger(__name__)


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="ports", platform="openstack", order=355)
class Ports(context.OpenStackContext):
    """Pre-create Neutron ports for scenarios that need them.

    Requires the ``network`` context to run first (lower order number).
    Ports are stored per project in ``context["tenants"][tid]["ports"]``
    and selected at runtime via ``iteration % len(ports)``.
    """

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "ports_per_project": {
                "type": "integer",
                "minimum": 1,
            },
        },
        "additionalProperties": False,
    }

    DEFAULT_CONFIG = {
        "ports_per_project": 1,
    }

    config: dict

    def setup(self) -> None:
        for user, tenant_id in self._iterate_per_tenants():
            tenant_ctx = self.context["tenants"][tenant_id]
            tenant_ctx["ports"] = []
            networks = tenant_ctx.get("networks", [])
            if not networks:
                raise ValueError(
                    "No networks found for project %s. "
                    "Ensure network@openstack context is configured."
                    % tenant_id)

            client = neutron.NeutronService(
                osclients.Clients(user["credential"]),
                name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions(),
            )
            for i in range(self.config["ports_per_project"]):
                network = networks[i % len(networks)]
                port = client.create_port(network_id=network["id"])
                tenant_ctx["ports"].append(port)

    def cleanup(self) -> None:
        for user, tenant_id in self._iterate_per_tenants():
            client = neutron.NeutronService(
                osclients.Clients(user["credential"]),
                name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions(),
            )
            for port in self.context["tenants"][tenant_id].get(
                    "ports", []):
                with logging.ExceptionLogger(
                        LOG,
                        "Failed to delete port %s for project %s"
                        % (port["id"], tenant_id)):
                    client.delete_port(port["id"])
