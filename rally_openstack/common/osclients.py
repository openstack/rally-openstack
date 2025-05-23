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

import abc
import os
from urllib.parse import urlparse
from urllib.parse import urlunparse

from rally.common import cfg
from rally.common import logging
from rally.common.plugin import plugin
from rally import exceptions

from rally_openstack.common import consts
from rally_openstack.common import credential as oscred


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class AuthenticationFailed(exceptions.AuthenticationFailed):
    error_code = 220

    msg_fmt = ("Failed to authenticate to %(url)s for user '%(username)s'"
               " in project '%(project)s': %(message)s")
    msg_fmt_2 = "%(message)s"

    def __init__(self, error, url, username, project):
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
            # this type of errors is general for all users no need to include
            # username, project name. The original error message should be
            # self-sufficient
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
            # something unexpected. include exception class as well.
            self._helpful_trace = True
            message = "[%s] %s" % (error.__class__.__name__, str(error))
        super(AuthenticationFailed, self).__init__(message=message, **kwargs)

    def is_trace_helpful(self):
        return self._helpful_trace


def configure(name, default_version=None, default_service_type=None,
              supported_versions=None):
    """OpenStack client class wrapper.

    Each client class has to be wrapped by configure() wrapper. It
    sets essential configuration of client classes.

    :param name: Name of the client
    :param default_version: Default version for client
    :param default_service_type: Default service type of endpoint(If this
        variable is not specified, validation will assume that your client
        doesn't allow to specify service type.
    :param supported_versions: List of supported versions(If this variable is
        not specified, `OSClient.validate_version` method will raise an
        exception that client doesn't support setting any versions. If this
        logic is wrong for your client, you should override `validate_version`
        in client object)
    """
    def wrapper(cls):
        cls = plugin.configure(name=name, platform="openstack")(cls)
        cls._meta_set("default_version", default_version)
        cls._meta_set("default_service_type", default_service_type)
        cls._meta_set("supported_versions", supported_versions or [])
        return cls

    return wrapper


@plugin.base()
class OSClient(plugin.Plugin):
    """Base class for OpenStack clients"""

    def __init__(self, credential, cache_obj=None):
        self.credential = credential
        if not isinstance(self.credential, oscred.OpenStackCredential):
            self.credential = oscred.OpenStackCredential(**self.credential)
        self.cache = cache_obj if cache_obj is not None else {}

    def choose_version(self, version=None):
        """Return version string.

        Choose version between transmitted(preferable value if present),
        version from api_info(configured from a context) and default.
        """
        # NOTE(andreykurilin): The result of choose is converted to string,
        # since most of clients contain map for versioned modules, where a key
        # is a string value of version. Example of map and its usage:
        #
        #     from oslo_utils import importutils
        #     ...
        #     version_map = {"1": "someclient.v1.client.Client",
        #                    "2": "someclient.v2.client.Client"}
        #
        #     def Client(version, *args, **kwargs):
        #         cls = importutils.import_class(version_map[version])
        #         return cls(*args, **kwargs)
        #
        # That is why type of version so important and we should ensure that
        # version is a string object.
        # For those clients which doesn't accept string value(for example
        # zaqarclient), this method should be overridden.
        version = (version
                   or self.credential.api_info.get(self.get_name(), {}).get(
                       "version") or self._meta_get("default_version"))
        if version is not None:
            version = str(version)
        return version

    @classmethod
    def get_supported_versions(cls):
        return cls._meta_get("supported_versions")

    @classmethod
    def validate_version(cls, version):
        supported_versions = cls.get_supported_versions()
        if supported_versions:
            if str(version) not in supported_versions:
                raise exceptions.ValidationError(
                    "'%(vers)s' is not supported. Should be one of "
                    "'%(supported)s'"
                    % {"vers": version, "supported": supported_versions})
        else:
            raise exceptions.RallyException("Setting version is not supported")
        try:
            float(version)
        except ValueError:
            raise exceptions.ValidationError(
                "'%s' is invalid. Should be numeric value." % version
            ) from None

    def choose_service_type(self, service_type=None):
        """Return service_type string.

        Choose service type between transmitted(preferable value if present),
        service type from api_info(configured from a context) and default.
        """
        return (service_type
                or self.credential.api_info.get(self.get_name(), {}).get(
                    "service_type") or self._meta_get("default_service_type"))

    @classmethod
    def is_service_type_configurable(cls):
        """Just checks that client supports setting service type."""
        if cls._meta_get("default_service_type") is None:
            raise exceptions.RallyException(
                "Setting service type is not supported.")

    @property
    def keystone(self):
        return OSClient.get("keystone")(self.credential, self.cache)

    def _get_endpoint(self, service_type=None):
        kw = {"service_type": self.choose_service_type(service_type),
              "region_name": self.credential.region_name}
        if self.credential.endpoint_type:
            kw["interface"] = self.credential.endpoint_type
        api_url = self.keystone.service_catalog.url_for(**kw)
        return api_url

    def _get_auth_info(self, user_key="username",
                       password_key="password",
                       auth_url_key="auth_url",
                       project_name_key="project_id",
                       domain_name_key="domain_name",
                       user_domain_name_key="user_domain_name",
                       project_domain_name_key="project_domain_name",
                       cacert_key="cacert",
                       endpoint_type="endpoint_type",
                       ):
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
    def create_client(self, *args, **kwargs):
        """Create new instance of client."""

    def __call__(self, *args, **kwargs):
        """Return initialized client instance."""
        key = "{0}{1}{2}".format(self.get_name(),
                                 str(args) if args else "",
                                 str(kwargs) if kwargs else "")
        if key not in self.cache:
            self.cache[key] = self.create_client(*args, **kwargs)
        return self.cache[key]

    @classmethod
    def get(cls, name, **kwargs):
        # NOTE(boris-42): Remove this after we finish rename refactoring.
        kwargs.pop("platform", None)
        kwargs.pop("namespace", None)
        return super(OSClient, cls).get(name, platform="openstack", **kwargs)


