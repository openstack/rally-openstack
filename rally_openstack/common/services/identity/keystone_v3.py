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
from rally.common import logging
from rally.task import atomic

from rally_openstack.common import service
from rally_openstack.common.services.identity import identity
from rally_openstack.common.services.identity import keystone_common


LOG = logging.getLogger(__name__)


@service.service("keystone", service_type="identity", version="3")
class KeystoneV3Service(service.Service, keystone_common.KeystoneMixin):

    def _get_domain_id(self, domain_name_or_id):
        from keystoneclient import exceptions as kc_exceptions

        try:
            # First try to find domain by ID
            return self._kc.domains.get(
                domain_name_or_id).id
        except kc_exceptions.NotFound:
            # Domain not found by ID, try to find it by name
            domains = self._kc.domains.list(
                name=domain_name_or_id)
            if domains:
                return domains[0].id
            # Domain not found by name
            raise exceptions.GetResourceNotFound(
                resource="KeystoneDomain(%s)" % domain_name_or_id)

    def create_project(self, project_name=None, domain_name="Default"):
        return self._ng.create_project(project_name, domain=domain_name)

    def update_project(self, project_id, name=None, enabled=None,
                       description=None):
        """Update tenant name and description.

        :param project_id: Id of project to update
        :param name: project name to be set (if boolean True, random name will
            be set)
        :param enabled: enabled status of project
        :param description: project description to be set (if boolean True,
            random description will be set)
        """
        if name is True:
            name = self.generate_random_name()
        if description is True:
            description = self.generate_random_name()
        self._ng.update_project(project_id, name=name, enabled=enabled,
                                description=description)

    def delete_project(self, project_id):
        self._ng.delete_project(project_id)

    def list_projects(self):
        return self._ng.list_projects()

    def get_project(self, project_id):
        """Get project."""
        return self._ng.get_project(project_id)

    def create_user(self, username=None, password=None, project_id=None,
                    domain_name="Default", enabled=True,
                    default_role="member"):
        """Create user.


        :param username: name of user
        :param password: user password
        :param project_id: user's default project
        :param domain_name: Name or id of domain where to create project.
        :param enabled: whether the user is enabled.
        :param default_role: user's default role
        """
        user = self._ng.create_user(
            username=username, password=password, project_id=project_id,
            domain=domain_name, enabled=enabled)
        if project_id and default_role:
            # NOTE(andreykurilin): the client does not grant a role on user
            #   creation, so this layer keeps doing it to stay compatible.
            #   New code resolves the role once and calls add_role itself
            #   instead of paying for a role listing per user.
            role = self._ng.find_role(default_role)
            if role is None:
                LOG.warning(f"Unable to set {default_role} role to created "
                            f"user.")
            else:
                self._ng.add_role(role_id=role.id, user_id=user.id,
                                  project_id=project_id)
        return user

    @atomic.action_timer("keystone_v3.create_users")
    def create_users(self, project_id, number_of_users, user_create_args=None):
        """Create specified amount of users.

        :param project_id: Id of project
        :param number_of_users: number of users to create
        :param user_create_args: additional user creation arguments
        """
        users = []
        for _i in range(number_of_users):
            users.append(self.create_user(project_id=project_id,
                                          **(user_create_args or {})))
        return users

    @atomic.action_timer("keystone_v3.update_user")
    def update_user(self, user_id, name=None, domain_name=None,
                    project_id=None, password=None, email=None,
                    description=None, enabled=None, default_project=None):
        domain = None
        if domain_name:
            domain = self._get_domain_id(domain_name)

        self._kc.users.update(
            user_id, name=name, domain=domain, project=project_id,
            password=password, email=email, description=description,
            enabled=enabled, default_project=default_project)

    @atomic.action_timer("keystone_v3.create_service")
    def create_service(self, name=None, service_type=None, description=None,
                       enabled=True):
        """Creates keystone service.

        :param name: name of service to create
        :param service_type: type of the service
        :param description: description of the service
        :param enabled: whether the service appears in the catalog
        :returns: keystone service instance
        """
        name = name or self.generate_random_name()
        service_type = service_type or "rally_test_type"
        description = description or self.generate_random_name()
        return self._kc.services.create(
            name, type=service_type, description=description, enabled=enabled)

    def create_role(self, name=None, domain_name=None):
        return self._ng.create_role(name=name, domain=domain_name)

    def add_role(self, role_id, user_id, project_id):
        self._ng.add_role(role_id=role_id, user_id=user_id,
                          project_id=project_id)

    def list_roles(self, user_id=None, project_id=None, domain_name=None):
        """List all roles."""
        if user_id:
            return self._ng.list_role_assignments(
                user_id, project_id=project_id, domain=domain_name)
        return self._ng.list_roles(domain=domain_name)

    def revoke_role(self, role_id, user_id, project_id):
        self._ng.revoke_role(role_id=role_id, user_id=user_id,
                             project_id=project_id)

    def create_domain(self, name, description=None, enabled=True):
        return self._ng.create_domain(name, description=description,
                                      is_enabled=enabled)

    @atomic.action_timer("keystone_v3.create_ec2creds")
    def create_ec2credentials(self, user_id, project_id):
        """Create ec2credentials.

        :param user_id: User ID for which to create credentials
        :param project_id: Tenant ID for which to create credentials

        :returns: Created ec2-credentials object
        """
        return self._kc.ec2.create(user_id, project_id=project_id)


