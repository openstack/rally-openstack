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

from rally_openstack.common import consts
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.octavia import utils

"""Scenarios for Octavia Loadbalancer pools."""


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_list_pools",
                    platform="openstack")
class CreateAndListPools(utils.OctaviaBase):

    def run(self, protocol, lb_algorithm):
        """Create a loadbalancer pool per each subnet and then pools.

        :param protocol: protocol for which the pool listens
        :param lb_algorithm: loadbalancer algorithm
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                project_id=project_id,
                subnet_id=subnet_id)
            loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            self.octavia.pool_create(
                lb_id=loadbalancer["id"],
                protocol=protocol, lb_algorithm=lb_algorithm)
        self.octavia.pool_list()


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_delete_pools",
                    platform="openstack")
class CreateAndDeletePools(utils.OctaviaBase):

    def run(self, protocol, lb_algorithm):
        """Create a pool per each subnet and then delete pool

        :param protocol: protocol for which the pool listens
        :param lb_algorithm: loadbalancer algorithm
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                project_id=project_id,
                subnet_id=subnet_id)
            loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            pools = self.octavia.pool_create(
                lb_id=loadbalancer["id"],
                protocol=protocol, lb_algorithm=lb_algorithm)
            self.octavia.pool_delete(pools["id"])


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_update_pools",
                    platform="openstack")
class CreateAndUpdatePools(utils.OctaviaBase):

    def run(self, protocol, lb_algorithm):
        """Create a pool per each subnet and then update

        :param protocol: protocol for which the pool listens
        :param lb_algorithm: loadbalancer algorithm
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                project_id=project_id,
                subnet_id=subnet_id)
            loadbalancers.append(lb)

        update_pool = {
            "name": self.generate_random_name()
        }

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            pools = self.octavia.pool_create(
                lb_id=loadbalancer["id"],
                protocol=protocol, lb_algorithm=lb_algorithm)
            self.octavia.pool_set(
                pool_id=pools["id"], pool_update_args=update_pool)


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_show_pools",
                    platform="openstack")
class CreateAndShowPools(utils.OctaviaBase):

    def run(self, protocol, lb_algorithm):
        """Create a pool per each subnet and show it

        :param protocol: protocol for which the pool listens
        :param lb_algorithm: loadbalancer algorithm
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                project_id=project_id,
                subnet_id=subnet_id)
            loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            pools = self.octavia.pool_create(
                lb_id=loadbalancer["id"],
                protocol=protocol, lb_algorithm=lb_algorithm)
            self.octavia.pool_show(pools["id"])
