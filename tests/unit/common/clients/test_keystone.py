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

import json
from unittest import mock

import ddt

from rally import exceptions

from rally_openstack.common import credential as oscredential
from rally_openstack.common.clients import keystone
from tests.unit import test


PATH = "rally_openstack.common.clients.keystone"


class _FakeResourceNotFoundError(Exception):
    """Stand-in for openstack.exceptions.ResourceNotFound.

    The real one cannot be imported in tests: importing ``openstack`` triggers
    a DeprecationWarning that the suite escalates to an error. The keystone
    client imports it lazily, so we inject a fake ``openstack`` module instead.
    """


def _patch_sdk_exceptions():
    fake_openstack = mock.MagicMock()
    fake_openstack.exceptions.ResourceNotFound = _FakeResourceNotFoundError
    return mock.patch.dict("sys.modules", {"openstack": fake_openstack})


class KeystoneTestMixin:

    def setUp(self):
        super().setUp()
        self.credential = oscredential.OpenStackCredential(
            "http://auth_url/v3", "user", "pass", "tenant")

    def _make_keystone(self, version="3", cache=None, name_generator=True):
        ks = keystone.Keystone(
            self.credential, {} if cache is None else cache)
        ks._clients = mock.Mock()
        if name_generator:
            ks._name_generator = mock.Mock(return_value="random_name")
        # shadow the ``version`` cached_property (a non-data descriptor)
        ks.version = version
        return ks

    @property
    def proxy(self):
        # the openstacksdk identity proxy is the mocked connection's
        # ``identity``
        return self.ks._clients._conn.identity


