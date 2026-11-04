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

from rally_openstack.task.contexts import api_versions
from tests.unit import test


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
