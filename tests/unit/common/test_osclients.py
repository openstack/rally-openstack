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

from rally.common import cfg
from rally import exceptions

from rally_openstack.common import consts
from rally_openstack.common import credential as oscredential
from rally_openstack.common import osclients
from tests.unit import fakes
from tests.unit import test

PATH = "rally_openstack.common.osclients"


@osclients.configure("dummy", supported_versions=("0.1", "1"),
                     default_service_type="bar")
class DummyClient(osclients.OSClient):
    def create_client(self, *args, **kwargs):
        pass


class OSClientTestCaseUtils(object):

    def set_up_keystone_mocks(self):
        self.ksc_module = mock.MagicMock(__version__="2.0.0")
        self.ksc_client = mock.MagicMock()
        self.ksa_identity_plugin = mock.MagicMock()
        self.ksa_password = mock.MagicMock(
            return_value=self.ksa_identity_plugin)
        self.ksa_identity = mock.MagicMock(Password=self.ksa_password)

        self.ksa_auth = mock.MagicMock()
        self.ksa_session = mock.MagicMock()
        self.patcher = mock.patch.dict("sys.modules",
                                       {"keystoneclient": self.ksc_module,
                                        "keystoneauth1": self.ksa_auth})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.ksc_module.client = self.ksc_client
        self.ksa_auth.identity = self.ksa_identity
        self.ksa_auth.session = self.ksa_session

    def make_auth_args(self):
        auth_kwargs = {
            "auth_url": "http://auth_url/", "username": "user",
            "password": "password", "tenant_name": "tenant",
            "domain_name": "domain", "project_name": "project_name",
            "project_domain_name": "project_domain_name",
            "user_domain_name": "user_domain_name",
        }
        kwargs = {"https_insecure": False, "https_cacert": None}
        kwargs.update(auth_kwargs)
        return auth_kwargs, kwargs


@ddt.ddt
class OSClientTestCase(test.TestCase, OSClientTestCaseUtils):

    @ddt.data((0.1, True), (1, True), ("0.1", True), ("1", True),
              (0.2, False), ("foo", False))
    @ddt.unpack
    def test_validate_version(self, version, valid):
        if valid:
            DummyClient.validate_version(version)
        else:
            self.assertRaises(exceptions.ValidationError,
                              DummyClient.validate_version, version)

    def test_choose_service_type(self):
        default_service_type = "default_service_type"

        @osclients.configure(self.id(),
                             default_service_type=default_service_type)
        class FakeClient(osclients.OSClient):
            create_client = mock.MagicMock()

        fake_client = FakeClient({"auth_url": "url", "username": "user",
                                  "password": "pass"}, {})
        self.assertEqual(default_service_type,
                         fake_client.choose_service_type())
        self.assertEqual("foo",
                         fake_client.choose_service_type("foo"))

    @mock.patch("%s.Keystone.service_catalog" % PATH)
    @ddt.data(
        {"endpoint_type": None, "service_type": None, "region_name": None},
        {"endpoint_type": "et", "service_type": "st", "region_name": "rn"}
    )
    @ddt.unpack
    def test__get_endpoint(self, mock_keystone_service_catalog, endpoint_type,
                           service_type, region_name):
        credential = oscredential.OpenStackCredential(
            "http://auth_url/v2.0", "user", "pass",
            endpoint_type=endpoint_type,
            region_name=region_name)
        mock_choose_service_type = mock.MagicMock()
        osclient = osclients.OSClient(credential, mock.MagicMock())
        osclient.choose_service_type = mock_choose_service_type
        mock_url_for = mock_keystone_service_catalog.url_for
        self.assertEqual(mock_url_for.return_value,
                         osclient._get_endpoint(service_type))
        call_args = {
            "service_type": mock_choose_service_type.return_value,
            "region_name": region_name}
        if endpoint_type:
            call_args["interface"] = endpoint_type
        mock_url_for.assert_called_once_with(**call_args)
        mock_choose_service_type.assert_called_once_with(service_type)


class CachedTestCase(test.TestCase):

    def test_cached(self):
        clients = osclients.Clients({"auth_url": "url", "username": "user",
                                     "password": "pass"})

        @osclients.configure(self.id())
        class SomeClient(osclients.OSClient):
            pass

        fake_client = SomeClient(clients.credential, clients.cache)
        fake_client.create_client = mock.MagicMock()

        self.assertEqual({}, clients.cache)
        fake_client()
        self.assertEqual(
            {self.id(): fake_client.create_client.return_value},
            clients.cache)
        fake_client.create_client.assert_called_once_with()
        fake_client()
        fake_client.create_client.assert_called_once_with()
        fake_client("2")
        self.assertEqual(
            {self.id(): fake_client.create_client.return_value,
             "%s('2',)" % self.id(): fake_client.create_client.return_value},
            clients.cache)
        clients.clear()
        self.assertEqual({}, clients.cache)