@ddt.ddt
class KeystoneSessionTestCase(KeystoneTestMixin, test.TestCase):

    def _set_up_ksa(self):
        self.ksa = mock.MagicMock()
        patcher = mock.patch.dict("sys.modules", {"keystoneauth1": self.ksa})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_keystone_property_restricted(self):
        ks = keystone.Keystone(self.credential, {})
        self.assertRaises(exceptions.RallyException, lambda: ks.keystone)

    def test_service_catalog(self):
        ks = keystone.Keystone(self.credential, {})
        auth_ref = mock.Mock()
        ks._cache["keystone_auth_ref"] = auth_ref
        self.assertIs(auth_ref.service_catalog, ks.service_catalog)

    def test_auth_ref(self):
        ks = keystone.Keystone(self.credential, {})
        session, plugin = mock.Mock(), mock.Mock()
        ks.get_session = mock.Mock(return_value=(session, plugin))
        self.assertEqual(plugin.get_access.return_value, ks.auth_ref)
        self.assertEqual(plugin.get_access.return_value,
                         ks._cache["keystone_auth_ref"])
        # cached: get_session is only called once
        ks.auth_ref
        ks.get_session.assert_called_once_with()

    @mock.patch("%s.LOG.exception" % PATH)
    @mock.patch("%s.logging.is_debug" % PATH)
    def test_auth_ref_fails(self, mock_is_debug, mock_log_exception):
        mock_is_debug.return_value = False
        ks = keystone.Keystone(self.credential, {})
        plugin = mock.Mock()
        plugin.get_access.side_effect = Exception
        ks.get_session = mock.Mock(return_value=(mock.Mock(), plugin))
        self.assertRaises(keystone.base.AuthenticationFailed,
                          lambda: ks.auth_ref)
        self.assertFalse(mock_log_exception.called)

    @mock.patch("%s.LOG.exception" % PATH)
    @mock.patch("%s.logging.is_debug" % PATH)
    def test_auth_ref_fails_debug(self, mock_is_debug, mock_log_exception):
        mock_is_debug.return_value = True
        ks = keystone.Keystone(self.credential, {})
        plugin = mock.Mock()
        plugin.get_access.side_effect = Exception
        ks.get_session = mock.Mock(return_value=(mock.Mock(), plugin))
        self.assertRaises(keystone.base.AuthenticationFailed,
                          lambda: ks.auth_ref)
        mock_log_exception.assert_called_once_with(mock.ANY)

    @ddt.data("http://auth_url/v2.0", "http://auth_url/v3",
              "http://auth_url/", "auth_url")
    def test_get_session_discovery(self, auth_url):
        self._set_up_ksa()
        cred = oscredential.OpenStackCredential(
            auth_url, "user", "pass", "tenant")
        ks = keystone.Keystone(cred, {})
        self.ksa.discover.Discover.return_value.version_data.return_value = [
            {"version": (1, 0)}]
        password = self.ksa.identity.Password
        session_cls = self.ksa.session.Session
        self.assertEqual((session_cls.return_value, password.return_value),
                         ks.get_session())
        if auth_url.endswith("v2.0"):
            password.assert_called_once_with(
                auth_url=auth_url, password="pass",
                tenant_name="tenant", username="user")
        else:
            password.assert_called_once_with(
                auth_url=auth_url, password="pass",
                tenant_name="tenant", username="user",
                domain_name=None, project_domain_name=None,
                user_domain_name=None)
        self.assertFalse(password.return_value.set_auth_state.called)

    def test_get_session_with_version_skips_discovery(self):
        self._set_up_ksa()
        cred = oscredential.OpenStackCredential(
            "http://auth_url/v3", "u", "p", "t")
        ks = keystone.Keystone(cred, {})
        ks.get_session(version="3")
        self.assertFalse(self.ksa.discover.Discover.called)

    def test_get_session_reuses_auth_state(self):
        self._set_up_ksa()
        cred = oscredential.OpenStackCredential(
            "http://auth_url/v3", "u", "p", "t")
        cred.auth = "auth-state"
        ks = keystone.Keystone(cred, {})
        ks.get_session(version="3")
        self.ksa.identity.Password.return_value.set_auth_state\
            .assert_called_once_with("auth-state")

    def test_get_session_cached(self):
        self._set_up_ksa()
        ks = keystone.Keystone(oscredential.OpenStackCredential(
            "http://auth_url/v3", "u", "p", "t"), {})
        first = ks.get_session(version="3")
        second = ks.get_session(version="3")
        self.assertIs(first, second)
        self.assertEqual(1, self.ksa.session.Session.call_count)

    @ddt.data({"original": "https://example.com/foo/v3",
               "cropped": "https://example.com/foo"},
              {"original": "https://example.com/foo/v2.0/",
               "cropped": "https://example.com/foo"},
              {"original": "https://example.com/foo",
               "cropped": "https://example.com/foo"})
    @ddt.unpack
    def test_remove_url_version(self, original, cropped):
        ks = keystone.Keystone(oscredential.OpenStackCredential(
            original, "u", "p", "t"), {})
        self.assertEqual(cropped, ks._remove_url_version())

    def test_create_client(self):
        ksc = mock.MagicMock(__version__="2.0.0")
        ks = self._make_keystone(version="3")
        auth_plugin = mock.Mock(_user_domain_name=None)
        ks.get_session = mock.Mock(return_value=(mock.Mock(), auth_plugin))
        ks._cache["keystone_auth_ref"] = mock.Mock()
        with mock.patch.dict("sys.modules", {"keystoneclient": ksc}):
            client = ks.create_client(version="3")
        self.assertIs(ksc.client.Client.return_value, client)
        _, kwargs = ksc.client.Client.call_args
        self.assertEqual("3", kwargs["version"])

    def test_create_client_region_and_interface(self):
        ksc = mock.MagicMock(__version__="2.0.0")
        cred = oscredential.OpenStackCredential(
            "http://auth_url/v3", "u", "p", "t",
            region_name="reg", endpoint_type="internal")
        ks = keystone.Keystone(cred, {})
        ks._clients = mock.Mock()
        ks.version = "3"
        ks.get_session = mock.Mock(
            return_value=(mock.Mock(), mock.Mock(_user_domain_name="d")))
        ks._cache["keystone_auth_ref"] = mock.Mock()
        with mock.patch.dict("sys.modules", {"keystoneclient": ksc}):
            ks.create_client(version="3")
        _, kwargs = ksc.client.Client.call_args
        self.assertEqual("reg", kwargs["region_name"])
        self.assertEqual("internal", kwargs["interface"])

    def test_create_client_warns_once(self):
        keystone.Keystone._legacy_deprecation_logged = False
        self.addCleanup(setattr, keystone.Keystone,
                        "_legacy_deprecation_logged", False)
        ksc = mock.MagicMock(__version__="2.0.0")
        ks = self._make_keystone(version="3")
        ks.get_session = mock.Mock(
            return_value=(mock.Mock(), mock.Mock(_user_domain_name=None)))
        ks._cache["keystone_auth_ref"] = mock.Mock()
        with mock.patch.dict("sys.modules", {"keystoneclient": ksc}):
            with mock.patch.object(keystone, "LOG") as mock_log:
                ks.create_client(version="3")
                ks.create_client(version="3")
        mock_log.warning.assert_called_once()

    def test_create_client_v1_keystoneclient(self):
        ksc = mock.MagicMock(__version__="1.0.0")
        ksa = mock.MagicMock()
        ks = self._make_keystone(version="3")
        session = mock.Mock()
        ks.get_session = mock.Mock(
            return_value=(session, mock.Mock(_user_domain_name="d")))
        ks._cache["keystone_auth_ref"] = mock.Mock()
        with mock.patch.dict("sys.modules", {"keystoneclient": ksc,
                                             "keystoneauth1": ksa}):
            ks.create_client(version="3")
        _, kwargs = ksc.client.Client.call_args
        self.assertEqual(session.get_endpoint.return_value, kwargs["auth_url"])


