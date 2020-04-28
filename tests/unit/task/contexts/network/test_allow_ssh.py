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

import copy
from unittest import mock

from rally_openstack.task.contexts.network import allow_ssh
from tests.unit import test


CTX = "rally_openstack.task.contexts.network.allow_ssh"


class AllowSSHContextTestCase(test.TestCase):

    def setUp(self):
        super(AllowSSHContextTestCase, self).setUp()
        self.users_count = 3

        self.ctx = test.get_test_context()
        self.ctx.update(
            users=[
                {
                    "tenant_id": f"uuid{i // 3}",
                    "credential": mock.MagicMock()
                }
                for i in range(1, self.users_count + 1)
            ],
            admin={
                "tenant_id": "uuid2",
                "credential": mock.MagicMock()},
            tenants={
                "uuid1": {"id": "uuid1", "name": "uuid1"},
                "uuid2": {"id": "uuid2", "name": "uuid1"}
            }
        )

    def test_setup(self):
        for i, user in enumerate(self.ctx["users"]):
            clients = user["credential"].clients.return_value
            nc = clients.neutron.return_value
            nc.list_extensions.return_value = {
                "extensions": [{"alias": "security-group"}]
            }
            nc.create_security_group.return_value = {
                "security_group": {
                    "name": "xxx",
                    "id": f"security-group-{i}",
                    "security_group_rules": []
                }
            }

        allow_ssh.AllowSSH(self.ctx).setup()

        # admin user should not be used
        self.assertFalse(self.ctx["admin"]["credential"].clients.called)

        processed_tenants = {}
        for i, user in enumerate(self.ctx["users"]):
            clients = user["credential"].clients.return_value
            nc = clients.neutron.return_value
            if i == 0:
                nc.list_extensions.assert_called_once_with()
            else:
                self.assertFalse(nc.list_extensions.called)

            if user["tenant_id"] in processed_tenants:
                self.assertFalse(nc.create_security_group.called)
                self.assertFalse(nc.create_security_group_rule.called)
            else:
                nc.create_security_group.assert_called_once_with({
                    "security_group": {
                        "name": mock.ANY,
                        "description": mock.ANY
                    }
                })
                secgroup = nc.create_security_group.return_value
                secgroup = secgroup["security_group"]

                rules = copy.deepcopy(allow_ssh._RULES_TO_ADD)
                for rule in rules:
                    rule["security_group_id"] = secgroup["id"]
                self.assertEqual(
                    [mock.call({"security_group_rule": rule})
                     for rule in rules],
                    nc.create_security_group_rule.call_args_list
                )

                processed_tenants[user["tenant_id"]] = secgroup

            self.assertEqual(processed_tenants[user["tenant_id"]]["id"],
                             user["secgroup"]["id"])

    def test_setup_no_security_group_extension(self):
        clients = self.ctx["users"][0]["credential"].clients.return_value
        nc = clients.neutron.return_value
        nc.list_extensions.return_value = {"extensions": []}

        allow_ssh.AllowSSH(self.ctx).setup()

        # admin user should not be used
        self.assertFalse(self.ctx["admin"]["credential"].clients.called)

        nc.list_extensions.assert_called_once_with()
        for i, user in enumerate(self.ctx["users"]):
            if i == 0:
                continue
            self.assertFalse(user["credential"].clients.called)
