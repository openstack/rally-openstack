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
from rally_openstack.common.wrappers import network as network_wrapper
from rally_openstack.task import context


LOG = logging.getLogger(__name__)


@validation.add("required_platform", platform="openstack", admin=True,
                users=True)
@context.configure(name="lbaas", platform="openstack", order=360)
class Lbaas(context.OpenStackContext):
    """Creates a lb-pool for every subnet created in network context."""
    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "pool": {
                "type": "object",
                "additionalProperties": True
            },
            "lbaas_version": {
                "type": "integer",
                "minimum": 1
            }
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "pool": {
            "lb_method": "ROUND_ROBIN",
            "protocol": "HTTP"
        },
        "lbaas_version": 1
    }

    config: dict

    def setup(self):
        net_wrapper = network_wrapper.wrap(
            osclients.Clients(self.context["admin"]["credential"]),
            self, config=self.config)

        use_lb, msg = net_wrapper.supports_extension("lbaas")
        if not use_lb:
            LOG.info(msg)
            return

        # Creates a lb-pool for every subnet created in network context.
        for user, tenant_id in self._iterate_per_tenants():
            for network in self.context["tenants"][tenant_id]["networks"]:
                for subnet in network.get("subnets", []):
                    if self.config["lbaas_version"] == 1:
                        network.setdefault("lb_pools", []).append(
                            net_wrapper.create_v1_pool(
                                tenant_id,
                                subnet,
                                **self.config["pool"]))
                    else:
                        raise NotImplementedError(
                            "Context for LBaaS version %s not implemented."
                            % self.config["lbaas_version"])

    def cleanup(self):
        net_wrapper = network_wrapper.wrap(
            osclients.Clients(self.context["admin"]["credential"]),
            self, config=self.config)
        for tenant_id, tenant_ctx in self.context["tenants"].items():
            for network in tenant_ctx.get("networks", []):
                for pool in network.get("lb_pools", []):
                    with logging.ExceptionLogger(
                            LOG,
                            "Failed to delete pool %(pool)s for tenant "
                            "%(tenant)s" % {"pool": pool["pool"]["id"],
                                            "tenant": tenant_id}):
                        if self.config["lbaas_version"] == 1:
                            net_wrapper.delete_v1_pool(pool["pool"]["id"])
