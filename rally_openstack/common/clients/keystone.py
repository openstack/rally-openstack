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

import copy
import functools
import json
import os
import typing as t
import uuid
from urllib.parse import urlparse
from urllib.parse import urlunparse

from rally import exceptions
from rally.common import cfg
from rally.common import logging
from rally.task import atomic

from rally_openstack.common.clients import base


if t.TYPE_CHECKING:
    import typing_extensions as te
    from keystoneauth1 import access
    from keystoneauth1 import identity
    from keystoneauth1 import session
    from keystoneauth1.access import service_catalog as ks_service_catalog
    from openstack.identity.v2 import _proxy as v2_proxy
    from openstack.identity.v2 import role as v2_role
    from openstack.identity.v2 import tenant as v2_tenant
    from openstack.identity.v2 import user as v2_user
    from openstack.identity.v3 import _proxy as v3_proxy
    from openstack.identity.v3 import credential as v3_credential
    from openstack.identity.v3 import domain as v3_domain
    from openstack.identity.v3 import project as v3_project
    from openstack.identity.v3 import role as v3_role
    from openstack.identity.v3 import role_domain_user_assignment
    from openstack.identity.v3 import role_project_user_assignment
    from openstack.identity.v3 import service
    from openstack.identity.v3 import user as v3_user

    Project = v2_tenant.Tenant | v3_project.Project
    User = v2_user.User | v3_user.User
    Role = v2_role.Role | v3_role.Role
    RoleAssignment = (
        role_project_user_assignment.RoleProjectUserAssignment
        | role_domain_user_assignment.RoleDomainUserAssignment
    )


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


