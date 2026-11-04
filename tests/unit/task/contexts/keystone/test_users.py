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

import ddt

from rally import exceptions
from rally.task import context

from rally_openstack.common import consts
from rally_openstack.common import credential as oscredential
from rally_openstack.task.contexts.keystone import users
from tests.unit import test


CTX = "rally_openstack.task.contexts.keystone.users"


@ddt.ddt
class UserGeneratorValidationTestCase(test.TestCase):

    @ddt.data(
        ({"admin": {"username": "a"}, "users": []},
         {"tenants": 2}, True),
        ({"admin": None, "users": [{"username": "u"}]},
         {}, True),
        ({"admin": None, "users": [{"username": "u"}]},
         {"user_choice_method": "round_robin"}, True),
        ({"admin": None, "users": [{"username": "u"}]},
         {"tenants": 2}, False),
        ({"admin": None, "users": [{"username": "u"}]},
         {"users_per_tenant": 2, "user_choice_method": "random"}, False),
    )
    @ddt.unpack
    def test_validate_admin_for_new_users(self, platform_data, config, valid):
        platforms = {"openstack": platform_data}
        results = context.Context.validate(
            "users@openstack",
            {"platforms": platforms, "env": {"platforms": platforms}},
            None, config)

        messages = [r for r in results if "requires admin" in r]
        if valid:
            self.assertEqual([], messages)
        else:
            self.assertEqual(1, len(messages))


class UserGeneratorBaseTestCase(test.ScenarioTestCase):
    def setUp(self):
        super().setUp()
        self.osclients_patcher = mock.patch("%s.osclients" % CTX)
        self.osclients = self.osclients_patcher.start()
        self.addCleanup(self.osclients_patcher.stop)
        self.keystone = self.osclients.Clients.return_value.keystone
        self.keystone.get_session.return_value = (mock.Mock(), mock.Mock())

        self.deployment_uuid = "deployment_id"

        self.admin_cred = {
            "username": "root", "password": "qwerty",
            "project_name": "admin",
            "auth_url": "https://example.com",
            "project_domain_name": "foo",
            "user_domain_name": "bar"}

        self.platforms = {
            "openstack": {
                "admin": self.admin_cred,
                "users": []
            }
        }

        self.context.update({
            "config": {"users": {}},
            "env": {"platforms": self.platforms},
            "task": {"uuid": "task_id",
                     "deployment_uuid": self.deployment_uuid}
        })

    def test___init__for_new_users(self):
        self.context["config"]["users"] = {
            "tenants": 1, "users_per_tenant": 1,
            "resource_management_workers": 1}

        user_generator = users.UserGenerator(self.context)

        self.assertEqual([], user_generator.existing_users)
        self.assertEqual(self.admin_cred["project_domain_name"],
                         user_generator.config["project_domain"])
        self.assertEqual(self.admin_cred["user_domain_name"],
                         user_generator.config["user_domain"])

        # the case #2 - existing users are presented in deployment but
        #   the user forces to create new ones
        self.platforms["openstack"]["users"] = [mock.Mock()]

        user_generator = users.UserGenerator(self.context)

        self.assertEqual([], user_generator.existing_users)
        self.assertEqual(self.admin_cred["project_domain_name"],
                         user_generator.config["project_domain"])
        self.assertEqual(self.admin_cred["user_domain_name"],
                         user_generator.config["user_domain"])

    def test___init__for_existing_users(self):
        foo_user = mock.Mock()

        self.platforms["openstack"]["users"] = [foo_user]

        user_generator = users.UserGenerator(self.context)

        self.assertEqual([foo_user], user_generator.existing_users)
        self.assertEqual({"user_choice_method": "random"},
                         user_generator.config)

        # the case #2: the config with `user_choice_method` option
        self.context["config"]["users"] = {"user_choice_method": "foo"}

        user_generator = users.UserGenerator(self.context)

        self.assertEqual([foo_user], user_generator.existing_users)
        self.assertEqual({"user_choice_method": "foo"}, user_generator.config)

    def test_setup(self):
        user_generator = users.UserGenerator(self.context)
        user_generator.use_existing_users = mock.Mock()
        user_generator.create_users = mock.Mock()

        # no existing users -> new users should be created
        user_generator.existing_users = []

        user_generator.setup()

        user_generator.create_users.assert_called_once_with()
        self.assertFalse(user_generator.use_existing_users.called)

        user_generator.create_users.reset_mock()
        user_generator.use_existing_users.reset_mock()

        # existing_users is not empty -> existing users should be created
        user_generator.existing_users = [mock.Mock()]

        user_generator.setup()

        user_generator.use_existing_users.assert_called_once_with()
        self.assertFalse(user_generator.create_users.called)

    def test_cleanup(self):
        user_generator = users.UserGenerator(self.context)
        user_generator._remove_default_neutron_resources = mock.Mock()
        user_generator._delete_users = mock.Mock()
        user_generator._delete_projects = mock.Mock()

        # In case if existing users nothing should be done
        user_generator.existing_users = [mock.Mock]

        user_generator.cleanup()

        self.assertFalse(
            user_generator._remove_default_neutron_resources.called)
        self.assertFalse(user_generator._delete_users.called)
        self.assertFalse(user_generator._delete_projects.called)

        # In case when new users were created, the proper cleanup should be
        #   performed
        user_generator.existing_users = []

        user_generator.cleanup()

        remove_neutron = user_generator._remove_default_neutron_resources
        remove_neutron.assert_called_once_with()
        user_generator._delete_users.assert_called_once_with()
        user_generator._delete_projects.assert_called_once_with()


