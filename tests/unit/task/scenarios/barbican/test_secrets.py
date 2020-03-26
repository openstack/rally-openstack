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

from rally_openstack.task.scenarios.barbican import secrets
from tests.unit import fakes
from tests.unit import test


class BarbicanSecretsTestCase(test.ScenarioTestCase):

    def get_test_context(self):
        context = super(BarbicanSecretsTestCase, self).get_test_context()
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
        super(BarbicanSecretsTestCase, self).setUp()
        m = "rally_openstack.common.services.key_manager.barbican"
        patch = mock.patch("%s.BarbicanService" % m)
        self.addCleanup(patch.stop)
        self.mock_secrets = patch.start()

    def test_list_secrets(self):
        secrets_service = self.mock_secrets.return_value
        scenario = secrets.BarbicanSecretsList(self.context)
        scenario.run()
        secrets_service.list_secrets.assert_called_once_with()

    def test_create_secret(self):
        secrets_service = self.mock_secrets.return_value
        scenario = secrets.BarbicanSecretsCreate(self.context)
        scenario.run()
        secrets_service.create_secret.assert_called_once_with()

    def test_create_and_delete_secret(self):
        secrets_service = self.mock_secrets.return_value
        scenario = secrets.BarbicanSecretsCreateAndDelete(self.context)
        scenario.run()

        secrets_service.create_secret.assert_called_once_with()
        self.assertEqual(1, secrets_service.delete_secret.call_count)

    def test_create_and_get_secret(self):
        secrets_service = self.mock_secrets.return_value
        fake_secret = fakes.FakeSecret(id=1, name="secretxxx")
        secrets_service.create_secret.return_value = fake_secret
        fake_secret_info = fakes.FakeSecret(id=1, name="secret1xxx")
        secrets_service.get_secret.return_value = fake_secret_info
        scenario = secrets.BarbicanSecretsCreateAndGet(self.context)
        scenario.run()

        secrets_service.create_secret.assert_called_once_with()

    def test_get_secret(self):
        secrets_service = self.mock_secrets.return_value
        scenario = secrets.BarbicanSecretsGet(self.context)
        scenario.run()

        secrets_service.create_secret.assert_called_once_with()

    def test_get_secret_with_secret(self):
        secret = mock.Mock()
        secret.secret_ref = mock.Mock()
        secrets_service = self.mock_secrets.return_value
        scenario = secrets.BarbicanSecretsGet(self.context)
        scenario.run()

        self.assertEqual(1, secrets_service.get_secret.call_count)

    def test_create_and_list_secret(self):
        secrets_service = self.mock_secrets.return_value
        scenario = secrets.BarbicanSecretsCreateAndList(self.context)
        scenario.run()
        secrets_service.create_secret.assert_called_once_with()
        secrets_service.list_secrets.assert_called_once_with()

    def test_create_and_delete_symmetric_secret(self):
        secrets_service = self.mock_secrets.return_value
        scenario = secrets.BarbicanSecretsCreateSymmetricAndDelete(
            self.context)
        scenario.run(
            payload="rally_data", algorithm="aes", bit_length=256,
            mode="cbc")
        self.assertEqual(1, secrets_service.create_secret.call_count)
