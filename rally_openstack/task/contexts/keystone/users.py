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

from rally.common import broker
from rally.common import cfg
from rally.common import logging
from rally.common import utils
from rally.common import validation
from rally import exceptions

from rally_openstack.common import consts
from rally_openstack.common import credential
from rally_openstack.common import osclients
from rally_openstack.common.services.identity import identity
from rally_openstack.common.services.network import neutron
from rally_openstack.task import context


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

RESOURCE_MANAGEMENT_WORKERS_DESCR = (
    "The number of concurrent threads to use for serving users context.")
PROJECT_DOMAIN_DESCR = "ID of domain in which projects will be created."
USER_DOMAIN_DESCR = "ID of domain in which users will be created."


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

    def __init__(self, context):
        super(UserGenerator, self).__init__(context)

        creds = self.env["platforms"]["openstack"]
        if creds.get("admin"):
            admin_cred = copy.deepcopy(creds["admin"])
            api_info = copy.deepcopy(creds.get("api_info", {}))
            if "api_info" in admin_cred:
                api_info.update(creds["admin"]["api_info"])
            admin_cred["api_info"] = api_info
            context["admin"] = {
                "credential": credential.OpenStackCredential(**admin_cred)
            }

        if creds["users"] and not (set(self.config) - {"user_choice_method"}):
            self.existing_users = creds["users"]
        else:
            self.existing_users = []
            self.credential = context["admin"]["credential"]
            project_domain = (self.credential["project_domain_name"]
                              or cfg.CONF.openstack.project_domain)
            user_domain = (self.credential["user_domain_name"]
                           or cfg.CONF.openstack.user_domain)
            self.DEFAULT_FOR_NEW_USERS["project_domain"] = project_domain
            self.DEFAULT_FOR_NEW_USERS["user_domain"] = user_domain
            with t.cast(utils.LockedDict, self.config).unlocked():
                for key, value in self.DEFAULT_FOR_NEW_USERS.items():
                    self.config.setdefault(key, value)

    def _create_tenants(self, threads):
        tenants = collections.deque()

        def publish(queue):
            for i in range(self.config["tenants"]):
                args = (self.config["project_domain"], self.task["uuid"], i)
                queue.append(args)

        def consume(cache, args):
            domain, task_id, i = args
            if "client" not in cache:
                clients = osclients.Clients(self.credential)
                cache["client"] = identity.Identity(
                    clients, name_generator=self.generate_random_name)
            tenant = cache["client"].create_project(domain_name=domain)
            tenant_dict = {"id": tenant.id, "name": tenant.name, "users": []}
            tenants.append(tenant_dict)

        # NOTE(msdubov): consume() will fill the tenants list in the closure.
        broker.run(publish, consume, threads)
        tenants_dict = {}
        for tenant in tenants:
            tenants_dict[tenant["id"]] = tenant

        return tenants_dict

    def _create_users(self, threads):
        # NOTE(msdubov): This should be called after _create_tenants().
        users_per_tenant = self.config["users_per_tenant"]
        default_role = cfg.CONF.openstack.keystone_default_role

        users = collections.deque()

        def publish(queue):
            for tenant_id in self.context["tenants"]:
                for user_id in range(users_per_tenant):
                    username = self.generate_random_name()
                    password = (str(uuid.uuid4())
                                if self.config.get("user_password") is None
                                else self.config["user_password"])
                    args = (username, password, self.config["project_domain"],
                            self.config["user_domain"], tenant_id)
                    queue.append(args)

        def consume(cache, args):
            username, password, project_dom, user_dom, tenant_id = args
            if "client" not in cache:
                clients = osclients.Clients(self.credential)
                cache["client"] = identity.Identity(
                    clients, name_generator=self.generate_random_name)
            client = cache["client"]
            user = client.create_user(username, password=password,
                                      project_id=tenant_id,
                                      domain_name=user_dom,
                                      default_role=default_role)
            user_credential = credential.OpenStackCredential(
                auth_url=self.credential["auth_url"],
                username=user.name,
                password=password,
                tenant_name=self.context["tenants"][tenant_id]["name"],
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
                          "tenant_id": tenant_id})

        # NOTE(msdubov): consume() will fill the users list in the closure.
        broker.run(publish, consume, threads)
        return list(users)

    def create_users(self):
        """Create tenants and users, using the broker pattern."""

        threads = min(self.config["resource_management_workers"],
                      self.config["tenants"])

        LOG.debug("Creating %(tenants)d tenants using %(threads)s threads"
                  % {"tenants": self.config["tenants"], "threads": threads})
        self.context["tenants"] = self._create_tenants(threads)

        if len(self.context["tenants"]) < self.config["tenants"]:
            raise exceptions.ContextSetupFailure(
                ctx_name=self.get_name(),
                msg="Failed to create the requested number of tenants.")

        users_num = self.config["users_per_tenant"] * self.config["tenants"]
        threads = min(self.config["resource_management_workers"], users_num)
        LOG.debug("Creating %(users)d users using %(threads)s threads"
                  % {"users": users_num, "threads": threads})
        self.context["users"] = self._create_users(threads)
        for user in self.context["users"]:
            self.context["tenants"][user["tenant_id"]]["users"].append(user)

        if len(self.context["users"]) < users_num:
            raise exceptions.ContextSetupFailure(
                ctx_name=self.get_name(),
                msg="Failed to create the requested number of users.")

    def use_existing_users(self):
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
            tenant_id = user_clients.keystone.auth_ref.project_id

            if tenant_id not in self.context["tenants"]:
                self.context["tenants"][tenant_id] = {
                    "id": tenant_id,
                    "name": user_credential.tenant_name
                }

            self.context["users"].append({
                "credential": user_credential,
                "id": user_id,
                "tenant_id": tenant_id
            })

    def setup(self):
        self.context["users"] = []
        self.context["tenants"] = {}
        self.context["user_choice_method"] = self.config["user_choice_method"]

        if self.existing_users:
            self.use_existing_users()
        else:
            self.create_users()

    def _remove_default_security_group(self):
        """Delete default security group for tenants."""

        admin_client = neutron.NeutronService(
            clients=osclients.Clients(self.credential),
            atomic_inst=self.atomic_actions()
        )

        if not admin_client.supports_extension("security-group", silent=True):
            LOG.debug("Security group context is disabled.")
            return

        security_groups = admin_client.list_security_groups(name="default")
        for security_group in security_groups:
            if security_group["tenant_id"] not in self.context["tenants"]:
                continue
            admin_client.delete_security_group(security_group["id"])

    def _get_consumer_for_deletion(self, func_name):
        def consume(cache, resource_id):
            if "client" not in cache:
                clients = osclients.Clients(self.credential)
                cache["client"] = identity.Identity(clients)
            getattr(cache["client"], func_name)(resource_id)
        return consume

    def _delete_tenants(self):
        threads = self.config["resource_management_workers"]

        def publish(queue):
            for tenant_id in self.context["tenants"]:
                queue.append(tenant_id)

        broker.run(publish, self._get_consumer_for_deletion("delete_project"),
                   threads)
        self.context["tenants"] = {}

    def _delete_users(self):
        threads = self.config["resource_management_workers"]

        def publish(queue):
            for user in self.context["users"]:
                queue.append(user["id"])

        broker.run(publish, self._get_consumer_for_deletion("delete_user"),
                   threads)
        self.context["users"] = []

    def cleanup(self):
        """Delete tenants and users, using the broker pattern."""
        if self.existing_users:
            # nothing to do here.
            return
        else:
            self._remove_default_security_group()
            self._delete_users()
            self._delete_tenants()
