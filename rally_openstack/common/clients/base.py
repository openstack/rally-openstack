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

import abc
import functools
import typing as t

from rally import exceptions
from rally.common import cfg
from rally.common import logging
from rally.common import utils
from rally.common.plugin import plugin
from rally.task import atomic

from rally_openstack.common import credential as oscred


if t.TYPE_CHECKING:
    import openstack.connection

    from rally_openstack.common import osclients
    from rally_openstack.common.clients import keystone

    ClientT = t.TypeVar("ClientT", bound="BaseClient")


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

# (client class, method name) pairs already reported by @deprecated_legacy, so
# a method called on every request warns once per process rather than per call.
_reported_legacy_usage: set[tuple[str, str]] = set()

F = t.TypeVar("F", bound=t.Callable[..., t.Any])


def deprecated_legacy(f: F) -> F:
    """Warn when a ported client reaches into the legacy compat layer."""
    @functools.wraps(f)
    def wrapper(self_or_cls: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
        cls = (self_or_cls if isinstance(self_or_cls, type)
               else type(self_or_cls))
        if not issubclass(cls, OSClient):
            key = (f"{cls.__module__}.{cls.__qualname__}", f.__name__)
            if key not in _reported_legacy_usage:
                _reported_legacy_usage.add(key)
                LOG.warning(
                    f"`{cls.__name__}.{f.__name__}` comes from the legacy "
                    f"python-*client compatibility layer and is deprecated "
                    f"for clients ported to openstacksdk. It will be removed "
                    f"once the legacy layer goes away."
                )
        return f(self_or_cls, *args, **kwargs)
    return t.cast("F", wrapper)


class AuthenticationFailed(exceptions.AuthenticationFailed):
    error_code = 220

    msg_fmt = ("Failed to authenticate to %(url)s for user '%(username)s'"
               " in project '%(project)s': %(message)s")
    msg_fmt_2 = "%(message)s"

    def __init__(
        self, error: Exception, url: str, username: str, project: str | None
    ) -> None:
        kwargs = {
            "error": error,
            "url": url,
            "username": username,
            "project": project
        }
        self._helpful_trace = False

        from keystoneauth1 import exceptions as ks_exc

        if isinstance(error, (ks_exc.ConnectionError,
                              ks_exc.DiscoveryFailure)):
            # These errors apply to every user, so there is no need to include
            # the username or project name; the original message is enough.
            self.msg_fmt = self.msg_fmt_2
            message = error.message
            if (message.startswith("Unable to establish connection to")
                    or isinstance(error, ks_exc.DiscoveryFailure)):
                if "Max retries exceeded with url" in message:
                    if "HTTPConnectionPool" in message:
                        splitter = ": HTTPConnectionPool"
                    else:
                        splitter = ": HTTPSConnectionPool"
                    message = message.split(splitter, 1)[0]
        elif isinstance(error, ks_exc.Unauthorized):
            message = error.message.split(" (HTTP 401)", 1)[0]
        else:
            # Something unexpected, so include the exception class too.
            self._helpful_trace = True
            message = "[%s] %s" % (error.__class__.__name__, str(error))
        super().__init__(message=message, **kwargs)

    def is_trace_helpful(self) -> bool:
        return self._helpful_trace


class ClientSpec:
    """Type metadata, version resolution and validation for a client class.

    One instance per client class, built by :func:`configure` and reached as
    ``SomeClient.spec``. It holds everything about the client *type*: its
    declared versions and service types, how a requested version or service
    type is resolved against a credential, and version validation. Resolution
    methods take the credential explicitly, so the spec itself stays stateless.

    A client with custom version validation subclasses this and passes it to
    ``configure(spec=...)``.
    """

    def __init__(self, client_cls: type[BaseClient]) -> None:
        self._cls = client_cls

    @property
    def default_version(self) -> str | None:
        return self._cls._meta_get("default_version")

    @property
    def default_service_type(self) -> str | None:
        return self._cls._meta_get("default_service_type")

    @property
    def supported_versions(self) -> list[str]:
        return self._cls._meta_get("supported_versions")

    @property
    def sdk_service_type(self) -> str | None:
        """openstacksdk service type for this client, or None.

        Falls back to ``default_service_type``. This is the openstacksdk name,
        which can differ from the catalog ``default_service_type`` (for example
        magnum). It is used both for the api_info version config on the
        Connection (``<type>_api_version``) and, for ported clients, to pick
        the proxy whose version discovery the ``api_versions`` context warms.
        None means the client is not openstacksdk-backed and contributes to
        neither.
        """
        return (self._cls._meta_get("sdk_service_type")
                or self._cls._meta_get("default_service_type"))

    def choose_version(
        self, credential: oscred.OpenStackCredential, version: t.Any = None
    ) -> str | None:
        """Return the version string for a credential.

        Choose between the transmitted value (preferred if present), the
        version from ``api_info`` (configured by a context) and the default.
        """
        # NOTE(andreykurilin): the result is a string because most clients keep
        # a map of versioned modules keyed by a string version. Clients that
        # need another type (e.g. zaqarclient) override ``choose_version``.
        version = (version
                   or credential.api_info.get(self._cls.get_name(), {}).get(
                       "version") or self.default_version)
        if version is not None:
            version = str(version)
        return version

    def choose_service_type(
        self,
        credential: oscred.OpenStackCredential,
        service_type: str | None = None
    ) -> str | None:
        """Return the service type for a credential.

        Choose between the transmitted value (preferred if present), the
        service type from ``api_info`` and the default.
        """
        return (service_type
                or credential.api_info.get(self._cls.get_name(), {}).get(
                    "service_type") or self.default_service_type)

    def validate_version(self, version: str | int | float) -> None:
        if self.supported_versions:
            if str(version) not in self.supported_versions:
                raise exceptions.ValidationError(
                    f"'{version}' is not supported. Should be one of "
                    f"'{self.supported_versions}'"
                )
        else:
            raise exceptions.RallyException("Setting version is not supported")
        try:
            float(version)
        except ValueError:
            raise exceptions.ValidationError(
                f"'{version}' is invalid. Should be numeric value."
            ) from None

    def is_service_type_configurable(self) -> None:
        """Check that the client supports setting a service type."""
        if self.default_service_type is None:
            raise exceptions.RallyException(
                "Setting service type is not supported.")


def configure(
    name: str,
    default_version: str | None = None,
    default_service_type: str | None = None,
    supported_versions: t.Sequence[str] | None = None,
    sdk_service_type: str | None = None,
    spec: type[ClientSpec] = ClientSpec,
) -> t.Callable[[type[ClientT]], type[ClientT]]:
    """OpenStack client class wrapper.

    Each client class has to be wrapped by configure() wrapper. It sets
    essential configuration of client classes and builds their
    :class:`ClientSpec`.

    :param name: Name of the client
    :param default_version: Default version for client
    :param default_service_type: Default service type of endpoint (if this
        variable is not specified, validation will assume that your client
        doesn't allow to specify service type).
    :param supported_versions: List of supported versions (if this variable is
        not specified, ``ClientSpec.validate_version`` raises that the client
        doesn't support setting any version; a client with custom version rules
        provides a ``spec`` subclass instead).
    :param sdk_service_type: openstacksdk service type this client maps to. It
        drives the api_info version config (openstacksdk keys version config by
        service type, e.g. ``identity_api_version``) and, for ported clients,
        the proxy whose discovery the ``api_versions`` context warms. Set it
        only when the openstacksdk type differs from ``default_service_type``
        (e.g. magnum's ``container_infrastructure_management`` versus the
        catalog's ``container-infra``), or when the client is
        openstacksdk-backed but has no ``default_service_type`` (keystone).
        Falls back to ``default_service_type`` when unset.
    :param spec: :class:`ClientSpec` subclass for client-specific metadata /
        version validation. Defaults to :class:`ClientSpec`.
    """
    def wrapper(cls: type[ClientT]) -> type[ClientT]:
        cls = plugin.configure(name=name, platform="openstack")(cls)
        cls._meta_set("default_version", default_version)
        cls._meta_set("default_service_type", default_service_type)
        cls._meta_set("supported_versions", supported_versions or [])
        cls._meta_set("sdk_service_type", sdk_service_type)
        cls.spec = spec(cls)
        return cls

    return wrapper


@plugin.base()
class BaseClient(plugin.Plugin, atomic.ActionTimerMixin):
    """Base class for an openstacksdk-backed rally client.

    A client is the rally-owned wrapper for one OpenStack service. Each method
    should be wrapped by atomic action context to measures all the timings and
    to reduce a need for extra scenario utils for specific service.
    """

    #: type metadata and resolution, built per subclass by :func:`configure`
    spec: t.ClassVar[ClientSpec]

    def __init__(
        self,
        credential: oscred.OpenStackCredential,
        cache_obj: dict[str, t.Any] | None = None,
        *,
        clients: osclients.Clients | None,
        atomic_inst: list[atomic.AtomicAction],
        name_generator: t.Callable[[], str] | None = None,
        sleeper: t.Callable[[float], None] | None = None,
    ) -> None:
        super().__init__()
        if isinstance(credential, dict):
            self.credential = oscred.OpenStackCredential(**credential)
        else:
            self.credential = credential
        self._cache = cache_obj if cache_obj is not None else {}
        self._clients = clients
        self._name_generator = name_generator
        self._atomic_actions = atomic_inst
        # A callable(seconds) that sleeps and records the delay as idle time.
        # Under a scenario it is that scenario's ``sleep_between``, so a wait
        # method's poll delay counts toward the scenario's idle_duration.
        # Standalone or context use falls back to a plain interruptable sleep
        # (abort-aware, but idle time is not tracked).
        self._sleeper = sleeper or utils.interruptable_sleep

    @property
    def _conn(self) -> openstack.connection.Connection:
        """The openstacksdk connection shared by the owning Clients."""
        if self._clients is None:
            raise exceptions.RallyException(
                "This client is not attached to a Clients container, so it "
                "has no openstacksdk connection.")
        return self._clients._conn

    def _atomic_action(self, name: str) -> atomic.ActionTimer:
        """Return a context manager that times an atomic action."""
        return atomic.ActionTimer(self, name)

    def generate_random_name(self) -> str:
        if self._name_generator is None:
            raise exceptions.RallyException(
                "You cannot use `generate_random_name` until the client is "
                "initialized with a `name_generator` argument.")
        return self._name_generator()

    @classmethod
    def get(
        cls,
        name: str,
        platform: str = "openstack",  # type: ignore[override]
        allow_hidden: bool = False
    ) -> type[BaseClient]:
        return super().get(
            name,
            platform=platform,
            allow_hidden=allow_hidden
        )


class LegacyClientCompat(BaseClient):
    """Transitional layer that adds the legacy ``python-*client`` factory.

    Inherited by clients not yet ported to openstacksdk, and by ported ones
    that keep a legacy escape hatch (keystone). It builds and caches a native
    ``python-*client`` (``create_client`` / ``__call__``) and resolves its
    endpoint from the keystone catalog. Version and service-type resolution are
    proxied to :attr:`BaseClient.spec`, so a subclass' ``create_client`` keeps
    calling ``self.choose_version(...)`` unchanged.

    Unlike :class:`BaseClient`, the container and atomic sink are optional
    here: a legacy client works as a bare factory without them.
    """

    def __init__(
        self,
        credential: oscred.OpenStackCredential,
        cache_obj: dict[str, t.Any] | None = None,
        *,
        clients: osclients.Clients | None = None,
        atomic_inst: list[atomic.AtomicAction] | None = None,
        name_generator: t.Callable[[], str] | None = None,
        sleeper: t.Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(
            credential, cache_obj,
            clients=clients,
            atomic_inst=atomic_inst if atomic_inst is not None else [],
            name_generator=name_generator,
            sleeper=sleeper
        )

    @property
    @deprecated_legacy
    def cache(self) -> dict[str, t.Any]:
        """The container's shared resource cache.

        Out-of-tree plugins built on the frozen ``OSClient`` surface receive
        this dict as the second constructor argument and read and write it
        directly, so the public name stays here. A ported client uses
        ``_cache``.
        """
        return self._cache

    @deprecated_legacy
    def choose_version(self, version: t.Any = None) -> str | None:
        """Deprecated. Use ``self.spec.choose_version`` instead."""
        return self.spec.choose_version(self.credential, version)

    @deprecated_legacy
    def choose_service_type(
        self, service_type: str | None = None
    ) -> str | None:
        """Deprecated. Use ``self.spec.choose_service_type`` instead."""
        return self.spec.choose_service_type(self.credential, service_type)

    @classmethod
    @deprecated_legacy
    def get_supported_versions(cls) -> list[str]:
        """Deprecated. Use ``cls.spec.supported_versions`` instead."""
        return cls.spec.supported_versions

    @classmethod
    @deprecated_legacy
    def validate_version(cls, version: str | int | float) -> None:
        """Deprecated. Use ``cls.spec.validate_version`` instead."""
        cls.spec.validate_version(version)

    @classmethod
    @deprecated_legacy
    def is_service_type_configurable(cls) -> None:
        """Deprecated. Use ``cls.spec.is_service_type_configurable``."""
        cls.spec.is_service_type_configurable()

    @property
    @deprecated_legacy
    def keystone(self) -> keystone.Keystone:
        keystone_cls = BaseClient.get("keystone")
        return t.cast("keystone.Keystone", keystone_cls(
            self.credential,
            self._cache,
            clients=self._clients,
            atomic_inst=self._atomic_actions,
            name_generator=self._name_generator,
            sleeper=self._sleeper,
        ))

    @deprecated_legacy
    def _get_endpoint(self, service_type: str | None = None) -> str:
        kw = {"service_type": self.spec.choose_service_type(
                  self.credential, service_type),
              "region_name": self.credential.region_name}
        if self.credential.endpoint_type:
            kw["interface"] = self.credential.endpoint_type
        api_url = self.keystone.service_catalog.url_for(**kw)
        # url_for raises EndpointNotFound rather than returning None
        assert api_url is not None
        return api_url

    @deprecated_legacy
    def _get_auth_info(
        self,
        user_key: str = "username",
        password_key: str = "password",
        auth_url_key: str = "auth_url",
        project_name_key: str | None = "project_id",
        domain_name_key: str = "domain_name",
        user_domain_name_key: str = "user_domain_name",
        project_domain_name_key: str = "project_domain_name",
        cacert_key: str = "cacert",
        endpoint_type: str = "endpoint_type",
    ) -> dict[str, t.Any]:
        kw = {
            user_key: self.credential.username,
            password_key: self.credential.password,
            auth_url_key: self.credential.auth_url,
            cacert_key: self.credential.https_cacert,
        }
        if project_name_key:
            kw.update({project_name_key: self.credential.tenant_name})

        if "v2.0" not in self.credential.auth_url:
            kw.update({
                domain_name_key: self.credential.domain_name})
            kw.update({
                user_domain_name_key:
                self.credential.user_domain_name or "Default"})
            kw.update({
                project_domain_name_key:
                self.credential.project_domain_name or "Default"})
        if self.credential.endpoint_type:
            kw[endpoint_type] = self.credential.endpoint_type
        return kw

    @abc.abstractmethod
    def create_client(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        """Create new instance of client."""

    @deprecated_legacy
    def __call__(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        """Return initialized client instance."""
        key = "{}{}{}".format(self.get_name(),
                              str(args) if args else "",
                              str(kwargs) if kwargs else "")
        if key not in self._cache:
            self._cache[key] = self.create_client(*args, **kwargs)
        return self._cache[key]


class OSClient(LegacyClientCompat):
    """Public plugin base for legacy ``python-*client`` wrappers.

    Out-of-tree plugins subclass this, so it keeps the historic
    ``__init__(credential, cache_obj)`` signature with no runtime-context
    kwargs.
    """

    def __init__(
        self,
        credential: oscred.OpenStackCredential,
        cache_obj: dict[str, t.Any] | None = None,
    ) -> None:
        super().__init__(credential, cache_obj)
