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

from unittest import mock

from rally import exceptions

from rally_openstack.task.contexts.keystone import roles
from tests.unit import test


CTX = "rally_openstack.task.contexts.keystone.roles"


class RoleGeneratorTestCase(test.TestCase):

    def _mock_keystone(self, mock_osclients, user_roles=None):
        """Set up the mock keystone client with two roles (r1, r2).

        ``list_roles()`` returns both role definitions (optionally filtered by
        name); ``list_role_assignments()`` returns ``user_roles`` (empty by
        default, so setup queues add_role).
        """
        role1 = mock.Mock(id="r1")
        role1.name = "test_role1"
        role2 = mock.Mock(id="r2")
        role2.name = "test_role2"

        def list_roles(name=None, domain_name=None):
            roles = [role1, role2]
            if name is not None:
                roles = [r for r in roles if r.name == name]
            return roles

        keystone = mock_osclients.Clients.return_value.keystone
        keystone.list_roles.side_effect = list_roles
        keystone.list_role_assignments.return_value = user_roles or []
        return keystone

    @property
    def context(self):
        return {
            "config": {
                "roles": [
                    "test_role1",
                    "test_role2"
                ]
            },
            "admin": {"credential": mock.MagicMock()},
            "task": mock.MagicMock()
        }

    @mock.patch("%s.osclients" % CTX)
    def test_add_role(self, mock_osclients):
        keystone = self._mock_keystone(mock_osclients)

        ctx = roles.RoleGenerator(self.context)
        ctx.context["users"] = [{"id": "u1", "tenant_id": "t1"},
                                {"id": "u2", "tenant_id": "t2"}]
        ctx.credential = mock.MagicMock()
        ctx.setup()

        expected = {"r1": "test_role1", "r2": "test_role2"}
        self.assertEqual(expected, ctx.context["roles"])
        keystone.add_role.assert_has_calls([
            mock.call(role_id="r1", user_id="u1", project_id="t1"),
            mock.call(role_id="r1", user_id="u2", project_id="t2"),
            mock.call(role_id="r2", user_id="u1", project_id="t1"),
            mock.call(role_id="r2", user_id="u2", project_id="t2"),
        ], any_order=True)

    @mock.patch("%s.osclients" % CTX)
    def test_add_role_which_does_not_exist(self, mock_osclients):
        self._mock_keystone(mock_osclients)

        ctx = roles.RoleGenerator(self.context)
        ctx.context["users"] = [{"id": "u1", "tenant_id": "t1"},
                                {"id": "u2", "tenant_id": "t2"}]
        ctx.config = ["unknown_role"]
        ctx.credential = mock.MagicMock()
        ex = self.assertRaises(exceptions.NotFoundException,
                               ctx._find_role, "unknown_role")

        expected = ("The resource can not be found: There is no role "
                    "with name `unknown_role`")
        self.assertEqual(expected, str(ex))

    @mock.patch("%s.osclients" % CTX)
    def test_remove_role(self, mock_osclients):
        keystone = self._mock_keystone(mock_osclients)

        ctx = roles.RoleGenerator(self.context)
        ctx.context["roles"] = {"r1": "test_role1",
                                "r2": "test_role2"}
        ctx.context["users"] = [{"id": "u1", "tenant_id": "t1",
                                 "assigned_roles": ["r1", "r2"]},
                                {"id": "u2", "tenant_id": "t2",
                                 "assigned_roles": ["r1", "r2"]}]
        ctx.credential = mock.MagicMock()
        ctx.cleanup()
        calls = [
            mock.call(role_id="r1", user_id="u1", project_id="t1"),
            mock.call(role_id="r1", user_id="u2", project_id="t2"),
            mock.call(role_id="r2", user_id="u1", project_id="t1"),
            mock.call(role_id="r2", user_id="u2", project_id="t2"),
        ]
        keystone.revoke_role.assert_has_calls(calls, any_order=True)

    @mock.patch("%s.osclients" % CTX)
    def test_setup_and_cleanup(self, mock_osclients):
        keystone = self._mock_keystone(mock_osclients)

        def list_role_assignments(user_id, project_id=None, domain_name=None):
            if user_id == "u3":
                return [mock.Mock(id="r1"), mock.Mock(id="r2")]
            return []
        keystone.list_role_assignments.side_effect = list_role_assignments

        with roles.RoleGenerator(self.context) as ctx:
            ctx.context["users"] = [{"id": "u1", "tenant_id": "t1"},
                                    {"id": "u2", "tenant_id": "t2"},
                                    {"id": "u3", "tenant_id": "t3"}]

            ctx.setup()
            ctx.credential = mock.MagicMock()
            calls = [
                mock.call(role_id="r1", user_id="u1", project_id="t1"),
                mock.call(role_id="r1", user_id="u2", project_id="t2"),
                mock.call(role_id="r2", user_id="u1", project_id="t1"),
                mock.call(role_id="r2", user_id="u2", project_id="t2"),
            ]
            keystone.add_role.assert_has_calls(calls, any_order=True)
            self.assertEqual(4, keystone.add_role.call_count)
            self.assertEqual(0, keystone.revoke_role.call_count)
            self.assertEqual(2, len(ctx.context["roles"]))

        # Cleanup (called by context manager)
        self.assertEqual(4, keystone.add_role.call_count)
        self.assertEqual(4, keystone.revoke_role.call_count)
        calls = [
            mock.call(role_id="r1", user_id="u1", project_id="t1"),
            mock.call(role_id="r1", user_id="u2", project_id="t2"),
            mock.call(role_id="r2", user_id="u1", project_id="t1"),
            mock.call(role_id="r2", user_id="u2", project_id="t2"),
        ]
        keystone.revoke_role.assert_has_calls(calls, any_order=True)
