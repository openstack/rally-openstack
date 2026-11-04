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

from __future__ import annotations

import functools
import typing as t

from rally.common import logging
from rally.task import context


if t.TYPE_CHECKING:
    from rally_openstack.task.contexts.keystone import users as users_ctx


configure = functools.partial(context.configure, platform="openstack")


class OpenStackContext(context.Context):
    """A base class for all OpenStack context classes."""

    def _iterate_per_projects(
        self, users: list[users_ctx.UserInfo] | None = None
    ) -> t.Generator[tuple[users_ctx.UserInfo, str], None, None]:
        """Iterate of a single arbitrary user from each project

        :type users: list of users
        :return: iterator of a single user from each project
        """
        if users is None:
            users = self.context.get("users", [])

        processed_projects = set()
        for user in users:
            if user["tenant_id"] not in processed_projects:
                processed_projects.add(user["tenant_id"])
                yield user, user["tenant_id"]

    @logging.log_deprecated(
        "use '_iterate_per_projects' instead", "4.2.0", once=True)
    def _iterate_per_tenants(
        self, users: list[users_ctx.UserInfo] | None = None
    ) -> t.Generator[tuple[users_ctx.UserInfo, str], None, None]:
        return self._iterate_per_projects(users)