@ddt.ddt
class KeystoneCallTestCase(KeystoneTestMixin, test.TestCase):

    def test_call_legacy_default(self):
        ks = self._make_keystone(version="3")
        ks.create_client = mock.Mock()
        client = ks()
        self.assertIs(ks.create_client.return_value, client)
        # the native client is built once and cached
        self.assertIs(client, ks())
        ks.create_client.assert_called_once_with(None)

    def test_call_non_legacy_returns_self(self):
        ks = self._make_keystone(version="3")
        self.assertIs(ks, ks(legacy=False))
        self.assertIs(ks, ks("3", legacy=False))
        self.assertIs(ks, ks(3, legacy=False))

    def test_call_non_legacy_override(self):
        ks = self._make_keystone(version="3")
        result = ks("2", legacy=False)
        ks._clients.override.assert_called_once_with(keystone="2")
        self.assertIs(ks._clients.override.return_value.keystone, result)

    def test_call_non_legacy_no_clients_raises(self):
        ks = keystone.Keystone(self.credential, {})
        ks.version = "3"
        self.assertRaises(exceptions.RallyException,
                          lambda: ks("2", legacy=False))

    def test_identity_endpoint_override_no_version(self):
        ks = self._make_keystone()
        ks.spec = mock.Mock()
        ks.spec.choose_version.return_value = None
        self.assertEqual(self.credential.auth_url,
                         ks.identity_endpoint_override)

    @ddt.data(("2", "http://auth_url/v2.0"), ("3", "http://auth_url/v3"))
    @ddt.unpack
    def test_identity_endpoint_override_versioned(self, version, expected):
        ks = self._make_keystone()
        ks.spec = mock.Mock()
        ks.spec.choose_version.return_value = version
        self.assertEqual(expected, ks.identity_endpoint_override)


