# Copyright 2013: Mirantis Inc.
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

import typing as t

from rally import exceptions
from rally.common import logging
from rally.common.plugin import plugin
from rally.task import validation

from rally_openstack.task import scenario


_TENANT_DEPRECATION = "Keystone tenants are called projects since Keystone V3"


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_user",
                    platform="openstack")
class CreateUser(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name_length' argument to create_user is ignored",
        "0.1.2", ["name_length"], once=True)
    def run(
        self,
        name_length: int = 10,
        password: str | None = None,
        project_id: str | None = None,
        domain: str = "Default",
        enabled: bool = True,
    ) -> None:
        """Create a keystone user with random name.

        :param name_length: the length of name
        :param password: the password of the user
        :param project_id: the default project of the user
        :param domain: name or id of the domain to create the user in
        :param enabled: whether the user is enabled
        """
        self._admin_clients.keystone.create_user(
            password=password, project_id=project_id, domain=domain,
            enabled=enabled)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_delete_user",
                    platform="openstack")
class CreateDeleteUser(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name_length' argument to create_delete_user is ignored",
        "0.1.2", ["name_length"], once=True)
    def run(
        self,
        name_length: int = 10,
        password: str | None = None,
        project_id: str | None = None,
        domain: str = "Default",
        enabled: bool = True,
    ) -> None:
        """Create a keystone user with random name and then delete it.

        :param name_length: the length of name
        :param password: the password of the user
        :param project_id: the default project of the user
        :param domain: name or id of the domain to create the user in
        :param enabled: whether the user is enabled
        """
        user = self._admin_clients.keystone.create_user(
            password=password, project_id=project_id, domain=domain,
            enabled=enabled)
        self._admin_clients.keystone.delete_user(user.id)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_user_set_enabled_and_delete",
                    platform="openstack")
class CreateUserSetEnabledAndDelete(scenario.OpenStackScenario):

    def run(
        self,
        enabled: bool = True,
        password: str | None = None,
        project_id: str | None = None,
        domain: str = "Default",
    ) -> None:
        """Create a keystone user, enable or disable it, and delete it.

        :param enabled: Initial state of user 'enabled' flag. The user
                        will be created with 'enabled' set to this
                        value, and then it will be toggled.
        :param password: the password of the user
        :param project_id: the default project of the user
        :param domain: name or id of the domain to create the user in
        """
        user = self._admin_clients.keystone.create_user(
            password=password, project_id=project_id, domain=domain,
            enabled=enabled)
        self._admin_clients.keystone.update_user(
            user.id, enabled=(not enabled))
        self._admin_clients.keystone.delete_user(user.id)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_project",
                    platform="openstack")
class CreateProject(scenario.OpenStackScenario):

    def run(self, domain: str = "Default") -> None:
        """Create a keystone project with random name.

        :param domain: name or id of the domain to create the project in
        """
        self._admin_clients.keystone.create_project(domain=domain)


@plugin.deprecated(f"{_TENANT_DEPRECATION}, use "
                   f"'KeystoneBasic.create_project' instead.",
                   rally_version="4.2.0")
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_tenant",
                    platform="openstack")
class CreateTenant(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name_length' argument to create_tenant is ignored",
        "0.1.2", ["name_length"], once=True)
    def run(self, name_length: int = 10, domain: str = "Default") -> None:
        """Create a keystone tenant with random name.

        :param name_length: the length of name
        :param domain: name or id of the domain to create the tenant in
        """
        self._admin_clients.keystone.create_project(domain=domain)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.authenticate_user_and_validate_token",
                    platform="openstack")
class AuthenticateUserAndValidateToken(scenario.OpenStackScenario):

    def run(self) -> None:
        """Authenticate and validate a keystone token."""
        token = self._admin_clients.keystone.fetch_token()
        self._admin_clients.keystone.validate_token(token)


@validation.add("number", param_name="users_per_project", minval=1)
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_project_with_users",
                    platform="openstack")
class CreateProjectWithUsers(scenario.OpenStackScenario):

    def run(self, users_per_project: int, domain: str = "Default") -> None:
        """Create a keystone project and several users belonging to it.

        :param users_per_project: number of users to create for the project
        :param domain: name or id of the domain to create the project and
            users in
        """
        project = self._admin_clients.keystone.create_project(domain=domain)
        # the same role for every user, so it is resolved once rather than
        # listing all role definitions per created user.
        role = self._admin_clients.keystone.find_role("member")
        for _ in range(users_per_project):
            user = self._admin_clients.keystone.create_user(
                project_id=project.id, domain=domain)
            if role is not None:
                self._admin_clients.keystone.add_role(
                    role_id=role.id, user_id=user.id, project_id=project.id
                )


