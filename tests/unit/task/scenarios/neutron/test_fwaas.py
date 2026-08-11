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
