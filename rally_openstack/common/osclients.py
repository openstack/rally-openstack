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

from __future__ import annotations

import copy
import os
import typing as t

from rally import exceptions
from rally.common import cfg
from rally.common import logging

from rally_openstack.common import consts
from rally_openstack.common import credential as oscred
from rally_openstack.common.clients import base
from rally_openstack.common.clients import keystone


if t.TYPE_CHECKING:
    import openstack.connection


# backward compatibility
AuthenticationFailed = base.AuthenticationFailed
Keystone = keystone.Keystone
BaseClient = base.BaseClient
OSClient = base.OSClient
configure = base.configure


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class NovaSpec(base.ClientSpec):
    def validate_version(self, version):
        from novaclient import api_versions
        from novaclient import exceptions as nova_exc

        try:
            api_versions.get_api_version(version)
        except nova_exc.UnsupportedVersion:
            raise exceptions.RallyException(
                "Version string '%s' is unsupported." % version) from None


@base.configure("nova", default_version="2", default_service_type="compute",
                spec=NovaSpec)
class Nova(base.OSClient):
    """Wrapper for NovaClient which returns a authenticated native client."""

    def create_client(self, version=None, service_type=None):
        """Return nova client."""
        from novaclient import client as nova

        client = nova.Client(
            session=self.keystone.get_session()[0],
            version=self.choose_version(version),
            endpoint_override=self._get_endpoint(service_type))
        return client


@base.configure("neutron", default_version="2.0",
                default_service_type="network",
                supported_versions=["2.0"])
class Neutron(base.OSClient):
    """Wrapper for NeutronClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return neutron client."""
        from neutronclient.neutron import client as neutron

        kw_args = {}
        if self.credential.endpoint_type:
            kw_args["endpoint_type"] = self.credential.endpoint_type

        client = neutron.Client(
            self.choose_version(version),
            session=self.keystone.get_session()[0],
            endpoint_override=self._get_endpoint(service_type),
            **kw_args)
        return client


@base.configure("octavia", default_version="2",
                default_service_type="load-balancer", supported_versions=["2"])
class Octavia(base.OSClient):
    """Wrapper for OctaviaClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return octavia client."""
        from octaviaclient.api.v2 import octavia

        kw_args = {}
        if self.credential.endpoint_type:
            kw_args["endpoint_type"] = self.credential.endpoint_type

        client = octavia.OctaviaAPI(
            endpoint=self._get_endpoint(service_type),
            session=self.keystone.get_session()[0],
            **kw_args)
        return client


@base.configure("glance", default_version="2", default_service_type="image",
                supported_versions=["1", "2"])
class Glance(base.OSClient):
    """Wrapper for GlanceClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return glance client."""
        import glanceclient as glance

        session = self.keystone.get_session()[0]
        client = glance.Client(
            version=self.choose_version(version),
            endpoint_override=self._get_endpoint(service_type),
            session=session)
        return client


@base.configure("heat", default_version="1",
                default_service_type="orchestration",
                supported_versions=["1"])
class Heat(base.OSClient):
    """Wrapper for HeatClient which returns an authenticated native client."""

    def create_client(self, version=None, service_type=None):
        """Return heat client."""
        from heatclient import client as heat

        # ToDo: Remove explicit endpoint_type or interface initialization
        #       when heatclient no longer uses it.
        kw_args = {}
        if self.credential.endpoint_type:
            kw_args["interface"] = self.credential.endpoint_type

        client = heat.Client(
            self.choose_version(version),
            session=self.keystone.get_session()[0],
            endpoint_override=self._get_endpoint(service_type),
            **kw_args)
        return client


class CinderSpec(base.ClientSpec):
    def validate_version(self, version):
        from cinderclient import api_versions
        from cinderclient import exceptions as cinder_exc

        version = str(version)
        if version in api_versions.REPLACEMENT_VERSIONS:
            LOG.warning(
                f"Version {version} is not supported by Cinder. Switching "
                f"to {api_versions.REPLACEMENT_VERSIONS[version]}."
            )
            version = api_versions.REPLACEMENT_VERSIONS[version]

        try:
            version_obj = api_versions.get_api_version(version)
            if version_obj > api_versions.APIVersion(api_versions.MAX_VERSION):
                raise cinder_exc.UnsupportedVersion()
        except cinder_exc.UnsupportedVersion:
            raise exceptions.RallyException(
                "Version string '%s' is unsupported." % version) from None


