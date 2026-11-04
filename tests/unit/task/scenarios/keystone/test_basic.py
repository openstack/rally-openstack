# Copyright 2013: Mirantis Inc.
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

from rally_openstack.task.scenarios.keystone import basic
from tests.unit import test


@ddt.ddt
class KeystoneBasicTestCase(test.ScenarioTestCase):

    def get_test_context(self):
        context = super().get_test_context()
        context.update({
            "admin": {
                "id": "fake_user_id",
                "credential": mock.MagicMock()
            },
            "user": {
                "id": "fake_user_id",
                "credential": mock.MagicMock()
            },
            "tenant": {"id": "fake_tenant_id",
                       "name": "fake_tenant_name"}
        })
        return context

    def setUp(self):
        super().setUp()
        # KeystoneBasic reads ``self._admin_clients.keystone`` /
        # ``self._clients.keystone`` (the ported identity client). Both share
        # the same PropertyMock, so admin and user keystone resolve to one
        # mock.
        patch = mock.patch(
            "rally_openstack.common.osclients.Clients.keystone",
            new_callable=mock.PropertyMock, create=True)
        self.addCleanup(patch.stop)
        self.mock_keystone = patch.start().return_value

    def test_create_user(self):
        scenario = basic.CreateUser(self.context)

        scenario.run(password="tttt", project_id="id")
        self.mock_keystone.create_user.assert_called_once_with(
            password="tttt", project_id="id", domain="Default", enabled=True)

    def test_create_delete_user(self):
        identity_service = self.mock_keystone
        fake_user = identity_service.create_user.return_value

        scenario = basic.CreateDeleteUser(self.context)

        scenario.run(domain="dom", enabled=False)

        identity_service.create_user.assert_called_once_with(
            password=None, project_id=None, domain="dom", enabled=False)
        identity_service.delete_user.assert_called_once_with(fake_user.id)

    def test_create_user_set_enabled_and_delete(self):
        identity_service = self.mock_keystone

        scenario = basic.CreateUserSetEnabledAndDelete(self.context)

        fake_user = identity_service.create_user.return_value
        scenario.run(enabled=True, password="pswd")

        identity_service.create_user.assert_called_once_with(
            password="pswd", project_id=None, domain="Default", enabled=True)
        identity_service.update_user.assert_called_once_with(
            fake_user.id, enabled=False)
        identity_service.delete_user.assert_called_once_with(fake_user.id)

    def test_user_authenticate_and_validate_token(self):
        identity_service = self.mock_keystone
        scenario = basic.AuthenticateUserAndValidateToken(self.context)

        fake_token = identity_service.fetch_token.return_value

        scenario.run()

        identity_service.fetch_token.assert_called_once_with()
        identity_service.validate_token.assert_called_once_with(fake_token)

    @ddt.data(basic.CreateProject, basic.CreateTenant)
    def test_create_project(self, scenario_cls):
        scenario = scenario_cls(self.context)

        scenario.run(domain="dom")

        self.mock_keystone.create_project.assert_called_once_with(
            domain="dom")

    @ddt.data((basic.CreateProjectWithUsers, "users_per_project"),
              (basic.CreateTenantWithUsers, "users_per_tenant"))
    @ddt.unpack
    def test_create_project_with_users(self, scenario_cls, users_arg):
        identity_service = self.mock_keystone
        fake_project = identity_service.create_project.return_value
        fake_user = identity_service.create_user.return_value
        fake_role = identity_service.find_role.return_value

        scenario = scenario_cls(self.context)

        scenario.run(**{users_arg: 1}, domain="dom")

        identity_service.create_project.assert_called_once_with(domain="dom")
        identity_service.find_role.assert_called_once_with("member")
        identity_service.create_user.assert_called_once_with(
            project_id=fake_project.id, domain="dom")
        identity_service.add_role.assert_called_once_with(
            role_id=fake_role.id, user_id=fake_user.id,
            project_id=fake_project.id)

    def test_create_project_with_users_without_member_role(self):
        identity_service = self.mock_keystone
        identity_service.find_role.return_value = None

        basic.CreateProjectWithUsers(self.context).run(users_per_project=2)

        self.assertEqual(2, identity_service.create_user.call_count)
        self.assertFalse(identity_service.add_role.called)

    def test_create_and_list_users(self):
        scenario = basic.CreateAndListUsers(self.context)

        passwd = "tttt"
        project_id = "id"

        scenario.run(password=passwd, project_id=project_id)
        self.mock_keystone.create_user.assert_called_once_with(
            password=passwd, project_id=project_id, domain="Default",
            enabled=True)
        self.mock_keystone.list_users.assert_called_once_with()

    @ddt.data(basic.CreateAndListProjects, basic.CreateAndListTenants)
    def test_create_and_list_projects(self, scenario_cls):
        identity_service = self.mock_keystone
        scenario = scenario_cls(self.context)
        scenario.run(domain="dom")
        identity_service.create_project.assert_called_once_with(domain="dom")
        identity_service.list_projects.assert_called_once_with()

    def test_assign_and_remove_user_role(self):
        fake_tenant = self.context["tenant"]["id"]
        fake_user = self.context["user"]["id"]
        fake_role = mock.MagicMock()

        self.mock_keystone.create_role.return_value = fake_role

        scenario = basic.AddAndRemoveUserRole(self.context)
        scenario.run()

        self.mock_keystone.create_role.assert_called_once_with()
        self.mock_keystone.add_role.assert_called_once_with(
            role_id=fake_role.id, user_id=fake_user, project_id=fake_tenant)

        self.mock_keystone.revoke_role.assert_called_once_with(
            fake_role.id, user_id=fake_user, project_id=fake_tenant)

    def test_create_and_delete_role(self):
        fake_role = mock.MagicMock()
        self.mock_keystone.create_role.return_value = fake_role

        scenario = basic.CreateAndDeleteRole(self.context)
        scenario.run()

        self.mock_keystone.create_role.assert_called_once_with()
        self.mock_keystone.delete_role.assert_called_once_with(
            fake_role.id)

    def test_create_and_get_role(self):
        fake_role = mock.MagicMock()
        self.mock_keystone.create_role.return_value = fake_role

        scenario = basic.CreateAndGetRole(self.context)
        scenario.run()

        self.mock_keystone.create_role.assert_called_once_with(domain=None)
        self.mock_keystone.get_role.assert_called_once_with(
            fake_role.id)

    def test_create_and_list_user_roles(self):
        scenario = basic.CreateAddAndListUserRoles(self.context)
        fake_tenant = self.context["tenant"]["id"]
        fake_user = self.context["user"]["id"]
        fake_role = mock.MagicMock()
        self.mock_keystone.create_role.return_value = fake_role

        scenario.run()

        self.mock_keystone.create_role.assert_called_once_with()
        self.mock_keystone.add_role.assert_called_once_with(
            user_id=fake_user, role_id=fake_role.id, project_id=fake_tenant)
        self.mock_keystone.list_role_assignments.assert_called_once_with(
            fake_user, project_id=fake_tenant)

    @ddt.data(
        ({}, None, {"name": None, "domain": None}),
        ({"domain": "dom"}, "dom", {"name": None, "domain": "dom"}),
        ({"domain": "dom", "create_role_kwargs": {"domain": "c_dom"},
          "list_role_kwargs": {"name": "role1"}},
         "c_dom", {"name": "role1", "domain": "dom"}),
    )
    @ddt.unpack
    def test_create_and_list_roles(self, args, create_domain, list_args):
        scenario = basic.CreateAddListRoles(self.context)
        self.mock_keystone.create_role = mock.Mock(return_value="role1")
        self.mock_keystone.list_roles = mock.Mock(
            return_value=("role1", "role2"))

        scenario.run(**args)

        self.mock_keystone.create_role.assert_called_once_with(
            domain=create_domain)
        self.mock_keystone.list_roles.assert_called_once_with(**list_args)

        self.mock_keystone.create_role.return_value = None
        self.assertRaises(exceptions.RallyAssertionError, scenario.run, **args)

        self.mock_keystone.create_role.return_value = "role3"
        self.assertRaises(exceptions.RallyAssertionError, scenario.run, **args)

    @ddt.data(None, "keystone", "fooservice")
    def test_get_entities(self, service_name):
        identity_service = self.mock_keystone

        fake_project = identity_service.create_project.return_value
        fake_user = identity_service.create_user.return_value
        fake_role = identity_service.create_role.return_value
        fake_service = identity_service.create_service.return_value

        scenario = basic.GetEntities(self.context)

        scenario.run(service_name)

        identity_service.create_project.assert_called_once_with()
        identity_service.create_user.assert_called_once_with(
            project_id=fake_project.id)
        identity_service.create_role.assert_called_once_with()

        identity_service.get_project.assert_called_once_with(fake_project.id)
        identity_service.get_user.assert_called_once_with(fake_user.id)
        identity_service.get_role.assert_called_once_with(fake_role.id)

        if service_name is None:
            identity_service.create_service.assert_called_once_with()
            self.assertFalse(identity_service.list_services.called)
            identity_service.get_service.assert_called_once_with(
                fake_service.id)
        else:
            identity_service.list_services.assert_called_once_with(
                name=service_name)
            self.assertFalse(identity_service.create_service.called)
            identity_service.get_service.assert_called_once_with(
                identity_service.list_services.return_value[0].id)

    def test_create_and_delete_service(self):
        identity_service = self.mock_keystone
        scenario = basic.CreateAndDeleteService(self.context)

        service_type = "test_service_type"
        description = "test_description"
        fake_service = identity_service.create_service.return_value

        scenario.run(service_type=service_type, description=description)

        identity_service.create_service.assert_called_once_with(
            service_type=service_type, description=description)
        identity_service.delete_service.assert_called_once_with(
            fake_service.id)

    @ddt.data(basic.CreateUpdateAndDeleteProject,
              basic.CreateUpdateAndDeleteTenant)
    def test_create_update_and_delete_project(self, scenario_cls):
        identity_service = self.mock_keystone

        scenario = scenario_cls(self.context)
        scenario.generate_random_name = mock.MagicMock()
        fake_project = identity_service.create_project.return_value

        scenario.run(domain="dom")

        identity_service.create_project.assert_called_once_with(domain="dom")
        identity_service.update_project.assert_called_once_with(
            fake_project.id,
            description=scenario.generate_random_name.return_value,
            name=scenario.generate_random_name.return_value)
        identity_service.delete_project.assert_called_once_with(
            fake_project.id)

    def test_create_user_update_password(self):
        identity_service = self.mock_keystone

        scenario = basic.CreateUserUpdatePassword(self.context)

        fake_password = "pswd"
        fake_user = identity_service.create_user.return_value
        scenario.generate_random_name = mock.MagicMock(
            return_value=fake_password)

        scenario.run()

        scenario.generate_random_name.assert_called_once_with()
        identity_service.create_user.assert_called_once_with()
        identity_service.update_user.assert_called_once_with(
            fake_user.id, password=fake_password)

    def test_create_and_update_user(self):
        identity_service = self.mock_keystone

        scenario = basic.CreateAndUpdateUser(self.context)
        fake_user = identity_service.create_user.return_value

        create_args = {"password": "pswd"}
        update_args = {"email": "e@mail", "enabled": False}
        identity_service.get_user.return_value.email = "e@mail"
        identity_service.get_user.return_value.is_enabled = False

        scenario.run(create_user_kwargs=create_args,
                     update_user_kwargs=update_args)

        identity_service.create_user.assert_called_once_with(**create_args)
        identity_service.update_user.assert_called_once_with(
            fake_user.id, **update_args)
        identity_service.get_user.assert_called_once_with(fake_user.id)

    def test_create_and_update_user_without_kwargs(self):
        identity_service = self.mock_keystone
        fake_user = identity_service.create_user.return_value

        basic.CreateAndUpdateUser(self.context).run()

        identity_service.create_user.assert_called_once_with()
        identity_service.update_user.assert_called_once_with(fake_user.id)

    def test_create_and_list_services(self):
        identity_service = self.mock_keystone

        scenario = basic.CreateAndListServices(self.context)
        service_type = "test_service_type"
        description = "test_description"

        scenario.run(service_type=service_type, description=description)

        identity_service.create_service.assert_called_once_with(
            service_type=service_type, description=description)
        identity_service.list_services.assert_called_once_with()

    def test_create_and_list_ec2credentials(self):
        identity_service = self.mock_keystone

        scenario = basic.CreateAndListEc2Credentials(self.context)

        scenario.run()

        identity_service.create_credential.assert_called_once_with(
            "ec2",
            user_id=self.context["user"]["id"],
            project_id=self.context["tenant"]["id"])
        identity_service.list_credentials.assert_called_with(
            user_id=self.context["user"]["id"], cred_type="ec2")

    def test_create_and_delete_ec2credential(self):
        identity_service = self.mock_keystone

        fake_cred = identity_service.create_credential.return_value

        scenario = basic.CreateAndDeleteEc2Credential(self.context)

        scenario.run()

        identity_service.create_credential.assert_called_once_with(
            "ec2",
            user_id=self.context["user"]["id"],
            project_id=self.context["tenant"]["id"])
        identity_service.delete_credential.assert_called_once_with(
            fake_cred.id)

    def test_add_and_remove_user_role(self):
        context = self.context
        tenant_id = context["tenant"]["id"]
        user_id = context["user"]["id"]

        fake_role = mock.MagicMock()
        self.mock_keystone.create_role.return_value = fake_role

        scenario = basic.AddAndRemoveUserRole(context)
        scenario.run()

        self.mock_keystone.create_role.assert_called_once_with()
        self.mock_keystone.add_role.assert_called_once_with(
            role_id=fake_role.id, user_id=user_id, project_id=tenant_id)
        self.mock_keystone.revoke_role.assert_called_once_with(
            fake_role.id, user_id=user_id, project_id=tenant_id)
