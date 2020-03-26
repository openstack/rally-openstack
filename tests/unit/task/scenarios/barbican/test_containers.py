# Copyright 2018 Red Hat Inc
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

from rally_openstack.task.scenarios.barbican import containers
from tests.unit import test


class BarbicanContainersTestCase(test.ScenarioTestCase):

    def get_test_context(self):
        context = super(BarbicanContainersTestCase, self).get_test_context()
        context.update({
            "admin": {
                "user_id": "fake",
                "credential": mock.MagicMock()
            },
            "user": {
                "user_id": "fake",
                "credential": mock.MagicMock()
            },
            "tenant": {"id": "fake"}
        })
        return context

    def setUp(self):
        super(BarbicanContainersTestCase, self).setUp()
        m = "rally_openstack.common.services.key_manager.barbican"
        patch = mock.patch("%s.BarbicanService" % m)
        self.addCleanup(patch.stop)
        self.mock_secrets = patch.start()

    def test_list_containers(self):
        secrets_service = self.mock_secrets.return_value
        scenario = containers.BarbicanContainersList(self.context)
        scenario.run()
        secrets_service.list_container.assert_called_once_with()

    def test_generic_container_create_and_delete(self):
        secrets_service = self.mock_secrets.return_value
        fake_container = {"container_ref": "fake_container_ref"}
        fake_container = secrets_service.container_create.return_value
        scenario = containers.BarbicanContainersGenericCreateAndDelete(
            self.context)
        scenario.run()
        secrets_service.container_create.assert_called_once_with()
        secrets_service.container_delete.assert_called_once_with(
            fake_container.container_ref)

    def test_generic_container_create_and_add_secret(self):
        secrets_service = self.mock_secrets.return_value
        fake_container = {"container_ref": "fake_container_ref"}
        fake_secrets = {"secret_ref": "fake_secret_ref"}
        fake_container = secrets_service.container_create.return_value
        fake_secrets = secrets_service.create_secret.return_value
        scenario = containers.BarbicanContainersGenericCreateAndAddSecret(
            self.context)
        scenario.run()

        secrets_service.create_secret.assert_called_once_with()
        secrets_service.container_create.assert_called_once_with(
            secrets={"secret": fake_secrets})
        secrets_service.container_delete.assert_called_once_with(
            fake_container.container_ref)

    def test_certificate_coentaineri_create_and_delete(self):
        secrets_service = self.mock_secrets.return_value
        fake_container = {"container_ref": "fake_container_ref"}
        fake_container = secrets_service.create_certificate_container \
            .return_value
        scenario = containers.BarbicanContainersCertificateCreateAndDelete(
            self.context)
        scenario.run()
        secrets_service.create_certificate_container.assert_called_once_with()
        secrets_service.container_delete.assert_called_once_with(
            fake_container.container_ref)

    def test_rsa_container_create_and_delete(self):
        secrets_service = self.mock_secrets.return_value
        fake_container = {"container_ref": "fake_container_ref"}
        fake_container = secrets_service.create_rsa_container.return_value
        scenario = containers.BarbicanContainersRSACreateAndDelete(
            self.context)
        scenario.run()
        secrets_service.create_rsa_container.assert_called_once_with()
        secrets_service.container_delete.assert_called_once_with(
            fake_container.container_ref)
