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

from __future__ import annotations

import typing_extensions as te

from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.common.clients.neutron import FirewallAction
from rally_openstack.common.clients.neutron import FirewallProtocol
from rally_openstack.common.clients.neutron import IPVersion
from rally_openstack.common.clients.neutron import PortRange
from rally_openstack.task import scenario


"""Scenarios for Neutron FWaaS v2."""


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_list_firewall_rules",
    platform="openstack")
class CreateAndListFirewallRules(scenario.OpenStackScenario):

    def run(
        self,
        protocol: FirewallProtocol = FirewallProtocol.ANY,
        action: FirewallAction | None = None,
        ip_version: IPVersion | None = None,
        source_ip_address: str | None = None,
        destination_ip_address: str | None = None,
        source_port: PortRange | None = None,
        destination_port: PortRange | None = None,
        enabled: bool | None = None,
        description: str | None = None,
    ) -> None:
        """Create and list Neutron firewall rules.

        :param protocol: IP protocol to match, ``any`` for every protocol
        :param action: what to do with the traffic the rule matches
        :param ip_version: IP version of the traffic to match
        :param source_ip_address: source address or CIDR to match
        :param destination_ip_address: destination address or CIDR to match
        :param source_port: source port or ``min:max`` range to match
        :param destination_port: destination port or ``min:max`` range
        :param enabled: whether the rule is in effect
        :param description: description of the rule
        """
        self._clients.neutron.create_firewall_rule(
            protocol=protocol,
            action=action,
            ip_version=ip_version,
            source_ip_address=source_ip_address,
            destination_ip_address=destination_ip_address,
            source_port=source_port,
            destination_port=destination_port,
            enabled=enabled,
            description=description,
        )
        self._clients.neutron.list_firewall_rules()


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_delete_firewall_rules",
    platform="openstack")
class CreateAndDeleteFirewallRules(scenario.OpenStackScenario):

    def run(
        self,
        protocol: FirewallProtocol = FirewallProtocol.ANY,
        action: FirewallAction | None = None,
        ip_version: IPVersion | None = None,
        source_ip_address: str | None = None,
        destination_ip_address: str | None = None,
        source_port: PortRange | None = None,
        destination_port: PortRange | None = None,
        enabled: bool | None = None,
        description: str | None = None,
    ) -> None:
        """Create and delete Neutron firewall rules.

        :param protocol: IP protocol to match, ``any`` for every protocol
        :param action: what to do with the traffic the rule matches
        :param ip_version: IP version of the traffic to match
        :param source_ip_address: source address or CIDR to match
        :param destination_ip_address: destination address or CIDR to match
        :param source_port: source port or ``min:max`` range to match
        :param destination_port: destination port or ``min:max`` range
        :param enabled: whether the rule is in effect
        :param description: description of the rule
        """
        rule = self._clients.neutron.create_firewall_rule(
            protocol=protocol,
            action=action,
            ip_version=ip_version,
            source_ip_address=source_ip_address,
            destination_ip_address=destination_ip_address,
            source_port=source_port,
            destination_port=destination_port,
            enabled=enabled,
            description=description,
        )
        self._clients.neutron.delete_firewall_rule(rule.id)


class FirewallRuleArgs(te.TypedDict, total=False):
    """Firewall rule attributes a task may set.

    The name is always generated by rally.
    """

    protocol: FirewallProtocol
    action: FirewallAction
    ip_version: IPVersion
    source_ip_address: str
    destination_ip_address: str
    source_port: PortRange
    destination_port: PortRange
    enabled: bool
    description: str


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_update_firewall_rules",
    platform="openstack")
class CreateAndUpdateFirewallRules(scenario.OpenStackScenario):

    def run(
        self,
        protocol: FirewallProtocol = FirewallProtocol.ANY,
        action: FirewallAction | None = None,
        ip_version: IPVersion | None = None,
        source_ip_address: str | None = None,
        destination_ip_address: str | None = None,
        source_port: PortRange | None = None,
        destination_port: PortRange | None = None,
        enabled: bool | None = None,
        description: str | None = None,
        firewall_rule_update_args: FirewallRuleArgs | None = None,
    ) -> None:
        """Create and update Neutron firewall rules.

        The update always gives the rule a new name.

        :param protocol: IP protocol to match, ``any`` for every protocol
        :param action: what to do with the traffic the rule matches
        :param ip_version: IP version of the traffic to match
        :param source_ip_address: source address or CIDR to match
        :param destination_ip_address: destination address or CIDR to match
        :param source_port: source port or ``min:max`` range to match
        :param destination_port: destination port or ``min:max`` range
        :param enabled: whether the rule is in effect
        :param description: description of the rule
        :param firewall_rule_update_args: rule attributes to change
        """
        rule = self._clients.neutron.create_firewall_rule(
            protocol=protocol,
            action=action,
            ip_version=ip_version,
            source_ip_address=source_ip_address,
            destination_ip_address=destination_ip_address,
            source_port=source_port,
            destination_port=destination_port,
            enabled=enabled,
            description=description,
        )
        self._clients.neutron.update_firewall_rule(
            rule.id,
            name=self.generate_random_name(),
            **(firewall_rule_update_args or {}))


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_list_firewall_policies",
    platform="openstack")
