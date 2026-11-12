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

from __future__ import annotations

import copy
import dataclasses
import traceback
import types
import typing as t

from rally.common import logging


if t.TYPE_CHECKING:
    from rally.task import atomic

    from rally_openstack.common import osclients


LOG = logging.getLogger(__file__)

# (file, line) of the callers already warned for omitting clients() arguments,
# so each wrong call site is reported once rather than on every call
_reported_implicit_clients_callers: set[tuple[str, int | None]] = set()


class ServiceApiInfo(t.TypedDict, total=False):
    """One service's entry in :attr:`OpenStackCredential.api_info`.

    ``api_info`` is keyed by client name (``"nova"``, ``"keystone"``, ...) and
    populated from the platform spec and the ``api_versions`` context. All keys
    are optional.
    """

    #: API version to use, e.g. ``2`` or ``"2.2"``
    version: str | int | float
    #: service type overriding the default catalog lookup
    service_type: str
    #: service name (resolved to a service type by the api_versions context)
    service_name: str
    #: neutron only: whether the Neutron API predates OpenStack Newton
    pre_newton: bool


@dataclasses.dataclass(init=False)
class OpenStackCredential:
    """Credential for OpenStack.

    A typed data holder for one OpenStack user's connection details. It crosses
    the pickle boundary into worker processes, so it stays plain data. Legacy
    dict-style item access (``credential["auth_url"]``) is preserved through
    :meth:`__getitem__` / :meth:`__setitem__` for backward compatibility;
    new code should prefer attribute access (``credential.auth_url``).

    ``tenant_name`` and ``https_key`` are constructor-only aliases: the former
    is the legacy name of ``project_name`` that platform data stored in the
    database may still carry, the latter is merged into ``https_cert``.
    """

    auth_url: str
    username: str
    password: str
    project_name: str
    region_name: str | None
    endpoint_type: t.Any
    domain_name: str | None
    user_domain_name: str | None
    project_domain_name: str | None
    https_insecure: bool
    https_cacert: str | None
    https_cert: t.Any
    profiler_hmac_key: str | None
    profiler_conn_str: str | None
    api_info: dict[str, ServiceApiInfo]

    # TODO(andreykurilin): deprecate permission and endpoint
    permission: t.Any
    endpoint: str | None

    # The output of keystoneauth's ``get_auth_state()`` for this user: the
    # token plus the full token response (roles, catalog, expiry). Clients
    # load it instead of authenticating again.
    _auth_state: str | None = dataclasses.field(repr=False, compare=False)
    # Facts about the cloud, keyed by client name (e.g. keystoneauth
    # discovery results under "keystone", extension aliases under "neutron").
    # The users context points every credential of a task at the same dict.
    # It is kept apart from ``_auth_state`` because the token belongs to one
    # user and must never be copied to another, while these facts are the
    # same for everyone: one shared dict needs no copying at all.
    _cloud_state: dict[str, dict[str, t.Any]] = dataclasses.field(
        repr=False, compare=False)

    def __init__(
        self,
        auth_url: str,
        username: str,
        password: str,
        project_name: str | None = None,
        region_name: str | None = None,
        endpoint_type: t.Any = None,
        domain_name: str | None = None,
        user_domain_name: str | None = None,
        project_domain_name: str | None = None,
        https_insecure: bool = False,
        https_cacert: str | None = None,
        https_cert: t.Any = None,
        profiler_hmac_key: str | None = None,
        profiler_conn_str: str | None = None,
        api_info: dict[str, ServiceApiInfo] | None = None,
        permission: t.Any = None,
        endpoint: str | None = None,
        tenant_name: str | None = None,
        https_key: str | None = None,
    ) -> None:
        project_name = project_name or tenant_name
        if not project_name:
            raise TypeError(
                "OpenStackCredential requires 'project_name' (or its legacy "
                "alias 'tenant_name').")
        self.auth_url = auth_url
        self.username = username
        self.password = password
        self.project_name = project_name
        self.region_name = region_name
        self.endpoint_type = endpoint_type
        self.domain_name = domain_name
        self.user_domain_name = user_domain_name
        self.project_domain_name = project_domain_name
        self.https_insecure = https_insecure
        self.https_cacert = https_cacert
        self.https_cert = https_cert
        if https_cert and https_key:
            self.https_cert = (https_cert, https_key)
        self.profiler_hmac_key = profiler_hmac_key
        self.profiler_conn_str = profiler_conn_str
        self.api_info = {} if api_info is None else api_info
        self.permission = permission
        self.endpoint = endpoint
        self._auth_state = None
        self._cloud_state = {}

    @property
    @logging.log_deprecated("use 'project_name' instead", "4.2.0", once=True)
    def tenant_name(self) -> str:
        return self.project_name

    @t.overload
    def __getitem__(
        self,
        key: t.Literal[
            "auth_url", "username", "password", "project_name", "tenant_name"
        ],
    ) -> str: ...

    @t.overload
    def __getitem__(
        self,
        key: t.Literal[
            "region_name",
            "domain_name",
            "endpoint",
            "user_domain_name",
            "project_domain_name",
            "https_cacert",
            "profiler_hmac_key",
            "profiler_conn_str",
        ],
    ) -> str | None: ...

    @t.overload
    def __getitem__(self, key: t.Literal["https_insecure"]) -> bool: ...

    @t.overload
    def __getitem__(
        self, key: t.Literal["api_info"]
    ) -> dict[str, ServiceApiInfo]: ...

    @t.overload
    def __getitem__(self, key: t.Literal[
        "permission", "endpoint_type", "https_cert"]) -> t.Any: ...

    def __getitem__(self, key: str) -> t.Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: t.Any) -> None:
        setattr(self, key, value)

    def to_dict(self) -> dict[str, t.Any]:
        return {f.name: getattr(self, f.name)
                for f in dataclasses.fields(self)
                if not f.name.startswith("_")}

    def __deepcopy__(
        self, memo: dict[int, t.Any] | None = None
    ) -> OpenStackCredential:
        # ``memo`` must reach the copy of every field: the runner deep-copies
        # the whole context once per iteration, and passing it on is what
        # keeps ``_cloud_state`` one dict shared by all the copied
        # credentials instead of one copy per user.
        memo = {} if memo is None else memo
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        for f in dataclasses.fields(self):
            setattr(new, f.name, copy.deepcopy(getattr(self, f.name), memo))
        return new

    def clients(
        self,
        *,
        atomic_inst: (
            list[atomic.AtomicAction] | None | types.EllipsisType) = ...,
        name_generator: (
            t.Callable[[], str] | None | types.EllipsisType) = ...,
        sleeper: (
            t.Callable[[float], None] | None | types.EllipsisType) = ...,
    ) -> osclients.Clients:
        """Build a Clients container for this credential.

        Every argument has to be passed explicitly, ``None`` included, so a
        caller states whether its clients record atomic actions, generate
        resource names and track idle time. An omitted one is treated as
        ``None`` and logged as deprecated.
        """
        from rally_openstack.common import osclients

        omitted = [
            name for name, value in (
                ("atomic_inst", atomic_inst),
                ("name_generator", name_generator),
                ("sleeper", sleeper),
            ) if isinstance(value, types.EllipsisType)
        ]
        if omitted:
            caller = traceback.extract_stack()[-2]
            key = (caller.filename, caller.lineno)
            if key not in _reported_implicit_clients_callers:
                _reported_implicit_clients_callers.add(key)
                LOG.warning(
                    f"Calling `OpenStackCredential.clients()` without "
                    f"{', '.join(omitted)} is deprecated since 4.2.0. Pass "
                    f"every argument explicitly (None to disable it). Used "
                    f"at {caller.filename}:{caller.lineno}")

        if isinstance(atomic_inst, types.EllipsisType):
            atomic_inst = None
        if isinstance(name_generator, types.EllipsisType):
            name_generator = None
        if isinstance(sleeper, types.EllipsisType):
            sleeper = None
        return osclients.Clients(
            self,
            atomic_inst=atomic_inst,
            name_generator=name_generator,
            sleeper=sleeper,
        )
