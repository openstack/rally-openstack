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

import uuid
from unittest import mock

import ddt

from rally import exceptions

from rally_openstack.common.services.identity import identity
from rally_openstack.common.services.identity import keystone_v3
from tests.unit import test


PATH = "rally_openstack.common.services.identity.keystone_v3"


@ddt.ddt
class KeystoneV3ServiceTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.clients = mock.MagicMock()
        self.kc = self.clients.keystone.return_value
        self.name_generator = mock.MagicMock()
        self.service = keystone_v3.KeystoneV3Service(
            self.clients, name_generator=self.name_generator)
        self.service._ng_cache = mock.MagicMock()
        self.ng = self.service._ng_cache

    def test__get_domain_id_not_found(self):
        from keystoneclient import exceptions as kc_exceptions

        self.kc.domains.get.side_effect = kc_exceptions.NotFound
        self.kc.domains.list.return_value = []
        domain_name_or_id = "some"

        self.assertRaises(exceptions.GetResourceNotFound,
                          self.service._get_domain_id, domain_name_or_id)
        self.kc.domains.get.assert_called_once_with(domain_name_or_id)
        self.kc.domains.list.assert_called_once_with(name=domain_name_or_id)

    def test__get_domain_id_find_by_name(self):
        from keystoneclient import exceptions as kc_exceptions

        self.kc.domains.get.side_effect = kc_exceptions.NotFound
        domain = mock.MagicMock()
        self.kc.domains.list.return_value = [domain]
        domain_name_or_id = "some"

        self.assertEqual(domain.id,
                         self.service._get_domain_id(domain_name_or_id))
        self.kc.domains.get.assert_called_once_with(domain_name_or_id)
        self.kc.domains.list.assert_called_once_with(name=domain_name_or_id)

    def test__get_domain_id_find_by_id(self):
        domain = mock.MagicMock()

        self.kc.domains.get.return_value = domain

        domain_name_or_id = "some"

        self.assertEqual(domain.id,
                         self.service._get_domain_id(domain_name_or_id))
        self.kc.domains.get.assert_called_once_with(domain_name_or_id)
        self.assertFalse(self.kc.domains.list.called)

    def test_create_project(self):
        name = "name"
        domain_name = "domain"

        project = self.service.create_project(name, domain_name=domain_name)

        self.assertEqual(self.ng.create_project.return_value, project)
        self.ng.create_project.assert_called_once_with(
            name, domain=domain_name)

    @ddt.data({"project_id": "fake_id", "name": True, "enabled": True,
               "description": True},
              {"project_id": "fake_id", "name": "some", "enabled": False,
               "description": "descr"})
    @ddt.unpack
    def test_update_project(self, project_id, name, enabled, description):

        self.service.update_project(project_id,
                                    name=name,
                                    description=description,
                                    enabled=enabled)

        if name is True:
            name = self.name_generator.return_value
        if description is True:
            description = self.name_generator.return_value

        self.ng.update_project.assert_called_once_with(
            project_id, name=name, enabled=enabled, description=description)

    def test_delete_project(self):
        project_id = "fake_id"
        self.service.delete_project(project_id)
        self.ng.delete_project.assert_called_once_with(project_id)

    def test_list_projects(self):
        self.assertEqual(self.ng.list_projects.return_value,
                         self.service.list_projects())
        self.ng.list_projects.assert_called_once_with()

    def test_get_project(self):
        project_id = "fake_id"
        self.service.get_project(project_id)
        self.ng.get_project.assert_called_once_with(project_id)

    def test_create_user(self):
        user = self.service.create_user("name", password="passwd",
                                        project_id="project",
                                        domain_name="domain")
        self.assertEqual(self.ng.create_user.return_value, user)
        self.ng.create_user.assert_called_once_with(
            username="name", password="passwd", project_id="project",
            domain="domain", enabled=True)
        # the client no longer grants the default role, so this deprecated
        # layer keeps doing it itself to preserve its contract.
        self.ng.find_role.assert_called_once_with("member")
        self.ng.add_role.assert_called_once_with(
            role_id=self.ng.find_role.return_value.id,
            user_id=user.id, project_id="project")

    def test_create_user_without_project(self):
        self.service.create_user("name", password="passwd")
        self.assertFalse(self.ng.find_role.called)
        self.assertFalse(self.ng.add_role.called)

    @mock.patch("%s.LOG.warning" % PATH)
    def test_create_user_default_role_not_found(self, mock_log_warning):
        self.ng.find_role.return_value = None
        self.service.create_user("name", project_id="project")
        self.assertFalse(self.ng.add_role.called)
        self.assertTrue(mock_log_warning.called)

    def test_create_users(self):
        self.service.create_user = mock.MagicMock()

        n = 2
        project_id = "some"
        self.assertEqual([self.service.create_user.return_value] * n,
                         self.service.create_users(number_of_users=n,
                                                   project_id=project_id))
        self.assertEqual([mock.call(project_id=project_id)] * n,
                         self.service.create_user.call_args_list)

    @ddt.data(None, "some")
    def test_update_user(self, domain_name):
        user_id = "fake_id"
        name = "new name"
        project_id = "new project"
        password = "pass"
        email = "mail"
        description = "n/a"
        enabled = False
        default_project = "some"

        self.service._get_domain_id = mock.MagicMock()

        self.service.update_user(user_id, name=name, domain_name=domain_name,
                                 project_id=project_id, password=password,
                                 email=email, description=description,
                                 enabled=enabled,
                                 default_project=default_project)

        domain = None
        if domain_name:
            self.service._get_domain_id.assert_called_once_with(domain_name)
            domain = self.service._get_domain_id.return_value
        else:
            self.assertFalse(self.service._get_domain_id.called)

        self.kc.users.update.assert_called_once_with(
            user_id, name=name, domain=domain, project=project_id,
            password=password, email=email, description=description,
            enabled=enabled, default_project=default_project)

    @ddt.data({"name": None, "service_type": None, "description": None,
               "enabled": True},
              {"name": "some", "service_type": "st", "description": "d",
               "enabled": False})
    @ddt.unpack
    def test_create_service(self, name, service_type, description, enabled):
        self.assertEqual(self.kc.services.create.return_value,
                         self.service.create_service(name=name,
                                                     service_type=service_type,
                                                     description=description,
                                                     enabled=enabled))
        name = name or self.name_generator.return_value
        service_type = service_type or "rally_test_type"
        description = description or self.name_generator.return_value
        self.kc.services.create.assert_called_once_with(
            name, type=service_type, description=description,
            enabled=enabled)

    def test_create_role(self):
        role = self.service.create_role("some", domain_name="domain")
        self.assertEqual(self.ng.create_role.return_value, role)
        self.ng.create_role.assert_called_once_with(
            name="some", domain="domain")

    @ddt.data({"domain_name": "domain", "user_id": "user", "project_id": "pr"},
              {"domain_name": None, "user_id": None, "project_id": None})
    @ddt.unpack
    def test_list_roles(self, domain_name, user_id, project_id):
        result = self.service.list_roles(user_id=user_id,
                                         domain_name=domain_name,
                                         project_id=project_id)
        if user_id:
            self.assertEqual(self.ng.list_role_assignments.return_value,
                             result)
            self.ng.list_role_assignments.assert_called_once_with(
                user_id, project_id=project_id, domain=domain_name)
        else:
            self.assertEqual(self.ng.list_roles.return_value, result)
            self.ng.list_roles.assert_called_once_with(
                domain=domain_name)

    def test_add_role(self):
        role_id = "fake_id"
        user_id = "user_id"
        project_id = "project_id"

        self.service.add_role(role_id, user_id=user_id, project_id=project_id)
        self.ng.add_role.assert_called_once_with(
            role_id=role_id, user_id=user_id, project_id=project_id)

    def test_revoke_role(self):
        role_id = "fake_id"
        user_id = "user_id"
        project_id = "tenant_id"

        self.service.revoke_role(role_id, user_id=user_id,
                                 project_id=project_id)

        self.ng.revoke_role.assert_called_once_with(
            role_id=role_id, user_id=user_id, project_id=project_id)

    def test_get_role(self):
        role_id = "fake_id"
        self.service.get_role(role_id)
        self.kc.roles.get.assert_called_once_with(role_id)

    def test_create_domain(self):
        name = "some_domain"
        descr = "descr"
        enabled = False

        self.service.create_domain(name, description=descr, enabled=enabled)
        self.ng.create_domain.assert_called_once_with(
            name, description=descr, is_enabled=enabled)

    def test_create_ec2credentials(self):
        user_id = "fake_id"
        project_id = "fake_id"

        self.assertEqual(self.kc.ec2.create.return_value,
                         self.service.create_ec2credentials(
                             user_id, project_id=project_id))
        self.kc.ec2.create.assert_called_once_with(user_id,
                                                   project_id=project_id)


