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

import ddt

from rally_openstack.task.scenarios.neutron import fwaas
from tests.unit import test


@ddt.ddt
class NeutronFWaaSTestCase(test.TestCase):

    @ddt.data(
        {},
        {"firewall_rule_create_args": {}},
        {"firewall_rule_create_args": {"description": "fake-description"}},
    )
    @ddt.unpack
    def test_create_and_list_firewall_rules(
            self, firewall_rule_create_args=None):
        scenario = fwaas.CreateAndListFirewallRules()
        firewall_rule_data = firewall_rule_create_args or {}
        scenario._create_firewall_rule = mock.Mock()
        scenario._list_firewall_rules = mock.Mock()
        scenario.run(firewall_rule_create_args=firewall_rule_create_args)
        scenario._create_firewall_rule.assert_called_once_with(
            **firewall_rule_data)
        scenario._list_firewall_rules.assert_called_once_with()

    @ddt.data(
        {},
        {"firewall_rule_create_args": {}},
        {"firewall_rule_create_args": {"description": "fake-description"}},
    )
    @ddt.unpack
    def test_create_and_delete_firewall_rules(
            self, firewall_rule_create_args=None):
        scenario = fwaas.CreateAndDeleteFirewallRules()
        firewall_rule_data = firewall_rule_create_args or {}
        scenario._create_firewall_rule = mock.Mock()
        scenario._delete_firewall_rule = mock.Mock()
        scenario.run(firewall_rule_create_args=firewall_rule_create_args)
        scenario._create_firewall_rule.assert_called_once_with(
            **firewall_rule_data)
        scenario._delete_firewall_rule.assert_called_once_with(
            scenario._create_firewall_rule.return_value)

    @ddt.data(
        {},
        {"firewall_rule_create_args": {}},
        {"firewall_rule_create_args": {"description": "fake-description"}},
        {"firewall_rule_update_args": {}},
        {"firewall_rule_update_args": {"description": "fake-updated-descr"}},
    )
    @ddt.unpack
    def test_create_and_update_firewall_rules(
            self, firewall_rule_create_args=None,
            firewall_rule_update_args=None):
        scenario = fwaas.CreateAndUpdateFirewallRules()
        firewall_rule_data = firewall_rule_create_args or {}
        firewall_rule_update_data = firewall_rule_update_args or {}
        scenario._create_firewall_rule = mock.Mock()
        scenario._update_firewall_rule = mock.Mock()
        scenario.run(firewall_rule_create_args=firewall_rule_create_args,
                     firewall_rule_update_args=firewall_rule_update_args)
        scenario._create_firewall_rule.assert_called_once_with(
            **firewall_rule_data)
        scenario._update_firewall_rule.assert_called_once_with(
            scenario._create_firewall_rule.return_value,
            **firewall_rule_update_data)

    @ddt.data(
        {},
        {"firewall_policy_create_args": {}},
        {"firewall_policy_create_args": {"description": "fake-description"}},
    )
    @ddt.unpack
    def test_create_and_list_firewall_policies(
            self, firewall_policy_create_args=None):
        scenario = fwaas.CreateAndListFirewallPolicies()
        firewall_policy_data = firewall_policy_create_args or {}
        scenario._create_firewall_policy = mock.Mock()
        scenario._list_firewall_policies = mock.Mock()
        scenario.run(firewall_policy_create_args=firewall_policy_create_args)
        scenario._create_firewall_policy.assert_called_once_with(
            **firewall_policy_data)
        scenario._list_firewall_policies.assert_called_once_with()

    @ddt.data(
        {},
        {"firewall_policy_create_args": {}},
        {"firewall_policy_create_args": {"description": "fake-description"}},
    )
    @ddt.unpack
    def test_create_and_delete_firewall_policies(
            self, firewall_policy_create_args=None):
        scenario = fwaas.CreateAndDeleteFirewallPolicies()
        firewall_policy_data = firewall_policy_create_args or {}
        scenario._create_firewall_policy = mock.Mock()
        scenario._delete_firewall_policy = mock.Mock()
        scenario.run(firewall_policy_create_args=firewall_policy_create_args)
        scenario._create_firewall_policy.assert_called_once_with(
            **firewall_policy_data)
        scenario._delete_firewall_policy.assert_called_once_with(
            scenario._create_firewall_policy.return_value)

    @ddt.data(
        {},
        {"firewall_policy_create_args": {}},
        {"firewall_policy_create_args": {"description": "fake-description"}},
        {"firewall_policy_update_args": {}},
        {"firewall_policy_update_args": {"description": "fake-updated-descr"}},
    )
    @ddt.unpack
    def test_create_and_update_firewall_policies(
            self, firewall_policy_create_args=None,
            firewall_policy_update_args=None):
        scenario = fwaas.CreateAndUpdateFirewallPolicies()
        firewall_policy_data = firewall_policy_create_args or {}
        firewall_policy_update_data = firewall_policy_update_args or {}
        scenario._create_firewall_policy = mock.Mock()
        scenario._update_firewall_policy = mock.Mock()
        scenario.run(firewall_policy_create_args=firewall_policy_create_args,
                     firewall_policy_update_args=firewall_policy_update_args)
        scenario._create_firewall_policy.assert_called_once_with(
            **firewall_policy_data)
        scenario._update_firewall_policy.assert_called_once_with(
            scenario._create_firewall_policy.return_value,
            **firewall_policy_update_data)

    @ddt.data(
        {},
        {"firewall_rule_create_args": {"description": "fake-rule"}},
        {"firewall_policy_create_args": {"description": "fake-policy"}},
        {"firewall_rule_create_args": {"description": "fake-rule"},
         "firewall_policy_create_args": {"description": "fake-policy"}},
    )
    @ddt.unpack
    def test_create_policy_add_and_remove_rules(
            self, firewall_rule_create_args=None,
            firewall_policy_create_args=None):
        scenario = fwaas.CreatePolicyAddAndRemoveRules()
        firewall_rule_data = firewall_rule_create_args or {}
        firewall_policy_data = firewall_policy_create_args or {}
        scenario._create_firewall_rule = mock.Mock()
        scenario._create_firewall_policy = mock.Mock()
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._remove_firewall_rule_from_policy = mock.Mock()
        scenario.run(firewall_rule_create_args=firewall_rule_create_args,
                     firewall_policy_create_args=firewall_policy_create_args)
        scenario._create_firewall_rule.assert_called_once_with(
            **firewall_rule_data)
        scenario._create_firewall_policy.assert_called_once_with(
            **firewall_policy_data)
        scenario._insert_firewall_rule_in_policy.assert_called_once_with(
            scenario._create_firewall_policy.return_value,
            scenario._create_firewall_rule.return_value)
        scenario._remove_firewall_rule_from_policy.assert_called_once_with(
            scenario._create_firewall_policy.return_value,
            scenario._create_firewall_rule.return_value)

    @ddt.data(
        {},
        {"firewall_group_create_args": {}},
        {"firewall_group_create_args": {"description": "fake-description"}},
    )
    @ddt.unpack
    def test_create_and_list_firewall_groups(
            self, firewall_group_create_args=None):
        scenario = fwaas.CreateAndListFirewallGroups()
        firewall_group_data = firewall_group_create_args or {}
        scenario._create_firewall_group = mock.Mock()
        scenario._list_firewall_groups = mock.Mock()
        scenario.run(firewall_group_create_args=firewall_group_create_args)
        scenario._create_firewall_group.assert_called_once_with(
            **firewall_group_data)
        scenario._list_firewall_groups.assert_called_once_with()

    @ddt.data(
        {},
        {"firewall_group_create_args": {}},
        {"firewall_group_create_args": {"description": "fake-description"}},
    )
    @ddt.unpack
    def test_create_and_delete_firewall_groups(
            self, firewall_group_create_args=None):
        scenario = fwaas.CreateAndDeleteFirewallGroups()
        firewall_group_data = firewall_group_create_args or {}
        scenario._create_firewall_group = mock.Mock()
        scenario._delete_firewall_group = mock.Mock()
        scenario.run(firewall_group_create_args=firewall_group_create_args)
        scenario._create_firewall_group.assert_called_once_with(
            **firewall_group_data)
        scenario._delete_firewall_group.assert_called_once_with(
            scenario._create_firewall_group.return_value)

    @ddt.data(
        {},
        {"firewall_group_create_args": {}},
        {"firewall_group_create_args": {"description": "fake-description"}},
        {"firewall_group_update_args": {}},
        {"firewall_group_update_args": {"description": "fake-updated-descr"}},
    )
    @ddt.unpack
    def test_create_and_update_firewall_groups(
            self, firewall_group_create_args=None,
            firewall_group_update_args=None):
        scenario = fwaas.CreateAndUpdateFirewallGroups()
        firewall_group_data = firewall_group_create_args or {}
        firewall_group_update_data = firewall_group_update_args or {}
        scenario._create_firewall_group = mock.Mock()
        scenario._update_firewall_group = mock.Mock()
        scenario.run(firewall_group_create_args=firewall_group_create_args,
                     firewall_group_update_args=firewall_group_update_args)
        scenario._create_firewall_group.assert_called_once_with(
            **firewall_group_data)
        scenario._update_firewall_group.assert_called_once_with(
            scenario._create_firewall_group.return_value,
            **firewall_group_update_data)

    def test_associate_disassociate_firewall_group_router_ports(self):
        scenario = fwaas.AssociateDisassociateFirewallGroupRouterPorts()
        scenario.context = {
            "tenant": {
                "networks": [{"id": "network-id", "router_id": "router-id",
                              "router_port_id": "port-id"}]
            },
            "iteration": 1,
        }
        scenario._create_firewall_rule = mock.Mock(
            return_value={"firewall_rule": {"id": "rule-id"}})
        scenario._create_firewall_policy = mock.Mock(
            return_value={"firewall_policy": {"id": "policy-id"}})
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._create_firewall_group = mock.Mock(
            return_value={"firewall_group": {"id": "group-id", "ports": []}})
        scenario._associate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": ["port-id"]}})
        scenario._disassociate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": []}})

        scenario.run()

        scenario._create_firewall_rule.assert_called_once()
        self.assertEqual(2, scenario._create_firewall_policy.call_count)
        call_count = scenario._insert_firewall_rule_in_policy.call_count
        self.assertEqual(2, call_count)
        scenario._create_firewall_group.assert_called_once()
        scenario._associate_firewall_group_port.assert_called_once()
        scenario._disassociate_firewall_group_port.assert_called_once()

    def test_associate_disassociate_firewall_group_router_ports_network_sel(
            self):
        scenario = fwaas.AssociateDisassociateFirewallGroupRouterPorts()
        scenario.context = {
            "tenant": {
                "networks": [
                    {"id": "network-0", "router_id": "router-0",
                     "router_port_id": "port-0"},
                    {"id": "network-1", "router_id": "router-1",
                     "router_port_id": "port-1"},
                ]
            },
            "iteration": 3,
        }
        scenario._create_firewall_rule = mock.Mock(
            return_value={"firewall_rule": {"id": "rule-id"}})
        scenario._create_firewall_policy = mock.Mock(
            return_value={"firewall_policy": {"id": "policy-id"}})
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._create_firewall_group = mock.Mock(
            return_value={"firewall_group": {"id": "group-id", "ports": []}})
        scenario._associate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": ["port-id"]}})
        scenario._disassociate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": []}})

        scenario.run()

        scenario._associate_firewall_group_port.assert_called_once_with(
            scenario._create_firewall_group.return_value,
            {"port": {"id": "port-1"}})

    def test_associate_disassociate_firewall_group_router_ports_skips_finally_when_associate_fails(  # noqa: E501
            self):
        scenario = fwaas.AssociateDisassociateFirewallGroupRouterPorts()
        scenario.context = {
            "tenant": {
                "networks": [{"id": "network-id", "router_id": "router-id",
                              "router_port_id": "port-id"}]
            },
            "iteration": 1,
        }
        scenario._create_firewall_rule = mock.Mock(
            return_value={"firewall_rule": {"id": "rule-id"}})
        scenario._create_firewall_policy = mock.Mock(
            return_value={"firewall_policy": {"id": "policy-id"}})
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._create_firewall_group = mock.Mock(
            return_value={"firewall_group": {"id": "group-id", "ports": []}})
        scenario._associate_firewall_group_port = mock.Mock(
            side_effect=RuntimeError("associate failed"))
        scenario._disassociate_firewall_group_port = mock.Mock()

        self.assertRaises(RuntimeError, scenario.run)
        scenario._disassociate_firewall_group_port.assert_not_called()

    def test_associate_disassociate_firewall_group_router_ports_fails_on_disassociate(  # noqa: E501
            self):
        scenario = fwaas.AssociateDisassociateFirewallGroupRouterPorts()
        scenario.context = {
            "tenant": {
                "networks": [{"id": "network-id", "router_id": "router-id",
                              "router_port_id": "port-id"}]
            },
            "iteration": 1,
        }
        scenario._create_firewall_rule = mock.Mock(
            return_value={"firewall_rule": {"id": "rule-id"}})
        scenario._create_firewall_policy = mock.Mock(
            return_value={"firewall_policy": {"id": "policy-id"}})
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._create_firewall_group = mock.Mock(
            return_value={"firewall_group": {"id": "group-id", "ports": []}})
        scenario._associate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": ["port-id"]}})
        scenario._disassociate_firewall_group_port = mock.Mock(
            side_effect=RuntimeError("disassociate failed"))

        self.assertRaises(RuntimeError, scenario.run)
        scenario._disassociate_firewall_group_port.assert_called_once()

    def test_update_policy_on_active_firewall_group(self):
        scenario = fwaas.UpdatePolicyOnActiveFirewallGroup()
        scenario.context = {
            "tenant": {
                "networks": [{"id": "network-id", "router_id": "router-id",
                              "router_port_id": "port-id"}]
            },
            "iteration": 1,
        }
        scenario._create_firewall_rule = mock.Mock(
            return_value={"firewall_rule": {"id": "rule-id"}})
        scenario._create_firewall_policy = mock.Mock(
            return_value={"firewall_policy": {"id": "policy-id"}})
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._create_firewall_group = mock.Mock(
            return_value={"firewall_group": {"id": "group-id", "ports": []}})
        scenario._associate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": ["port-id"]}})
        scenario._update_firewall_group = mock.Mock()
        scenario._disassociate_firewall_group_port = mock.Mock()

        scenario.run()

        # 2 rules: initial + updated
        self.assertEqual(2, scenario._create_firewall_rule.call_count)
        # 3 policies: ingress, egress, updated
        self.assertEqual(3, scenario._create_firewall_policy.call_count)
        call_count = scenario._insert_firewall_rule_in_policy.call_count
        self.assertEqual(3, call_count)
        scenario._create_firewall_group.assert_called_once()
        scenario._associate_firewall_group_port.assert_called_once()
        scenario._update_firewall_group.assert_called_once()
        scenario._disassociate_firewall_group_port.assert_called_once()

    def test_update_policy_on_active_firewall_group_network_selection(self):
        scenario = fwaas.UpdatePolicyOnActiveFirewallGroup()
        scenario.context = {
            "tenant": {
                "networks": [
                    {"id": "network-0", "router_id": "router-0",
                     "router_port_id": "port-0"},
                    {"id": "network-1", "router_id": "router-1",
                     "router_port_id": "port-1"},
                ]
            },
            "iteration": 3,
        }
        scenario._create_firewall_rule = mock.Mock(
            return_value={"firewall_rule": {"id": "rule-id"}})
        scenario._create_firewall_policy = mock.Mock(
            return_value={"firewall_policy": {"id": "policy-id"}})
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._create_firewall_group = mock.Mock(
            return_value={"firewall_group": {"id": "group-id", "ports": []}})
        scenario._associate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": ["port-id"]}})
        scenario._update_firewall_group = mock.Mock()
        scenario._disassociate_firewall_group_port = mock.Mock()

        scenario.run()

        scenario._associate_firewall_group_port.assert_called_once_with(
            scenario._create_firewall_group.return_value,
            {"port": {"id": "port-1"}})

    def test_update_policy_on_active_firewall_group_disassociates_on_failure(
            self):
        scenario = fwaas.UpdatePolicyOnActiveFirewallGroup()
        scenario.context = {
            "tenant": {
                "networks": [{"id": "network-id", "router_id": "router-id",
                              "router_port_id": "port-id"}]
            },
            "iteration": 1,
        }
        scenario._create_firewall_rule = mock.Mock(
            return_value={"firewall_rule": {"id": "rule-id"}})
        scenario._create_firewall_policy = mock.Mock(
            return_value={"firewall_policy": {"id": "policy-id"}})
        scenario._insert_firewall_rule_in_policy = mock.Mock()
        scenario._create_firewall_group = mock.Mock(
            return_value={"firewall_group": {"id": "group-id", "ports": []}})
        scenario._associate_firewall_group_port = mock.Mock(
            return_value={"firewall_group": {
                "id": "group-id", "ports": ["port-id"]}})
        scenario._update_firewall_group = mock.Mock(
            side_effect=RuntimeError("update failed"))
        scenario._disassociate_firewall_group_port = mock.Mock()

        self.assertRaises(RuntimeError, scenario.run)
        scenario._disassociate_firewall_group_port.assert_called_once()

