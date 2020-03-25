# Copyright 2013: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from rally_openstack.task import context
from tests.unit import test


class TenantIteratorTestCase(test.TestCase):

    def test__iterate_per_tenant(self):

        class DummyContext(context.OpenStackContext):
            def __init__(self, ctx):
                self.context = ctx

            def setup(self):
                pass

            def cleanup(self):
                pass

        users = []
        tenants_count = 2
        users_per_tenant = 5
        for tenant_id in range(tenants_count):
            for user_id in range(users_per_tenant):
                users.append({"id": str(user_id),
                              "tenant_id": str(tenant_id)})

        expected_result = [
            ({"id": "0", "tenant_id": str(i)}, str(i)) for i in range(
                tenants_count)]
        real_result = [
            i for i in DummyContext({"users": users})._iterate_per_tenants()]

        self.assertEqual(expected_result, real_result)
