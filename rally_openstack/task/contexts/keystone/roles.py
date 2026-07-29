# Copyright 2014: Mirantis Inc.
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

from rally import exceptions
from rally.common import broker
from rally.common import cfg
from rally.common import logging
from rally.common import validation

from rally_openstack.common import consts
from rally_openstack.common import osclients
from rally_openstack.task import context


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="roles", platform="openstack", order=330)
class RoleGenerator(context.OpenStackContext):
    """Context class for assigning roles for users."""

    CONFIG_SCHEMA = {
        "type": "array",
        "$schema": consts.JSON_SCHEMA,
        "items": {
            "type": "string",
            "description": "The name of role to assign to user"
        }
    }

    def __init__(self, ctx):
        super().__init__(ctx)
        self.credential = self.context["admin"]["credential"]
        # One identity client for the whole context. setup() authenticates it
        # in the single-threaded publish step before the broker threads run.
        self.keystone = osclients.Clients(self.credential).keystone

    def _find_role(self, context_role: str):
        """Return the role with the given name.

        :param context_role: name of an existing role.
        """
        roles = self.keystone.list_roles(name=context_role)
        if roles:
            return roles[0]
        raise exceptions.NotFoundException(
            f"There is no role with name `{context_role}`")

    def _get_consumer(self, *, revoke: bool):
        def consume(cache, args):
            role_id, user_id, project_id = args
            if revoke:
                self.keystone.revoke_role(
                    role_id=role_id, user_id=user_id, project_id=project_id
                )
            else:
                self.keystone.add_role(
                    role_id=role_id, user_id=user_id, project_id=project_id
                )
        return consume

    def setup(self) -> None:
        """Add all roles to users."""
        threads = cfg.CONF.openstack.roles_context_resource_management_workers
        roles_dict = {}

        def publish(queue):
            for context_role in self.config:
                role = self._find_role(context_role)
                roles_dict[role.id] = role.name
                LOG.debug(
                    f"Adding role {role.name} having ID {role.id} to all "
                    f"users using {threads} threads"
                )
                for user in self.context["users"]:
                    if "roles" not in user:
                        user_roles = self.keystone.list_role_assignments(
                            user["id"], project_id=user["tenant_id"]
                        )
                        user["roles"] = [role.id for role in user_roles]
                        user["assigned_roles"] = []

                    if role.id not in user["roles"]:
                        args = (role.id, user["id"], user["tenant_id"])
                        queue.append(args)
                        user["assigned_roles"].append(role.id)

        broker.run(
            publish,
            self._get_consumer(revoke=False),
            cfg.CONF.openstack.roles_context_resource_management_workers
        )
        self.context["roles"] = roles_dict

    def cleanup(self) -> None:
        """Remove assigned roles from users."""

        def publish(queue):
            for role_id in self.context["roles"]:
                LOG.debug(f"Removing assigned role {role_id} from all users")
                for user in self.context["users"]:
                    if role_id in user["assigned_roles"]:
                        args = (role_id, user["id"], user["tenant_id"])
                        queue.append(args)

        broker.run(
            publish,
            self._get_consumer(revoke=True),
            cfg.CONF.openstack.roles_context_resource_management_workers
        )