@plugin.deprecated(f"{_TENANT_DEPRECATION}, use "
                   f"'KeystoneBasic.create_project_with_users' instead.",
                   rally_version="4.2.0")
@validation.add("number", param_name="users_per_tenant", minval=1)
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_tenant_with_users",
                    platform="openstack")
class CreateTenantWithUsers(CreateProjectWithUsers):

    @logging.log_deprecated_args(
        "The 'name_length' argument to create_tenant_with_users is ignored",
        "0.1.2", ["name_length"], once=True)
    def run(
        self,
        users_per_tenant: int,
        name_length: int = 10,
        domain: str = "Default",
    ) -> None:
        """Create a keystone tenant and several users belonging to it.

        :param users_per_tenant: number of users to create for the tenant
        :param name_length: the length of name
        :param domain: name or id of the domain to create the tenant and
            users in
        """
        super().run(users_per_project=users_per_tenant, domain=domain)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_list_users",
                    platform="openstack")
class CreateAndListUsers(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name_length' and 'name' arguments to create_and_list_users are "
        "ignored", "0.1.2", ["name_length", "name"], once=True)
    def run(
        self,
        name_length: int = 10,
        name: str | None = None,
        password: str | None = None,
        project_id: str | None = None,
        domain: str = "Default",
        enabled: bool = True,
    ) -> None:
        """Create a keystone user with random name and list all users.

        :param name_length: the length of name
        :param name: ignored, the user always gets a random name
        :param password: the password of the user
        :param project_id: the default project of the user
        :param domain: name or id of the domain to create the user in
        :param enabled: whether the user is enabled
        """
        self._admin_clients.keystone.create_user(
            password=password, project_id=project_id, domain=domain,
            enabled=enabled)
        self._admin_clients.keystone.list_users()


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_list_projects",
                    platform="openstack")
class CreateAndListProjects(scenario.OpenStackScenario):

    def run(self, domain: str = "Default") -> None:
        """Create a keystone project with random name and list all projects.

        :param domain: name or id of the domain to create the project in
        """
        self._admin_clients.keystone.create_project(domain=domain)
        self._admin_clients.keystone.list_projects()


@plugin.deprecated(f"{_TENANT_DEPRECATION}, use "
                   f"'KeystoneBasic.create_and_list_projects' instead.",
                   rally_version="4.2.0")
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_list_tenants",
                    platform="openstack")
class CreateAndListTenants(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name_length' argument to create_and_list_tenants is ignored",
        "0.1.2", ["name_length"], once=True)
    def run(self, name_length: int = 10, domain: str = "Default") -> None:
        """Create a keystone tenant with random name and list all tenants.

        :param name_length: the length of name
        :param domain: name or id of the domain to create the tenant in
        """
        self._admin_clients.keystone.create_project(domain=domain)
        self._admin_clients.keystone.list_projects()


@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.add_and_remove_user_role",
                    platform="openstack")
class AddAndRemoveUserRole(scenario.OpenStackScenario):

    def run(self) -> None:
        """Create a user role add to a user and disassociate."""
        project_id = self.context["tenant"]["id"]
        user_id = self.context["user"]["id"]
        role = self._admin_clients.keystone.create_role()
        self._admin_clients.keystone.add_role(
            role_id=role.id, user_id=user_id, project_id=project_id)
        self._admin_clients.keystone.revoke_role(
            role.id, user_id=user_id, project_id=project_id)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_delete_role",
                    platform="openstack")
class CreateAndDeleteRole(scenario.OpenStackScenario):

    def run(self) -> None:
        """Create a user role and delete it."""
        role = self._admin_clients.keystone.create_role()
        self._admin_clients.keystone.delete_role(role.id)


@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_add_and_list_user_roles",
                    platform="openstack")
class CreateAddAndListUserRoles(scenario.OpenStackScenario):

    def run(self) -> None:
        """Create user role, add it and list user roles for given user."""
        project_id = self.context["tenant"]["id"]
        user_id = self.context["user"]["id"]
        role = self._admin_clients.keystone.create_role()
        self._admin_clients.keystone.add_role(
            user_id=user_id, role_id=role.id, project_id=project_id)
        self._admin_clients.keystone.list_role_assignments(
            user_id, project_id=project_id)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.get_entities",
                    platform="openstack")