class CreateAndListFirewallPolicies(scenario.OpenStackScenario):

    def run(
        self,
        audited: bool | None = None,
        description: str | None = None,
    ) -> None:
        """Create and list Neutron firewall policies.

        :param audited: whether to mark the policy as audited
        :param description: description of the policy
        """
        self._clients.neutron.create_firewall_policy(
            audited=audited, description=description)
        self._clients.neutron.list_firewall_policies()


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_delete_firewall_policies",
    platform="openstack")
class CreateAndDeleteFirewallPolicies(scenario.OpenStackScenario):

    def run(
        self,
        audited: bool | None = None,
        description: str | None = None,
    ) -> None:
        """Create and delete Neutron firewall policies.

        :param audited: whether to mark the policy as audited
        :param description: description of the policy
        """
        policy = self._clients.neutron.create_firewall_policy(
            audited=audited, description=description)
        self._clients.neutron.delete_firewall_policy(policy.id)


class FirewallPolicyArgs(te.TypedDict, total=False):
    """Firewall policy attributes a task may set.

    The name is always generated by rally.
    """

    audited: bool
    description: str


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_update_firewall_policies",
    platform="openstack")
class CreateAndUpdateFirewallPolicies(scenario.OpenStackScenario):

    def run(
        self,
        audited: bool | None = None,
        description: str | None = None,
        firewall_policy_update_args: FirewallPolicyArgs | None = None,
    ) -> None:
        """Create and update Neutron firewall policies.

        The update always gives the policy a new name.

        :param audited: whether to mark the policy as audited
        :param description: description of the policy
        :param firewall_policy_update_args: policy attributes to change
        """
        policy = self._clients.neutron.create_firewall_policy(
            audited=audited, description=description)
        self._clients.neutron.update_firewall_policy(
            policy.id,
            name=self.generate_random_name(),
            **(firewall_policy_update_args or {}))


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_policy_add_and_remove_rules",
    platform="openstack")
class CreatePolicyAddAndRemoveRules(scenario.OpenStackScenario):

    def run(
        self,
        firewall_rule_args: FirewallRuleArgs | None = None,
        firewall_policy_args: FirewallPolicyArgs | None = None,
    ) -> None:
        """Create a policy, then add and remove a firewall rule.

        Measure firewall policy create plus insert-rule and remove-rule
        performance.

        :param firewall_rule_args: attributes of the rule to create
        :param firewall_policy_args: attributes of the policy to create
        """
        neutron = self._clients.neutron
        rule = neutron.create_firewall_rule(**(firewall_rule_args or {}))
        policy = neutron.create_firewall_policy(
            **(firewall_policy_args or {}))
        neutron.insert_firewall_rule_in_policy(policy.id, rule.id)
        neutron.remove_firewall_rule_from_policy(policy.id, rule.id)


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_list_firewall_groups",
    platform="openstack")
class CreateAndListFirewallGroups(scenario.OpenStackScenario):

    def run(
        self,
        admin_state_up: bool | None = None,
        description: str | None = None,
    ) -> None:
        """Create and list Neutron firewall groups.

        :param admin_state_up: administrative state of the group
        :param description: description of the group
        """
        self._clients.neutron.create_firewall_group(
            admin_state_up=admin_state_up, description=description)
        self._clients.neutron.list_firewall_groups()


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_delete_firewall_groups",
    platform="openstack")
class CreateAndDeleteFirewallGroups(scenario.OpenStackScenario):

    def run(
        self,
        admin_state_up: bool | None = None,
        description: str | None = None,
    ) -> None:
        """Create and delete Neutron firewall groups.

        :param admin_state_up: administrative state of the group
        :param description: description of the group
        """
        group = self._clients.neutron.create_firewall_group(
            admin_state_up=admin_state_up, description=description)
        self._clients.neutron.delete_firewall_group(group.id)


class FirewallGroupArgs(te.TypedDict, total=False):
    """Firewall group attributes a task may set.

    The name is always generated by rally.
    """

    admin_state_up: bool
    description: str


@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.create_and_update_firewall_groups",
    platform="openstack")
class CreateAndUpdateFirewallGroups(scenario.OpenStackScenario):

    def run(
        self,
        admin_state_up: bool | None = None,
        description: str | None = None,
        firewall_group_update_args: FirewallGroupArgs | None = None,
    ) -> None:
        """Create and update Neutron firewall groups.

        The update always gives the group a new name.

        :param admin_state_up: administrative state of the group
        :param description: description of the group
        :param firewall_group_update_args: group attributes to change
        """
        group = self._clients.neutron.create_firewall_group(
            admin_state_up=admin_state_up, description=description)
        self._clients.neutron.update_firewall_group(
            group.id,
            name=self.generate_random_name(),
            **(firewall_group_update_args or {}))


