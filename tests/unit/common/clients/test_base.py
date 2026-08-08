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

from rally import exceptions

from rally_openstack.common import credential as oscredential
from rally_openstack.common.clients import base
from tests.unit import test


@base.configure("base_test_client", supported_versions=["1", "2"],
                default_service_type="foo")
class _BaseTestClient(base.OSClient):
    def create_client(self, *args, **kwargs):
        return mock.Mock()


@base.configure("base_test_sdk_client", default_service_type="foo",
                sdk_service_type="foo-sdk")
class _BaseTestSDKClient(base.OSClient):
    def create_client(self, *args, **kwargs):
        pass


@base.configure("base_test_noversion_client", default_service_type="foo")
class _BaseTestNoVersionClient(base.OSClient):
    def create_client(self, *args, **kwargs):
        pass


@base.configure("base_test_badversion_client", supported_versions=["notanum"])
class _BaseTestBadVersionClient(base.OSClient):
    def create_client(self, *args, **kwargs):
        pass


@base.configure("base_test_ported_client", default_service_type="foo",
                supported_versions=["1"])
class _BaseTestPortedClient(base.LegacyClientCompat):
    def create_client(self, *args, **kwargs):
        return mock.Mock()


def _credential(**kwargs):
    kwargs.setdefault("auth_url", "http://auth/v3")
    kwargs.setdefault("username", "user")
    kwargs.setdefault("password", "pass")
    return oscredential.OpenStackCredential(**kwargs)


class ClientSpecTestCase(test.TestCase):

    def test_sdk_service_type_explicit(self):
        self.assertEqual("foo-sdk", _BaseTestSDKClient.spec.sdk_service_type)

    def test_sdk_service_type_falls_back_to_default(self):
        self.assertEqual("foo", _BaseTestClient.spec.sdk_service_type)

    def test_validate_version_unsupported(self):
        e = self.assertRaises(exceptions.ValidationError,
                              _BaseTestClient.spec.validate_version, "5")
        self.assertIn("not supported", str(e))

    def test_validate_version_setting_not_supported(self):
        e = self.assertRaises(
            exceptions.RallyException,
            _BaseTestNoVersionClient.spec.validate_version, 1)
        self.assertIn("Setting version is not supported", str(e))

    def test_validate_version_non_numeric(self):
        self.assertRaises(
            exceptions.ValidationError,
            _BaseTestBadVersionClient.spec.validate_version, "notanum")

    def test_is_service_type_configurable(self):
        self.assertIsNone(_BaseTestClient.spec.is_service_type_configurable())


class BaseClientTestCase(test.TestCase):

    def test_init_normalizes_dict_credential(self):
        client = _BaseTestClient({"auth_url": "u", "username": "n",
                                  "password": "p"})
        self.assertIsInstance(client.credential,
                              oscredential.OpenStackCredential)
        self.assertEqual("u", client.credential.auth_url)

    def test_conn_without_clients_raises(self):
        client = _BaseTestClient(_credential())
        self.assertRaises(exceptions.RallyException, lambda: client._conn)

    def test_conn_delegates_to_clients(self):
        fake_clients = mock.Mock()
        client = _BaseTestPortedClient(_credential(), clients=fake_clients,
                                       atomic_inst=[])
        self.assertEqual(fake_clients._conn, client._conn)

    def test_atomic_action(self):
        timer = _BaseTestClient(_credential())._atomic_action("foo")
        self.assertEqual("foo", timer.name)

    def test_generate_random_name_without_generator(self):
        client = _BaseTestClient(_credential())
        self.assertRaises(exceptions.RallyException,
                          client.generate_random_name)

    def test_generate_random_name(self):
        client = _BaseTestPortedClient(
            _credential(), clients=None, atomic_inst=[],
            name_generator=lambda: "generated-name")
        self.assertEqual("generated-name", client.generate_random_name())


class LegacyClientCompatTestCase(test.TestCase):

    def test_get_auth_info_v3_with_endpoint_type(self):
        cred = _credential(auth_url="http://auth/v3", tenant_name="tenant",
                           domain_name="d", user_domain_name="ud",
                           project_domain_name="pd", endpoint_type="internal")
        info = _BaseTestClient(cred)._get_auth_info()
        self.assertEqual("user", info["username"])
        self.assertEqual("pass", info["password"])
        self.assertEqual("tenant", info["project_id"])
        self.assertEqual("d", info["domain_name"])
        self.assertEqual("ud", info["user_domain_name"])
        self.assertEqual("pd", info["project_domain_name"])
        self.assertEqual("internal", info["endpoint_type"])

    def test_get_auth_info_domain_defaults(self):
        info = _BaseTestClient(_credential(auth_url="http://auth/v3"))\
            ._get_auth_info()
        self.assertEqual("Default", info["user_domain_name"])
        self.assertEqual("Default", info["project_domain_name"])

    def test_get_auth_info_v2_without_project_key(self):
        cred = _credential(auth_url="http://auth/v2.0", tenant_name="tenant")
        info = _BaseTestClient(cred)._get_auth_info(project_name_key=None)
        self.assertNotIn("project_id", info)
        # v2.0 in auth_url -> no domain args
        self.assertNotIn("domain_name", info)