@ddt.ddt
class UserGeneratorForExistingUsersTestCase(test.ScenarioTestCase):
    def setUp(self):
        super().setUp()
        self.osclients_patcher = mock.patch("%s.osclients" % CTX)
        self.osclients = self.osclients_patcher.start()
        self.addCleanup(self.osclients_patcher.stop)

        self.deployment_uuid = "deployment_id"

        self.platforms = {
            "openstack": {
                "admin": {"username": "root",
                          "password": "qwerty",
                          "project_name": "admin",
                          "auth_url": "https://example.com"},
                "users": []
            }
        }
        self.context.update({
            "config": {"users": {}},
            "users": [],
            "env": {"platforms": self.platforms},
            "task": {"uuid": "task_id",
                     "deployment_uuid": self.deployment_uuid}
        })

    @mock.patch("%s.credential.OpenStackCredential" % CTX)
    @mock.patch("%s.osclients.Clients" % CTX)
    def test_use_existing_users(self, mock_clients,
                                mock_open_stack_credential):
        user1 = {"tenant_name": "proj", "username": "usr",
                 "password": "pswd", "auth_url": "https://example.com"}
        user2 = {"tenant_name": "proj", "username": "usr",
                 "password": "pswd", "auth_url": "https://example.com"}
        user3 = {"tenant_name": "proj", "username": "usr",
                 "password": "pswd", "auth_url": "https://example.com"}

        user_list = [user1, user2, user3]

        class AuthRef:
            USER_ID_COUNT = 0
            PROJECT_ID_COUNT = 0

            @property
            def user_id(self):
                self.USER_ID_COUNT += 1
                return "u%s" % self.USER_ID_COUNT

            @property
            def project_id(self):
                self.PROJECT_ID_COUNT += 1
                return "p%s" % (self.PROJECT_ID_COUNT % 2)

        auth_ref = AuthRef()

        mock_clients.return_value.keystone.auth_ref = auth_ref
        mock_clients.return_value.keystone.get_session.return_value = (
            mock.Mock(), mock.Mock())

        self.platforms["openstack"]["users"] = user_list

        user_generator = users.UserGenerator(self.context)
        user_generator.setup()

        self.assertIn("users", self.context)
        self.assertIn("tenants", self.context)
        self.assertIn("user_choice_method", self.context)
        self.assertEqual("random", self.context["user_choice_method"])

        creds = mock_open_stack_credential.return_value
        u1 = {"id": "u1", "credential": creds, "tenant_id": "p1"}
        u2 = {"id": "u2", "credential": creds, "tenant_id": "p0"}
        u3 = {"id": "u3", "credential": creds, "tenant_id": "p1"}
        self.assertEqual([u1, u2, u3], self.context["users"])
        self.assertEqual(
            {"p0": {"id": "p0", "name": creds.project_name, "users": [u2]},
             "p1": {"id": "p1", "name": creds.project_name,
                    "users": [u1, u3]}},
            self.context["tenants"])

    @ddt.data(
        {"user_id": None, "project_id": "p1"},
        {"user_id": "u1", "project_id": None},
    )
    @ddt.unpack
    @mock.patch(f"{CTX}.credential.OpenStackCredential")
    @mock.patch(f"{CTX}.osclients.Clients")
    def test_use_existing_users_not_scoped(
        self, mock_clients, mock_open_stack_credential, user_id, project_id
    ):
        auth_ref = mock_clients.return_value.keystone.auth_ref
        auth_ref.user_id = user_id
        auth_ref.project_id = project_id
        self.platforms["openstack"]["users"] = [
            {"username": "usr", "password": "pswd",
             "auth_url": "https://example.com"}
        ]

        user_generator = users.UserGenerator(self.context)
        self.assertRaises(exceptions.ContextSetupFailure,
                          user_generator.use_existing_users)
        self.assertEqual([], self.context["users"])


