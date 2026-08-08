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
from rally.common import utils
from rally.task import context

from rally_openstack.common import osclients
from rally_openstack.task.contexts import api_versions
from tests.unit import test


class _PortedClient:
    spec = mock.Mock()


_PortedClient.spec.sdk_service_type = "compute"


class _TypelessClient:
    spec = mock.Mock()


_TypelessClient.spec.sdk_service_type = None


@ddt.ddt
class OpenStackServicesTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.mock_clients = mock.patch(
            "rally_openstack.common.osclients.Clients").start()
        osclient_kc = self.mock_clients.return_value.keystone
        self.mock_kc = osclient_kc
        self.service_catalog = osclient_kc.service_catalog
        self.service_catalog.get_endpoints.return_value = []
        self.mock_kc.list_services.return_value = []

    @ddt.data(({"nova": {"service_type": "compute", "version": 2},
                "cinder": {"service_name": "cinderv2", "version": 2},
                "neutron": {"service_type": "network"},
                "glance": {"service_name": "glance"},
                "heat": {"version": 1}}, True),
              ({"nova": {"service_type": "compute",
                         "service_name": "nova"}}, False),
              ({"keystone": {"service_type": "foo"}}, False),
              ({"nova": {"version": "foo"}}, False),
              ({}, False))
    @ddt.unpack
    def test_validate(self, config, valid):
        results = context.Context.validate("api_versions", None, None, config)
        if valid:
            self.assertEqual([], results)
        else:
            self.assertGreater(len(results), 0)

    def test_setup_with_wrong_service_name(self):
        context_obj = {
            "config": {api_versions.OpenStackAPIVersions.get_fullname(): {
                "nova": {"service_name": "service_name"}}},
            "admin": {"credential": mock.MagicMock()},
            "users": [{"credential": mock.MagicMock()}]}
        ctx = api_versions.OpenStackAPIVersions(context_obj)
        self.assertRaises(exceptions.ValidationError, ctx.setup)
        self.service_catalog.get_endpoints.assert_called_once_with()
        self.mock_kc.list_services.assert_called_once_with()

    def test_setup_with_wrong_service_name_and_without_admin(self):
        context_obj = {
            "config": {api_versions.OpenStackAPIVersions.get_fullname(): {
                "nova": {"service_name": "service_name"}}},
            "users": [{"credential": mock.MagicMock()}]}
        ctx = api_versions.OpenStackAPIVersions(context_obj)
        self.assertRaises(exceptions.ContextSetupFailure, ctx.setup)
        self.service_catalog.get_endpoints.assert_called_once_with()
        self.assertFalse(self.mock_kc.list_services.called)

    def test_setup_with_wrong_service_type(self):
        context_obj = {
            "config": {api_versions.OpenStackAPIVersions.get_fullname(): {
                "nova": {"service_type": "service_type"}}},
            "users": [{"credential": mock.MagicMock()}]}
        ctx = api_versions.OpenStackAPIVersions(context_obj)
        self.assertRaises(exceptions.ValidationError, ctx.setup)
        self.service_catalog.get_endpoints.assert_called_once_with()

    def test_setup_with_service_name(self):
        self.mock_kc.list_services.return_value = [
            utils.Struct(type="computev21", name="NovaV21")]
        name = api_versions.OpenStackAPIVersions.get_fullname()
        context = {
            "config": {name: {"nova": {"service_name": "NovaV21"}}},
            "admin": {"credential": mock.MagicMock()},
            "users": [{"credential": mock.MagicMock()}]}
        ctx = api_versions.OpenStackAPIVersions(context)
        ctx.setup()

        self.service_catalog.get_endpoints.assert_called_once_with()
        self.mock_kc.list_services.assert_called_once_with()

        versions = ctx.context["config"]["api_versions@openstack"]
        self.assertEqual(
            "computev21",
            versions["nova"]["service_type"])

    def test_setup_no_admin_and_plain_config(self):
        # config without service_name never needs admin: covers the loop
        # skipping both branches and the "no admin_cred" path.
        self.service_catalog.get_endpoints.return_value = ["compute"]
        name = api_versions.OpenStackAPIVersions.get_fullname()
        user_cred = mock.MagicMock()
        ctx = api_versions.OpenStackAPIVersions({
            "config": {name: {"nova": {"service_type": "compute"},
                              "heat": {"version": 1}}},
            "users": [{"credential": user_cred}]})
        ctx.setup()
        user_cred.__getitem__.return_value.update.assert_called_with(
            ctx.context["config"]["api_versions@openstack"])

    def test_setup_two_service_names_reuse_admin_lookup(self):
        self.mock_kc.list_services.return_value = [
            utils.Struct(type="computev21", name="NovaV21"),
            utils.Struct(type="volumev3", name="CinderV3")]
        name = api_versions.OpenStackAPIVersions.get_fullname()
        ctx = api_versions.OpenStackAPIVersions({
            "config": {name: {"nova": {"service_name": "NovaV21"},
                              "cinder": {"service_name": "CinderV3"}}},
            "admin": {"credential": mock.MagicMock()},
            "users": [{"credential": mock.MagicMock()}]})
        ctx.setup()
        # admin lookup performed exactly once despite two service_name entries
        self.mock_kc.list_services.assert_called_once_with()

    def test_cleanup_is_noop(self):
        name = api_versions.OpenStackAPIVersions.get_fullname()
        ctx = api_versions.OpenStackAPIVersions({
            "config": {name: {"nova": {"version": 2}}},
            "users": [{"credential": mock.MagicMock()}]})
        self.assertIsNone(ctx.cleanup())

    def _prefetch_ctx(self, scenario_name="Foo.bar", with_admin=True):
        name = api_versions.OpenStackAPIVersions.get_fullname()
        self.users = [{"credential": self._cred({"identity": "data"})},
                      {"credential": self._cred()}]
        ctx = {"config": {name: {"nova": {"version": 2}}},
               "users": self.users}
        if scenario_name is not None:
            ctx["scenario_name"] = scenario_name
        if with_admin:
            self.admin_cred = self._cred()
            ctx["admin"] = {"credential": self.admin_cred}
        return api_versions.OpenStackAPIVersions(ctx)

    @staticmethod
    def _cred(discovery_cache=None):
        cred = mock.Mock()
        cred.discovery_cache = (
            {} if discovery_cache is None else discovery_cache)
        return cred

    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_no_scenario_name(self, mock_scenario):
        ctx = self._prefetch_ctx(scenario_name=None)
        ctx._prefetch_discovery()
        self.assertFalse(mock_scenario.get.called)

    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_scenario_not_found(self, mock_scenario):
        mock_scenario.get.side_effect = exceptions.PluginNotFound(
            name="Foo.bar", platform="openstack", base="")
        ctx = self._prefetch_ctx()
        ctx._prefetch_discovery()
        self.assertEqual({}, self.users[1]["credential"].discovery_cache)

    @mock.patch("rally_openstack.task.contexts.api_versions.osclients"
                ".BaseClient")
    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_skips_when_no_ported_services(self, mock_scenario,
                                                    mock_base_client):
        scenario_cls = mock.Mock()
        scenario_cls._meta_get.return_value = [
            ("required_services", (), {"services": ["nova"]})]
        mock_scenario.get.return_value = scenario_cls
        # a legacy OSClient is skipped -> service_types stays empty
        mock_base_client.get.return_value = osclients.OSClient
        ctx = self._prefetch_ctx()
        ctx._prefetch_discovery()
        # returned before building a connection / sharing discovery
        self.assertFalse(self.mock_clients.return_value._conn.called)
        self.assertEqual({}, self.users[1]["credential"].discovery_cache)

    @mock.patch("rally_openstack.task.contexts.api_versions.osclients"
                ".BaseClient")
    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_warms_and_shares_discovery(self, mock_scenario,
                                                 mock_base_client):
        scenario_cls = mock.Mock()
        scenario_cls._meta_get.return_value = [
            ("required_services", (), {"services": "nova"}),
            ("number", (), {})]
        mock_scenario.get.return_value = scenario_cls

        def get(service):
            if service == "nova":
                return _PortedClient
            raise exceptions.PluginNotFound(
                name=service, platform="openstack", base="")
        mock_base_client.get.side_effect = get

        ctx = self._prefetch_ctx()
        ctx._prefetch_discovery()

        # connection built from the first credential and the compute proxy
        # accessed to warm discovery
        self.mock_clients.assert_any_call(self.users[0]["credential"])
        getattr(self.mock_clients.return_value._conn, "compute")
        # first credential's discovery is shared to the rest
        self.assertEqual({"identity": "data"},
                         self.users[1]["credential"].discovery_cache)
        self.assertEqual({"identity": "data"},
                         self.admin_cred.discovery_cache)

    @mock.patch("rally_openstack.task.contexts.api_versions.LOG")
    @mock.patch("rally_openstack.task.contexts.api_versions.osclients"
                ".BaseClient")
    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_swallows_discovery_errors(
        self, mock_scenario, mock_base_client, mock_log
    ):
        scenario_cls = mock.Mock()
        scenario_cls._meta_get.return_value = [
            ("required_services", (), {"services": ["nova"]})]
        mock_scenario.get.return_value = scenario_cls
        mock_base_client.get.return_value = _PortedClient

        class _RaisingConn:
            def __getattr__(self, name):
                raise RuntimeError("boom")

        self.mock_clients.return_value._conn = _RaisingConn()
        ctx = self._prefetch_ctx()
        ctx._prefetch_discovery()
        self.assertTrue(mock_log.debug.called)
        # discovery still shared even when a warm-up fails
        self.assertEqual({"identity": "data"},
                         self.users[1]["credential"].discovery_cache)

    @mock.patch("rally_openstack.task.contexts.api_versions.osclients"
                ".BaseClient")
    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_ignores_unknown_and_typeless(self, mock_scenario,
                                                   mock_base_client):
        scenario_cls = mock.Mock()
        scenario_cls._meta_get.return_value = [
            ("required_services", (),
             {"services": ["unknown", "typeless", "nova"]})]
        mock_scenario.get.return_value = scenario_cls

        def get(service):
            if service == "typeless":
                return _TypelessClient
            if service == "nova":
                return _PortedClient
            raise exceptions.PluginNotFound(
                name=service, platform="openstack", base="")
        mock_base_client.get.side_effect = get

        ctx = self._prefetch_ctx()
        ctx._prefetch_discovery()
        self.assertEqual({"identity": "data"},
                         self.users[1]["credential"].discovery_cache)

    @mock.patch("rally_openstack.task.contexts.api_versions.osclients"
                ".BaseClient")
    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_without_admin(self, mock_scenario, mock_base_client):
        scenario_cls = mock.Mock()
        scenario_cls._meta_get.return_value = [
            ("required_services", (), {"services": ["nova"]})]
        mock_scenario.get.return_value = scenario_cls
        mock_base_client.get.return_value = _PortedClient
        ctx = self._prefetch_ctx(with_admin=False)
        ctx._prefetch_discovery()
        self.assertEqual({"identity": "data"},
                         self.users[1]["credential"].discovery_cache)

    @mock.patch("rally_openstack.task.contexts.api_versions.osclients"
                ".BaseClient")
    @mock.patch("rally_openstack.task.contexts.api_versions.scenario.Scenario")
    def test_prefetch_no_credentials(self, mock_scenario, mock_base_client):
        scenario_cls = mock.Mock()
        scenario_cls._meta_get.return_value = [
            ("required_services", (), {"services": ["nova"]})]
        mock_scenario.get.return_value = scenario_cls
        mock_base_client.get.return_value = _PortedClient
        name = api_versions.OpenStackAPIVersions.get_fullname()
        ctx = api_versions.OpenStackAPIVersions({
            "config": {name: {"nova": {"version": 2}}},
            "scenario_name": "Foo.bar", "users": []})
        ctx._prefetch_discovery()
        self.assertFalse(self.mock_clients.return_value._conn.called)