@base.configure("cinder", default_version="3",
                default_service_type="block-storage", spec=CinderSpec)
class Cinder(base.OSClient):
    """Wrapper for CinderClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return cinder client."""
        from cinderclient import client as cinder

        client = cinder.Client(
            self.choose_version(version),
            session=self.keystone.get_session()[0],
            endpoint_override=self._get_endpoint(service_type))
        return client


class ManilaSpec(base.ClientSpec):
    def validate_version(self, version):
        from manilaclient import api_versions
        from manilaclient import exceptions as manila_exc

        try:
            api_versions.get_api_version(version)
        except manila_exc.UnsupportedVersion:
            raise exceptions.RallyException(
                "Version string '%s' is unsupported." % version) from None


@base.configure("manila", default_version="2",
                default_service_type="shared-file-system", spec=ManilaSpec)
class Manila(base.OSClient):
    """Wrapper for ManilaClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return manila client."""
        from manilaclient import client as manila
        manila_client = manila.Client(
            self.choose_version(version),
            insecure=self.credential.https_insecure,
            session=self.keystone.get_session()[0],
            service_catalog_url=self._get_endpoint(service_type))
        return manila_client


@base.configure("gnocchi", default_service_type="metric", default_version="1",
                supported_versions=["1"])
class Gnocchi(base.OSClient):
    """Wrapper for GnocchiClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return gnocchi client."""
        # NOTE(sumantmurke): gnocchiclient requires keystoneauth1 for
        # authenticating and creating a session.
        from gnocchiclient import client as gnocchi

        service_type = self.choose_service_type(service_type)
        sess = self.keystone.get_session()[0]
        gclient = gnocchi.Client(
            version=self.choose_version(version), session=sess,
            adapter_options={"service_type": service_type,
                             "interface": self.credential.endpoint_type})
        return gclient


@base.configure("ironic", default_version="1",
                default_service_type="baremetal",
                supported_versions=["1"])
class Ironic(base.OSClient):
    """Wrapper for IronicClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return Ironic client."""
        from ironicclient import client as ironic

        ironic_version = self.choose_version(version)
        # ironic always has a default version
        assert ironic_version is not None
        client = ironic.get_client(
            ironic_version,
            session=self.keystone.get_session()[0],
            endpoint=self._get_endpoint(service_type))
        return client


@base.configure("zaqar", default_version="2", default_service_type="messaging",
                supported_versions=["2"])
class Zaqar(base.OSClient):
    """Wrapper for ZaqarClient which returns an authenticated native client.

    """

    def choose_version(self, version=None):
        # zaqarclient accepts only int as version
        version = super().choose_version(version)
        return int(version) if version is not None else None

    def create_client(self, version=None, service_type=None):
        """Return Zaqar client."""
        from zaqarclient.queues import client as zaqar
        client = zaqar.Client(url=self._get_endpoint(),
                              version=self.choose_version(version),
                              session=self.keystone.get_session()[0])
        return client


@base.configure("designate", default_version="2", default_service_type="dns",
                supported_versions=["2"])
class Designate(base.OSClient):
    """Wrapper for DesignateClient which returns authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return designate client."""
        from designateclient import client

        version = self.choose_version(version)

        api_url = self._get_endpoint(service_type)
        api_url += "/v%s" % version

        session = self.keystone.get_session()[0]
        return client.Client(version, session=session,
                             endpoint_override=api_url)


@base.configure("trove", default_version="1.0", supported_versions=["1.0"],
                default_service_type="database")
class Trove(base.OSClient):
    """Wrapper for TroveClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Returns trove client."""
        from troveclient import client as trove

        client = trove.Client(self.choose_version(version),
                              session=self.keystone.get_session()[0],
                              endpoint=self._get_endpoint(service_type))
        return client


@base.configure("mistral", default_service_type="workflowv2")
class Mistral(base.OSClient):
    """Wrapper for MistralClient which returns an authenticated native client.

    """

    def create_client(self, service_type=None):
        """Return Mistral client."""
        from mistralclient.api import client as mistral

        client = mistral.client(
            mistral_url=self._get_endpoint(service_type),
            service_type=self.choose_service_type(service_type),
            auth_token=self.keystone.auth_ref.auth_token)
        return client


