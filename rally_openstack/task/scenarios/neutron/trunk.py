# Copyright 2014: Intel Inc.
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

from rally.common import cfg
from rally.task import types
from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.neutron import utils as neutron_utils
from rally_openstack.task.scenarios.nova import utils as nova_utils


CONF = cfg.CONF

"""Scenarios for Neutron Trunk."""


@validation.add("number", param_name="subport_count", minval=1,
                integer_only=True)
@validation.add("required_services", services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["neutron"]},
                    name="NeutronTrunks.create_and_list_trunks")
class CreateAndListTrunks(neutron_utils.NeutronScenario):

    def run(self, network_create_args=None, subport_count=10):
        """Create and a given number of trunks with subports and list all trunks

        :param network_create_args: dict, POST /v2.0/networks request
                                    options. Deprecated.
        :param trunk_count: int, number of trunk ports
        :param subport_count: int, number of subports per trunk
        """
        net = self._create_network(network_create_args or {})
        ports = [self._create_port(net, {}) for _ in range(subport_count + 1)]
        parent, subports = ports[0], ports[1:]
        subport_payload = [{"port_id": p["port"]["id"],
                            "segmentation_type": "vlan",
                            "segmentation_id": seg_id}
                           for seg_id, p in enumerate(subports, start=1)]
        trunk_payload = {"port_id": parent["port"]["id"],
                         "sub_ports": subport_payload}
        trunk = self._create_trunk(trunk_payload)
        self._update_port(parent, {"device_id": "sometrunk"})
        self._list_trunks()
        self._list_subports_by_trunk(trunk["trunk"]["id"])
        self._list_ports_by_device_id("sometrunk")


@types.convert(image={"type": "glance_image"},
               flavor={"type": "nova_flavor"})
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=(consts.Service.NOVA,
                                               consts.Service.NEUTRON))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["neutron", "nova"]},
                    name="NeutronTrunks.boot_server_with_subports",
                    platform="openstack")
class BootServerWithSubports(nova_utils.NovaScenario,
                             neutron_utils.NeutronScenario):

    def run(self, image, flavor, network_create_args=None, subport_count=10):
        """Boot a server with subports.

        Returns when the server is actually booted and in "ACTIVE" state.
        :param image: image ID or instance for server creation
        :param flavor: int, flavor ID or instance for server creation
        :param network_create_args: arguments for creating network
        :param subport_count: number of subports for the trunk port
        """
        kwargs = {}
        ports = []
        network_create_args = network_create_args or {}
        for _ in range(subport_count + 1):
            net, subnet = self._create_network_and_subnets(
                network_create_args=network_create_args)
            ports.append(self._create_port(
                net, {"fixed_ips": [{
                    "subnet_id": subnet[0]["subnet"]["id"]}]}))
        parent, subports = ports[0], ports[1:]
        subport_payload = [{"port_id": p["port"]["id"],
                            "segmentation_type": "vlan",
                            "segmentation_id": seg_id}
                           for seg_id, p in enumerate(subports, start=1)]
        trunk_payload = {"port_id": parent["port"]["id"],
                         "sub_ports": subport_payload}
        self._create_trunk(trunk_payload)
        kwargs["nics"] = [{"port-id": parent["port"]["id"]}]
        self._boot_server(image, flavor, **kwargs)


@types.convert(image={"type": "glance_image"},
               flavor={"type": "nova_flavor"})
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=(consts.Service.NOVA,
                                               consts.Service.NEUTRON))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["neutron", "nova"]},
                    name="NeutronTrunks.boot_server_and_add_subports",
                    platform="openstack")
class BootServerAndAddSubports(nova_utils.NovaScenario,
                               neutron_utils.NeutronScenario):

    def run(self, image, flavor, network_create_args=None, subport_count=10):
        """Boot a server and add subports.

        Returns when the server is actually booted and in "ACTIVE" state.
        :param image: image ID or instance for server creation
        :param flavor: int, flavor ID or instance for server creation
        :param network_create_args: arguments for creating network
        :param subport_count: number of subports for the trunk port
        """
        kwargs = {}
        ports = []
        network_create_args = network_create_args or {}
        for _ in range(subport_count + 1):
            net, subnet = self._create_network_and_subnets(
                network_create_args=network_create_args)
            ports.append(self._create_port(
                net, {"fixed_ips": [{
                    "subnet_id": subnet[0]["subnet"]["id"]}]}))
        parent, subports = ports[0], ports[1:]
        trunk_payload = {"port_id": parent["port"]["id"]}
        trunk = self._create_trunk(trunk_payload)
        kwargs["nics"] = [{"port-id": parent["port"]["id"]}]
        self._boot_server(image, flavor, **kwargs)
        for seg_id, p in enumerate(subports, start=1):
            subport_payload = [{"port_id": p["port"]["id"],
                                "segmentation_type": "vlan",
                                "segmentation_id": seg_id}]
            self._add_subports_to_trunk(trunk["trunk"]["id"], subport_payload)


@types.convert(image={"type": "glance_image"},
               flavor={"type": "nova_flavor"})
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=(consts.Service.NOVA,
                                               consts.Service.NEUTRON))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["neutron", "nova"]},
                    name="NeutronTrunks.boot_server_and_batch_add_subports",
                    platform="openstack")
class BootServerAndBatchAddSubports(nova_utils.NovaScenario,
                                    neutron_utils.NeutronScenario):

    def run(self, image, flavor, network_create_args=None,
            subports_per_batch=10, batches=5):
        """Boot a server and add subports in batches.

        Returns when the server is actually booted and in "ACTIVE" state.
        :param image: image ID or instance for server creation
        :param flavor: int, flavor ID or instance for server creation
        :param network_create_args: arguments for creating network
        :param subports_per_batch: number of subports per batches
        :param batches: number of batches to create subports in
        """
        kwargs = {}
        ports = []
        network_create_args = network_create_args or {}
        for _ in range(subports_per_batch * batches + 1):
            net, subnet = self._create_network_and_subnets(
                network_create_args=network_create_args)
            ports.append(self._create_port(
                net, {"fixed_ips": [{
                    "subnet_id": subnet[0]["subnet"]["id"]}]}))
        parent, subports = ports[0], ports[1:]
        trunk_payload = {"port_id": parent["port"]["id"]}
        trunk = self._create_trunk(trunk_payload)
        kwargs["nics"] = [{"port-id": parent["port"]["id"]}]
        self._boot_server(image, flavor, **kwargs)
        begin = 0
        for _ in range(0, batches):
            end = begin + subports_per_batch
            subport_payload = [{"port_id": p["port"]["id"],
                                "segmentation_type": "vlan",
                                "segmentation_id": seg_id}
                               for seg_id, p in enumerate(
                                   subports[slice(begin, end)],
                                   start=begin + 1)]
            begin = begin + subports_per_batch
            self._add_subports_to_trunk(trunk["trunk"]["id"], subport_payload)