@base.configure(
    "keystone", sdk_service_type="identity", supported_versions=("2", "3")
)
class Keystone(base.LegacyClientCompat):
    """Identity (keystone) client backed by openstacksdk.

    Provides version-agnostic identity operations that work against both
    Keystone v2 and v3. Each operation records a ``keystone.<op>`` atomic
    action wrapping the version-specific ``keystone_v{2,3}.<op>`` one.
    """

    # process-wide guard so the legacy-client deprecation is logged only once
    _legacy_deprecation_logged = False

    @property
    def keystone(self) -> t.NoReturn:
        raise exceptions.RallyException(
            "Method 'keystone' is restricted for keystoneclient. :)")

    @property
    def service_catalog(self) -> ks_service_catalog.ServiceCatalog:
        return self.auth_ref.service_catalog

    @property
    def auth_ref(self) -> access.AccessInfo:
        try:
            if "keystone_auth_ref" not in self._cache:
                sess, plugin = self.get_session()
                self._cache["keystone_auth_ref"] = plugin.get_access(sess)
        except Exception as original_e:
            e = base.AuthenticationFailed(
                error=original_e,
                username=self.credential.username,
                project=self.credential.tenant_name,
                url=self.credential.auth_url
            )
            if logging.is_debug() and e.is_trace_helpful():
                LOG.exception(
                    f"Unable to authenticate for user "
                    f"{self.credential.username} in project "
                    f"{self.credential.tenant_name}"
                )

            raise e from None
        return self._cache["keystone_auth_ref"]

    def get_session(
        self, version: str | None = None
    ) -> tuple[session.Session, identity.Password]:
        key = f"keystone_session_and_plugin_{version}"
        if key not in self._cache:
            from keystoneauth1 import discover
            from keystoneauth1 import identity
            from keystoneauth1 import session

            version = self.spec.choose_version(self.credential, version)
            auth_url = self.credential.auth_url
            if version is not None:
                auth_url = self._remove_url_version()

            # Arguments for the Password plugin; domain args are added below
            # for v3.
            password_args: dict[str, t.Any] = {
                "auth_url": auth_url,
                "username": self.credential.username,
                "password": self.credential.password,
                "tenant_name": self.credential.tenant_name
            }

            if version is None:
                # NOTE(rvasilets): If version not specified than we discover
                # available version with the smallest number. To be able to
                # discover versions we need session
                temp_session = session.Session(
                    verify=(self.credential.https_cacert
                            or not self.credential.https_insecure),
                    cert=self.credential.https_cert,
                    timeout=CONF.openstack_client_http_timeout)
                version = str(discover.Discover(
                    temp_session,
                    password_args["auth_url"]).version_data()[0]["version"][0])
                temp_session.session.close()

            if "v2.0" not in password_args["auth_url"] and version != "2":
                password_args.update({
                    "user_domain_name": self.credential.user_domain_name,
                    "domain_name": self.credential.domain_name,
                    "project_domain_name": self.credential.project_domain_name
                })
            identity_plugin = identity.Password(**password_args)
            if self.credential.auth:
                # Reuse the authentication captured by the context instead of
                # re-authenticating; the Password plugin still refreshes the
                # token itself once it expires.
                identity_plugin.set_auth_state(self.credential.auth)
            sess = session.Session(
                auth=identity_plugin,
                verify=(self.credential.https_cacert
                        or not self.credential.https_insecure),
                cert=self.credential.https_cert,
                timeout=CONF.openstack_client_http_timeout,
                discovery_cache=self.credential.discovery_cache
            )
            self._cache[key] = (sess, identity_plugin)
        return self._cache[key]

    def _remove_url_version(self) -> str:
        """Remove any version from the auth_url.

        The keystone Client code requires that auth_url be the root url
        if a version override is used.
        """
        url = urlparse(self.credential.auth_url)
        path = url.path.rstrip("/")
        if path.endswith("v2.0") or path.endswith("v3"):
            path = os.path.join(*os.path.split(path)[:-1])
            parts = (url.scheme, url.netloc, path, url.params, url.query,
                     url.fragment)
            return urlunparse(parts)
        return self.credential.auth_url

    @property
    def identity_endpoint_override(self) -> str:
        """Versioned identity endpoint so openstacksdk skips version discovery.

        Pointing openstacksdk at a versioned identity endpoint stops it from
        re-discovering the identity version when the proxy is created, which is
        how the legacy keystone client behaved. Uses the version pinned in
        api_info when set, otherwise the version already present in
        ``auth_url``.
        """
        version = self.spec.choose_version(self.credential)
        if version is None:
            return self.credential.auth_url
        base = self._remove_url_version().rstrip("/")
        suffix = "v2.0" if str(version) == "2" else f"v{version}"
        return f"{base}/{suffix}"

    def create_client(self, version: str | int | None = None) -> t.Any:
        """Return a keystone client.

        :param version: Keystone API version, can be one of:
            ("2", "3")

        If this object was constructed with a version in the api_info
        then that will be used unless the version parameter is passed.
        """

        if not Keystone._legacy_deprecation_logged:
            LOG.warning(
                "Accessing the raw python-keystoneclient via "
                "`clients.keystone(...)` is deprecated and will be "
                "removed. Use the rally-owned identity client (the "
                "`clients.keystone` attribute, or "
                "`clients.keystone(legacy=False)`) instead."
            )
            Keystone._legacy_deprecation_logged = True

        import keystoneclient
        from keystoneclient import client

        # Use the version in the api_info if provided, otherwise fall
        # back to the passed version (which may be None, in which case
        # keystoneclient chooses).
        version = self.spec.choose_version(self.credential, version)

        sess, auth_plugin = self.get_session(version=version)

        kw = {"version": version, "session": sess,
              "timeout": CONF.openstack_client_http_timeout}
        # check for keystone version
        if auth_plugin._user_domain_name and self.credential.region_name:
            kw["region_name"] = self.credential.region_name

        if keystoneclient.__version__[0] == "1":
            # NOTE(andreykurilin): let's leave this hack for envs which uses
            #  old(<2.0.0) keystoneclient version. Upstream fix:
            #  https://github.com/openstack/python-keystoneclient/commit/d9031c252848d89270a543b67109a46f9c505c86
            from keystoneauth1 import plugin
            kw["auth_url"] = sess.get_endpoint(interface=plugin.AUTH_INTERFACE)
        if self.credential.endpoint_type:
            kw["interface"] = self.credential.endpoint_type

        # NOTE(amyge):
        # In auth_ref(), plugin.get_access(sess) only returns a auth_ref object
        # and won't check the authentication access until it is actually being
        # called. To catch the authentication failure in auth_ref(), we will
        # have to call self.auth_ref.auth_token here to actually use auth_ref.
        self.auth_ref

        return client.Client(**kw)

    @t.overload
    def __call__(
        self, version: str | int | None = ..., *, legacy: t.Literal[False]
    ) -> te.Self: ...

    @t.overload
    def __call__(
        self, version: str | int | None = ..., *, legacy: t.Literal[True] = ...
    ) -> t.Any: ...

    def __call__(
        self, version: str | int | None = None, *, legacy: bool = True
    ) -> t.Any:
        """Return an identity client.

        :param version: API major version to pin to.
        :param legacy: when true (the default, for backward compatibility),
            return the raw ``python-keystoneclient``. This is deprecated and
            emits a warning. Pass ``legacy=False`` to get this client instead,
            pinned to ``version`` when given.
        """
        if legacy:
            key = f"keystone_legacy_client_{version}"
            if key not in self._cache:
                self._cache[key] = self.create_client(version)
            return self._cache[key]
        if version is None or str(version) == self.version:
            return self
        if self._clients is None:
            raise exceptions.RallyException(
                "Cannot pin a version on a client that is not attached to a "
                "Clients container.")
        return self._clients.override(keystone=str(version)).keystone

    @functools.cached_property
    def version(self) -> str:
        major = self._identity.get_api_major_version()
        if not major:
            raise exceptions.RallyException(
                "Unable to determine the identity API version.")
        return str(major[0])

    @property
    def _identity(self) -> v2_proxy.Proxy | v3_proxy.Proxy:
        return self._conn.identity

    @property
    def _v2(self) -> v2_proxy.Proxy:
        if self.version != "2":
            raise exceptions.RallyException(
                f"identity v2 proxy requested while running v{self.version}.")
        return t.cast("v2_proxy.Proxy", self._conn.identity)

    @property
    def _v3(self) -> v3_proxy.Proxy:
        if self.version != "3":
            raise exceptions.RallyException(
                f"identity v3 proxy requested while running v{self.version}.")
        return t.cast("v3_proxy.Proxy", self._conn.identity)

    @property
    def _auth_domain(self) -> tuple[str | None, str | None]:
        session = self._conn.session
        auth = session.auth
        if auth is None:
            return None, None
        ref = auth.get_auth_ref(session)
        if ref is None:
            return None, None
        return ref.project_domain_name, ref.project_domain_id

    def get_domain_id(self, domain_name_or_id: str) -> str:
        auth_name, auth_id = self._auth_domain
        if auth_id and domain_name_or_id in (auth_name, auth_id):
            return auth_id
        from openstack import exceptions as sdk_exc
        with self._atomic_action("keystone_v3.get_domain"):
            try:
                return self._v3.get_domain(domain_name_or_id).id
            except sdk_exc.ResourceNotFound:
                pass
            for domain in self._v3.domains(name=domain_name_or_id):
                return domain.id
        raise exceptions.GetResourceNotFound(
            resource=f"KeystoneDomain({domain_name_or_id})")

    @atomic.action_timer("keystone.create_project")
    def create_project(
        self, project_name: str | None = None,
        domain: str = "Default",
    ) -> Project:
        project_name = project_name or self.generate_random_name()
        if self.version == "2":
            with self._atomic_action("keystone_v2.create_tenant"):
                return self._v2.create_tenant(name=project_name)
        domain_id = self.get_domain_id(domain)
        with self._atomic_action("keystone_v3.create_project"):
            return self._v3.create_project(
                name=project_name, domain_id=domain_id)

    @atomic.action_timer("keystone.update_project")
    def update_project(
        self, project_id: str, name: str | None = None,
        enabled: bool | None = None,
        description: str | None = None,
    ) -> None:
        attrs: dict[str, t.Any] = {}
        if name is not None:
            attrs["name"] = name
        if enabled is not None:
            attrs["is_enabled"] = enabled
        if description is not None:
            attrs["description"] = description
        if self.version == "2":
            with self._atomic_action("keystone_v2.update_tenant"):
                self._v2.update_tenant(project_id, **attrs)
        else:
            with self._atomic_action("keystone_v3.update_project"):
                self._v3.update_project(project_id, **attrs)

    @atomic.action_timer("keystone.delete_project")
    def delete_project(self, project_id: str) -> None:
        if self.version == "2":
            with self._atomic_action("keystone_v2.delete_tenant"):
                self._v2.delete_tenant(project_id)
        else:
            with self._atomic_action("keystone_v3.delete_project"):
                self._v3.delete_project(project_id)

    @atomic.action_timer("keystone.list_projects")
    def list_projects(self) -> list[Project]:
        if self.version == "2":
            with self._atomic_action("keystone_v2.list_tenants"):
                return list(self._v2.tenants())
        with self._atomic_action("keystone_v3.list_projects"):
            return list(self._v3.projects())

    @atomic.action_timer("keystone.get_project")
    def get_project(self, project_id: str) -> Project:
        if self.version == "2":
            with self._atomic_action("keystone_v2.get_tenant"):
                return self._v2.get_tenant(project_id)
        with self._atomic_action("keystone_v3.get_project"):
            return self._v3.get_project(project_id)

    @atomic.action_timer("keystone.create_user")
    def create_user(
        self,
        username: str | None = None,
        password: str | None = None,
        project_id: str | None = None,
        domain: str = "Default",
        enabled: bool = True,
    ) -> User:
        if self.version == "2":
            with self._atomic_action("keystone_v2.create_user"):
                return self._identity.create_user(
                    name=username or self.generate_random_name(),
                    password=password,
                    tenant_id=project_id,
                    is_enabled=enabled
                )

        domain_id = self.get_domain_id(domain)
        with self._atomic_action("keystone_v3.create_user"):
            user = self._identity.create_user(
                name=username or self.generate_random_name(),
                password=password,
                default_project_id=project_id,
                domain_id=domain_id,
                is_enabled=enabled
            )
        return user

    @atomic.action_timer("keystone.update_user")
    def update_user(
        self,
        user_id: str,
        enabled: bool | None = None,
        name: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        attrs: dict[str, t.Any] = {}
        if name is not None:
            attrs["name"] = name
        if email is not None:
            attrs["email"] = email
        if enabled is not None:
            attrs["is_enabled"] = enabled
        if self.version == "2":
            with self._atomic_action("keystone_v2.update_user"):
                if attrs:
                    self._identity.update_user(user_id, **attrs)
                if password is not None:
                    # v2 has no password attribute on the user resource; the
                    # password is changed through a dedicated endpoint.
                    self._identity.put(
                        f"/users/{user_id}/OS-KSADM/password",
                        json={"user": {"password": password}}
                    )
            return
        if password is not None:
            attrs["password"] = password
        with self._atomic_action("keystone_v3.update_user"):
            self._identity.update_user(user_id, **attrs)

    @atomic.action_timer("keystone.delete_user")
    def delete_user(self, user_id: str) -> None:
        with self._atomic_action(f"keystone_v{self.version}.delete_user"):
            self._identity.delete_user(user_id)

    @atomic.action_timer("keystone.list_users")
    def list_users(self) -> list[User]:
        with self._atomic_action(f"keystone_v{self.version}.list_users"):
            return list(self._identity.users())

    @atomic.action_timer("keystone.get_user")
    def get_user(self, user_id: str) -> User:
        with self._atomic_action(f"keystone_v{self.version}.get_user"):
            return self._identity.get_user(user_id)

    @atomic.action_timer("keystone.create_role")
    def create_role(
        self,
        name: str | None = None,
        domain: str | None = None,
    ) -> Role:
        name = name or self.generate_random_name()
        if self.version == "2":
            with self._atomic_action("keystone_v2.create_role"):
                return self._identity.create_role(name=name)
        attrs: dict[str, t.Any] = {"name": name}
        if domain:
            attrs["domain_id"] = self.get_domain_id(domain)
        with self._atomic_action("keystone_v3.create_role"):
            return self._identity.create_role(**attrs)

    @atomic.action_timer("keystone.add_role")
    def add_role(self, role_id: str, user_id: str, project_id: str) -> None:
        if self.version == "2":
            with self._atomic_action("keystone_v2.add_role"):
                self._identity.put(
                    f"/tenants/{project_id}/"
                    f"users/{user_id}/roles/OS-KSADM/{role_id}"
                )
            return
        with self._atomic_action("keystone_v3.add_role"):
            self._v3.assign_project_role_to_user(
                project_id, user_id, role_id)

    @atomic.action_timer("keystone.revoke_role")
    def revoke_role(self, role_id: str, user_id: str, project_id: str) -> None:
        if self.version == "2":
            with self._atomic_action("keystone_v2.revoke_role"):
                self._identity.delete(
                    f"/tenants/{project_id}/"
                    f"users/{user_id}/roles/OS-KSADM/{role_id}"
                )
            return
        with self._atomic_action("keystone_v3.revoke_role"):
            self._v3.unassign_project_role_from_user(
                project_id, user_id, role_id)

    @atomic.action_timer("keystone.list_roles")
    def list_roles(
        self, *, name: str | None = None, domain: str | None = None,
    ) -> list[Role]:
        """List role definitions."""
        if self.version == "2":
            with self._atomic_action("keystone_v2.list_roles"):
                roles: list[Role] = list(self._identity.roles())
            # keystone v2 has no name filter; match client-side.
            if name is not None:
                roles = [r for r in roles if r.name == name]
            return roles
        query: dict[str, t.Any] = {}
        if name:
            query["name"] = name
        if domain:
            query["domain_id"] = self.get_domain_id(domain)
        with self._atomic_action("keystone_v3.list_roles"):
            return list(self._v3.roles(**query))

    def find_role(self, name: str) -> Role | None:
        """Return the role definition matching ``name``, or None.

        Matching is case-insensitive and tolerates the underscore decoration
        keystone puts around some built-in roles: ``member`` matches
        ``_member_``. An exact match anywhere in the list wins over a
        decorated one, so a cloud carrying both ``member`` and ``_member_``
        resolves to the former.
        """
        roles = self.list_roles()
        name = name.lower()
        for role in roles:
            if role.name.lower() == name:
                return role
        for role in roles:
            if role.name.lower().strip("_") == name:
                return role
        return None

    @atomic.action_timer("keystone.list_role_assignments")
    def list_role_assignments(
        self, user_id: str, *, project_id: str | None = None,
        domain: str | None = None,
    ) -> list[RoleAssignment]:
        """List the roles assigned to a user on a project or domain.

        Reads the role-grants endpoint (``.../users/{id}/roles``), so the
        result describes what the user is granted in one scope, not the
        assignment records keystone v3 serves at ``/role_assignments``.

        Keystone v3 requires a scope: pass ``project_id`` or ``domain``
        (``domain`` wins if both are given). Keystone v2 also accepts neither,
        listing the user's roles across all tenants.
        """
        if self.version == "2":
            from openstack.identity.v3 import role_project_user_assignment

            path = (f"/tenants/{project_id}/users/{user_id}/roles"
                    if project_id else f"/users/{user_id}/roles")
            with self._atomic_action("keystone_v2.list_role_assignments"):
                resp = self._identity.get(path)
                # v2 answers with bare role dicts; wrap them in the resource
                # the v3 branch returns so both versions look the same. The
                # scope is not echoed by the API, so it is carried over from
                # the request (project_id is None for the all-tenants case).
                return [
                    role_project_user_assignment.RoleProjectUserAssignment(
                        project_id=project_id, user_id=user_id, **r)
                    for r in resp.json()["roles"]]
        domain_id = self.get_domain_id(domain) if domain else None
        with self._atomic_action("keystone_v3.list_role_assignments"):
            return list(self._v3.role_assignments_filter(
                user=user_id, project=project_id, domain=domain_id))

    @atomic.action_timer("keystone.delete_role")
    def delete_role(self, role_id: str) -> None:
        with self._atomic_action(f"keystone_v{self.version}.delete_role"):
            self._identity.delete_role(role_id)

    @atomic.action_timer("keystone.get_role")
    def get_role(self, role_id: str) -> Role:
        with self._atomic_action(f"keystone_v{self.version}.get_role"):
            return self._identity.get_role(role_id)

    @atomic.action_timer("keystone.create_service")
    def create_service(
        self, name: str | None = None,
        service_type: str | None = None,
        description: str | None = None,
    ) -> service.Service:
        name = name or self.generate_random_name()
        service_type = service_type or "rally_test_type"
        description = description or self.generate_random_name()
        if self.version == "2":
            from openstack.identity.v3 import service

            with self._atomic_action("keystone_v2.create_service"):
                body = {
                    "OS-KSADM:service": {
                        "name": name,
                        "type": service_type,
                        "description": description
                    }
                }
                resp = self._identity.post("/OS-KSADM/services", json=body)
                return service.Service(**resp.json()["OS-KSADM:service"])
        with self._atomic_action("keystone_v3.create_service"):
            return self._v3.create_service(
                name=name,
                type=service_type,
                description=description,
                is_enabled=True
            )

    @atomic.action_timer("keystone.delete_service")
    def delete_service(self, service_id: str) -> None:
        if self.version == "2":
            with self._atomic_action("keystone_v2.delete_service"):
                self._identity.delete(f"/OS-KSADM/services/{service_id}")
            return
        with self._atomic_action("keystone_v3.delete_service"):
            self._v3.delete_service(service_id)

    @atomic.action_timer("keystone.list_services")
    def list_services(
        self, *, name: str | None = None
    ) -> list[service.Service]:
        if self.version == "2":
            from openstack.identity.v3 import service

            with self._atomic_action("keystone_v2.list_services"):
                resp = self._identity.get("/OS-KSADM/services")
                services: list[service.Service] = [
                    service.Service(**s)
                    for s in resp.json()["OS-KSADM:services"]]
            # keystone v2 (OS-KSADM) has no name filter; match client-side.
            if name is not None:
                services = [s for s in services if s.name == name]
            return services
        query = {"name": name} if name is not None else {}
        with self._atomic_action("keystone_v3.list_services"):
            return list(self._v3.services(**query))

    @atomic.action_timer("keystone.get_service")
    def get_service(self, service_id: str) -> service.Service:
        if self.version == "2":
            from openstack.identity.v3 import service

            with self._atomic_action("keystone_v2.get_services"):
                resp = self._identity.get(
                    f"/OS-KSADM/services/{service_id}")
                return service.Service(**resp.json()["OS-KSADM:service"])
        with self._atomic_action("keystone_v3.get_services"):
            return self._v3.get_service(service_id)

    @atomic.action_timer("keystone.create_domain")
    def create_domain(
        self, name: str, description: str | None = None,
        is_enabled: bool = True,
    ) -> v3_domain.Domain:
        with self._atomic_action("keystone_v3.create_domain"):
            return self._v3.create_domain(
                name=name, description=description, is_enabled=is_enabled)

    @atomic.action_timer("keystone.create_credential")
    def create_credential(
        self, cred_type: str, user_id: str | None = None,
        project_id: str | None = None, blob: str | None = None,
    ) -> v3_credential.Credential:
        """Create a credential of any ``cred_type`` (``ec2``, ``cert``, ...).

        Keystone v3 uses the generic ``/v3/credentials`` API, where the caller
        supplies the ``blob``; for ``ec2`` an ``access``/``secret`` pair is
        generated when none is given. Keystone v2 has no generic credentials
        API and supports only ``ec2``, which goes through the OS-EC2 extension
        (keystone generates the pair). Both cases return an openstacksdk
        ``Credential`` so callers get the same type on either version.
        """
        user_id = user_id or self.auth_ref.user_id
        if self.version == "2":
            if cred_type != "ec2":
                raise exceptions.RallyException(
                    "Keystone v2 supports only 'ec2' credentials.")
            return self._create_ec2_credential_v2(user_id, project_id)
        if cred_type == "ec2" and blob is None:
            blob = json.dumps({"access": uuid.uuid4().hex,
                               "secret": uuid.uuid4().hex})
        with self._atomic_action("keystone_v3.create_credential"):
            return self._v3.create_credential(
                blob=blob, type=cred_type, user_id=user_id,
                project_id=project_id
            )

    @atomic.action_timer("keystone.get_credential")
    def get_credential(self, credential_id: str) -> v3_credential.Credential:
        if self.version == "2":
            user_id = self.auth_ref.user_id
            with self._atomic_action("keystone_v2.get_credential"):
                resp = self._identity.get(
                    f"/users/{user_id}/credentials/OS-EC2/{credential_id}")
                return self._ec2_to_credential(resp.json()["credential"])
        with self._atomic_action("keystone_v3.get_credential"):
            return self._v3.get_credential(credential_id)

    @atomic.action_timer("keystone.list_credentials")
    def list_credentials(
        self, *, user_id: str | None = None, cred_type: str | None = None,
    ) -> list[v3_credential.Credential]:
        if self.version == "2":
            if cred_type not in (None, "ec2"):
                raise exceptions.RallyException(
                    "Keystone v2 supports only 'ec2' credentials.")
            user_id = user_id or self.auth_ref.user_id
            with self._atomic_action("keystone_v2.list_credentials"):
                resp = self._identity.get(
                    f"/users/{user_id}/credentials/OS-EC2")
                return [self._ec2_to_credential(c)
                        for c in resp.json()["credentials"]]
        query: dict[str, t.Any] = {}
        if user_id:
            query["user_id"] = user_id
        if cred_type:
            query["type"] = cred_type
        with self._atomic_action("keystone_v3.list_credentials"):
            return list(self._v3.credentials(**query))

    @atomic.action_timer("keystone.delete_credential")
    def delete_credential(self, credential_id: str) -> None:
        if self.version == "2":
            user_id = self.auth_ref.user_id
            with self._atomic_action("keystone_v2.delete_credential"):
                self._identity.delete(
                    f"/users/{user_id}/credentials/OS-EC2/{credential_id}")
            return
        with self._atomic_action("keystone_v3.delete_credential"):
            self._v3.delete_credential(credential_id)

    def _create_ec2_credential_v2(
        self, user_id: str | None, project_id: str | None
    ) -> v3_credential.Credential:
        with self._atomic_action("keystone_v2.create_credential"):
            resp = self._identity.post(
                f"/users/{user_id}/credentials/OS-EC2",
                json={"tenant_id": project_id})
            return self._ec2_to_credential(resp.json()["credential"])

    @staticmethod
    def _ec2_to_credential(data: dict[str, t.Any]) -> v3_credential.Credential:
        """Wrap a raw OS-EC2 credential dict as an openstacksdk Credential.

        The v3 ``Credential.id`` doubles as the OS-EC2 delete key on v2, so the
        ``access`` key is stored there (``delete_credential`` then works
        version-agnostically with ``credential.id``).
        """
        from openstack.identity.v3 import credential as v3_credential
        return v3_credential.Credential(
            id=data.get("access"),
            type="ec2",
            blob=json.dumps(data),
            user_id=data.get("user_id"),
            project_id=data.get("tenant_id"))

    def close(self) -> None:
        """Close the keystoneauth sessions opened by this client."""
        for key in [k for k in self._cache
                    if k.startswith("keystone_session_and_plugin_")]:
            sess, _plugin = self._cache.pop(key)
            sess.session.close()
        self._cache.pop("keystone_auth_ref", None)

    @atomic.action_timer("keystone.fetch_token")
    def fetch_token(self) -> str:
        with self._atomic_action(f"keystone_v{self.version}.fetch_token"):
            # Build a fresh client with the cached token cleared so this
            # measures a real authentication instead of returning the token
            # the context already fetched. Its session is private to that
            # client, so it has to be closed here -- otherwise every iteration
            # of this scenario would leak a connection pool.
            credential = copy.deepcopy(self.credential)
            credential.auth = None
            client = Keystone(credential)
            try:
                token = client.auth_ref.auth_token
            finally:
                client.close()
            if token is None:
                raise exceptions.RallyException("Failed to fetch auth token.")
            return token

    @atomic.action_timer("keystone.validate_token")
    def validate_token(self, token: str) -> None:
        if self.version == "2":
            with self._atomic_action("keystone_v2.validate_token"):
                self._identity.get(f"/tokens/{token}")
            return
        with self._atomic_action("keystone_v3.validate_token"):
            self._v3.validate_token(token)