@ddt.ddt
class TestCreateKeystoneClient(test.TestCase, OSClientTestCaseUtils):

    def setUp(self):
        super(TestCreateKeystoneClient, self).setUp()
        self.credential = oscredential.OpenStackCredential(
            "http://auth_url/v2.0", "user", "pass", "tenant")

    def test_create_client(self):
        # NOTE(bigjools): This is a very poor testing strategy as it
        # tightly couples the test implementation to the tested
        # function's implementation. Ideally, we'd use a fake keystone
        # but all that's happening here is that it's checking the right
        # parameters were passed to the various parts that create a
        # client. Hopefully one day we'll get a real fake from the
        # keystone guys.
        self.set_up_keystone_mocks()
        keystone = osclients.Keystone(self.credential, mock.MagicMock())
        keystone.get_session = mock.Mock(
            return_value=(self.ksa_session, self.ksa_identity_plugin,))
        client = keystone.create_client(version=3)

        kwargs_session = self.credential.to_dict()
        kwargs_session.update({
            "auth_url": "http://auth_url/",
            "session": self.ksa_session,
            "timeout": 180.0})
        keystone.get_session.assert_called_with()
        called_with = self.ksc_client.Client.call_args_list[0][1]
        self.assertEqual(
            {"session": self.ksa_session, "timeout": 180.0, "version": "3"},
            called_with)
        self.ksc_client.Client.assert_called_once_with(
            session=self.ksa_session, timeout=180.0, version="3")
        self.assertIs(client, self.ksc_client.Client())

    def test_create_client_removes_url_path_if_version_specified(self):
        # If specifying a version on the client creation call, ensure
        # the auth_url is versionless and the version required is passed
        # into the Client() call.
        self.set_up_keystone_mocks()
        auth_kwargs, all_kwargs = self.make_auth_args()
        keystone = osclients.Keystone(
            self.credential, mock.MagicMock())
        keystone.get_session = mock.Mock(
            return_value=(self.ksa_session, self.ksa_identity_plugin,))
        client = keystone.create_client(version="3")

        self.assertIs(client, self.ksc_client.Client())
        called_with = self.ksc_client.Client.call_args_list[0][1]
        self.assertEqual(
            {"session": self.ksa_session, "timeout": 180.0, "version": "3"},
            called_with)

    @ddt.data({"original": "https://example.com/identity/foo/v3",
               "cropped": "https://example.com/identity/foo"},
              {"original": "https://example.com/identity/foo/v3/",
               "cropped": "https://example.com/identity/foo"},
              {"original": "https://example.com/identity/foo/v2.0",
               "cropped": "https://example.com/identity/foo"},
              {"original": "https://example.com/identity/foo/v2.0/",
               "cropped": "https://example.com/identity/foo"},
              {"original": "https://example.com/identity/foo",
               "cropped": "https://example.com/identity/foo"})
    @ddt.unpack
    def test__remove_url_version(self, original, cropped):
        credential = oscredential.OpenStackCredential(
            original, "user", "pass", "tenant")
        keystone = osclients.Keystone(credential, {})
        self.assertEqual(cropped, keystone._remove_url_version())

    @ddt.data("http://auth_url/v2.0", "http://auth_url/v3",
              "http://auth_url/", "auth_url")
    def test_keystone_get_session(self, auth_url):
        credential = oscredential.OpenStackCredential(
            auth_url, "user", "pass", "tenant")
        self.set_up_keystone_mocks()
        keystone = osclients.Keystone(credential, {})

        version_data = mock.Mock(return_value=[{"version": (1, 0)}])
        self.ksa_auth.discover.Discover.return_value = (
            mock.Mock(version_data=version_data))

        self.assertEqual((self.ksa_session.Session.return_value,
                          self.ksa_identity_plugin),
                         keystone.get_session())
        if auth_url.endswith("v2.0"):
            self.ksa_password.assert_called_once_with(
                auth_url=auth_url, password="pass",
                tenant_name="tenant", username="user")
        else:
            self.ksa_password.assert_called_once_with(
                auth_url=auth_url, password="pass",
                tenant_name="tenant", username="user",
                domain_name=None, project_domain_name=None,
                user_domain_name=None)
        self.assertEqual(
            [mock.call(timeout=180.0, verify=True, cert=None),
             mock.call(auth=self.ksa_identity_plugin, timeout=180.0,
                       verify=True, cert=None)],
            self.ksa_session.Session.call_args_list
        )

    def test_keystone_property(self):
        keystone = osclients.Keystone(self.credential, None)
        self.assertRaises(exceptions.RallyException, lambda: keystone.keystone)

    @mock.patch("%s.Keystone.get_session" % PATH)
    def test_auth_ref(self, mock_keystone_get_session):
        session = mock.MagicMock()
        auth_plugin = mock.MagicMock()
        mock_keystone_get_session.return_value = (session, auth_plugin)
        cache = {}
        keystone = osclients.Keystone(self.credential, cache)

        self.assertEqual(auth_plugin.get_access.return_value,
                         keystone.auth_ref)
        self.assertEqual(auth_plugin.get_access.return_value,
                         cache["keystone_auth_ref"])

        # check that auth_ref was cached.
        keystone.auth_ref
        mock_keystone_get_session.assert_called_once_with()

    @mock.patch("%s.LOG.exception" % PATH)
    @mock.patch("%s.logging.is_debug" % PATH)
    def test_auth_ref_fails(self, mock_is_debug, mock_log_exception):
        mock_is_debug.return_value = False
        keystone = osclients.Keystone(self.credential, {})
        session = mock.Mock()
        auth_plugin = mock.Mock()
        auth_plugin.get_access.side_effect = Exception
        keystone.get_session = mock.Mock(return_value=(session, auth_plugin))

        self.assertRaises(osclients.AuthenticationFailed,
                          lambda: keystone.auth_ref)

        self.assertFalse(mock_log_exception.called)
        mock_is_debug.assert_called_once_with()
        auth_plugin.get_access.assert_called_once_with(session)

    @mock.patch("%s.LOG.exception" % PATH)
    @mock.patch("%s.logging.is_debug" % PATH)
    def test_auth_ref_fails_debug(self, mock_is_debug, mock_log_exception):
        mock_is_debug.return_value = True
        keystone = osclients.Keystone(self.credential, {})
        session = mock.Mock()
        auth_plugin = mock.Mock()
        auth_plugin.get_access.side_effect = Exception
        keystone.get_session = mock.Mock(return_value=(session, auth_plugin))

        self.assertRaises(osclients.AuthenticationFailed,
                          lambda: keystone.auth_ref)

        mock_log_exception.assert_called_once_with(mock.ANY)
        mock_is_debug.assert_called_once_with()
        auth_plugin.get_access.assert_called_once_with(session)

    @mock.patch("%s.LOG.exception" % PATH)
    @mock.patch("%s.logging.is_debug" % PATH)
    def test_auth_ref_fails_debug_with_native_keystone_error(
            self, mock_is_debug, mock_log_exception):
        from keystoneauth1 import exceptions as ks_exc

        mock_is_debug.return_value = True
        keystone = osclients.Keystone(self.credential, {})
        session = mock.Mock()
        auth_plugin = mock.Mock()
        auth_plugin.get_access.side_effect = ks_exc.ConnectFailure("foo")
        keystone.get_session = mock.Mock(return_value=(session, auth_plugin))

        self.assertRaises(osclients.AuthenticationFailed,
                          lambda: keystone.auth_ref)

        self.assertFalse(mock_log_exception.called)
        mock_is_debug.assert_called_once_with()
        auth_plugin.get_access.assert_called_once_with(session)

    def test_authentication_failed_exception(self):
        from keystoneauth1 import exceptions as ks_exc

        original_e = KeyError("Oops")
        e = osclients.AuthenticationFailed(
            url="https://example.com", username="foo", project="project",
            error=original_e
        )
        self.assertEqual(
            "Failed to authenticate to https://example.com for user 'foo' in "
            "project 'project': [KeyError] 'Oops'",
            e.format_message())

        original_e = ks_exc.Unauthorized("The request you have made requires "
                                         "authentication.", request_id="ID")
        e = osclients.AuthenticationFailed(
            url="https://example.com", username="foo", project="project",
            error=original_e
        )
        self.assertEqual(
            "Failed to authenticate to https://example.com for user 'foo' in "
            "project 'project': The request you have made requires "
            "authentication.",
            e.format_message())

        original_e = ks_exc.ConnectionError("Some user-friendly native error")
        e = osclients.AuthenticationFailed(
            url="https://example.com", username="foo", project="project",
            error=original_e
        )
        self.assertEqual("Some user-friendly native error",
                         e.format_message())

        original_e = ks_exc.ConnectionError(
            "Unable to establish connection to https://example.com:500: "
            "HTTPSConnectionPool(host='example.com', port=500): Max retries "
            "exceeded with url: / (Caused by NewConnectionError('<urllib3."
            "connection.VerifiedHTTPSConnection object at 0x7fb87a48e510>: "
            "Failed to establish a new connection: [Errno 101] Network "
            "is unreachable")
        e = osclients.AuthenticationFailed(
            url="https://example.com", username="foo", project="project",
            error=original_e
        )
        self.assertEqual(
            "Unable to establish connection to https://example.com:500",
            e.format_message())

        original_e = ks_exc.ConnectionError(
            "Unable to establish connection to https://example.com:500: "
            # another pool class
            "HTTPConnectionPool(host='example.com', port=500): Max retries "
            "exceeded with url: / (Caused by NewConnectionError('<urllib3."
            "connection.VerifiedHTTPSConnection object at 0x7fb87a48e510>: "
            "Failed to establish a new connection: [Errno 101] Network "
            "is unreachable")
        e = osclients.AuthenticationFailed(
            url="https://example.com", username="foo", project="project",
            error=original_e
        )
        self.assertEqual(
            "Unable to establish connection to https://example.com:500",
            e.format_message())


