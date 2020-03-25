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

import functools

from rally.task import context


configure = functools.partial(context.configure, platform="openstack")


class OpenStackContext(context.Context):
    """A base class for all OpenStack context classes."""

    def _iterate_per_tenants(self, users=None):
        """Iterate of a single arbitrary user from each tenant

        :type users: list of users
        :return: iterator of a single user from each tenant
        """
        if users is None:
            users = self.context.get("users", [])

        processed_tenants = set()
        for user in users:
            if user["tenant_id"] not in processed_tenants:
                processed_tenants.add(user["tenant_id"])
                yield user, user["tenant_id"]
