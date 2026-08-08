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


@dataclasses.dataclass
class OpenStackCredential:
    """Credential for OpenStack.

    A typed data holder for one OpenStack user's connection details. It crosses
    the pickle boundary into worker processes, so it stays plain data. Legacy
    dict-style item access (``credential["auth_url"]``) is preserved through
    :meth:`__getitem__` / :meth:`__setitem__` for backward compatibility;
    new code should prefer attribute access (``credential.auth_url``).

    ``project_name`` and ``https_key`` are constructor-only aliases: the former
    falls back into ``tenant_name``, the latter is merged into ``https_cert``.
    """

    auth_url: str
    username: str
    password: str
    tenant_name: str | None = None
    project_name: dataclasses.InitVar[str | None] = None
    region_name: str | None = None
    endpoint_type: t.Any = None
    domain_name: str | None = None
    user_domain_name: str | None = None
    project_domain_name: str | None = None
    https_insecure: bool = False
    https_cacert: str | None = None
    https_cert: t.Any = None
    https_key: dataclasses.InitVar[str | None] = None
    profiler_hmac_key: str | None = None
    profiler_conn_str: str | None = None
    api_info: dict[str, ServiceApiInfo] = dataclasses.field(
        default_factory=dict)
    auth: t.Any = None
    discovery_cache: dict[str, t.Any] = dataclasses.field(default_factory=dict)

    # TODO(andreykurilin): deprecate permission and endpoint
    permission: t.Any = None
    endpoint: str | None = None

    def __post_init__(
        self, project_name: str | None, https_key: str | None
    ) -> None:
        # TODO(andreykurilin): deprecate permission and endpoint
        if self.tenant_name is None:
            self.tenant_name = project_name
        if self.https_cert and https_key:
            self.https_cert = (self.https_cert, https_key)
        if self.api_info is None:
            self.api_info = {}
        if self.discovery_cache is None:
            self.discovery_cache = {}
        # per-credential runtime cache reused by :meth:`clients`; not a field,
        # so it never lands in :meth:`to_dict` / deepcopy.
        self._clients_cache: dict[str, t.Any] = {}

    @t.overload
    def __getitem__(
        self, key: t.Literal["auth_url", "username", "password"]) -> str: ...

    @t.overload
    def __getitem__(
        self,
        key: t.Literal[
            "tenant_name",
            "project_name",
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