class GetEntities(scenario.OpenStackScenario):

    def run(self, service_name: str | None = "keystone") -> None:
        """Get instance of a project, user, role and service by id's.

        An ephemeral project, user, and role are each created. By
        default, fetches the 'keystone' service. This can be
        overridden (for instance, to get the 'Identity Service'
        service on older OpenStack), or None can be passed explicitly
        to service_name to create a new service and then query it by
        ID.

        :param service_name: The name of the service to get by ID; or
                             None, to create an ephemeral service and
                             get it by ID.
        """
        project = self._admin_clients.keystone.create_project()
        user = self._admin_clients.keystone.create_user(project_id=project.id)
        role = self._admin_clients.keystone.create_role()
        self._admin_clients.keystone.get_project(project.id)
        self._admin_clients.keystone.get_user(user.id)
        self._admin_clients.keystone.get_role(role.id)
        if service_name is None:
            service = self._admin_clients.keystone.create_service()
        else:
            services = self._admin_clients.keystone.list_services(
                name=service_name)
            if not services:
                raise exceptions.GetResourceNotFound(
                    resource=f"Service({service_name})")
            service = services[0]
        self._admin_clients.keystone.get_service(service.id)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_delete_service",
                    platform="openstack")
class CreateAndDeleteService(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name' argument to create_and_delete_service will be ignored",
        "0.0.5", ["name"])
    def run(
        self,
        name: str | None = None,
        service_type: str | None = None,
        description: str | None = None,
    ) -> None:
        """Create and delete service.

        :param name: name of the service
        :param service_type: type of the service
        :param description: description of the service
        """
        service = self._admin_clients.keystone.create_service(
            service_type=service_type, description=description)
        self._admin_clients.keystone.delete_service(service.id)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_update_and_delete_project",
                    platform="openstack")
class CreateUpdateAndDeleteProject(scenario.OpenStackScenario):

    def run(self, domain: str = "Default") -> None:
        """Create, update and delete project.

        :param domain: name or id of the domain to create the project in
        """
        project = self._admin_clients.keystone.create_project(domain=domain)
        self._admin_clients.keystone.update_project(
            project.id,
            name=self.generate_random_name(),
            description=self.generate_random_name(),
        )
        self._admin_clients.keystone.delete_project(project.id)


@plugin.deprecated(f"{_TENANT_DEPRECATION}, use "
                   f"'KeystoneBasic.create_update_and_delete_project' "
                   f"instead.",
                   rally_version="4.2.0")
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_update_and_delete_tenant",
                    platform="openstack")
class CreateUpdateAndDeleteTenant(CreateUpdateAndDeleteProject):

    @logging.log_deprecated_args(
        "The 'name_length' argument to create_update_and_delete_tenant is "
        "ignored", "0.1.2", ["name_length"], once=True)
    def run(
        self, name_length: int | None = None, domain: str = "Default"
    ) -> None:
        """Create, update and delete tenant.

        :param name_length: the length of name
        :param domain: name or id of the domain to create the tenant in
        """
        super().run(domain=domain)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_user_update_password",
                    platform="openstack")
class CreateUserUpdatePassword(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name_length' and 'password_length' arguments to "
        "create_user_update_password are ignored",
        "0.1.2", ["name_length", "password_length"], once=True)
    def run(
        self,
        name_length: int | None = None,
        password_length: int | None = None,
    ) -> None:
        """Create user and update password for that user.

        :param name_length: the length of name
        :param password_length: the length of password
        """
        user = self._admin_clients.keystone.create_user()
        self._admin_clients.keystone.update_user(
            user.id, password=self.generate_random_name())


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_list_services",
                    platform="openstack")
class CreateAndListServices(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "The 'name' argument to create_and_list_services will be ignored",
        "0.0.5", ["name"])
    def run(
        self,
        name: str | None = None,
        service_type: str | None = None,
        description: str | None = None,
    ) -> None:
        """Create and list services.

        :param name: name of the service
        :param service_type: type of the service
        :param description: description of the service
        """
        self._admin_clients.keystone.create_service(
            service_type=service_type, description=description)
        self._admin_clients.keystone.list_services()


