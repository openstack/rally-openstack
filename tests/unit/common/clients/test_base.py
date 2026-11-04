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

from rally_openstack.common import credential as oscredential
from rally_openstack.common import osclients
from rally_openstack.common.clients import base
from tests.unit import fakes
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


@base.configure("base_test_dashed_client", default_service_type="foo-bar")
class _BaseTestDashedClient(base.LegacyClientCompat):
    pass


@base.configure("base_test_typeless_client")
class _BaseTestTypelessClient(base.LegacyClientCompat):
    pass


@base.configure("base_test_deprecating_client", supported_versions=["1", "2"],
                deprecated_versions={"1": "4.2.0"})
class _BaseTestDeprecatingClient(base.OSClient):
    def create_client(self, *args, **kwargs):
        pass


@base.configure("base_test_legacy_client", default_service_type="legacy")
class _BaseTestLegacyClient(base.OSClient):
    def create_client(self, *args, **kwargs):
        self.cache["native_clients"] = self.cache.get("native_clients", 0) + 1


def _credential(**kwargs):
    kwargs.setdefault("auth_url", "http://auth/v3")
    kwargs.setdefault("username", "user")
    kwargs.setdefault("password", "pass")
    kwargs.setdefault("project_name", "project")
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

    def test_deprecated_versions(self):
        patcher = mock.patch.object(
            base, "_reported_deprecated_versions", set())
        patcher.start()
        self.addCleanup(patcher.stop)
        spec = _BaseTestDeprecatingClient.spec
        notice = ("The 'base_test_deprecating_client' API v1 is deprecated "
                  "since Rally-OpenStack 4.2.0 and its support will be "
                  "removed.")

        with self.assertLogs("rally_openstack.common.clients.base",
                             level="WARNING") as logs:
            spec.validate_version("1")
            spec.validate_version(1)
            spec.validate_version("2")
            self.assertEqual(notice, spec.warn_if_deprecated(1))

        self.assertEqual([notice], [r.getMessage() for r in logs.records])
        self.assertIsNone(spec.get_deprecation("2"))
        self.assertIsNone(_BaseTestClient.spec.get_deprecation("1"))


@ddt.ddt
class BaseClientTestCase(test.TestCase):

    def test_init_normalizes_dict_credential(self):
        client = _BaseTestClient({"auth_url": "u", "username": "n",
                                  "password": "p", "project_name": "t"})
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

    @ddt.data(("glance", "image", False),
              ("base_test_dashed_client", "foo_bar", False),
              ("glance", "image", True))
    @ddt.unpack
    def test_check_availability(self, client_name, proxy, skip_discovery):
        cloud = fakes.FakeOpenStack(self)
        cloud.services.add(proxy)
        if skip_discovery:
            cloud.skip_discovery.add(proxy)
        cred = _credential()

        getattr(osclients.Clients(cred), client_name).check_availability()

        self.assertEqual([proxy], cloud.accessed)
        if skip_discovery:
            self.assertEqual({}, cred.discovery_cache)
        else:
            self.assertIn({"service": proxy}, cred.discovery_cache.values())

    def test_check_availability_without_openstacksdk(self):
        cloud = fakes.FakeOpenStack(self)
        clients = osclients.Clients(_credential())

        clients.base_test_legacy_client.check_availability()
        self.assertRaises(exceptions.RallyException,
                          clients.base_test_typeless_client.check_availability)

        self.assertEqual(1, clients.cache["native_clients"])
        self.assertEqual([], cloud.accessed)

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
        cred = _credential(auth_url="http://auth/v3", project_name="tenant",
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
        cred = _credential(auth_url="http://auth/v2.0", project_name="tenant")
        info = _BaseTestClient(cred)._get_auth_info(project_name_key=None)
        self.assertNotIn("project_id", info)
        # v2.0 in auth_url -> no domain args
        self.assertNotIn("domain_name", info)