@ddt.ddt
class OSClientsTestCase(test.TestCase):

    def setUp(self):
        super(OSClientsTestCase, self).setUp()
        self.credential = oscredential.OpenStackCredential(
            "http://auth_url/v2.0", "user", "pass", "tenant")
        self.clients = osclients.Clients(self.credential, {})

        self.fake_keystone = fakes.FakeKeystoneClient()

        keystone_patcher = mock.patch(
            "%s.Keystone.create_client" % PATH,
            return_value=self.fake_keystone)
        self.mock_create_keystone_client = keystone_patcher.start()

        self.auth_ref_patcher = mock.patch("%s.Keystone.auth_ref" % PATH)
        self.auth_ref = self.auth_ref_patcher.start()

        self.service_catalog = self.auth_ref.service_catalog
        self.service_catalog.url_for = mock.MagicMock()

    def test_create_from_env(self):
        with mock.patch.dict("os.environ",
                             {"OS_AUTH_URL": "foo_auth_url",
                              "OS_USERNAME": "foo_username",
                              "OS_PASSWORD": "foo_password",
                              "OS_TENANT_NAME": "foo_tenant_name",
                              "OS_REGION_NAME": "foo_region_name"}):
            clients = osclients.Clients.create_from_env()

        self.assertEqual("foo_auth_url", clients.credential.auth_url)
        self.assertEqual("foo_username", clients.credential.username)
        self.assertEqual("foo_password", clients.credential.password)
        self.assertEqual("foo_tenant_name", clients.credential.tenant_name)
        self.assertEqual("foo_region_name", clients.credential.region_name)

    def test_keystone(self):
        self.assertNotIn("keystone", self.clients.cache)
        client = self.clients.keystone()
        self.assertEqual(self.fake_keystone, client)
        credential = {"timeout": cfg.CONF.openstack_client_http_timeout,
                      "insecure": False, "cacert": None}
        kwargs = self.credential.to_dict()
        kwargs.update(credential)
        self.mock_create_keystone_client.assert_called_once_with()
        self.assertEqual(self.fake_keystone, self.clients.cache["keystone"])

    def test_keystone_versions(self):
        self.clients.keystone.validate_version(2)
        self.clients.keystone.validate_version(3)

    def test_keysonte_service_type(self):
        self.assertRaises(exceptions.RallyException,
                          self.clients.keystone.is_service_type_configurable)

    def test_verified_keystone(self):
        self.auth_ref.role_names = ["admin"]
        self.assertEqual(self.mock_create_keystone_client.return_value,
                         self.clients.verified_keystone())

    def test_verified_keystone_user_not_admin(self):
        self.auth_ref.role_names = ["notadmin"]
        self.assertRaises(exceptions.InvalidAdminException,
                          self.clients.verified_keystone)

    @mock.patch("%s.Keystone.get_session" % PATH)
    def test_verified_keystone_authentication_fails(self,
                                                    mock_keystone_get_session):
        self.auth_ref_patcher.stop()
        mock_keystone_get_session.side_effect = (
            exceptions.AuthenticationFailed(
                username=self.credential.username,
                project=self.credential.tenant_name,
                url=self.credential.auth_url,
                etype=KeyError,
                error="oops")
        )
        self.assertRaises(exceptions.AuthenticationFailed,
                          self.clients.verified_keystone)

    @mock.patch("%s.Nova._get_endpoint" % PATH)
    def test_nova(self, mock_nova__get_endpoint):
        fake_nova = fakes.FakeNovaClient()
        mock_nova__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_nova = mock.MagicMock()
        mock_nova.client.Client.return_value = fake_nova
        mock_keystoneauth1 = mock.MagicMock()
        self.assertNotIn("nova", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"novaclient": mock_nova,
                              "keystoneauth1": mock_keystoneauth1}):
            mock_keystoneauth1.discover.Discover.return_value = (
                mock.Mock(version_data=mock.Mock(return_value=[
                    {"version": (2, 0)}]))
            )
            client = self.clients.nova()
            self.assertEqual(fake_nova, client)
            kw = {
                "version": "2",
                "session": mock_keystoneauth1.session.Session(),
                "endpoint_override": mock_nova__get_endpoint.return_value}
            mock_nova.client.Client.assert_called_once_with(**kw)
            self.assertEqual(fake_nova, self.clients.cache["nova"])

    def test_nova_validate_version(self):
        osclients.Nova.validate_version("2")
        self.assertRaises(exceptions.RallyException,
                          osclients.Nova.validate_version, "foo")

    def test_nova_service_type(self):
        self.clients.nova.is_service_type_configurable()

    @mock.patch("%s.Neutron._get_endpoint" % PATH)
    def test_neutron(self, mock_neutron__get_endpoint):
        fake_neutron = fakes.FakeNeutronClient()
        mock_neutron__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_neutron = mock.MagicMock()
        mock_keystoneauth1 = mock.MagicMock()
        mock_neutron.client.Client.return_value = fake_neutron
        self.assertNotIn("neutron", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"neutronclient.neutron": mock_neutron,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.neutron()
            self.assertEqual(fake_neutron, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint_override": mock_neutron__get_endpoint.return_value}
            mock_neutron.client.Client.assert_called_once_with("2.0", **kw)
            self.assertEqual(fake_neutron, self.clients.cache["neutron"])

    @mock.patch("%s.Neutron._get_endpoint" % PATH)
    def test_neutron_endpoint_type(self, mock_neutron__get_endpoint):
        fake_neutron = fakes.FakeNeutronClient()
        mock_neutron__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_neutron = mock.MagicMock()
        mock_keystoneauth1 = mock.MagicMock()
        mock_neutron.client.Client.return_value = fake_neutron
        self.assertNotIn("neutron", self.clients.cache)
        self.credential["endpoint_type"] = "internal"
        with mock.patch.dict("sys.modules",
                             {"neutronclient.neutron": mock_neutron,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.neutron()
            self.assertEqual(fake_neutron, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint_override": mock_neutron__get_endpoint.return_value,
                "endpoint_type": "internal"}
            mock_neutron.client.Client.assert_called_once_with("2.0", **kw)
            self.assertEqual(fake_neutron, self.clients.cache["neutron"])

    @mock.patch("%s.Octavia._get_endpoint" % PATH)
    def test_octavia(self, mock_octavia__get_endpoint):
        fake_octavia = fakes.FakeOctaviaClient()
        mock_octavia__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_octavia = mock.MagicMock()
        mock_keystoneauth1 = mock.MagicMock()
        mock_octavia.octavia.OctaviaAPI.return_value = fake_octavia
        self.assertNotIn("octavia", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"octaviaclient.api.v2": mock_octavia,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.octavia()
            self.assertEqual(fake_octavia, client)
            kw = {"endpoint": mock_octavia__get_endpoint.return_value,
                  "session": mock_keystoneauth1.session.Session()}
            mock_octavia.octavia.OctaviaAPI.assert_called_once_with(**kw)
            self.assertEqual(fake_octavia, self.clients.cache["octavia"])

    @mock.patch("%s.Heat._get_endpoint" % PATH)
    def test_heat(self, mock_heat__get_endpoint):
        fake_heat = fakes.FakeHeatClient()
        mock_heat__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_heat = mock.MagicMock()
        mock_keystoneauth1 = mock.MagicMock()
        mock_heat.client.Client.return_value = fake_heat
        self.assertNotIn("heat", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"heatclient": mock_heat,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.heat()
            self.assertEqual(fake_heat, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint_override": mock_heat__get_endpoint.return_value}
            mock_heat.client.Client.assert_called_once_with("1", **kw)
        self.assertEqual(fake_heat, self.clients.cache["heat"])

    @mock.patch("%s.Heat._get_endpoint" % PATH)
    def test_heat_endpoint_type_interface(self, mock_heat__get_endpoint):
        fake_heat = fakes.FakeHeatClient()
        mock_heat__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_heat = mock.MagicMock()
        mock_keystoneauth1 = mock.MagicMock()
        mock_heat.client.Client.return_value = fake_heat
        self.assertNotIn("heat", self.clients.cache)
        self.credential["endpoint_type"] = "internal"
        with mock.patch.dict("sys.modules",
                             {"heatclient": mock_heat,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.heat()
            self.assertEqual(fake_heat, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint_override": mock_heat__get_endpoint.return_value,
                "interface": "internal"}
            mock_heat.client.Client.assert_called_once_with("1", **kw)
        self.assertEqual(fake_heat, self.clients.cache["heat"])

    @mock.patch("%s.Glance._get_endpoint" % PATH)
    def test_glance(self, mock_glance__get_endpoint):
        fake_glance = fakes.FakeGlanceClient()
        mock_glance = mock.MagicMock()
        mock_glance__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()
        mock_glance.Client = mock.MagicMock(return_value=fake_glance)
        with mock.patch.dict("sys.modules",
                             {"glanceclient": mock_glance,
                              "keystoneauth1": mock_keystoneauth1}):
            self.assertNotIn("glance", self.clients.cache)
            client = self.clients.glance()
            self.assertEqual(fake_glance, client)
            kw = {
                "version": "2",
                "session": mock_keystoneauth1.session.Session(),
                "endpoint_override": mock_glance__get_endpoint.return_value}
            mock_glance.Client.assert_called_once_with(**kw)
            self.assertEqual(fake_glance, self.clients.cache["glance"])

    @mock.patch("%s.Cinder._get_endpoint" % PATH)
    def test_cinder(self, mock_cinder__get_endpoint):
        fake_cinder = mock.MagicMock(client=fakes.FakeCinderClient())
        mock_cinder = mock.MagicMock()
        mock_cinder.client.Client.return_value = fake_cinder
        mock_cinder__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()
        self.assertNotIn("cinder", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"cinderclient": mock_cinder,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.cinder()
            self.assertEqual(fake_cinder, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint_override": mock_cinder__get_endpoint.return_value}
            mock_cinder.client.Client.assert_called_once_with(
                "3", **kw)
            self.assertEqual(fake_cinder, self.clients.cache["cinder"])

    def test_cinder_validate_version(self):
        osclients.Cinder.validate_version("2")
        osclients.Cinder.validate_version("3")
        osclients.Cinder.validate_version("3.0")
        osclients.Cinder.validate_version("3.10")
        self.assertRaises(exceptions.RallyException,
                          osclients.Cinder.validate_version, "foo")
        self.assertRaises(exceptions.RallyException,
                          osclients.Cinder.validate_version, "3.1000")

    @mock.patch("%s.Manila._get_endpoint" % PATH)
    def test_manila(self, mock_manila__get_endpoint):
        mock_manila = mock.MagicMock()
        mock_manila__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()
        self.assertNotIn("manila", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"manilaclient": mock_manila,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.manila()
            self.assertEqual(mock_manila.client.Client.return_value, client)
            kw = {
                "insecure": False,
                "session": mock_keystoneauth1.session.Session(),
                "service_catalog_url": mock_manila__get_endpoint.return_value
            }
            mock_manila.client.Client.assert_called_once_with("1", **kw)
            self.assertEqual(
                mock_manila.client.Client.return_value,
                self.clients.cache["manila"])

    def test_manila_validate_version(self):
        osclients.Manila.validate_version("2.0")
        osclients.Manila.validate_version("2.32")
        self.assertRaises(exceptions.RallyException,
                          osclients.Manila.validate_version, "foo")

    def test_gnocchi(self):
        fake_gnocchi = fakes.FakeGnocchiClient()
        mock_gnocchi = mock.MagicMock()
        mock_gnocchi.client.Client.return_value = fake_gnocchi
        mock_keystoneauth1 = mock.MagicMock()
        self.assertNotIn("gnocchi", self.clients.cache)
        self.credential["endpoint_type"] = "internal"
        with mock.patch.dict("sys.modules",
                             {"gnocchiclient": mock_gnocchi,
                              "keystoneauth1": mock_keystoneauth1}):
            mock_keystoneauth1.discover.Discover.return_value = (
                mock.Mock(version_data=mock.Mock(return_value=[
                    {"version": (1, 0)}]))
            )
            client = self.clients.gnocchi()

            self.assertEqual(fake_gnocchi, client)
            kw = {"version": "1",
                  "session": mock_keystoneauth1.session.Session(),
                  "adapter_options": {"service_type": "metric",
                                      "interface": "internal"}}
            mock_gnocchi.client.Client.assert_called_once_with(**kw)
            self.assertEqual(fake_gnocchi, self.clients.cache["gnocchi"])

    @mock.patch("%s.Ironic._get_endpoint" % PATH)
    def test_ironic(self, mock_ironic__get_endpoint):
        fake_ironic = fakes.FakeIronicClient()
        mock_ironic = mock.MagicMock()
        mock_ironic.client.get_client = mock.MagicMock(
            return_value=fake_ironic)
        mock_ironic__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()
        self.assertNotIn("ironic", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"ironicclient": mock_ironic,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.ironic()
            self.assertEqual(fake_ironic, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint": mock_ironic__get_endpoint.return_value}
            mock_ironic.client.get_client.assert_called_once_with("1", **kw)
            self.assertEqual(fake_ironic, self.clients.cache["ironic"])

    def test_zaqar(self):
        fake_zaqar = fakes.FakeZaqarClient()
        mock_zaqar = mock.MagicMock()
        mock_zaqar.client.Client = mock.MagicMock(return_value=fake_zaqar)
        self.assertNotIn("zaqar", self.clients.cache)
        mock_keystoneauth1 = mock.MagicMock()
        with mock.patch.dict("sys.modules", {"zaqarclient.queues":
                                             mock_zaqar,
                                             "keystoneauth1":
                                             mock_keystoneauth1}):
            client = self.clients.zaqar()
            self.assertEqual(fake_zaqar, client)
            self.service_catalog.url_for.assert_called_once_with(
                service_type="messaging",
                region_name=self.credential.region_name)
            fake_zaqar_url = self.service_catalog.url_for.return_value
            mock_zaqar.client.Client.assert_called_once_with(
                url=fake_zaqar_url, version=2,
                session=mock_keystoneauth1.session.Session())
            self.assertEqual(fake_zaqar, self.clients.cache["zaqar"],
                             mock_keystoneauth1.session.Session())

    @mock.patch("%s.Trove._get_endpoint" % PATH)
    def test_trove(self, mock_trove__get_endpoint):
        fake_trove = fakes.FakeTroveClient()
        mock_trove = mock.MagicMock()
        mock_trove.client.Client = mock.MagicMock(return_value=fake_trove)
        mock_trove__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()
        self.assertNotIn("trove", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"troveclient": mock_trove,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.trove()
            self.assertEqual(fake_trove, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint": mock_trove__get_endpoint.return_value}
            mock_trove.client.Client.assert_called_once_with("1.0", **kw)
            self.assertEqual(fake_trove, self.clients.cache["trove"])

    def test_mistral(self):
        fake_mistral = fakes.FakeMistralClient()
        mock_mistral = mock.Mock()
        mock_mistral.client.client.return_value = fake_mistral

        self.assertNotIn("mistral", self.clients.cache)
        with mock.patch.dict(
                "sys.modules", {"mistralclient": mock_mistral,
                                "mistralclient.api": mock_mistral}):
            client = self.clients.mistral()
            self.assertEqual(fake_mistral, client)
            self.service_catalog.url_for.assert_called_once_with(
                service_type="workflowv2",
                region_name=self.credential.region_name
            )
            fake_mistral_url = self.service_catalog.url_for.return_value
            mock_mistral.client.client.assert_called_once_with(
                mistral_url=fake_mistral_url,
                service_type="workflowv2",
                auth_token=self.auth_ref.auth_token
            )
            self.assertEqual(fake_mistral, self.clients.cache["mistral"])

    def test_swift(self):
        fake_swift = fakes.FakeSwiftClient()
        mock_swift = mock.MagicMock()
        mock_swift.client.Connection = mock.MagicMock(return_value=fake_swift)
        self.assertNotIn("swift", self.clients.cache)
        with mock.patch.dict("sys.modules", {"swiftclient": mock_swift}):
            client = self.clients.swift()
            self.assertEqual(fake_swift, client)
            self.service_catalog.url_for.assert_called_once_with(
                service_type="object-store",
                region_name=self.credential.region_name)
            kw = {"retries": 1,
                  "preauthurl": self.service_catalog.url_for.return_value,
                  "preauthtoken": self.auth_ref.auth_token,
                  "insecure": False,
                  "cacert": None,
                  "user": self.credential.username,
                  "tenant_name": self.credential.tenant_name,
                  }
            mock_swift.client.Connection.assert_called_once_with(**kw)
            self.assertEqual(fake_swift, self.clients.cache["swift"])

    @mock.patch("%s.Keystone.service_catalog" % PATH)
    def test_services(self, mock_keystone_service_catalog):
        available_services = {consts.ServiceType.IDENTITY: {},
                              consts.ServiceType.COMPUTE: {},
                              "some_service": {}}
        mock_get_endpoints = mock_keystone_service_catalog.get_endpoints
        mock_get_endpoints.return_value = available_services
        clients = osclients.Clients(self.credential)

        self.assertEqual(
            {consts.ServiceType.IDENTITY: consts.Service.KEYSTONE,
             consts.ServiceType.COMPUTE: consts.Service.NOVA,
             "some_service": "__unknown__"},
            clients.services())

    @mock.patch("%s.Keystone.get_session" % PATH)
    @ddt.data(
        {},
        {"version": "2"},
        {"version": None}
    )
    @ddt.unpack
    def test_designate(self, mock_keystone_get_session, version=None):
        fake_designate = fakes.FakeDesignateClient()
        mock_designate = mock.Mock()
        mock_designate.client.Client.return_value = fake_designate

        mock_keystone_get_session.return_value = ("fake_session",
                                                  "fake_auth_plugin")

        self.assertNotIn("designate", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"designateclient": mock_designate}):
            if version is not None:
                client = self.clients.designate(version=version)
            else:
                client = self.clients.designate()
            self.assertEqual(fake_designate, client)
            self.service_catalog.url_for.assert_called_once_with(
                service_type="dns",
                region_name=self.credential.region_name
            )

            default = version or "2"

            # Check that we append /v<version>
            url = self.service_catalog.url_for.return_value
            url.__iadd__.assert_called_once_with("/v%s" % default)

            mock_keystone_get_session.assert_called_once_with()

            mock_designate.client.Client.assert_called_once_with(
                default,
                endpoint_override=url.__iadd__.return_value,
                session="fake_session")

            key = "designate"
            if version is not None:
                key += "%s" % {"version": version}
            self.assertEqual(fake_designate, self.clients.cache[key])

    @mock.patch("%s.Magnum._get_endpoint" % PATH)
    def test_magnum(self, mock_magnum__get_endpoint):
        fake_magnum = fakes.FakeMagnumClient()
        mock_magnum = mock.MagicMock()
        mock_magnum.client.Client.return_value = fake_magnum

        mock_magnum__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()

        self.assertNotIn("magnum", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"magnumclient": mock_magnum,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.magnum()

            self.assertEqual(fake_magnum, client)
            kw = {
                "interface": self.credential.endpoint_type,
                "session": mock_keystoneauth1.session.Session(),
                "magnum_url": mock_magnum__get_endpoint.return_value}

            mock_magnum.client.Client.assert_called_once_with(**kw)
            self.assertEqual(fake_magnum, self.clients.cache["magnum"])

    @mock.patch("%s.Watcher._get_endpoint" % PATH)
    def test_watcher(self, mock_watcher__get_endpoint):
        fake_watcher = fakes.FakeWatcherClient()
        mock_watcher = mock.MagicMock()
        mock_watcher__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()
        mock_watcher.client.Client.return_value = fake_watcher
        self.assertNotIn("watcher", self.clients.cache)
        with mock.patch.dict("sys.modules",
                             {"watcherclient": mock_watcher,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.watcher()

            self.assertEqual(fake_watcher, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "endpoint": mock_watcher__get_endpoint.return_value}

            mock_watcher.client.Client.assert_called_once_with("1", **kw)
            self.assertEqual(fake_watcher, self.clients.cache["watcher"])

    @mock.patch("%s.Barbican._get_endpoint" % PATH)
    def test_barbican(self, mock_barbican__get_endpoint):
        fake_barbican = fakes.FakeBarbicanClient()
        mock_barbican = mock.MagicMock()
        mock_barbican__get_endpoint.return_value = "http://fake.to:2/fake"
        mock_keystoneauth1 = mock.MagicMock()
        mock_barbican.client.Client.return_value = fake_barbican
        with mock.patch.dict("sys.modules",
                             {"barbicanclient": mock_barbican,
                              "keystoneauth1": mock_keystoneauth1}):
            client = self.clients.barbican()

            self.assertEqual(fake_barbican, client)
            kw = {
                "session": mock_keystoneauth1.session.Session(),
                "version": "v1"
            }
            mock_barbican.client.Client.assert_called_once_with(**kw)
            self.assertEqual(fake_barbican, self.clients.cache["barbican"])


class AuthenticationFailedTestCase(test.TestCase):
    def test_init(self):
        from keystoneauth1 import exceptions as ks_exc

        actual_exc = ks_exc.ConnectionError("Something")
        exc = osclients.AuthenticationFailed(
            error=actual_exc, url="https://example.com", username="user",
            project="project")
        # only original exc should be used
        self.assertEqual("Something", exc.format_message())

        actual_exc = Exception("Something")
        exc = osclients.AuthenticationFailed(
            error=actual_exc, url="https://example.com", username="user",
            project="project")
        # additional info should be added
        self.assertEqual("Failed to authenticate to https://example.com for "
                         "user 'user' in project 'project': "
                         "[Exception] Something", exc.format_message())

        # check cutting message
        actual_exc = ks_exc.DiscoveryFailure(
            "Could not find versioned identity endpoints when attempting to "
            "authenticate. Please check that your auth_url is correct. "
            "Unable to establish connection to https://example.com: "
            "HTTPConnectionPool(host='example.com', port=80): Max retries "
            "exceeded with url: / (Caused by NewConnectionError('"
            "<urllib3.connection.HTTPConnection object at 0x7f32ab9809d0>: "
            "Failed to establish a new connection: [Errno -2] Name or service"
            " not known',))")
        exc = osclients.AuthenticationFailed(
            error=actual_exc, url="https://example.com", username="user",
            project="project")
        # original message should be simplified
        self.assertEqual(
            "Could not find versioned identity endpoints when attempting to "
            "authenticate. Please check that your auth_url is correct. "
            "Unable to establish connection to https://example.com",
            exc.format_message())