@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_list_ec2credentials",
                    platform="openstack")
class CreateAndListEc2Credentials(scenario.OpenStackScenario):

    def run(self) -> None:
        """Create and list all keystone ec2-credentials."""
        self._clients.keystone.create_credential(
            "ec2",
            user_id=self.context["user"]["id"],
            project_id=self.context["tenant"]["id"])
        self._clients.keystone.list_credentials(
            user_id=self.context["user"]["id"], cred_type="ec2")


@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_delete_ec2credential",
                    platform="openstack")
class CreateAndDeleteEc2Credential(scenario.OpenStackScenario):

    def run(self) -> None:
        """Create and delete keystone ec2-credential."""
        cred = self._clients.keystone.create_credential(
            "ec2",
            user_id=self.context["user"]["id"],
            project_id=self.context["tenant"]["id"])
        self._clients.keystone.delete_credential(cred.id)


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_get_role",
                    platform="openstack")
class CreateAndGetRole(scenario.OpenStackScenario):

    def run(self, domain: str | None = None) -> None:
        """Create a user role and get it detailed information.

        :param domain: name or id of the domain to create the role in;
            a global role is created when omitted
        """
        role = self._admin_clients.keystone.create_role(domain=domain)
        self._admin_clients.keystone.get_role(role.id)


class CreateRoleArgs(t.TypedDict, total=False):
    """Optional arguments for creating a keystone role."""

    domain: str


class ListRolesArgs(t.TypedDict, total=False):
    """Optional arguments for listing keystone roles."""

    name: str
    domain: str


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_list_roles",
                    platform="openstack")
class CreateAddListRoles(scenario.OpenStackScenario):

    @logging.log_deprecated_args(
        "Use the 'domain' argument of create_and_list_roles instead of "
        "'create_role_kwargs' and 'list_role_kwargs'",
        "4.2.0", ["create_role_kwargs", "list_role_kwargs"], once=True)
    def run(
        self,
        domain: str | None = None,
        create_role_kwargs: CreateRoleArgs | None = None,
        list_role_kwargs: ListRolesArgs | None = None,
    ) -> None:
        """Create a role, then list all roles.

        :param domain: name or id of the domain to create the role in and to
            list the roles of; global roles are used when omitted
        :param create_role_kwargs: Optional additional arguments for
                                   roles create
        :param list_role_kwargs: Optional additional arguments for roles list
        """
        create_role_kwargs = create_role_kwargs or {}
        list_role_kwargs = list_role_kwargs or {}

        role = self._admin_clients.keystone.create_role(
            domain=create_role_kwargs.get("domain", domain))
        self.assertTrue(role, err_msg="Role isn't created")
        all_roles = self._admin_clients.keystone.list_roles(
            name=list_role_kwargs.get("name"),
            domain=list_role_kwargs.get("domain", domain))
        self.assertIn(role, all_roles,
                      err_msg="Created role is not in the list of all "
                              "available roles")


class CreateUserArgs(t.TypedDict, total=False):
    """Optional arguments for creating a keystone user."""

    password: str
    project_id: str
    domain: str
    enabled: bool


class UpdateUserArgs(t.TypedDict, total=False):
    """Optional arguments for updating a keystone user."""

    enabled: bool
    email: str
    password: str


@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(context={"admin_cleanup@openstack": ["keystone"]},
                    name="KeystoneBasic.create_and_update_user",
                    platform="openstack")
class CreateAndUpdateUser(scenario.OpenStackScenario):

    def run(
        self,
        create_user_kwargs: CreateUserArgs | None = None,
        update_user_kwargs: UpdateUserArgs | None = None,
    ) -> None:
        """Create user and update the user.

        :param create_user_kwargs: Optional additional arguments for user
                                   creation
        :param update_user_kwargs: Optional additional arguments for user
                                   updation
        """
        update_user_kwargs = update_user_kwargs or {}

        user = self._admin_clients.keystone.create_user(
            **(create_user_kwargs or {}))
        self._admin_clients.keystone.update_user(
            user.id, **update_user_kwargs)
        user_data = self._admin_clients.keystone.get_user(user.id)

        for key, expected in update_user_kwargs.items():
            # the openstacksdk user resource exposes ``enabled`` as
            # ``is_enabled``.
            attr = "is_enabled" if key == "enabled" else key
            self.assertEqual(getattr(user_data, attr), expected,
                             err_msg=f"{key} isn't updated")