class FirewallGroupScenario(scenario.OpenStackScenario):
    """Base class for scenarios that put a firewall group on router ports."""

    def _router_port_id(self) -> str:
        """Pick a router interface port of the project for this iteration.

        Iterations running at the same time get different ports as long as
        the project has enough networks, since a port belongs to one
        firewall group at a time.
        """
        networks = self.context["tenant"]["networks"]
        network = networks[self.context["iteration"] % len(networks)]
        return network["router_port_id"]

    def _create_firewall_group_with_rule(
        self,
        firewall_rule_args: FirewallRuleArgs | None,
        firewall_policy_args: FirewallPolicyArgs | None,
        firewall_group_args: FirewallGroupArgs | None,
    ) -> str:
        """Create a group whose ingress and egress policies hold one rule.

        :returns: id of the group
        """
        neutron = self._clients.neutron
        rule = neutron.create_firewall_rule(**(firewall_rule_args or {}))
        ingress = neutron.create_firewall_policy(
            **(firewall_policy_args or {}))
        neutron.insert_firewall_rule_in_policy(ingress.id, rule.id)
        egress = neutron.create_firewall_policy(
            **(firewall_policy_args or {}))
        neutron.insert_firewall_rule_in_policy(egress.id, rule.id)
        group = neutron.create_firewall_group(
            ingress_firewall_policy_id=ingress.id,
            egress_firewall_policy_id=egress.id,
            **(firewall_group_args or {}))
        return group.id


@validation.add("required_networks_per_project")
@validation.add("required_context_config", context_name="network",
                context_config={"router": {"external": True}}, exact=False)
@validation.add("required_contexts", contexts=["network"])
@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.associate_disassociate_firewall_group_router_ports",
    platform="openstack")
class AssociateDisassociateFirewallGroupRouterPorts(FirewallGroupScenario):

    def run(
        self,
        firewall_rule_args: FirewallRuleArgs | None = None,
        firewall_policy_args: FirewallPolicyArgs | None = None,
        firewall_group_args: FirewallGroupArgs | None = None,
    ) -> None:
        """Associate and disassociate a firewall group on a router port.

        Requires ``network`` context with ``router: {external: true}``
        and ``networks_per_tenant >= ceil(concurrency / projects)``.

        Measure associate and disassociate firewall group performance.

        :param firewall_rule_args: attributes of the rule to create
        :param firewall_policy_args: attributes of the ingress and egress
            policies to create
        :param firewall_group_args: attributes of the group to create
        """
        group_id = self._create_firewall_group_with_rule(
            firewall_rule_args, firewall_policy_args, firewall_group_args)
        self._clients.neutron.associate_firewall_group_ports(
            group_id, [self._router_port_id()])
        self._clients.neutron.disassociate_firewall_group_ports(group_id)


@validation.add("required_networks_per_project")
@validation.add("required_context_config", context_name="network",
                context_config={"router": {"external": True}}, exact=False)
@validation.add("required_contexts", contexts=["network"])
@validation.add("required_neutron_extensions", extensions=["fwaas_v2"])
@validation.add("required_services",
                services=[consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["neutron"]},
    name="NeutronFWaaS.update_policy_on_active_firewall_group",
    platform="openstack")
class UpdatePolicyOnActiveFirewallGroup(FirewallGroupScenario):

    def run(
        self,
        firewall_rule_args: FirewallRuleArgs | None = None,
        firewall_policy_args: FirewallPolicyArgs | None = None,
        firewall_group_args: FirewallGroupArgs | None = None,
    ) -> None:
        """Update ingress policy on an active firewall group.

        Requires ``network`` context with ``router: {external: true}``
        and ``networks_per_tenant >= ceil(concurrency / projects)``.

        Attach a firewall group to a router port, swap the group's ingress
        policy while it remains associated, then disassociate the port so it
        can be reused by other iterations.

        :param firewall_rule_args: attributes of the rules to create
        :param firewall_policy_args: attributes of the policies to create
        :param firewall_group_args: attributes of the group to create
        """
        neutron = self._clients.neutron
        group_id = self._create_firewall_group_with_rule(
            firewall_rule_args, firewall_policy_args, firewall_group_args)
        neutron.associate_firewall_group_ports(
            group_id, [self._router_port_id()])
        try:
            rule = neutron.create_firewall_rule(**(firewall_rule_args or {}))
            policy = neutron.create_firewall_policy(
                **(firewall_policy_args or {}))
            neutron.insert_firewall_rule_in_policy(policy.id, rule.id)
            neutron.update_firewall_group(
                group_id,
                name=self.generate_random_name(),
                ingress_firewall_policy_id=policy.id)
        finally:
            neutron.disassociate_firewall_group_ports(group_id)