@ddt.ddt
class KeystoneVersionTestCase(KeystoneTestMixin, test.TestCase):

    def test_version(self):
        ks = keystone.Keystone(self.credential, {})
        ks._clients = mock.Mock()
        ks._clients._conn.identity.get_api_major_version.return_value = (3, 0)
        self.assertEqual("3", ks.version)

    def test_version_unknown(self):
        ks = keystone.Keystone(self.credential, {})
        ks._clients = mock.Mock()
        ks._clients._conn.identity.get_api_major_version.return_value = None
        self.assertRaises(exceptions.RallyException, lambda: ks.version)

    def test_identity(self):
        self.ks = self._make_keystone()
        self.assertIs(self.proxy, self.ks._identity)

    def test_v2(self):
        self.ks = self._make_keystone(version="2")
        self.assertIs(self.proxy, self.ks._v2)

    def test_v2_wrong_version(self):
        ks = self._make_keystone(version="3")
        self.assertRaises(exceptions.RallyException, lambda: ks._v2)

    def test_v3(self):
        self.ks = self._make_keystone(version="3")
        self.assertIs(self.proxy, self.ks._v3)

    def test_v3_wrong_version(self):
        ks = self._make_keystone(version="2")
        self.assertRaises(exceptions.RallyException, lambda: ks._v3)

    def test_auth_domain(self):
        self.ks = self._make_keystone()
        ref = self.ks._clients._conn.session.auth.get_auth_ref.return_value
        self.assertEqual((ref.project_domain_name, ref.project_domain_id),
                         self.ks._auth_domain)

    def test_auth_domain_no_auth(self):
        ks = self._make_keystone()
        ks._clients._conn.session.auth = None
        self.assertEqual((None, None), ks._auth_domain)

    def test_auth_domain_no_ref(self):
        ks = self._make_keystone()
        ks._clients._conn.session.auth.get_auth_ref.return_value = None
        self.assertEqual((None, None), ks._auth_domain)

    def _set_auth_domain(self, ks, name, did):
        ref = ks._clients._conn.session.auth.get_auth_ref.return_value
        ref.project_domain_name = name
        ref.project_domain_id = did

    def test_get_domain_id_from_auth(self):
        self.ks = self._make_keystone(version="3")
        self._set_auth_domain(self.ks, "mydomain", "did")
        self.assertEqual("did", self.ks.get_domain_id("mydomain"))
        self.assertFalse(self.proxy.get_domain.called)

    def test_get_domain_id_via_get_domain(self):
        self.ks = self._make_keystone(version="3")
        self._set_auth_domain(self.ks, "other", "otherid")
        self.proxy.get_domain.return_value.id = "found-id"
        with _patch_sdk_exceptions():
            self.assertEqual("found-id", self.ks.get_domain_id("mydomain"))

    def test_get_domain_id_via_domains(self):
        self.ks = self._make_keystone(version="3")
        self._set_auth_domain(self.ks, "other", "otherid")
        self.proxy.get_domain.side_effect = _FakeResourceNotFoundError
        self.proxy.domains.return_value = iter([mock.Mock(id="dom-id")])
        with _patch_sdk_exceptions():
            self.assertEqual("dom-id", self.ks.get_domain_id("mydomain"))

    def test_get_domain_id_not_found(self):
        self.ks = self._make_keystone(version="3")
        self._set_auth_domain(self.ks, "other", "otherid")
        self.proxy.get_domain.side_effect = _FakeResourceNotFoundError
        self.proxy.domains.return_value = iter([])
        with _patch_sdk_exceptions():
            self.assertRaises(exceptions.GetResourceNotFound,
                              self.ks.get_domain_id, "mydomain")


