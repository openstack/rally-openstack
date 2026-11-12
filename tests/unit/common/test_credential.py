# Copyright 2017: Mirantis Inc.
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

import copy
from unittest import mock

from rally_openstack.common import credential
from tests.unit import test


class OpenStackCredentialTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.credential = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password", "foo_project")

    def test_to_dict(self):
        self.assertEqual({"auth_url": "foo_url",
                          "username": "foo_user",
                          "password": "foo_password",
                          "project_name": "foo_project",
                          "region_name": None,
                          "domain_name": None,
                          "permission": None,
                          "endpoint": None,
                          "endpoint_type": None,
                          "https_insecure": False,
                          "https_cacert": None,
                          "https_cert": None,
                          "project_domain_name": None,
                          "user_domain_name": None,
                          "profiler_hmac_key": None,
                          "profiler_conn_str": None,
                          "api_info": {}},
                         self.credential.to_dict())

    def test_legacy_tenant_name(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password", tenant_name="foo_tenant")
        self.assertEqual("foo_tenant", cred.project_name)
        self.assertEqual("foo_tenant", cred.tenant_name)
        self.assertEqual("foo_tenant", cred["tenant_name"])
        self.assertNotIn("tenant_name", cred.to_dict())

    def test_project_name_wins_over_tenant_name(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password",
            tenant_name="foo_tenant", project_name="foo_project")
        self.assertEqual("foo_project", cred.project_name)

    def test_project_name_is_required(self):
        self.assertRaises(TypeError, credential.OpenStackCredential,
                          "foo_url", "foo_user", "foo_password")

    def test_https_cert_and_key_are_merged(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password", "foo_project",
            https_cert="foo_cert", https_key="foo_key")
        self.assertEqual(("foo_cert", "foo_key"), cred.https_cert)

    def test_none_api_info_normalized(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password", "foo_project",
            api_info=None)
        self.assertEqual({}, cred.api_info)

    def test_private_state_is_hidden(self):
        self.credential._auth_state = "secret-token"
        self.credential._cloud_state["neutron"] = {"extensions": ["trunk"]}
        self.assertNotIn("secret-token", repr(self.credential))
        self.assertNotIn("_auth_state", self.credential.to_dict())
        self.assertNotIn("_cloud_state", self.credential.to_dict())
        other = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password", "foo_project")
        self.assertEqual(other, self.credential)

    def test_getitem(self):
        self.assertEqual("foo_url", self.credential["auth_url"])
        self.assertEqual("foo_project", self.credential["project_name"])

    def test_setitem(self):
        self.credential["region_name"] = "foo_region"
        self.assertEqual("foo_region", self.credential.region_name)

    def test_deepcopy(self):
        self.credential._auth_state = "auth-state"
        self.credential._cloud_state["neutron"] = {"extensions": ["trunk"]}
        clone = copy.deepcopy(self.credential)
        self.assertIsNot(clone, self.credential)
        self.assertEqual(self.credential.to_dict(), clone.to_dict())
        self.assertEqual("auth-state", clone._auth_state)
        self.assertEqual(self.credential._cloud_state, clone._cloud_state)
        self.assertIsNot(self.credential._cloud_state, clone._cloud_state)

    def test_deepcopy_keeps_cloud_state_shared(self):
        other = credential.OpenStackCredential(
            "foo_url", "bar_user", "bar_password", "bar_project")
        other._cloud_state = self.credential._cloud_state

        ctx = copy.deepcopy({"users": [self.credential, other]})

        first, second = ctx["users"]
        self.assertIs(first._cloud_state, second._cloud_state)
        self.assertIsNot(self.credential._cloud_state, first._cloud_state)

    @mock.patch("rally_openstack.common.osclients.Clients")
    def test_clients(self, mock_clients):
        atomic_inst = []
        name_generator = mock.Mock()
        sleeper = mock.Mock()

        with mock.patch.object(credential.LOG, "warning") as mock_warning:
            clients = self.credential.clients(
                atomic_inst=atomic_inst, name_generator=name_generator,
                sleeper=sleeper)

        mock_clients.assert_called_once_with(
            self.credential, atomic_inst=atomic_inst,
            name_generator=name_generator, sleeper=sleeper)
        self.assertIs(mock_clients.return_value, clients)
        self.assertFalse(mock_warning.called)

    @mock.patch("rally_openstack.common.osclients.Clients")
    def test_clients_with_omitted_args(self, mock_clients):
        with (
            mock.patch.object(
                credential, "_reported_implicit_clients_callers", set()),
            mock.patch.object(credential.LOG, "warning") as mock_warning,
        ):
            for _ in range(2):
                self.credential.clients(atomic_inst=None)
            self.credential.clients()

        self.assertEqual(
            [mock.call(self.credential, atomic_inst=None,
                       name_generator=None, sleeper=None)] * 3,
            mock_clients.call_args_list)
        self.assertEqual(2, mock_warning.call_count)
        first, second = (c.args[0] for c in mock_warning.call_args_list)
        self.assertIn("without name_generator, sleeper is deprecated", first)
        self.assertIn(f"Used at {__file__}:", first)
        self.assertIn(
            "without atomic_inst, name_generator, sleeper is deprecated",
            second)
        self.assertNotEqual(first.rsplit(":", 1)[1],
                            second.rsplit(":", 1)[1])
