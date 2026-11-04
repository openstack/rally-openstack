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

from __future__ import annotations

import collections
import copy
import typing as t
import uuid

from rally import exceptions
from rally.common import broker
from rally.common import cfg
from rally.common import logging
from rally.common import utils
from rally.common import validation
from rally.common.plugin import plugin

from rally_openstack.common import consts
from rally_openstack.common import credential
from rally_openstack.common import osclients
from rally_openstack.common.clients import neutron as neutron_client
from rally_openstack.task import context


if t.TYPE_CHECKING:
    from rally_openstack.common.clients import keystone


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

RESOURCE_MANAGEMENT_WORKERS_DESCR = (
    "The number of concurrent threads to use for serving users context.")
PROJECT_DOMAIN_DESCR = "ID of domain in which projects will be created."
USER_DOMAIN_DESCR = "ID of domain in which users will be created."


class UserInfo(t.TypedDict):
    """An entry of ``context["users"]``."""

    id: str
    credential: credential.OpenStackCredential
    tenant_id: str


class ProjectInfo(t.TypedDict):
    """A value of ``context["tenants"]``, keyed by the project id."""

    id: str
    name: str
    users: list[UserInfo]


def _uses_existing_users(
    platform_users: list[dict[str, t.Any]], config: t.Mapping[str, t.Any]
) -> bool:
    """Whether the users context reuses the users of the environment.

    It does so when the environment has users and the context is not asked
    to create new ones (the only option for existing users is the user
    choice method).
    """
    return bool(platform_users) and not (
        set(config) - {"user_choice_method"})


@validation.add("required_platform", platform="openstack", users=True)
@validation.configure("check_users_context_admin", platform="openstack")
class AdminForNewUsersValidator(validation.Validator):
    """Ensure there is an admin when the users context creates users."""

    def validate(
        self,
        context: dict[str, t.Any],
        config: dict[str, t.Any] | None,
        plugin_cls: type[plugin.Plugin],
        plugin_cfg: dict[str, t.Any] | None,
    ) -> None:
        platform_data = context["env"]["platforms"]["openstack"]
        if platform_data.get("admin"):
            return
        if _uses_existing_users(platform_data.get("users", []),
                                plugin_cfg or {}):
            return
        self.fail(
            "Creating temporary users and projects requires admin "
            "credentials, but the environment has none. Remove the users "
            "context settings other than 'user_choice_method' to use the "
            "existing users of the environment, or add admin credentials "
            "to it.")


