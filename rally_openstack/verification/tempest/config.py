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

import configparser
import inspect
import io
import os

from rally.common import cfg
from rally.common import logging
from rally import exceptions
from rally.verification import utils

from rally_openstack.common import consts
from rally_openstack.common import credential


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class TempestConfigfileManager(object):
    """Class to create a Tempest config file."""

    def __init__(self, env):
        openstack_platform = env.data["platforms"]["openstack"]
        self.credential = credential.OpenStackCredential(
            permission=consts.EndpointPermission.ADMIN,
            **openstack_platform["platform_data"]["admin"])

        if not self.credential:
            raise exceptions.ValidationError(
                f"Failed to configure 'tempest' for '{env} since "
                "admin credentials for OpenStack platform is missed there."
            )
        self.clients = self.credential.clients()
        self.available_services = self.clients.services().values()

        self.conf = configparser.ConfigParser(allow_no_value=True)
        self.conf.optionxform = str

    def _get_service_type_by_service_name(self, service_name):
        for s_type, s_name in self.clients.services().items():
            if s_name == service_name:
                return s_type

    def _configure_auth(self, section_name="auth"):
        self.conf.set(section_name, "admin_username",
                      self.credential.username)
        self.conf.set(section_name, "admin_password",
                      self.credential.password)
        self.conf.set(section_name, "admin_project_name",
                      self.credential.tenant_name)
        # Keystone v3 related parameter
        self.conf.set(section_name, "admin_domain_name",
                      self.credential.user_domain_name or "Default")

    def _configure_identity(self, section_name="identity"):
        self.conf.set(section_name, "region",
                      self.credential.region_name)
        # discover keystone versions

        def get_versions(auth_url):
            from keystoneauth1 import discover
            from keystoneauth1 import session

            temp_session = session.Session(
                verify=(self.credential.https_cacert
                        or not self.credential.https_insecure),
                timeout=CONF.openstack_client_http_timeout)
            data = discover.Discover(temp_session, auth_url).version_data()
            return dict([(v["version"][0], v["url"]) for v in data])

        # check the original auth_url without cropping versioning to identify
        # the default version

        versions = get_versions(self.credential.auth_url)
        cropped_auth_url = self.clients.keystone._remove_url_version()
        if cropped_auth_url == self.credential.auth_url:
            # the given auth_url doesn't contain version
            if set(versions.keys()) == {2, 3}:
                # ok, both versions of keystone are enabled, we can take urls
                # there
                uri = versions[2]
                uri_v3 = versions[3]
                target_version = 3
            elif set(versions.keys()) == {2} or set(versions.keys()) == {3}:
                # only one version is available while discovering

                # get the most recent version
                target_version = sorted(versions.keys())[-1]
                if target_version == 2:
                    uri = versions[2]
                    uri_v3 = os.path.join(cropped_auth_url, "v3")
                else:
                    # keystone v2 is disabled. let's do it explicitly
                    self.conf.set("identity-feature-enabled", "api_v2",
                                  "False")
                    uri_v3 = versions[3]
                    uri = os.path.join(cropped_auth_url, "v2.0")
            else:
                # Does Keystone released new version of API ?!
                LOG.debug("Discovered keystone versions: %s" % versions)
                raise exceptions.RallyException("Failed to discover keystone "
                                                "auth urls.")

        else:
            if self.credential.auth_url.rstrip("/").endswith("v2.0"):
                uri = self.credential.auth_url
                uri_v3 = uri.replace("/v2.0", "/v3")
                target_version = 2
            else:
                uri_v3 = self.credential.auth_url
                uri = uri_v3.replace("/v3", "/v2.0")
                target_version = 3

        self.conf.set(section_name, "auth_version", "v%s" % target_version)
        self.conf.set(section_name, "uri", uri)
        self.conf.set(section_name, "uri_v3", uri_v3)
        if self.credential.endpoint_type:
            self.conf.set(section_name, "v2_endpoint_type",
                          self.credential.endpoint_type)
            self.conf.set(section_name, "v3_endpoint_type",
                          self.credential.endpoint_type)

        self.conf.set(section_name, "disable_ssl_certificate_validation",
                      str(self.credential.https_insecure))
        self.conf.set(section_name, "ca_certificates_file",
                      self.credential.https_cacert)

    # The compute section is configured in context class for Tempest resources.
    # Options which are configured there: 'image_ref', 'image_ref_alt',
    # 'flavor_ref', 'flavor_ref_alt'.

    def _configure_network(self, section_name="network"):
        if "neutron" in self.available_services:
            neutronclient = self.clients.neutron()
            public_nets = [
                net for net in neutronclient.list_networks()["networks"]
                if net["status"] == "ACTIVE" and net["router:external"] is True
            ]
            if public_nets:
                net_id = public_nets[0]["id"]
                net_name = public_nets[0]["name"]
                self.conf.set(section_name, "public_network_id", net_id)
                self.conf.set(section_name, "floating_network_name", net_name)
        else:
            novaclient = self.clients.nova()
            net_name = next(net.human_id for net in novaclient.networks.list()
                            if net.human_id is not None)
            self.conf.set("compute", "fixed_network_name", net_name)
            self.conf.set("validation", "network_for_ssh", net_name)

    def _configure_network_feature_enabled(
            self, section_name="network-feature-enabled"):
        if "neutron" in self.available_services:
            neutronclient = self.clients.neutron()
            extensions = neutronclient.list_ext("extensions", "/extensions",
                                                retrieve_all=True)
            aliases = [ext["alias"] for ext in extensions["extensions"]]
            aliases_str = ",".join(aliases)
            self.conf.set(section_name, "api_extensions", aliases_str)

    def _configure_object_storage(self, section_name="object-storage"):
        self.conf.set(section_name, "operator_role",
                      CONF.openstack.swift_operator_role)
        self.conf.set(section_name, "reseller_admin_role",
                      CONF.openstack.swift_reseller_admin_role)

    def _configure_service_available(self, section_name="service_available"):
        services = ["cinder", "glance", "heat", "ironic", "neutron", "nova",
                    "swift"]
        for service in services:
            # Convert boolean to string because ConfigParser fails
            # on attempt to get option with boolean value
            self.conf.set(section_name, service,
                          str(service in self.available_services))

    def _configure_validation(self, section_name="validation"):
        if "neutron" in self.available_services:
            self.conf.set(section_name, "connect_method", "floating")
        else:
            self.conf.set(section_name, "connect_method", "fixed")

    def _configure_orchestration(self, section_name="orchestration"):
        self.conf.set(section_name, "stack_owner_role",
                      CONF.openstack.heat_stack_owner_role)
        self.conf.set(section_name, "stack_user_role",
                      CONF.openstack.heat_stack_user_role)

    def create(self, conf_path, extra_options=None):
        self.conf.read(os.path.join(os.path.dirname(__file__), "config.ini"))

        for name, method in inspect.getmembers(self, inspect.ismethod):
            if name.startswith("_configure_"):
                method()

        if extra_options:
            utils.add_extra_options(extra_options, self.conf)

        with open(conf_path, "w") as configfile:
            self.conf.write(configfile)

        raw_conf = io.StringIO()
        raw_conf.write("# Some empty values of options will be replaced while "
                       "creating required resources (images, flavors, etc).\n")
        self.conf.write(raw_conf)

        return raw_conf.getvalue()
