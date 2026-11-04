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

from unittest import mock

from rally_openstack.common.clients import neutron as neutron_client
from rally_openstack.task.scenarios.neutron import fwaas
from tests.unit import test


RULE_KWARGS_UNSET = {
    "protocol": neutron_client.FirewallProtocol.ANY,
    "action": None,
    "ip_version": None,
    "source_ip_address": None,
    "destination_ip_address": None,
    "source_port": None,
    "destination_port": None,
    "enabled": None,
    "description": None,
}


class FirewallScenarioTestCase(test.ScenarioTestCase):

    def make_scenario(self, scenario_cls, **context):
        self.context.update(context)
        scenario = scenario_cls(self.context, clients=mock.MagicMock())
        scenario.generate_random_name = mock.Mock(return_value="new-name")
        return scenario

    def test_create_and_list_firewall_rules(self):
        scenario = self.make_scenario(fwaas.CreateAndListFirewallRules)
        neutron = scenario._clients.neutron

        scenario.run(protocol=neutron_client.FirewallProtocol.UDP,
                     destination_port=53)

        neutron.create_firewall_rule.assert_called_once_with(
            **dict(RULE_KWARGS_UNSET, protocol="udp", destination_port=53))
        neutron.list_firewall_rules.assert_called_once_with()

    def test_create_and_delete_firewall_rules(self):
        scenario = self.make_scenario(fwaas.CreateAndDeleteFirewallRules)
        neutron = scenario._clients.neutron
        neutron.create_firewall_rule.return_value = mock.Mock(id="rule-id")

        scenario.run(action=neutron_client.FirewallAction.ALLOW)

        neutron.create_firewall_rule.assert_called_once_with(
            **dict(RULE_KWARGS_UNSET, action="allow"))
        neutron.delete_firewall_rule.assert_called_once_with("rule-id")

    def test_create_and_update_firewall_rules(self):
        scenario = self.make_scenario(fwaas.CreateAndUpdateFirewallRules)
        neutron = scenario._clients.neutron
        neutron.create_firewall_rule.return_value = mock.Mock(id="rule-id")

        scenario.run(enabled=True,
                     firewall_rule_update_args={"enabled": False})

        neutron.create_firewall_rule.assert_called_once_with(
            **dict(RULE_KWARGS_UNSET, enabled=True))
        neutron.update_firewall_rule.assert_called_once_with(
            "rule-id", name="new-name", enabled=False)

    def test_create_and_update_firewall_rules_name_only(self):
        scenario = self.make_scenario(fwaas.CreateAndUpdateFirewallRules)
        neutron = scenario._clients.neutron
        neutron.create_firewall_rule.return_value = mock.Mock(id="rule-id")

        scenario.run()

        neutron.update_firewall_rule.assert_called_once_with(
            "rule-id", name="new-name")

    def test_create_and_list_firewall_policies(self):
        scenario = self.make_scenario(fwaas.CreateAndListFirewallPolicies)
        neutron = scenario._clients.neutron

        scenario.run(description="desc")

        neutron.create_firewall_policy.assert_called_once_with(
            audited=None, description="desc")
        neutron.list_firewall_policies.assert_called_once_with()

    def test_create_and_delete_firewall_policies(self):
        scenario = self.make_scenario(fwaas.CreateAndDeleteFirewallPolicies)
        neutron = scenario._clients.neutron
        neutron.create_firewall_policy.return_value = mock.Mock(
            id="policy-id")

        scenario.run(audited=True)

        neutron.create_firewall_policy.assert_called_once_with(
            audited=True, description=None)
        neutron.delete_firewall_policy.assert_called_once_with("policy-id")

    def test_create_and_update_firewall_policies(self):
        scenario = self.make_scenario(fwaas.CreateAndUpdateFirewallPolicies)
        neutron = scenario._clients.neutron
        neutron.create_firewall_policy.return_value = mock.Mock(
            id="policy-id")

        scenario.run(firewall_policy_update_args={"description": "new"})

        neutron.create_firewall_policy.assert_called_once_with(
            audited=None, description=None)
        neutron.update_firewall_policy.assert_called_once_with(
            "policy-id", name="new-name", description="new")

    def test_create_policy_add_and_remove_rules(self):
        scenario = self.make_scenario(fwaas.CreatePolicyAddAndRemoveRules)
        neutron = scenario._clients.neutron
        neutron.create_firewall_rule.return_value = mock.Mock(id="rule-id")
        neutron.create_firewall_policy.return_value = mock.Mock(
            id="policy-id")

        scenario.run(firewall_rule_args={"protocol": "tcp"},
                     firewall_policy_args={"audited": True})

        neutron.create_firewall_rule.assert_called_once_with(protocol="tcp")
        neutron.create_firewall_policy.assert_called_once_with(audited=True)
        neutron.insert_firewall_rule_in_policy.assert_called_once_with(
            "policy-id", "rule-id")
        neutron.remove_firewall_rule_from_policy.assert_called_once_with(
            "policy-id", "rule-id")

    def test_create_and_list_firewall_groups(self):
        scenario = self.make_scenario(fwaas.CreateAndListFirewallGroups)
        neutron = scenario._clients.neutron

        scenario.run(admin_state_up=False)

        neutron.create_firewall_group.assert_called_once_with(
            admin_state_up=False, description=None)
        neutron.list_firewall_groups.assert_called_once_with()

    def test_create_and_delete_firewall_groups(self):
        scenario = self.make_scenario(fwaas.CreateAndDeleteFirewallGroups)
        neutron = scenario._clients.neutron
        neutron.create_firewall_group.return_value = mock.Mock(id="group-id")

        scenario.run()

        neutron.create_firewall_group.assert_called_once_with(
            admin_state_up=None, description=None)
        neutron.delete_firewall_group.assert_called_once_with("group-id")

    def test_create_and_update_firewall_groups(self):
        scenario = self.make_scenario(fwaas.CreateAndUpdateFirewallGroups)
        neutron = scenario._clients.neutron
        neutron.create_firewall_group.return_value = mock.Mock(id="group-id")

        scenario.run(description="old",
                     firewall_group_update_args={"admin_state_up": False})

        neutron.create_firewall_group.assert_called_once_with(
            admin_state_up=None, description="old")
        neutron.update_firewall_group.assert_called_once_with(
            "group-id", name="new-name", admin_state_up=False)

    def _mock_group_with_rule(self, neutron):
        neutron.create_firewall_rule.side_effect = [
            mock.Mock(id="rule-1"), mock.Mock(id="rule-2")]
        neutron.create_firewall_policy.side_effect = [
            mock.Mock(id="ingress"), mock.Mock(id="egress"),
            mock.Mock(id="new-ingress")]
        neutron.create_firewall_group.return_value = mock.Mock(id="group-id")

    def _router_networks(self, iteration):
        return {
            "iteration": iteration,
            "tenant": {"networks": [{"router_port_id": "port-0"},
                                    {"router_port_id": "port-1"}]},
        }

    def test_associate_disassociate_firewall_group_router_ports(self):
        scenario = self.make_scenario(
            fwaas.AssociateDisassociateFirewallGroupRouterPorts,
            **self._router_networks(iteration=3))
        neutron = scenario._clients.neutron
        self._mock_group_with_rule(neutron)

        scenario.run(firewall_rule_args={"action": "allow"},
                     firewall_group_args={"description": "desc"})

        neutron.create_firewall_rule.assert_called_once_with(action="allow")
        self.assertEqual(2, neutron.create_firewall_policy.call_count)
        self.assertEqual(
            [mock.call("ingress", "rule-1"), mock.call("egress", "rule-1")],
            neutron.insert_firewall_rule_in_policy.call_args_list)
        neutron.create_firewall_group.assert_called_once_with(
            ingress_firewall_policy_id="ingress",
            egress_firewall_policy_id="egress",
            description="desc")
        neutron.associate_firewall_group_ports.assert_called_once_with(
            "group-id", ["port-1"])
        neutron.disassociate_firewall_group_ports.assert_called_once_with(
            "group-id")

    def test_update_policy_on_active_firewall_group(self):
        scenario = self.make_scenario(
            fwaas.UpdatePolicyOnActiveFirewallGroup,
            **self._router_networks(iteration=2))
        neutron = scenario._clients.neutron
        self._mock_group_with_rule(neutron)

        scenario.run()

        neutron.associate_firewall_group_ports.assert_called_once_with(
            "group-id", ["port-0"])
        neutron.insert_firewall_rule_in_policy.assert_called_with(
            "new-ingress", "rule-2")
        neutron.update_firewall_group.assert_called_once_with(
            "group-id", name="new-name",
            ingress_firewall_policy_id="new-ingress")
        neutron.disassociate_firewall_group_ports.assert_called_once_with(
            "group-id")

    def test_update_policy_on_active_firewall_group_disassociates(self):
        scenario = self.make_scenario(
            fwaas.UpdatePolicyOnActiveFirewallGroup,
            **self._router_networks(iteration=0))
        neutron = scenario._clients.neutron
        self._mock_group_with_rule(neutron)
        neutron.update_firewall_group.side_effect = RuntimeError("boom")

        self.assertRaises(RuntimeError, scenario.run)

        neutron.disassociate_firewall_group_ports.assert_called_once_with(
            "group-id")
