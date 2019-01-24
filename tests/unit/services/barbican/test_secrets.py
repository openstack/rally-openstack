# Copyright 2018 Red Hat, Inc. <http://www.redhat.com>
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

import mock

from rally_openstack.services.key_manager import barbican
from tests.unit import test


class BarbicanServiceTestCase(test.TestCase):
    def setUp(self):
        super(BarbicanServiceTestCase, self).setUp()
        self.clients = mock.MagicMock()
        self.name_generator = mock.MagicMock()
        self.service = barbican.BarbicanService(
            self.clients,
            name_generator=self.name_generator)

    def atomic_actions(self):
        return self.service._atomic_actions

    def test__list_secrets(self):
        self.assertEqual(
            self.service.list_secrets(),
            self.service._clients.barbican().secrets.list.return_value
        )
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "barbican.list_secrets")

    def test__create_secret(self):
        self.assertEqual(
            self.service.create_secret(),
            self.service._clients.barbican().secrets.create(
                name="fake_secret", payload="rally_data")
        )
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "barbican.create_secret")

    def test__get_secret(self):
        self.service.get_secret("fake_secret")
        self.service._clients.barbican().secrets.get \
            .assert_called_once_with("fake_secret")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "barbican.get_secret")

    def test__delete_secret(self):
        self.service.delete_secret("fake_secret")
        self.service._clients.barbican().secrets.delete \
            .assert_called_once_with("fake_secret")
        self._test_atomic_action_timer(self.atomic_actions(),
                                       "barbican.delete_secret")

    def test__list_containers(self):
        self.assertEqual(
            self.service.list_container(),
            self.service._clients.barbican().containers.list.return_value)
        self._test_atomic_action_timer(
            self.atomic_actions(), "barbican.list_container")

    def test__container_delete(self):
        self.service.container_delete("fake_container")
        self.service._clients.barbican().containers.delete \
            .assert_called_once_with("fake_container")
        self._test_atomic_action_timer(
            self.atomic_actions(), "barbican.container_delete")

    def test__container_create(self):
        self.service.generate_random_name = mock.MagicMock(
            return_value="container")
        self.service.container_create()
        self.service._clients.barbican().containers.create \
            .assert_called_once_with(name="container", secrets=None)

    def test__create_rsa_container(self):
        self.service.generate_random_name = mock.MagicMock(
            return_value="container")
        self.service.create_rsa_container()
        self.service._clients.barbican().containers.create_rsa \
            .assert_called_once_with(
                name="container", private_key=None,
                private_key_passphrase=None, public_key=None)

    def test__create_generate_container(self):
        self.service.generate_random_name = mock.MagicMock(
            return_value="container")
        self.service.create_certificate_container()
        self.service._clients.barbican().containers \
            .create_certificate.assert_called_once_with(
                certificate=None, intermediates=None,
                name="container", private_key=None,
                private_key_passphrase=None)