@base.configure("swift", default_service_type="object-store")
class Swift(base.OSClient):
    """Wrapper for SwiftClient which returns an authenticated native client.

    """

    def create_client(self, service_type=None):
        """Return swift client."""
        from swiftclient import client as swift

        auth_token = self.keystone.auth_ref.auth_token
        client = swift.Connection(retries=1,
                                  preauthurl=self._get_endpoint(service_type),
                                  preauthtoken=auth_token,
                                  insecure=self.credential.https_insecure,
                                  cacert=self.credential.https_cacert,
                                  user=self.credential.username,
                                  tenant_name=self.credential.tenant_name,
                                  )
        return client


@base.configure("magnum", default_version="1", supported_versions=["1"],
                default_service_type="container-infra",)
class Magnum(base.OSClient):
    """Wrapper for MagnumClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return magnum client."""
        from magnumclient import client as magnum

        api_url = self._get_endpoint(service_type)
        session = self.keystone.get_session()[0]

        return magnum.Client(
            session=session,
            interface=self.credential.endpoint_type,
            magnum_url=api_url)


@base.configure("watcher", default_version="1",
                default_service_type="infra-optim",
                supported_versions=["1"])
class Watcher(base.OSClient):
    """Wrapper for WatcherClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return watcher client."""
        from watcherclient import client as watcher_client
        watcher_api_url = self._get_endpoint(
            self.choose_service_type(service_type))
        client = watcher_client.Client(
            self.choose_version(version),
            endpoint=watcher_api_url,
            session=self.keystone.get_session()[0])
        return client


@base.configure("barbican", default_version="1",
                default_service_type="key-manager")
class Barbican(base.OSClient):
    """Wrapper for BarbicanClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return Barbican client."""
        from barbicanclient import client as barbican_client

        version = "v%s" % self.choose_version(version)

        client = barbican_client.Client(
            version=self.choose_version(version),
            session=self.keystone.get_session()[0])

        return client


