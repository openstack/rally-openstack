# Copyright 2014: Mirantis Inc.
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
from rally_openstack.common.services.network import neutron
from rally_openstack.task.cleanup import manager as resource_manager
from rally_openstack.task import context


LOG = logging.getLogger(__name__)


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="network", platform="openstack", order=350)
class Network(context.OpenStackContext):
    """Create networking resources.

    This creates networks for all tenants, and optionally creates
    another resources like subnets and routers.
    """

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "start_cidr": {
                "type": "string"
            },
            "networks_per_tenant": {
                "type": "integer",
                "minimum": 1
            },
            "subnets_per_network": {
                "type": "integer",
                "minimum": 1
            },
            "network_create_args": {
                "type": "object",
                "additionalProperties": True
            },
            "dns_nameservers": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True
            },
            "dualstack": {
                "type": "boolean",
            },
            "router": {
                "type": "object",
                "properties": {
                    "external": {
                        "type": "boolean",
                        "description": "Create a new external router."
                    },
                    "enable_snat": {
                        "type": "boolean",
                        "description": "Whether to enable SNAT for a router "
                                       "if there is following extension or not"
                    },
                    "external_gateway_info": {
                        "description": "The external gateway information .",
                        "type": "object",
                        "properties": {
                            "network_id": {"type": "string"},
                            "enable_snat": {"type": "boolean"}
                        },
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            }
        },
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "start_cidr": "10.2.0.0/24",
        "networks_per_tenant": 1,
        "subnets_per_network": 1,
        "network_create_args": {},
        "router": {"external": True},
        "dualstack": False
    }

    def setup(self):
        # NOTE(rkiran): Some clients are not thread-safe. Thus during
        #               multithreading/multiprocessing, it is likely the
        #               sockets are left open. This problem is eliminated by
        #               creating a connection in setup and cleanup separately.

        for user, tenant_id in self._iterate_per_tenants():
            self.context["tenants"][tenant_id]["networks"] = []
            self.context["tenants"][tenant_id]["subnets"] = []

            client = neutron.NeutronService(
                user["credential"].clients(),
                name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions()
            )
            network_create_args = self.config["network_create_args"].copy()
            subnet_create_args = {
                "start_cidr": (self.config["start_cidr"]
                               if not self.config["dualstack"] else None)}
            if "dns_nameservers" in self.config:
                dns_nameservers = self.config["dns_nameservers"]
                subnet_create_args["dns_nameservers"] = dns_nameservers

            router_create_args = dict(self.config["router"] or {})
            if not router_create_args:
                # old behaviour - empty dict means no router create
                router_create_args = None
            elif "external" in router_create_args:
                external = router_create_args.pop("external")
                router_create_args["discover_external_gw"] = external

            for i in range(self.config["networks_per_tenant"]):

                net_infra = client.create_network_topology(
                    network_create_args=network_create_args,
                    subnet_create_args=subnet_create_args,
                    subnets_dualstack=self.config["dualstack"],
                    subnets_count=self.config["subnets_per_network"],
                    router_create_args=router_create_args)

                if net_infra["routers"]:
                    router_id = net_infra["routers"][0]["id"]
                else:
                    router_id = None
                net_infra["network"]["router_id"] = router_id

                self.context["tenants"][tenant_id]["networks"].append(
                    net_infra["network"]
                )
                self.context["tenants"][tenant_id]["subnets"].extend(
                    net_infra["subnets"]
                )

    def cleanup(self):
        resource_manager.cleanup(
            names=[
                "neutron.subnet", "neutron.network", "neutron.router",
                "neutron.port"
            ],
            admin=self.context.get("admin"),
            users=self.context.get("users", []),
            task_id=self.get_owner_id(),
            superclass=self.__class__
        )
