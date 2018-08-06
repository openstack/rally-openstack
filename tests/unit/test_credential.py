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

import mock

from rally_openstack import credential
from tests.unit import test


class OpenStackCredentialTestCase(test.TestCase):

    def setUp(self):
        super(OpenStackCredentialTestCase, self).setUp()
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
                          "api_info": {}},
                         self.credential.to_dict())

    @mock.patch("rally_openstack.osclients.Clients")
    def test_clients(self, mock_clients):
        clients = self.credential.clients(api_info="fake_info")
        mock_clients.assert_called_once_with(
            self.credential, api_info="fake_info", cache={})
        self.assertIs(mock_clients.return_value, clients)