class UserGeneratorForNewUsersTestCase(test.ScenarioTestCase):

    tenants_num = 1
    users_per_tenant = 5
    users_num = tenants_num * users_per_tenant
    threads = 10

    def setUp(self):
        super().setUp()
        self.osclients_patcher = mock.patch("%s.osclients" % CTX)
        self.osclients = self.osclients_patcher.start()
        self.addCleanup(self.osclients_patcher.stop)
        self.keystone = self.osclients.Clients.return_value.keystone
        ks_plugin = mock.Mock()
        ks_plugin.get_auth_state.return_value = None
        self.keystone.get_session.return_value = (mock.Mock(), ks_plugin)

        # Force the case of creating new users
        self.platforms = {
            "openstack": {
                "admin": {"username": "root",
                          "password": "qwerty",
                          "project_name": "admin",
                          "auth_url": "https://example.com"},
                "users": []
            }
        }

        self.context.update({
            "config": {
                "users": {
                    "tenants": self.tenants_num,
                    "users_per_tenant": self.users_per_tenant,
                    "resource_management_workers": self.threads,
                }
            },
            "env": {"platforms": self.platforms},
            "users": [],
            "task": {"uuid": "task_id", "deployment_uuid": "dep_uuid"}
        })

    def _mock_neutron_client(self, extensions=(), services=None):
        self.context.update(tenants={"tenant-1": {}, "tenant-2": {}})
        clients = self.osclients.Clients.return_value
        clients.services.return_value = (
            {"network": "neutron"} if services is None else services)
        clients.neutron.supports_extension.side_effect = (
            lambda alias: alias in extensions)
        return clients.neutron

    def test__remove_default_neutron_resources_security_groups(self):
        neutron = self._mock_neutron_client(extensions=["security-group"])
        neutron.list_security_groups.return_value = [
            mock.Mock(id="id-1", project_id="tenant-1"),
            mock.Mock(id="id-2", project_id="tenant-2"),
            mock.Mock(id="id-3", project_id="tenant-3"),
        ]

        users.UserGenerator(self.context)._remove_default_neutron_resources()

        neutron.list_security_groups.assert_called_once_with(name="default")
        self.assertEqual(
            [mock.call("id-1"), mock.call("id-2")],
            neutron.delete_security_group.call_args_list)
        self.assertFalse(neutron.list_firewall_groups.called)

    def test__remove_default_neutron_resources_no_extensions(self):
        neutron = self._mock_neutron_client()

        users.UserGenerator(self.context)._remove_default_neutron_resources()

        self.assertFalse(neutron.list_security_groups.called)
        self.assertFalse(neutron.list_firewall_groups.called)

    def test__remove_default_neutron_resources_no_neutron(self):
        neutron = self._mock_neutron_client(services={})

        users.UserGenerator(self.context)._remove_default_neutron_resources()

        self.assertFalse(neutron.supports_extension.called)

    def test__remove_default_neutron_resources_firewall_groups(self):
        neutron = self._mock_neutron_client(extensions=["fwaas_v2"])
        neutron.list_firewall_groups.return_value = [
            mock.Mock(id="fwg-1", project_id="tenant-1", ports=["port-1"],
                      ingress_firewall_policy_id="in-1",
                      egress_firewall_policy_id="eg-1"),
            mock.Mock(id="fwg-2", project_id="tenant-2", ports=[],
                      ingress_firewall_policy_id="in-2",
                      egress_firewall_policy_id=None),
            mock.Mock(id="fwg-3", project_id="tenant-3", ports=[],
                      ingress_firewall_policy_id="in-3",
                      egress_firewall_policy_id="eg-3"),
        ]
        policies = {
            "in-1": mock.Mock(firewall_rules=["r-1", "r-2"]),
            "eg-1": mock.Mock(firewall_rules=["r-3"]),
            "in-2": mock.Mock(firewall_rules=["r-4"]),
        }
        neutron.get_firewall_policy.side_effect = policies.__getitem__

        users.UserGenerator(self.context)._remove_default_neutron_resources()

        self.assertFalse(neutron.list_security_groups.called)
        neutron.list_firewall_groups.assert_called_once_with(name="default")
        neutron.disassociate_firewall_group_ports.assert_called_once_with(
            "fwg-1")
        self.assertEqual(
            [mock.call("fwg-1"), mock.call("fwg-2")],
            neutron.delete_firewall_group.call_args_list)
        self.assertEqual(
            [mock.call("r-1"), mock.call("r-2"), mock.call("r-3"),
             mock.call("r-4")],
            neutron.delete_firewall_rule.call_args_list)

    def test__create_tenants(self):
        self.context["config"]["users"]["tenants"] = 1
        user_generator = users.UserGenerator(self.context)
        tenants = user_generator._create_projects(1)
        self.assertEqual(1, len(tenants))
        _id, tenant = tenants.popitem()
        self.assertIn("name", tenant)

    def test__create_users(self):
        self.context["config"]["users"]["users_per_tenant"] = 2
        user_generator = users.UserGenerator(self.context)
        user_generator.context["tenants"] = {"t1": {"id": "t1", "name": "t1"},
                                             "t2": {"id": "t2", "name": "t2"}}
        users_ = user_generator._create_users(4)
        self.assertEqual(4, len(users_))
        for user in users_:
            self.assertIn("id", user)
            self.assertIn("credential", user)

    def test__create_users_user_password(self):
        self.context["config"]["users"]["users_per_tenant"] = 2
        self.context["config"]["users"]["user_password"] = "TrustMe"
        user_generator = users.UserGenerator(self.context)
        user_generator.context["tenants"] = {"t1": {"id": "t1", "name": "t1"},
                                             "t2": {"id": "t2", "name": "t2"}}
        users_ = user_generator._create_users(4)
        self.assertEqual(4, len(users_))
        for user in users_:
            self.assertIn("id", user)
            self.assertIn("credential", user)
            self.assertEqual("TrustMe", user["credential"]["password"])

    def test__delete_tenants(self):
        user_generator = users.UserGenerator(self.context)
        user_generator.context["tenants"] = {"t1": {"id": "t1", "name": "t1"},
                                             "t2": {"id": "t2", "name": "t2"}}
        user_generator._delete_projects()
        self.assertEqual(0, len(user_generator.context["tenants"]))

    def test__delete_tenants_failure(self):
        self.keystone.delete_project.side_effect = Exception()
        user_generator = users.UserGenerator(self.context)
        user_generator.context["tenants"] = {"t1": {"id": "t1", "name": "t1"},
                                             "t2": {"id": "t2", "name": "t2"}}
        user_generator._delete_projects()
        self.assertEqual(0, len(user_generator.context["tenants"]))

    def test__delete_users(self):
        user_generator = users.UserGenerator(self.context)
        user1 = mock.MagicMock()
        user2 = mock.MagicMock()
        user_generator.context["users"] = [user1, user2]
        user_generator._delete_users()
        self.assertEqual(0, len(user_generator.context["users"]))

    def test__delete_users_failure(self):
        self.keystone.delete_user.side_effect = Exception()
        user_generator = users.UserGenerator(self.context)
        user1 = mock.MagicMock()
        user2 = mock.MagicMock()
        user_generator.context["users"] = [user1, user2]
        user_generator._delete_users()
        self.assertEqual(0, len(user_generator.context["users"]))

    def test_setup_and_cleanup(self):
        with users.UserGenerator(self.context) as ctx:

            ctx.setup()

            self.assertEqual(self.users_num,
                             len(ctx.context["users"]))
            self.assertEqual(self.tenants_num,
                             len(ctx.context["tenants"]))

            self.assertEqual("random", ctx.context["user_choice_method"])

        # Cleanup (called by content manager)
        self.assertEqual(0, len(ctx.context["users"]))
        self.assertEqual(0, len(ctx.context["tenants"]))

    @mock.patch("rally.common.broker.LOG.warning")
    def test_setup_and_cleanup_with_error_during_create_user(
            self, mock_log_warning):
        self.keystone.create_user.side_effect = Exception()
        with users.UserGenerator(self.context) as ctx:
            self.assertRaises(exceptions.ContextSetupFailure, ctx.setup)
            mock_log_warning.assert_called_with(
                "Failed to consume a task from the queue: ")

        # Ensure that tenants get deleted anyway
        self.assertEqual(0, len(ctx.context["tenants"]))

    def test_users_and_tenants_in_context(self):
        credential = oscredential.OpenStackCredential(
            "foo_url", "foo", "foo_pass", "foo_project",
            https_insecure=True,
            https_cacert="cacert")
        tmp_context = dict(self.context)
        tmp_context["config"]["users"] = {"tenants": 1,
                                          "users_per_tenant": 2,
                                          "resource_management_workers": 1}
        tmp_context["env"]["platforms"]["openstack"]["admin"] = (
            credential.to_dict())

        credential_dict = credential.to_dict()
        user_list = [mock.MagicMock(id="id_%d" % i)
                     for i in range(self.users_num)]
        self.keystone.create_user.side_effect = user_list

        with users.UserGenerator(tmp_context) as ctx:
            ctx.generate_random_name = mock.Mock()
            ctx.setup()

            create_tenant_calls = []
            for i, t in enumerate(ctx.context["tenants"]):
                create_tenant_calls.append(
                    mock.call(ctx.generate_random_name.return_value,
                              ctx.config["project_domain"]))

            for user in ctx.context["users"]:
                self.assertEqual({"id", "credential", "tenant_id"},
                                 set(user.keys()))

                user_credential_dict = user["credential"].to_dict()

                excluded_keys = ["auth_url", "username", "password",
                                 "project_name", "region_name",
                                 "project_domain_name",
                                 "user_domain_name", "permission"]
                for key in (set(credential_dict.keys()) - set(excluded_keys)):
                    self.assertEqual(credential_dict[key],
                                     user_credential_dict[key],
                                     "The key '%s' differs." % key)

            tenants_ids = []
            for t in ctx.context["tenants"].keys():
                tenants_ids.append(t)

            for (user, tenant_id, orig_user) in zip(ctx.context["users"],
                                                    tenants_ids, user_list):
                self.assertEqual(orig_user.id, user["id"])
                self.assertEqual(tenant_id, user["tenant_id"])

    def test_users_contains_correct_endpoint_type(self):
        credential = oscredential.OpenStackCredential(
            "foo_url", "foo", "foo_pass", "foo_project",
            endpoint_type=consts.EndpointType.INTERNAL)
        config = {
            "config": {
                "users": {
                    "tenants": 1,
                    "users_per_tenant": 2,
                    "resource_management_workers": 1
                }
            },
            "env": {"platforms": {"openstack": {"admin": credential.to_dict(),
                                                "users": []}}},
            "task": {"uuid": "task_id", "deployment_uuid": "deployment_id"}
        }

        user_generator = users.UserGenerator(config)
        users_ = user_generator._create_users(2)

        for user in users_:
            self.assertEqual("internal", user["credential"].endpoint_type)

    def test_users_contains_default_endpoint_type(self):
        credential = oscredential.OpenStackCredential(
            "foo_url", "foo", "foo_pass", "foo_project")
        config = {
            "config": {
                "users": {
                    "tenants": 1,
                    "users_per_tenant": 2,
                    "resource_management_workers": 1
                }
            },
            "env": {"platforms": {"openstack": {"admin": credential.to_dict(),
                                                "users": []}}},
            "task": {"uuid": "task_id", "deployment_uuid": "deployment_id"}
        }

        user_generator = users.UserGenerator(config)
        users_ = user_generator._create_users(2)

        for user in users_:
            self.assertEqual("public", user["credential"].endpoint_type)