@configure("keystone", supported_versions=("2", "3"))
class Keystone(OSClient):
    """Wrapper for KeystoneClient which hides OpenStack auth details."""

    @property
    def keystone(self):
        raise exceptions.RallyException(
            "Method 'keystone' is restricted for keystoneclient. :)")

    @property
    def service_catalog(self):
        return self.auth_ref.service_catalog

    @property
    def auth_ref(self):
        try:
            if "keystone_auth_ref" not in self.cache:
                sess, plugin = self.get_session()
                self.cache["keystone_auth_ref"] = plugin.get_access(sess)
        except Exception as original_e:
            e = AuthenticationFailed(
                error=original_e,
                username=self.credential.username,
                project=self.credential.tenant_name,
                url=self.credential.auth_url
            )
            if logging.is_debug() and e.is_trace_helpful():
                LOG.exception("Unable to authenticate for user"
                              " %(username)s in project"
                              " %(tenant_name)s" %
                              {"username": self.credential.username,
                               "tenant_name": self.credential.tenant_name})

            raise e from None
        return self.cache["keystone_auth_ref"]

    def get_session(self, version=None):
        key = "keystone_session_and_plugin_%s" % version
        if key not in self.cache:
            from keystoneauth1 import discover
            from keystoneauth1 import identity
            from keystoneauth1 import session

            version = self.choose_version(version)
            auth_url = self.credential.auth_url
            if version is not None:
                auth_url = self._remove_url_version()

            password_args = {
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
            sess = session.Session(
                auth=identity_plugin,
                verify=(self.credential.https_cacert
                        or not self.credential.https_insecure),
                cert=self.credential.https_cert,
                timeout=CONF.openstack_client_http_timeout)
            self.cache[key] = (sess, identity_plugin)
        return self.cache[key]

    def _remove_url_version(self):
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

    def create_client(self, version=None):
        """Return a keystone client.

        :param version: Keystone API version, can be one of:
            ("2", "3")

        If this object was constructed with a version in the api_info
        then that will be used unless the version parameter is passed.
        """
        import keystoneclient
        from keystoneclient import client

        # Use the version in the api_info if provided, otherwise fall
        # back to the passed version (which may be None, in which case
        # keystoneclient chooses).
        version = self.choose_version(version)

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
        self.auth_ref   # noqa

        return client.Client(**kw)


@configure("nova", default_version="2", default_service_type="compute")
class Nova(OSClient):
    """Wrapper for NovaClient which returns a authenticated native client."""

    @classmethod
    def validate_version(cls, version):
        from novaclient import api_versions
        from novaclient import exceptions as nova_exc

        try:
            api_versions.get_api_version(version)
        except nova_exc.UnsupportedVersion:
            raise exceptions.RallyException(
                "Version string '%s' is unsupported." % version) from None

    def create_client(self, version=None, service_type=None):
        """Return nova client."""
        from novaclient import client as nova

        client = nova.Client(
            session=self.keystone.get_session()[0],
            version=self.choose_version(version),
            endpoint_override=self._get_endpoint(service_type))
        return client


@configure("neutron", default_version="2.0", default_service_type="network",
           supported_versions=["2.0"])
class Neutron(OSClient):
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


@configure("octavia", default_version="2",
           default_service_type="load-balancer", supported_versions=["2"])
class Octavia(OSClient):
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


@configure("glance", default_version="2", default_service_type="image",
           supported_versions=["1", "2"])
class Glance(OSClient):
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


@configure("heat", default_version="1", default_service_type="orchestration",
           supported_versions=["1"])
class Heat(OSClient):
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


@configure("cinder", default_version="3", default_service_type="block-storage")
class Cinder(OSClient):
    """Wrapper for CinderClient which returns an authenticated native client.

    """

    @classmethod
    def validate_version(cls, version):
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

    def create_client(self, version=None, service_type=None):
        """Return cinder client."""
        from cinderclient import client as cinder

        client = cinder.Client(
            self.choose_version(version),
            session=self.keystone.get_session()[0],
            endpoint_override=self._get_endpoint(service_type))
        return client


@configure("manila", default_version="1", default_service_type="share")
class Manila(OSClient):
    """Wrapper for ManilaClient which returns an authenticated native client.

    """
    @classmethod
    def validate_version(cls, version):
        from manilaclient import api_versions
        from manilaclient import exceptions as manila_exc

        try:
            api_versions.get_api_version(version)
        except manila_exc.UnsupportedVersion:
            raise exceptions.RallyException(
                "Version string '%s' is unsupported." % version) from None

    def create_client(self, version=None, service_type=None):
        """Return manila client."""
        from manilaclient import client as manila
        manila_client = manila.Client(
            self.choose_version(version),
            insecure=self.credential.https_insecure,
            session=self.keystone.get_session()[0],
            service_catalog_url=self._get_endpoint(service_type))
        return manila_client


@configure("gnocchi", default_service_type="metric", default_version="1",
           supported_versions=["1"])
class Gnocchi(OSClient):
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


@configure("ironic", default_version="1", default_service_type="baremetal",
           supported_versions=["1"])
class Ironic(OSClient):
    """Wrapper for IronicClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return Ironic client."""
        from ironicclient import client as ironic

        client = ironic.get_client(
            self.choose_version(version),
            session=self.keystone.get_session()[0],
            endpoint=self._get_endpoint(service_type))
        return client


@configure("zaqar", default_version="1.1", default_service_type="messaging",
           supported_versions=["1", "1.1"])
class Zaqar(OSClient):
    """Wrapper for ZaqarClient which returns an authenticated native client.

    """

    def choose_version(self, version=None):
        # zaqarclient accepts only int or float obj as version
        return float(super(Zaqar, self).choose_version(version))

    def create_client(self, version=None, service_type=None):
        """Return Zaqar client."""
        from zaqarclient.queues import client as zaqar
        client = zaqar.Client(url=self._get_endpoint(),
                              version=self.choose_version(version),
                              session=self.keystone.get_session()[0])
        return client


@configure("designate", default_version="2", default_service_type="dns",
           supported_versions=["2"])
class Designate(OSClient):
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


@configure("trove", default_version="1.0", supported_versions=["1.0"],
           default_service_type="database")
class Trove(OSClient):
    """Wrapper for TroveClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Returns trove client."""
        from troveclient import client as trove

        client = trove.Client(self.choose_version(version),
                              session=self.keystone.get_session()[0],
                              endpoint=self._get_endpoint(service_type))
        return client


@configure("mistral", default_service_type="workflowv2")
class Mistral(OSClient):
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


@configure("swift", default_service_type="object-store")
class Swift(OSClient):
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


@configure("monasca", default_version="2_0",
           default_service_type="monitoring", supported_versions=["2_0"])
class Monasca(OSClient):
    """Wrapper for MonascaClient which returns an authenticated native client.

    """

    def create_client(self, version=None, service_type=None):
        """Return monasca client."""
        from monascaclient import client as monasca

        # Change this to use session once it's supported by monascaclient
        client = monasca.Client(
            self.choose_version(version),
            self._get_endpoint(service_type),
            token=self.keystone.auth_ref.auth_token,
            timeout=CONF.openstack_client_http_timeout,
            insecure=self.credential.https_insecure,
            **self._get_auth_info(project_name_key="tenant_name"))
        return client


@configure("magnum", default_version="1", supported_versions=["1"],
           default_service_type="container-infra",)
class Magnum(OSClient):
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


@configure("watcher", default_version="1", default_service_type="infra-optim",
           supported_versions=["1"])
class Watcher(OSClient):
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


@configure("barbican", default_version="1", default_service_type="key-manager")
class Barbican(OSClient):
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


class Clients(object):
    """This class simplify and unify work with OpenStack python clients."""

    def __init__(self, credential, cache=None):
        self.credential = credential
        self.cache = cache or {}

    def __getattr__(self, client_name):
        """Lazy load of clients."""
        return OSClient.get(client_name)(self.credential, self.cache)

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
        """Remove all cached client handles."""
        self.cache = {}

    def verified_keystone(self):
        """Ensure keystone endpoints are valid and then authenticate

        :returns: Keystone Client
        """
        # Ensure that user is admin
        if "admin" not in [role.lower() for role in
                           self.keystone.auth_ref.role_names]:
            raise exceptions.InvalidAdminException(
                username=self.credential.username)
        return self.keystone()

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