@ddt.ddt
class UnifiedKeystoneV3ServiceTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.clients = mock.MagicMock()
        self.service = keystone_v3.UnifiedKeystoneV3Service(self.clients)
        self.service._impl = mock.MagicMock()

    def test_init_identity_service(self):
        self.clients.keystone.version = "3"
        self.assertIsInstance(identity.Identity(self.clients)._impl,
                              keystone_v3.UnifiedKeystoneV3Service)

    def test__unify_project(self):
        class KeystoneV3Project:
            def __init__(self):
                self.id = str(uuid.uuid4())
                self.name = str(uuid.uuid4())
                self.domain_id = str(uuid.uuid4())

        project = KeystoneV3Project()
        unified_project = self.service._unify_project(project)
        self.assertIsInstance(unified_project, identity.Project)
        self.assertEqual(project.id, unified_project.id)
        self.assertEqual(project.name, unified_project.name)
        self.assertEqual(project.domain_id, unified_project.domain_id)
        self.assertEqual(project.domain_id, unified_project.domain_id)

    def test__unify_user(self):
        class KeystoneV3User:
            def __init__(self, project_id=None):
                self.id = str(uuid.uuid4())
                self.name = str(uuid.uuid4())
                self.domain_id = str(uuid.uuid4())
                if project_id is not None:
                    self.default_project_id = project_id

        user = KeystoneV3User()

        unified_user = self.service._unify_user(user)
        self.assertIsInstance(unified_user, identity.User)
        self.assertEqual(user.id, unified_user.id)
        self.assertEqual(user.name, unified_user.name)
        self.assertEqual(user.domain_id, unified_user.domain_id)
        self.assertIsNone(unified_user.project_id)

        project_id = "tenant_id"
        user = KeystoneV3User(project_id=project_id)
        unified_user = self.service._unify_user(user)
        self.assertIsInstance(unified_user, identity.User)
        self.assertEqual(user.id, unified_user.id)
        self.assertEqual(user.name, unified_user.name)
        self.assertEqual(user.domain_id, unified_user.domain_id)
        self.assertEqual(project_id, unified_user.project_id)

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_project" % PATH)
    def test_create_project(self,
                            mock_unified_keystone_v3_service__unify_project):
        mock_unify_project = mock_unified_keystone_v3_service__unify_project
        name = "name"
        domain = "domain"

        self.assertEqual(mock_unify_project.return_value,
                         self.service.create_project(name, domain_name=domain))
        mock_unify_project.assert_called_once_with(
            self.service._impl.create_project.return_value)
        self.service._impl.create_project.assert_called_once_with(
            name, domain_name=domain)

    def test_update_project(self):
        project_id = "fake_id"
        name = "name"
        description = "descr"
        enabled = False

        self.service.update_project(project_id=project_id, name=name,
                                    description=description, enabled=enabled)
        self.service._impl.update_project.assert_called_once_with(
            project_id=project_id, name=name, description=description,
            enabled=enabled)

    def test_delete_project(self):
        project_id = "fake_id"
        self.service.delete_project(project_id)
        self.service._impl.delete_project.assert_called_once_with(project_id)

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_project" % PATH)
    def test_get_project(self,
                         mock_unified_keystone_v3_service__unify_project):
        mock_unify_project = mock_unified_keystone_v3_service__unify_project
        project_id = "id"

        self.assertEqual(mock_unify_project.return_value,
                         self.service.get_project(project_id))
        mock_unify_project.assert_called_once_with(
            self.service._impl.get_project.return_value)
        self.service._impl.get_project.assert_called_once_with(project_id)

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_project" % PATH)
    def test_list_projects(self,
                           mock_unified_keystone_v3_service__unify_project):
        mock_unify_project = mock_unified_keystone_v3_service__unify_project

        projects = [mock.MagicMock()]
        self.service._impl.list_projects.return_value = projects

        self.assertEqual([mock_unify_project.return_value],
                         self.service.list_projects())
        mock_unify_project.assert_called_once_with(projects[0])

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_user" % PATH)
    def test_create_user(self, mock_unified_keystone_v3_service__unify_user):
        mock_unify_user = mock_unified_keystone_v3_service__unify_user

        name = "name"
        password = "passwd"
        project_id = "project"
        domain_name = "domain"
        default_role = "role"

        self.assertEqual(mock_unify_user.return_value,
                         self.service.create_user(name, password=password,
                                                  project_id=project_id,
                                                  domain_name=domain_name,
                                                  default_role=default_role))
        mock_unify_user.assert_called_once_with(
            self.service._impl.create_user.return_value)
        self.service._impl.create_user.assert_called_once_with(
            username=name, password=password, project_id=project_id,
            domain_name=domain_name, default_role=default_role, enabled=True)

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_user" % PATH)
    def test_create_users(self, mock_unified_keystone_v3_service__unify_user):
        project_id = "project"
        n = 3
        domain_name = "Default"

        self.service.create_users(
            project_id, number_of_users=3,
            user_create_args={"domain_name": domain_name})
        self.service._impl.create_users.assert_called_once_with(
            project_id=project_id, number_of_users=n,
            user_create_args={"domain_name": domain_name})

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_user" % PATH)
    def test_list_users(self, mock_unified_keystone_v3_service__unify_user):
        mock_unify_user = mock_unified_keystone_v3_service__unify_user

        users = [mock.MagicMock()]
        self.service._impl.list_users.return_value = users

        self.assertEqual([mock_unify_user.return_value],
                         self.service.list_users())
        mock_unify_user.assert_called_once_with(users[0])

    @ddt.data({"user_id": "id", "enabled": False, "name": "Fake",
               "email": "badboy@example.com", "password": "pass"},
              {"user_id": "id", "enabled": None, "name": None,
               "email": None, "password": None})
    @ddt.unpack
    def test_update_user(self, user_id, enabled, name, email, password):
        self.service.update_user(user_id, enabled=enabled, name=name,
                                 email=email, password=password)
        self.service._impl.update_user.assert_called_once_with(
            user_id, enabled=enabled, name=name, email=email,
            password=password)

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_service" % PATH)
    def test_list_services(self,
                           mock_unified_keystone_v3_service__unify_service):
        mock_unify_service = mock_unified_keystone_v3_service__unify_service

        services = [mock.MagicMock()]
        self.service._impl.list_services.return_value = services

        self.assertEqual([mock_unify_service.return_value],
                         self.service.list_services())
        mock_unify_service.assert_called_once_with(services[0])

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_role" % PATH)
    def test_create_role(self, mock_unified_keystone_v3_service__unify_role):
        mock_unify_role = mock_unified_keystone_v3_service__unify_role
        name = "some"
        domain = "some"

        self.assertEqual(mock_unify_role.return_value,
                         self.service.create_role(name, domain_name=domain))

        self.service._impl.create_role.assert_called_once_with(
            name, domain_name=domain)
        mock_unify_role.assert_called_once_with(
            self.service._impl.create_role.return_value)

    def test_add_role(self):
        role_id = "fake_id"
        user_id = "user_id"
        project_id = "user_id"

        self.service.add_role(role_id, user_id=user_id, project_id=project_id)

        self.service._impl.add_role.assert_called_once_with(
            user_id=user_id, role_id=role_id, project_id=project_id)

    def test_revoke_role(self):
        role_id = "fake_id"
        user_id = "user_id"
        project_id = "user_id"

        self.service.revoke_role(role_id, user_id=user_id,
                                 project_id=project_id)

        self.service._impl.revoke_role.assert_called_once_with(
            user_id=user_id, role_id=role_id, project_id=project_id)

    @mock.patch("%s.UnifiedKeystoneV3Service._unify_role" % PATH)
    def test_list_roles(self, mock_unified_keystone_v3_service__unify_role):
        mock_unify_role = mock_unified_keystone_v3_service__unify_role

        roles = [mock.MagicMock()]
        self.service._impl.list_roles.return_value = roles

        self.assertEqual([mock_unify_role.return_value],
                         self.service.list_roles())
        mock_unify_role.assert_called_once_with(roles[0])

    def test_create_ec2credentials(self):
        user_id = "id"
        project_id = "project-id"

        self.assertEqual(self.service._impl.create_ec2credentials.return_value,
                         self.service.create_ec2credentials(
                             user_id=user_id, project_id=project_id))

        self.service._impl.create_ec2credentials.assert_called_once_with(
            user_id=user_id, project_id=project_id)
