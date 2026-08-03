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
from rally_openstack.task.scenarios.neutron import utils


"""Scenarios for Neutron FWaaS."""


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_list_firewall_rules",
    platform="openstack")
class CreateAndListFirewallRules(utils.NeutronScenario):

    def run(self, firewall_rule_create_args=None):
        """Create and list Neutron firewall rules.

        Measure the "neutron firewall-rule-create" and "neutron
        firewall-rule-list" command performance.

        :param firewall_rule_create_args: dict, POST /v2.0/fwaas/firewall_rules
                                          request options
        """
        firewall_rule_create_args = firewall_rule_create_args or {}
        self._create_firewall_rule(**firewall_rule_create_args)
        self._list_firewall_rules()


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_delete_firewall_rules",
    platform="openstack")
class CreateAndDeleteFirewallRules(utils.NeutronScenario):

    def run(self, firewall_rule_create_args=None):
        """Create and delete Neutron firewall rules.

        Measure the "neutron firewall-rule-create" and "neutron
        firewall-rule-delete" command performance.

        :param firewall_rule_create_args: dict, POST /v2.0/fwaas/firewall_rules
                                          request options
        """
        firewall_rule_create_args = firewall_rule_create_args or {}
        firewall_rule = self._create_firewall_rule(
            **firewall_rule_create_args)
        self._delete_firewall_rule(firewall_rule)


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_update_firewall_rules",
    platform="openstack")
class CreateAndUpdateFirewallRules(utils.NeutronScenario):

    def run(self, firewall_rule_create_args=None,
            firewall_rule_update_args=None):
        """Create and update Neutron firewall rules.

        Measure the "neutron firewall-rule-create" and "neutron
        firewall-rule-update" command performance.

        :param firewall_rule_create_args: dict, POST /v2.0/fwaas/firewall_rules
                                          request options
        :param firewall_rule_update_args: dict, PUT /v2.0/fwaas/firewall_rules
                                          update options
        """
        firewall_rule_create_args = firewall_rule_create_args or {}
        firewall_rule_update_args = firewall_rule_update_args or {}
        firewall_rule = self._create_firewall_rule(
            **firewall_rule_create_args)
        self._update_firewall_rule(firewall_rule,
                                   **firewall_rule_update_args)