@service.compat_layer(KeystoneV3Service)
class UnifiedKeystoneV3Service(keystone_common.UnifiedKeystoneMixin,
                               identity.Identity):

    @staticmethod
    def _unify_project(project):
        return identity.Project(id=project.id, name=project.name,
                                domain_id=project.domain_id)

    @staticmethod
    def _unify_user(user):
        # When user has default_project_id that is None user.default_project_id
        # will raise AttributeError
        project_id = getattr(user, "project_id",
                             getattr(user, "default_project_id", None))
        return identity.User(id=user.id, name=user.name, project_id=project_id,
                             domain_id=user.domain_id)

    def create_project(self, project_name=None, domain_name="Default"):
        """Creates new project/tenant and return project object.

        :param project_name: Name of project to be created.
        :param domain_name: Name or id of domain where to create project,
        """
        project = self._impl.create_project(project_name,
                                            domain_name=domain_name)
        return self._unify_project(project)

    def update_project(self, project_id, name=None, enabled=None,
                       description=None):
        """Update project name, enabled and description

        :param project_id: Id of project to update
        :param name: project name to be set
        :param enabled: enabled status of project
        :param description: project description to be set
        """
        self._impl.update_project(project_id=project_id, name=name,
                                  enabled=enabled, description=description)

    def delete_project(self, project_id):
        """Deletes project."""
        return self._impl.delete_project(project_id)

    def list_projects(self):
        """List all projects."""
        return [self._unify_project(p) for p in self._impl.list_projects()]

    def get_project(self, project_id):
        """Get project."""
        return self._unify_project(self._impl.get_project(project_id))

    def create_user(self, username=None, password=None, project_id=None,
                    domain_name="Default", enabled=True,
                    default_role="member"):
        """Create user.

        :param username: name of user
        :param password: user password
        :param project_id: user's default project
        :param domain_name: Name or id of domain where to create project,
        :param enabled: whether the user is enabled.
        :param default_role: Name of default user's role
        """
        return self._unify_user(self._impl.create_user(
            username=username, password=password, project_id=project_id,
            domain_name=domain_name, default_role=default_role,
            enabled=enabled))

    def create_users(self, project_id, number_of_users, user_create_args=None):
        """Create specified amount of users.

        :param project_id: Id of project
        :param number_of_users: number of users to create
        :param user_create_args: additional user creation arguments
        """
        return [self._unify_user(u)
                for u in self._impl.create_users(
                project_id=project_id, number_of_users=number_of_users,
                user_create_args=user_create_args)]

    def list_users(self):
        """List all users."""
        return [self._unify_user(u) for u in self._impl.list_users()]

    def update_user(self, user_id, enabled=None, name=None, email=None,
                    password=None):
        return self._impl.update_user(user_id, enabled=enabled, name=name,
                                      email=email, password=password)

    def list_services(self):
        """List all services."""
        return [self._unify_service(s) for s in self._impl.list_services()]

    def create_role(self, name=None, domain_name=None):
        """Add role to user."""
        return self._unify_role(self._impl.create_role(
            name, domain_name=domain_name))

    def add_role(self, role_id, user_id, project_id):
        """Add role to user."""
        self._impl.add_role(role_id=role_id, user_id=user_id,
                            project_id=project_id)

    def revoke_role(self, role_id, user_id, project_id):
        """Revokes a role from a user."""
        return self._impl.revoke_role(role_id=role_id, user_id=user_id,
                                      project_id=project_id)

    def list_roles(self, user_id=None, project_id=None, domain_name=None):
        """List all roles."""
        return [self._unify_role(role) for role in self._impl.list_roles(
            user_id=user_id, project_id=project_id, domain_name=domain_name)]

    def create_ec2credentials(self, user_id, project_id):
        """Create ec2credentials.

        :param user_id: User ID for which to create credentials
        :param project_id: Project ID for which to create credentials

        :returns: Created ec2-credentials object
        """
        return self._impl.create_ec2credentials(user_id=user_id,
                                                project_id=project_id)
