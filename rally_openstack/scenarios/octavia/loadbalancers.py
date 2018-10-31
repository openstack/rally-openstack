# Copyright 2018: Red Hat Inc.
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

from rally.task import validation

from rally_openstack import consts
from rally_openstack import scenario
from rally_openstack.services.loadbalancer import octavia

"""Scenarios for Octavia Loadbalancer."""


class OctaviaBase(scenario.OpenStackScenario):
    """Base class for Octavia scenarios with basic atomic actions."""

    def __init__(self, context=None, admin_clients=None, clients=None):
        super(OctaviaBase, self).__init__(context, admin_clients, clients)
        self.octavia = octavia.Octavia(
            self._clients, name_generator=self.generate_random_name,
            atomic_inst=self.atomic_actions())


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_list_loadbalancers",
                    platform="openstack")
class CreateAndListLoadbalancers(OctaviaBase):

    def run(self):
        """Create a loadbalancer per each subnet and then list loadbalancers.

        Measure the "Octavia loadbalancer list" command performance.
        The scenario creates a loadbalancer for every subnet and then lists
        loadbalancers.
        """
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        for network in networks:
            for subnet_id in network.get("subnets", []):
                lb = self.octavia.load_balancer_create(subnet_id)
                loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
        self.octavia.load_balancer_list()
