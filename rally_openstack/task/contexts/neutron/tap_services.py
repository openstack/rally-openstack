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
from rally_openstack.task import context


LOG = logging.getLogger(__name__)


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="tap_services", platform="openstack", order=360)
class TapServices(context.OpenStackContext):
    """Prepare tap services on ports supplied by the ports context.

    Each service uses a different port from the start of the project's pool.
    Service IDs and destination port IDs are stored per project in
    ``context["tenants"][project_id]["tap_services"]``.

    The port pool must contain at least ``services_per_project`` ports.
    Tap-flow tasks also need source ports outside this destination pool;
    provision at least ``services_per_project + ceil(concurrency / projects)``
    ports per project for those tasks. Multiple flows can share a service.
    """

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "services_per_project": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    }

    DEFAULT_CONFIG = {"services_per_project": 1}

    config: dict

    def setup(self) -> None:
        for user, project_id in self._iterate_per_projects():
            project = self.context["tenants"][project_id]
            project["tap_services"] = []
            ports = project.get("ports", [])
            count = self.config["services_per_project"]
            if len(ports) < count:
                raise ValueError(
                    "Project %s requires at least %d context ports to create "
                    "tap services. Configure ports_per_project accordingly."
                    % (project_id, count))

            client = osclients.Clients(
                user["credential"],
                name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions(),
            ).neutron
            for port in ports[:count]:
                service = client.create_tap_service(port_id=port["id"])
                project["tap_services"].append(
                    {"id": service.id, "port_id": port["id"]})

    def cleanup(self) -> None:
        for user, project_id in self._iterate_per_projects():
            client = osclients.Clients(user["credential"]).neutron
            for service in self.context["tenants"][project_id].get(
                    "tap_services", []):
                with logging.ExceptionLogger(
                        LOG, "Failed to delete tap service %s for project %s"
                        % (service["id"], project_id)):
                    client.delete_tap_service(service["id"])
