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
from rally_openstack.task.scenarios.octavia import utils as octavia_utils

"""Scenarios for Octavia Loadbalancer."""


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_list_loadbalancers",
                    platform="openstack")
class CreateAndListLoadbalancers(octavia_utils.OctaviaBase):

    def run(self, description=None, admin_state=True,
            listeners=None, flavor_id=None, provider=None,
            vip_qos_policy_id=None):
        """Create a loadbalancer per each subnet and then list loadbalancers.

        :param description: Human-readable description of the loadbalancer
        :param admin_state: The administrative state of the loadbalancer,
            which is up(true) or down(false)
        :param listeners: The associated listener id, if any
        :param flavor_id: The ID of the flavor
        :param provider: Provider name for the loadbalancer
        :param vip_qos_policy_id: The ID of the QoS policy
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                subnet_id=subnet_id,
                description=description,
                admin_state=admin_state,
                project_id=project_id,
                listeners=listeners,
                flavor_id=flavor_id,
                provider=provider,
                vip_qos_policy_id=vip_qos_policy_id)
            loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
        self.octavia.load_balancer_list()


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_delete_loadbalancers",
                    platform="openstack")
class CreateAndDeleteLoadbalancers(octavia_utils.OctaviaBase):

    def run(self, description=None, admin_state=True,
            listeners=None, flavor_id=None, provider=None,
            vip_qos_policy_id=None):
        """Create a loadbalancer per each subnet and then delete loadbalancer

        :param description: Human-readable description of the loadbalancer
        :param admin_state: The administrative state of the loadbalancer,
            which is up(true) or down(false)
        :param listeners: The associated listener id, if any
        :param flavor_id: The ID of the flavor
        :param provider: Provider name for the loadbalancer
        :param vip_qos_policy_id: The ID of the QoS policy
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                subnet_id=subnet_id,
                description=description,
                admin_state=admin_state,
                project_id=project_id,
                listeners=listeners,
                flavor_id=flavor_id,
                provider=provider,
                vip_qos_policy_id=vip_qos_policy_id)
            loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            self.octavia.load_balancer_delete(
                loadbalancer["id"])


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_update_loadbalancers",
                    platform="openstack")
class CreateAndUpdateLoadBalancers(octavia_utils.OctaviaBase):

    def run(self, description=None, admin_state=True,
            listeners=None, flavor_id=None, provider=None,
            vip_qos_policy_id=None):
        """Create a loadbalancer per each subnet and then update

        :param description: Human-readable description of the loadbalancer
        :param admin_state: The administrative state of the loadbalancer,
            which is up(true) or down(false)
        :param listeners: The associated listener id, if any
        :param flavor_id: The ID of the flavor
        :param provider: Provider name for the loadbalancer
        :param vip_qos_policy_id: The ID of the QoS policy
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                subnet_id=subnet_id,
                description=description,
                admin_state=admin_state,
                project_id=project_id,
                listeners=listeners,
                flavor_id=flavor_id,
                provider=provider,
                vip_qos_policy_id=vip_qos_policy_id)
            loadbalancers.append(lb)

            update_loadbalancer = {
                "name": self.generate_random_name()
            }

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            self.octavia.load_balancer_set(
                lb_id=loadbalancer["id"],
                lb_update_args=update_loadbalancer)


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_stats_loadbalancers",
                    platform="openstack")
class CreateAndShowStatsLoadBalancers(octavia_utils.OctaviaBase):

    def run(self, description=None, admin_state=True,
            listeners=None, flavor_id=None, provider=None,
            vip_qos_policy_id=None):
        """Create a loadbalancer per each subnet and stats

        :param description: Human-readable description of the loadbalancer
        :param admin_state: The administrative state of the loadbalancer,
            which is up(true) or down(false)
        :param listeners: The associated listener id, if any
        :param flavor_id: The ID of the flavor
        :param provider: Provider name for the loadbalancer
        :param vip_qos_policy_id: The ID of the QoS policy
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                subnet_id=subnet_id,
                description=description,
                admin_state=admin_state,
                project_id=project_id,
                listeners=listeners,
                flavor_id=flavor_id,
                provider=provider,
                vip_qos_policy_id=vip_qos_policy_id)
            loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            self.octavia.load_balancer_stats_show(
                loadbalancer["id"])


@validation.add("required_services", services=[consts.Service.OCTAVIA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["octavia"]},
                    name="Octavia.create_and_show_loadbalancers",
                    platform="openstack")
class CreateAndShowLoadBalancers(octavia_utils.OctaviaBase):

    def run(self, description=None, admin_state=True,
            listeners=None, flavor_id=None, provider=None,
            vip_qos_policy_id=None):
        """Create a loadbalancer per each subnet and then compare

        :param description: Human-readable description of the loadbalancer
        :param admin_state: The administrative state of the loadbalancer,
            which is up(true) or down(false)
        :param listeners: The associated listener id, if any
        :param flavor_id: The ID of the flavor
        :param provider: Provider name for the loadbalancer
        :param vip_qos_policy_id: The ID of the QoS policy
        """
        subnets = []
        loadbalancers = []
        networks = self.context.get("tenant", {}).get("networks", [])
        project_id = self.context["tenant"]["id"]
        for network in networks:
            subnets.extend(network.get("subnets", []))
        for subnet_id in subnets:
            lb = self.octavia.load_balancer_create(
                subnet_id=subnet_id,
                description=description,
                admin_state=admin_state,
                project_id=project_id,
                listeners=listeners,
                flavor_id=flavor_id,
                provider=provider,
                vip_qos_policy_id=vip_qos_policy_id)
            loadbalancers.append(lb)

        for loadbalancer in loadbalancers:
            self.octavia.wait_for_loadbalancer_prov_status(loadbalancer)
            self.octavia.load_balancer_show(
                loadbalancer["id"])