@ddt.ddt
class KeystoneProjectMethodsTestCase(KeystoneTestMixin, test.TestCase):

    def test_create_project_v2(self):
        self.ks = self._make_keystone(version="2")
        result = self.ks.create_project("proj")
        self.assertIs(self.proxy.create_tenant.return_value, result)
        self.proxy.create_tenant.assert_called_once_with(name="proj")

    def test_create_project_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.get_domain_id = mock.Mock(return_value="did")
        result = self.ks.create_project("proj", domain="dom")
        self.assertIs(self.proxy.create_project.return_value, result)
        self.proxy.create_project.assert_called_once_with(
            name="proj", domain_id="did")

    def test_create_project_generates_name(self):
        self.ks = self._make_keystone(version="2")
        self.ks.create_project()
        self.proxy.create_tenant.assert_called_once_with(name="random_name")

    @ddt.data("2", "3")
    def test_update_project(self, version):
        self.ks = self._make_keystone(version=version)
        self.ks.update_project("pid", name="n", enabled=True,
                               description="d")
        target = (self.proxy.update_tenant if version == "2"
                  else self.proxy.update_project)
        target.assert_called_once_with(
            "pid", name="n", is_enabled=True, description="d")

    @ddt.data("2", "3")
    def test_delete_project(self, version):
        self.ks = self._make_keystone(version=version)
        self.ks.delete_project("pid")
        target = (self.proxy.delete_tenant if version == "2"
                  else self.proxy.delete_project)
        target.assert_called_once_with("pid")

    def test_list_projects_v2(self):
        self.ks = self._make_keystone(version="2")
        self.proxy.tenants.return_value = iter(["a", "b"])
        self.assertEqual(["a", "b"], self.ks.list_projects())

    def test_list_projects_v3(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.projects.return_value = iter(["a", "b"])
        self.assertEqual(["a", "b"], self.ks.list_projects())

    def test_get_project_v2(self):
        self.ks = self._make_keystone(version="2")
        self.assertIs(self.proxy.get_tenant.return_value,
                      self.ks.get_project("pid"))

    def test_get_project_v3(self):
        self.ks = self._make_keystone(version="3")
        self.assertIs(self.proxy.get_project.return_value,
                      self.ks.get_project("pid"))

    def test_update_project_no_attrs(self):
        self.ks = self._make_keystone(version="3")
        self.ks.update_project("pid")
        self.proxy.update_project.assert_called_once_with("pid")


@ddt.ddt
class KeystoneUserMethodsTestCase(KeystoneTestMixin, test.TestCase):

    def test_create_user_v2(self):
        self.ks = self._make_keystone(version="2")
        result = self.ks.create_user("u", password="p", project_id="pid")
        self.assertIs(self.proxy.create_user.return_value, result)
        self.proxy.create_user.assert_called_once_with(
            name="u", password="p", tenant_id="pid", is_enabled=True)

    def test_create_user_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.get_domain_id = mock.Mock(return_value="did")
        self.ks.add_role = mock.Mock()
        result = self.ks.create_user("u", password="p", project_id="pid")
        self.assertIs(self.proxy.create_user.return_value, result)
        self.proxy.create_user.assert_called_once_with(
            name="u", password="p", default_project_id="pid",
            domain_id="did", is_enabled=True)
        # granting a role is the caller's job -- it resolves the role once
        # instead of listing every role definition per created user.
        self.assertFalse(self.ks.add_role.called)

    def test_update_user_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.update_user("uid", enabled=False, name="n", email="e",
                            password="p")
        self.proxy.update_user.assert_called_once_with(
            "uid", name="n", email="e", is_enabled=False, password="p")

    def test_update_user_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks.update_user("uid", enabled=False, name="n", password="p")
        self.proxy.update_user.assert_called_once_with(
            "uid", name="n", is_enabled=False)
        self.proxy.put.assert_called_once_with(
            "/users/uid/OS-KSADM/password",
            json={"user": {"password": "p"}})

    def test_update_user_v2_no_password(self):
        self.ks = self._make_keystone(version="2")
        self.ks.update_user("uid", name="n")
        self.assertFalse(self.proxy.put.called)

    def test_update_user_v2_password_only(self):
        self.ks = self._make_keystone(version="2")
        self.ks.update_user("uid", password="p")
        self.assertFalse(self.proxy.update_user.called)
        self.proxy.put.assert_called_once_with(
            "/users/uid/OS-KSADM/password",
            json={"user": {"password": "p"}})

    @ddt.data("2", "3")
    def test_delete_user(self, version):
        self.ks = self._make_keystone(version=version)
        self.ks.delete_user("uid")
        self.proxy.delete_user.assert_called_once_with("uid")

    @ddt.data("2", "3")
    def test_list_users(self, version):
        self.ks = self._make_keystone(version=version)
        self.proxy.users.return_value = iter(["a"])
        self.assertEqual(["a"], self.ks.list_users())

    @ddt.data("2", "3")
    def test_get_user(self, version):
        self.ks = self._make_keystone(version=version)
        self.assertIs(self.proxy.get_user.return_value,
                      self.ks.get_user("uid"))

    def test_update_user_v3_no_attrs(self):
        self.ks = self._make_keystone(version="3")
        self.ks.update_user("uid")
        self.proxy.update_user.assert_called_once_with("uid")


@ddt.ddt
class KeystoneRoleMethodsTestCase(KeystoneTestMixin, test.TestCase):

    def test_create_role_v2(self):
        self.ks = self._make_keystone(version="2")
        result = self.ks.create_role("r")
        self.assertIs(self.proxy.create_role.return_value, result)
        self.proxy.create_role.assert_called_once_with(name="r")

    def test_create_role_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.create_role("r")
        self.proxy.create_role.assert_called_once_with(name="r")

    def test_create_role_v3_with_domain(self):
        self.ks = self._make_keystone(version="3")
        self.ks.get_domain_id = mock.Mock(return_value="did")
        self.ks.create_role("r", domain="dom")
        self.proxy.create_role.assert_called_once_with(
            name="r", domain_id="did")

    def test_add_role_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks.add_role("rid", "uid", "pid")
        self.proxy.put.assert_called_once_with(
            "/tenants/pid/users/uid/roles/OS-KSADM/rid")

    def test_add_role_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.add_role("rid", "uid", "pid")
        self.proxy.assign_project_role_to_user.assert_called_once_with(
            "pid", "uid", "rid")

    def test_revoke_role_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks.revoke_role("rid", "uid", "pid")
        self.proxy.delete.assert_called_once_with(
            "/tenants/pid/users/uid/roles/OS-KSADM/rid")

    def test_revoke_role_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.revoke_role("rid", "uid", "pid")
        self.proxy.unassign_project_role_from_user.assert_called_once_with(
            "pid", "uid", "rid")

    def test_list_roles_v2(self):
        self.ks = self._make_keystone(version="2")
        self.proxy.roles.return_value = iter(["a"])
        self.assertEqual(["a"], self.ks.list_roles())

    def test_list_roles_v3_no_args(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.roles.return_value = iter([])
        self.ks.list_roles()
        self.proxy.roles.assert_called_once_with()

    def test_list_role_assignments_v2_project(self):
        from openstack.identity.v3 import role_project_user_assignment

        self.ks = self._make_keystone(version="2")
        self.proxy.get.return_value.json.return_value = {
            "roles": [{"id": "r1", "name": "admin"}]}
        result = self.ks.list_role_assignments("uid", project_id="pid")
        self.proxy.get.assert_called_once_with(
            "/tenants/pid/users/uid/roles")
        # v2 payloads are adapted to the resource the v3 branch returns
        self.assertIsInstance(
            result[0],
            role_project_user_assignment.RoleProjectUserAssignment)
        self.assertEqual("r1", result[0].id)
        self.assertEqual("admin", result[0].name)
        self.assertEqual("pid", result[0].project_id)
        self.assertEqual("uid", result[0].user_id)

    def test_list_role_assignments_v2_no_project(self):
        self.ks = self._make_keystone(version="2")
        self.proxy.get.return_value.json.return_value = {
            "roles": [{"id": "r1"}]}
        self.ks.list_role_assignments("uid")
        self.proxy.get.assert_called_once_with("/users/uid/roles")

    def test_list_role_assignments_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.get_domain_id = mock.Mock(return_value="did")
        self.proxy.role_assignments_filter.return_value = iter(["a"])
        self.assertEqual(["a"], self.ks.list_role_assignments(
            "uid", project_id="pid", domain="dom"))
        self.proxy.role_assignments_filter.assert_called_once_with(
            user="uid", project="pid", domain="did")

    def test_list_role_assignments_v3_no_domain(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.role_assignments_filter.return_value = iter(["a"])
        self.ks.list_role_assignments("uid", project_id="pid")
        self.proxy.role_assignments_filter.assert_called_once_with(
            user="uid", project="pid", domain=None)

    def test_list_roles_v3_name_filter(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.roles.return_value = iter(["match"])
        self.assertEqual(["match"], self.ks.list_roles(name="admin"))
        self.proxy.roles.assert_called_once_with(name="admin")

    def test_list_roles_v2_name_filter(self):
        self.ks = self._make_keystone(version="2")
        r1 = mock.Mock()
        r1.name = "other"
        r2 = mock.Mock()
        r2.name = "admin"
        self.proxy.roles.return_value = iter([r1, r2])
        self.assertEqual([r2], self.ks.list_roles(name="admin"))

    def test_find_role_exact_match_wins(self):
        self.ks = self._make_keystone(version="3")
        decorated = mock.Mock(id="rid1")
        decorated.name = "_member_"
        exact = mock.Mock(id="rid2")
        exact.name = "Member"
        self.ks.list_roles = mock.Mock(return_value=[decorated, exact])
        self.assertIs(exact, self.ks.find_role("member"))

    def test_find_role_falls_back_to_decorated(self):
        self.ks = self._make_keystone(version="3")
        decorated = mock.Mock(id="rid")
        decorated.name = "_member_"
        self.ks.list_roles = mock.Mock(return_value=[decorated])
        self.assertIs(decorated, self.ks.find_role("member"))

    def test_find_role_not_found(self):
        self.ks = self._make_keystone(version="3")
        role = mock.Mock(id="rid")
        role.name = "admin"
        self.ks.list_roles = mock.Mock(return_value=[role])
        self.assertIsNone(self.ks.find_role("member"))

    @ddt.data("2", "3")
    def test_delete_role(self, version):
        self.ks = self._make_keystone(version=version)
        self.ks.delete_role("rid")
        self.proxy.delete_role.assert_called_once_with("rid")

    @ddt.data("2", "3")
    def test_get_role(self, version):
        self.ks = self._make_keystone(version=version)
        self.assertIs(self.proxy.get_role.return_value,
                      self.ks.get_role("rid"))


@ddt.ddt
class KeystoneServiceMethodsTestCase(KeystoneTestMixin, test.TestCase):

    def test_create_service_v2(self):
        self.ks = self._make_keystone(version="2")
        self.proxy.post.return_value.json.return_value = {
            "OS-KSADM:service": {"id": "sid", "name": "n"}}
        result = self.ks.create_service(name="n", service_type="t",
                                        description="d")
        self.assertEqual("sid", result.id)
        self.proxy.post.assert_called_once_with(
            "/OS-KSADM/services",
            json={"OS-KSADM:service": {"name": "n", "type": "t",
                                       "description": "d"}})

    def test_create_service_v3(self):
        self.ks = self._make_keystone(version="3")
        result = self.ks.create_service(name="n", service_type="t",
                                        description="d")
        self.assertIs(self.proxy.create_service.return_value, result)
        self.proxy.create_service.assert_called_once_with(
            name="n", type="t", description="d", is_enabled=True)

    def test_create_service_defaults(self):
        self.ks = self._make_keystone(version="3")
        self.ks.create_service()
        self.proxy.create_service.assert_called_once_with(
            name="random_name", type="rally_test_type",
            description="random_name", is_enabled=True)

    def test_delete_service_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks.delete_service("sid")
        self.proxy.delete.assert_called_once_with("/OS-KSADM/services/sid")

    def test_delete_service_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.delete_service("sid")
        self.proxy.delete_service.assert_called_once_with("sid")

    def test_list_services_v2(self):
        self.ks = self._make_keystone(version="2")
        self.proxy.get.return_value.json.return_value = {
            "OS-KSADM:services": [{"id": "s1"}]}
        result = self.ks.list_services()
        self.assertEqual("s1", result[0].id)

    def test_list_services_v3(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.services.return_value = iter(["a"])
        self.assertEqual(["a"], self.ks.list_services())

    def test_get_service_v2(self):
        self.ks = self._make_keystone(version="2")
        self.proxy.get.return_value.json.return_value = {
            "OS-KSADM:service": {"id": "sid"}}
        self.assertEqual("sid", self.ks.get_service("sid").id)

    def test_get_service_v3(self):
        self.ks = self._make_keystone(version="3")
        self.assertIs(self.proxy.get_service.return_value,
                      self.ks.get_service("sid"))

    def test_list_services_v3_name_filter(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.services.return_value = iter(["match"])
        self.assertEqual(["match"], self.ks.list_services(name="target"))
        self.proxy.services.assert_called_once_with(name="target")

    def test_list_services_v2_name_filter(self):
        self.ks = self._make_keystone(version="2")
        self.proxy.get.return_value.json.return_value = {
            "OS-KSADM:services": [{"id": "s1", "name": "other"},
                                  {"id": "s2", "name": "target"}]}
        result = self.ks.list_services(name="target")
        self.assertEqual(["s2"], [s.id for s in result])

    def test_create_domain(self):
        self.ks = self._make_keystone(version="3")
        self.ks.create_domain("n", description="d")
        self.proxy.create_domain.assert_called_once_with(
            name="n", description="d", is_enabled=True)

    def test_validate_token_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks.validate_token("tok")
        self.proxy.get.assert_called_once_with("/tokens/tok")

    def test_validate_token_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.validate_token("tok")
        self.proxy.validate_token.assert_called_once_with("tok")


@ddt.ddt
class KeystoneCredentialMethodsTestCase(KeystoneTestMixin, test.TestCase):

    def test_ec2_to_credential(self):
        data = {"access": "acc", "secret": "sec",
                "user_id": "uid", "tenant_id": "tid"}
        fake_v3 = mock.MagicMock()
        with mock.patch.dict("sys.modules",
                             {"openstack.identity.v3": fake_v3}):
            result = keystone.Keystone._ec2_to_credential(data)
        credential_cls = fake_v3.credential.Credential
        self.assertIs(credential_cls.return_value, result)
        credential_cls.assert_called_once_with(
            id="acc", type="ec2", blob=json.dumps(data),
            user_id="uid", project_id="tid")

    def test_create_credential_v3_generic(self):
        self.ks = self._make_keystone(version="3")
        self.ks._cache["keystone_auth_ref"] = mock.Mock(user_id="uid")
        self.ks.create_credential("cert", blob="theblob", project_id="pid")
        self.proxy.create_credential.assert_called_once_with(
            blob="theblob", type="cert", user_id="uid", project_id="pid")

    def test_create_credential_v3_ec2_autoblob(self):
        self.ks = self._make_keystone(version="3")
        self.ks.create_credential("ec2", user_id="uid", project_id="pid")
        _, kwargs = self.proxy.create_credential.call_args
        self.assertEqual("ec2", kwargs["type"])
        blob = json.loads(kwargs["blob"])
        self.assertIn("access", blob)
        self.assertIn("secret", blob)

    def test_create_credential_v2_ec2(self):
        self.ks = self._make_keystone(version="2")
        self.ks._ec2_to_credential = mock.Mock(return_value="CRED")
        raw = {"access": "acc", "user_id": "uid", "tenant_id": "pid"}
        self.proxy.post.return_value.json.return_value = {"credential": raw}
        self.assertEqual("CRED", self.ks.create_credential(
            "ec2", user_id="uid", project_id="pid"))
        self.proxy.post.assert_called_once_with(
            "/users/uid/credentials/OS-EC2", json={"tenant_id": "pid"})
        self.ks._ec2_to_credential.assert_called_once_with(raw)

    def test_create_credential_v2_non_ec2_raises(self):
        self.ks = self._make_keystone(version="2")
        self.ks._cache["keystone_auth_ref"] = mock.Mock(user_id="uid")
        self.assertRaises(exceptions.RallyException,
                          self.ks.create_credential, "cert")

    def test_get_credential_v3(self):
        self.ks = self._make_keystone(version="3")
        self.assertIs(self.proxy.get_credential.return_value,
                      self.ks.get_credential("cid"))

    def test_get_credential_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks._ec2_to_credential = mock.Mock(return_value="CRED")
        self.ks._cache["keystone_auth_ref"] = mock.Mock(user_id="uid")
        self.proxy.get.return_value.json.return_value = {
            "credential": {"access": "acc"}}
        self.assertEqual("CRED", self.ks.get_credential("acc"))
        self.proxy.get.assert_called_once_with(
            "/users/uid/credentials/OS-EC2/acc")

    def test_list_credentials_v3(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.credentials.return_value = iter(["a"])
        self.assertEqual(["a"], self.ks.list_credentials(
            user_id="uid", cred_type="ec2"))
        self.proxy.credentials.assert_called_once_with(
            user_id="uid", type="ec2")

    def test_list_credentials_v3_no_filters(self):
        self.ks = self._make_keystone(version="3")
        self.proxy.credentials.return_value = iter([])
        self.ks.list_credentials()
        self.proxy.credentials.assert_called_once_with()

    def test_list_credentials_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks._ec2_to_credential = mock.Mock(
            side_effect=lambda c: c["access"])
        self.ks._cache["keystone_auth_ref"] = mock.Mock(user_id="uid")
        self.proxy.get.return_value.json.return_value = {
            "credentials": [{"access": "acc"}]}
        self.assertEqual(["acc"], self.ks.list_credentials())
        self.proxy.get.assert_called_once_with(
            "/users/uid/credentials/OS-EC2")

    def test_list_credentials_v2_non_ec2_raises(self):
        self.ks = self._make_keystone(version="2")
        self.assertRaises(exceptions.RallyException,
                          self.ks.list_credentials, cred_type="cert")

    def test_delete_credential_v3(self):
        self.ks = self._make_keystone(version="3")
        self.ks.delete_credential("cid")
        self.proxy.delete_credential.assert_called_once_with("cid")

    def test_delete_credential_v2(self):
        self.ks = self._make_keystone(version="2")
        self.ks._cache["keystone_auth_ref"] = mock.Mock(user_id="uid")
        self.ks.delete_credential("acc")
        self.proxy.delete.assert_called_once_with(
            "/users/uid/credentials/OS-EC2/acc")


class KeystoneFetchTokenTestCase(KeystoneTestMixin, test.TestCase):

    @mock.patch.object(keystone.Keystone, "auth_ref",
                       new_callable=mock.PropertyMock)
    def test_fetch_token(self, mock_keystone_auth_ref):
        mock_keystone_auth_ref.return_value.auth_token = "the-token"
        ks = self._make_keystone(version="3")
        self.assertEqual("the-token", ks.fetch_token())

    @mock.patch.object(keystone.Keystone, "auth_ref",
                       new_callable=mock.PropertyMock)
    def test_fetch_token_none_raises(self, mock_keystone_auth_ref):
        mock_keystone_auth_ref.return_value.auth_token = None
        ks = self._make_keystone(version="3")
        self.assertRaises(exceptions.RallyException, ks.fetch_token)
