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

import copy
import dataclasses
import typing as t

from rally.common import logging


if t.TYPE_CHECKING:
    from rally_openstack.common import osclients


LOG = logging.getLogger(__file__)


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
    auth: t.Any
    discovery_cache: dict[str, t.Any]

    # TODO(andreykurilin): deprecate permission and endpoint
    permission: t.Any
    endpoint: str | None

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
        auth: t.Any = None,
        discovery_cache: dict[str, t.Any] | None = None,
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
        self.auth = auth
        self.discovery_cache = (
            {} if discovery_cache is None else discovery_cache)
        self.permission = permission
        self.endpoint = endpoint
        # per-credential runtime cache reused by :meth:`clients`; not a field,
        # so it never lands in :meth:`to_dict` / deepcopy.
        self._clients_cache: dict[str, t.Any] = {}

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
    def __getitem__(
        self, key: t.Literal["discovery_cache"]
    ) -> dict[str, t.Any]: ...

    @t.overload
    def __getitem__(self, key: t.Literal[
        "permission", "endpoint_type", "https_cert", "auth"]) -> t.Any: ...

    def __getitem__(self, key: str) -> t.Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: t.Any) -> None:
        setattr(self, key, value)

    def to_dict(self) -> dict[str, t.Any]:
        return {f.name: getattr(self, f.name)
                for f in dataclasses.fields(self)}

    def __deepcopy__(
        self, memodict: dict | None = None
    ) -> "OpenStackCredential":
        return self.__class__(**copy.deepcopy(self.to_dict()))

    @logging.log_deprecated(
        "build the container explicitly instead: "
        "osclients.Clients(credential)",
        "4.2.0", once=True)
    def clients(self) -> "osclients.Clients":
        from rally_openstack.common import osclients

        return osclients.Clients(self, cache=self._clients_cache)
