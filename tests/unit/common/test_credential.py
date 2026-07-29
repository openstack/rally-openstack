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

from unittest import mock

from rally_openstack.common import credential
from tests.unit import test


class OpenStackCredentialTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.credential = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password",
            tenant_name="foo_tenant")

    def test_to_dict(self):
        self.assertEqual({"auth_url": "foo_url",
                          "username": "foo_user",
                          "password": "foo_password",
                          "tenant_name": "foo_tenant",
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
                          "api_info": {},
                          "auth": None,
                          "discovery_cache": {}},
                         self.credential.to_dict())

    def test_project_name_falls_back_to_tenant_name(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password",
            project_name="foo_project")
        self.assertEqual("foo_project", cred.tenant_name)

    def test_explicit_tenant_name_wins_over_project_name(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password",
            tenant_name="foo_tenant", project_name="foo_project")
        self.assertEqual("foo_tenant", cred.tenant_name)

    def test_https_cert_and_key_are_merged(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password",
            https_cert="foo_cert", https_key="foo_key")
        self.assertEqual(("foo_cert", "foo_key"), cred.https_cert)

    def test_none_api_info_and_discovery_cache_normalized(self):
        cred = credential.OpenStackCredential(
            "foo_url", "foo_user", "foo_password",
            api_info=None, discovery_cache=None)
        self.assertEqual({}, cred.api_info)
        self.assertEqual({}, cred.discovery_cache)

    def test_getitem(self):
        self.assertEqual("foo_url", self.credential["auth_url"])
        self.assertEqual("foo_tenant", self.credential["tenant_name"])

    def test_setitem(self):
        self.credential["region_name"] = "foo_region"
        self.assertEqual("foo_region", self.credential.region_name)

    def test_deepcopy(self):
        import copy
        clone = copy.deepcopy(self.credential)
        self.assertIsNot(clone, self.credential)
        self.assertEqual(self.credential.to_dict(), clone.to_dict())

    @mock.patch("rally_openstack.common.osclients.Clients")
    def test_clients(self, mock_clients):
        clients = self.credential.clients()
        mock_clients.assert_called_once_with(self.credential, cache={})
        self.assertIs(mock_clients.return_value, clients)