class Clients:
    """This class simplify and unify work with OpenStack python clients."""

    def __init__(
        self,
        credential: oscred.OpenStackCredential,
        cache: dict[str, t.Any] | None = None,
        *,
        atomic_inst: list | None = None,
        name_generator: t.Callable[[], str] | None = None,
        sleeper: t.Callable[[float], None] | None = None,
    ) -> None:
        self.credential = credential
        self.cache: dict[str, t.Any] = cache or {}
        self._atomic_inst = atomic_inst if atomic_inst is not None else []
        self._name_generator = name_generator
        self._sleeper = sleeper

    if t.TYPE_CHECKING:
        # keystone is the one ported client; declare its type so
        # ``clients.keystone`` resolves to Keystone instead of the ``Any``
        # that ``__getattr__`` returns for every other (legacy) service. At
        # runtime ``__getattr__`` builds and memoizes it like the rest.
        keystone: Keystone

    def __getattr__(self, name: str) -> t.Any:
        """Return the client for a service name.

        The runtime context (this container, the atomic sink, the name
        generator, the idle sleeper) is passed only to *ported* clients. A
        legacy :class:`~...clients.base.OSClient` subclass -- including every
        out-of-tree plugin -- keeps its historic ``(credential, cache)``
        constructor, so it is built without those kwargs.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        key = f"client:{name}"
        if key not in self.cache:
            client_cls = base.BaseClient.get(name)
            if issubclass(client_cls, base.OSClient):
                self.cache[key] = client_cls(self.credential, self.cache)
            else:
                self.cache[key] = client_cls(
                    self.credential, self.cache,
                    clients=self,
                    atomic_inst=self._atomic_inst,
                    name_generator=self._name_generator,
                    sleeper=self._sleeper)
        return self.cache[key]

    @classmethod
    def create_from_env(cls):
        from rally_openstack.common import credential
        from rally_openstack.environment.platforms import existing

        spec = existing.OpenStack.create_spec_from_sys_environ(os.environ)
        if not spec["available"]:
            raise ValueError(spec["message"]) from None

        creds = spec["spec"]
        oscred = credential.OpenStackCredential(
            auth_url=creds["auth_url"],
            username=creds["admin"]["username"],
            password=creds["admin"]["password"],
            tenant_name=creds["admin"].get(
                "tenant_name", creds["admin"].get("project_name")),
            endpoint_type=creds["endpoint_type"],
            user_domain_name=creds["admin"].get("user_domain_name"),
            project_domain_name=creds["admin"].get("project_domain_name"),
            region_name=creds["region_name"],
            https_cacert=creds["https_cacert"],
            https_insecure=creds["https_insecure"])
        return cls(oscred)

    def clear(self):
        """Remove all cached client handles and shared resources."""
        self.cache = {}

    def verified_keystone(self):
        """Ensure keystone endpoints are valid and then authenticate

        :returns: rally-owned identity client
        """
        # Ensure that user is admin
        if "admin" not in [
            role.lower() for role in (self.keystone.auth_ref.role_names or [])
        ]:
            raise exceptions.InvalidAdminException(
                username=self.credential.username)
        return self.keystone

    def services(self):
        """Return available services names and types.

        :returns: dict, {"service_type": "service_name", ...}
        """
        if "services_data" not in self.cache:
            services_data = {}
            available_services = self.keystone.service_catalog.get_endpoints()
            for stype in available_services.keys():
                if stype in consts.ServiceType:
                    services_data[stype] = consts.ServiceType[stype]
                else:
                    services_data[stype] = "__unknown__"
            self.cache["services_data"] = services_data

        return self.cache["services_data"]

    def override(self, **client_versions: str) -> Clients:
        """Return a Clients pinned to specific API versions."""
        credential = copy.deepcopy(self.credential)
        for client_name, version in client_versions.items():
            credential["api_info"].setdefault(client_name, {})
            credential["api_info"][client_name]["version"] = str(version)
        cache = {key: value for key, value in self.cache.items()
                 if not key.startswith("client:")}
        return Clients(credential,
                       cache=cache,
                       atomic_inst=self._atomic_inst,
                       name_generator=self._name_generator,
                       sleeper=self._sleeper)

    def _sdk_service_config(self) -> dict[str, str]:
        """Build openstacksdk per-service config."""
        config: dict[str, str] = {}
        for client_name in self.credential.api_info:
            try:
                spec = base.BaseClient.get(client_name).spec
            except exceptions.PluginNotFound:
                continue
            sdk_type = spec.sdk_service_type
            if not sdk_type:
                continue
            prefix = sdk_type.replace("-", "_")
            version = self.credential.api_info[client_name].get("version")
            if version:
                config[f"{prefix}_api_version"] = str(version)
            service_type = spec.choose_service_type(self.credential)
            if service_type and service_type != sdk_type:
                config[f"{prefix}_service_type"] = service_type
        return config

    @property
    def _conn(self) -> openstack.connection.Connection:
        """Return an openstacksdk Connection sharing the keystone session."""
        service_config = self._sdk_service_config()
        key = "sdk_connection_"
        key += "_".join(
            f"{name}={value}"
            for name, value in sorted(service_config.items())
        )
        if key not in self.cache:
            import openstack.connection

            session = self.keystone.get_session()[0]
            self.cache[key] = openstack.connection.Connection(
                session=session,
                region_name=self.credential.region_name,
                # Point the identity proxy straight at the versioned endpoint
                # so openstacksdk does not re-discover the identity version on
                # proxy init.
                identity_endpoint_override=(
                    self.keystone.identity_endpoint_override),
                # Per-service api_version/service_type kwargs go to the SDK's
                # ``**kwargs``. The cast keeps the splat from being matched
                # against the named Connection params.
                **t.cast("dict[str, t.Any]", service_config),
            )
        return self.cache[key]

    def refresh_token_if_needed(self):
        """Proactively refresh a reused token near expiry (untimed).

        The token captured by the context is reused across iterations. If it
        is about to expire, refresh it here at iteration init, before any
        atomic action, so the refresh request never lands inside a measured
        action. Does nothing when no token was seeded (the plugin authenticates
        on first use anyway) or when the token is still valid.
        """
        # A seeded auth state is the string produced by ``get_auth_state()``;
        # anything else (None, or a test mock) means there is nothing to
        # refresh.
        if not isinstance(self.credential.auth, str):
            return
        sess, plugin = self.keystone.get_session()
        margin = CONF.openstack_client_token_refresh_margin
        if plugin.get_access(sess).will_expire_soon(margin):
            plugin.invalidate()
            # overwrite the auth_ref memoized by the keystone client, otherwise
            # it would keep handing out the token we have just invalidated.
            self.cache["keystone_auth_ref"] = plugin.get_access(sess)