@validation.add("check_users_context_admin")
@validation.add("required_platform", platform="openstack", users=True)
@context.configure(name="users", platform="openstack", order=100)
class UserGenerator(context.OpenStackContext):
    """Creates specified amount of keystone users and tenants."""

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "anyOf": [
            {"description": "Create new temporary users and tenants.",
             "properties": {
                "tenants": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "The number of tenants to create."
                },
                 "users_per_tenant": {
                     "type": "integer",
                     "minimum": 1,
                     "description": "The number of users to create per one "
                                    "tenant."},
                 "user_password": {
                     "type": "string",
                     "description": "Specify custom user password instead of "
                                    "randomly generated in case of password "
                                    "requirements."},
                 "resource_management_workers": {
                     "type": "integer",
                     "minimum": 1,
                     "description": RESOURCE_MANAGEMENT_WORKERS_DESCR},
                 "project_domain": {
                     "type": "string",
                     "description": PROJECT_DOMAIN_DESCR},
                 "user_domain": {
                     "type": "string",
                     "description": USER_DOMAIN_DESCR},
                 "user_choice_method": {
                     "$ref": "#/definitions/user_choice_method"}},
             "additionalProperties": False},
            # TODO(andreykurilin): add ability to specify users here.
            {"description": "Use existing users and tenants.",
             "properties": {
                 "user_choice_method": {
                     "$ref": "#/definitions/user_choice_method"}
             },
             "additionalProperties": False}
        ],
        "definitions": {
            "user_choice_method": {
                "enum": ["random", "round_robin"],
                "description": "The mode of balancing usage of users between "
                               "scenario iterations."}

        }
    }

    DEFAULT_CONFIG = {"user_choice_method": "random"}

    DEFAULT_FOR_NEW_USERS = {
        "tenants": 1,
        "users_per_tenant": 1,
        "resource_management_workers":
            cfg.CONF.openstack.users_context_resource_management_workers,
    }

    config: utils.LockedDict

    def __init__(self, ctx: dict[str, t.Any]) -> None:
        super().__init__(ctx)

        creds = self.env["platforms"]["openstack"]
        if creds.get("admin"):
            admin_cred = copy.deepcopy(creds["admin"])
            api_info = copy.deepcopy(creds.get("api_info", {}))
            if "api_info" in admin_cred:
                api_info.update(creds["admin"]["api_info"])
            admin_cred["api_info"] = api_info
            ctx["admin"] = {
                "credential": credential.OpenStackCredential(**admin_cred)
            }

        if _uses_existing_users(creds["users"], self.config):
            self.existing_users = creds["users"]
        else:
            self.existing_users = []
            self.credential: credential.OpenStackCredential = (
                ctx["admin"]["credential"])
            self.DEFAULT_FOR_NEW_USERS["project_domain"] = (
                self.credential.project_domain_name
                or cfg.CONF.openstack.project_domain
            )
            self.DEFAULT_FOR_NEW_USERS["user_domain"] = (
                self.credential.user_domain_name
                or cfg.CONF.openstack.user_domain
            )
            with self.config.unlocked():
                for key, value in self.DEFAULT_FOR_NEW_USERS.items():
                    self.config.setdefault(key, value)

    def _create_projects(self, threads: int) -> dict[str, ProjectInfo]:
        projects: collections.deque[ProjectInfo] = collections.deque()

        def publish(queue: collections.deque[tuple[str, str, int]]) -> None:
            for i in range(self.config["tenants"]):
                args = (self.config["project_domain"], self.task["uuid"], i)
                queue.append(args)

        def consume(
            cache: dict[str, keystone.Keystone],
            args: tuple[str, str, int],
        ) -> None:
            domain, task_id, i = args
            if "client" not in cache:
                clients = osclients.Clients(
                    self.credential,
                    name_generator=self.generate_random_name)
                cache["client"] = clients.keystone
            project = cache["client"].create_project(domain=domain)
            projects.append(
                {"id": project.id, "name": project.name, "users": []}
            )

        # NOTE(msdubov): consume() will fill the projects list in the closure.
        broker.run(publish, consume, threads)
        return {project["id"]: project for project in projects}

    def _get_default_role_id(self) -> str | None:
        """Resolve the role every created user gets, once.

        The role is the same for all of them, so it is looked up here instead
        of per user -- a lookup lists every role definition in the cloud, and
        doing that once per created user is the dominant cost of this context
        on a large tenants x users_per_tenant grid.

        Returns None when no role should be assigned: keystone v2 grants the
        default role itself when a user is created inside a tenant, and a
        misconfigured role name is a warning rather than a failure.
        """
        ks = osclients.Clients(self.credential).keystone
        if ks.version == "2":
            return None
        default_role = cfg.CONF.openstack.keystone_default_role
        role = ks.find_role(default_role)
        if role is None:
            LOG.warning(f"Unable to set {default_role} role to created users.")
            return None
        return role.id

    def _create_users(self, threads: int) -> list[UserInfo]:
        # NOTE(msdubov): This should be called after _create_projects().
        users_per_project = self.config["users_per_tenant"]
        default_role_id = self._get_default_role_id()

        users: collections.deque[UserInfo] = collections.deque()

        def publish(
            queue: collections.deque[tuple[str, str, str, str, str]],
        ) -> None:
            for project_id in self.context["tenants"]:
                for user_id in range(users_per_project):
                    username = self.generate_random_name()
                    password = (str(uuid.uuid4())
                                if self.config.get("user_password") is None
                                else self.config["user_password"])
                    args = (username, password, self.config["project_domain"],
                            self.config["user_domain"], project_id)
                    queue.append(args)

        def consume(
            cache: dict[str, keystone.Keystone],
            args: tuple[str, str, str, str, str],
        ) -> None:
            username, password, project_dom, user_dom, project_id = args
            if "client" not in cache:
                clients = osclients.Clients(
                    self.credential,
                    name_generator=self.generate_random_name)
                cache["client"] = clients.keystone
            client = cache["client"]
            user = client.create_user(username, password=password,
                                      project_id=project_id,
                                      domain=user_dom)
            if default_role_id is not None:
                client.add_role(role_id=default_role_id, user_id=user.id,
                                project_id=project_id)
            user_credential = credential.OpenStackCredential(
                auth_url=self.credential["auth_url"],
                username=user.name,
                password=password,
                project_name=self.context["tenants"][project_id]["name"],
                permission=consts.EndpointPermission.USER,
                project_domain_name=project_dom,
                user_domain_name=user_dom,
                endpoint_type=self.credential["endpoint_type"],
                https_insecure=self.credential["https_insecure"],
                https_cacert=self.credential["https_cacert"],
                region_name=self.credential["region_name"],
                profiler_hmac_key=self.credential["profiler_hmac_key"],
                profiler_conn_str=self.credential["profiler_conn_str"],
                api_info=self.credential["api_info"])
            users.append({"id": user.id,
                          "credential": user_credential,
                          "tenant_id": project_id})

        # NOTE(msdubov): consume() will fill the users list in the closure.
        broker.run(publish, consume, threads)
        return list(users)

    def create_users(self) -> None:
        """Create tenants and users, using the broker pattern."""

        threads = min(self.config["resource_management_workers"],
                      self.config["tenants"])

        LOG.debug(f"Creating {self.config['tenants']} tenants using "
                  f"{threads} threads")
        projects = self._create_projects(threads)
        self.context["tenants"] = projects

        if len(projects) < self.config["tenants"]:
            raise exceptions.ContextSetupFailure(
                ctx_name=self.get_name(),
                msg="Failed to create the requested number of tenants.")

        users_num = self.config["users_per_tenant"] * self.config["tenants"]
        threads = min(self.config["resource_management_workers"], users_num)
        LOG.debug(f"Creating {users_num} users using {threads} threads")
        users = self._create_users(threads)
        self.context["users"] = users
        for user in users:
            projects[user["tenant_id"]]["users"].append(user)

        if len(users) < users_num:
            raise exceptions.ContextSetupFailure(
                ctx_name=self.get_name(),
                msg="Failed to create the requested number of users.")

    def use_existing_users(self) -> None:
        LOG.debug("Using existing users for OpenStack platform.")
        api_info = copy.deepcopy(self.env["platforms"]["openstack"].get(
            "api_info", {}))
        self.context["config"]["existing_users"] = self.existing_users
        for user_credential in self.existing_users:
            user_credential = copy.deepcopy(user_credential)
            if "api_info" in user_credential:
                api_info.update(user_credential["api_info"])
            user_credential["api_info"] = api_info
            user_credential = credential.OpenStackCredential(**user_credential)
            user_clients = osclients.Clients(user_credential)
            user_id = user_clients.keystone.auth_ref.user_id
            project_id = user_clients.keystone.auth_ref.project_id
            if user_id is None or project_id is None:
                raise exceptions.ContextSetupFailure(
                    ctx_name=self.get_name(),
                    msg=f"Existing user '{user_credential.username}' is not "
                        f"scoped to a project.")
            # the user is authenticated now, so keep that auth state instead
            # of paying for a second authentication in _seed_auth_state.
            user_credential.auth = (
                user_clients.keystone.get_session()[1].get_auth_state())

            if project_id not in self.context["tenants"]:
                self.context["tenants"][project_id] = ProjectInfo(
                    id=project_id,
                    name=user_credential.project_name,
                    users=[]
                )

            user = UserInfo(
                id=user_id,
                credential=user_credential,
                tenant_id=project_id
            )
            self.context["users"].append(user)
            self.context["tenants"][project_id]["users"].append(user)

    def setup(self) -> None:
        self.context["users"] = []
        self.context["tenants"] = {}
        self.context["user_choice_method"] = self.config["user_choice_method"]

        if self.existing_users:
            self.use_existing_users()
        else:
            self.create_users()

        self._seed_auth_state()

    def _seed_auth_state(self) -> None:
        """Authenticate each user (and admin) once so iterations reuse it.

        Credentials that are already authenticated (the existing_users path
        does it while resolving user and tenant ids) are skipped.
        """
        credentials: list[credential.OpenStackCredential] = [
            user["credential"] for user in self.context["users"]
        ]
        admin = self.context.get("admin", {}).get("credential")
        if admin is not None:
            credentials.append(admin)
        if not credentials:
            return

        def publish(
            queue: collections.deque[credential.OpenStackCredential],
        ) -> None:
            for cred in credentials:
                if not cred.auth:
                    queue.append(cred)

        def consume(
            cache: dict[str, object], cred: credential.OpenStackCredential
        ) -> None:
            clients = osclients.Clients(cred)
            sess, plugin = clients.keystone.get_session()
            plugin.get_access(sess)
            cred.auth = plugin.get_auth_state()

        # NOTE(andreykurilin): resource_management_workers is defaulted only
        #   for the new-users path, while this runs for existing users too.
        threads = min(
            self.config.get(
                "resource_management_workers",
                cfg.CONF.openstack.users_context_resource_management_workers),
            len(credentials))
        broker.run(publish, consume, threads)

    def _remove_default_neutron_resources(self) -> None:
        """Delete the resources neutron creates for every project by itself.

        These are the default security group and, with FWaaS v2, the default
        firewall group with its policies and rules. Only admin may delete
        them, so the generic cleanup leaves them behind.
        """
        clients = osclients.Clients(
            self.credential, atomic_inst=self.atomic_actions())
        if "neutron" not in clients.services().values():
            LOG.debug("Default neutron resources cleanup is disabled: "
                      "neutron is not available.")
            return
        client = clients.neutron

        if client.supports_extension("security-group"):
            for security_group in client.list_security_groups(name="default"):
                if security_group.project_id in self.context["tenants"]:
                    client.delete_security_group(security_group.id)

        if not client.supports_extension("fwaas_v2"):
            return

        groups = client.list_firewall_groups(
            name=neutron_client.DEFAULT_FIREWALL_GROUP_NAME)
        for group in groups:
            if group.project_id not in self.context["tenants"]:
                continue
            rule_ids: list[str] = []
            for policy_id in (group.ingress_firewall_policy_id,
                              group.egress_firewall_policy_id):
                if policy_id:
                    policy = client.get_firewall_policy(policy_id)
                    rule_ids.extend(policy.firewall_rules or [])
            if group.ports:
                client.disassociate_firewall_group_ports(group.id)
            client.delete_firewall_group(group.id)
            for rule_id in rule_ids:
                client.delete_firewall_rule(rule_id)

    def _get_consumer_for_deletion(
        self, func_name: str
    ) -> t.Callable[[dict[str, keystone.Keystone], str], None]:
        def consume(
            cache: dict[str, keystone.Keystone], resource_id: str
        ) -> None:
            if "client" not in cache:
                clients = osclients.Clients(self.credential)
                cache["client"] = clients.keystone
            getattr(cache["client"], func_name)(resource_id)
        return consume

    def _delete_projects(self) -> None:
        threads: int = self.config["resource_management_workers"]

        def publish(queue: collections.deque[str]) -> None:
            for project_id in self.context["tenants"]:
                queue.append(project_id)

        broker.run(publish, self._get_consumer_for_deletion("delete_project"),
                   threads)
        self.context["tenants"] = {}

    def _delete_users(self) -> None:
        threads: int = self.config["resource_management_workers"]

        def publish(queue: collections.deque[str]) -> None:
            for user in self.context["users"]:
                queue.append(user["id"])

        broker.run(publish, self._get_consumer_for_deletion("delete_user"),
                   threads)
        self.context["users"] = []

    def cleanup(self) -> None:
        """Delete tenants and users, using the broker pattern."""
        if self.existing_users:
            # nothing to do here.
            return
        else:
            self._remove_default_neutron_resources()
            self._delete_users()
            self._delete_projects()
