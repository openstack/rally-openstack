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

import random

from rally import exceptions
from rally.common import logging
from rally.common import validation
from rally.task import scenario

from rally_openstack.common import consts
from rally_openstack.common import osclients
from rally_openstack.task import context


LOG = logging.getLogger(__name__)


@validation.configure("check_api_versions")
class CheckOpenStackAPIVersionsValidator(validation.Validator):
    """Additional validation for api_versions context"""

    def validate(self, context, config, plugin_cls, plugin_cfg):
        for client in plugin_cfg:
            client_cls = osclients.BaseClient.get(client)
            try:
                if ("service_type" in plugin_cfg[client]
                        or "service_name" in plugin_cfg[client]):
                    client_cls.spec.is_service_type_configurable()

                if "version" in plugin_cfg[client]:
                    client_cls.spec.validate_version(
                        plugin_cfg[client]["version"])

            except exceptions.RallyException as e:
                return self.fail(
                    "Invalid settings for '%(client)s': %(error)s" % {
                        "client": client,
                        "error": e.format_message()})


@validation.add("check_api_versions")
@context.configure(name="api_versions", platform="openstack", order=150)
class OpenStackAPIVersions(context.OpenStackContext):
    """Context for specifying OpenStack clients versions and service types.

    Some OpenStack services support several API versions. To recognize
    the endpoints of each version, separate service types are provided in
    Keystone service catalog.

    Rally has the map of default service names - service types. But since
    service type is an entity, which can be configured manually by admin(
    via keystone api) without relation to service name, such map can be
    insufficient.

    Also, Keystone service catalog does not provide a map types to name
    (this statement is true for keystone < 3.3 ).

    This context was designed for not-default service types and not-default
    API versions usage.

    An example of specifying API version:

    .. code-block:: json

        # In this example we will launch NovaKeypair.create_and_list_keypairs
        # scenario on 2.2 api version.
        {
            "version": 2,
            "title": "Launch NovaKeypair.create_and_list_keypairs on 2.2",
            "subtasks": [
                {
                    "title": "Create and list keypairs",
                    "scenario": {
                        "NovaKeypair.create_and_list_keypairs": {
                            "key_type": "x509"
                        }
                    },
                    "runner": {
                        "constant": {
                            "times": 10,
                            "concurrency": 2
                        }
                    },
                    "contexts": {
                        "users": {
                            "tenants": 3,
                            "users_per_tenant": 2
                        },
                        "api_versions": {
                            "nova": {
                                "version": 2.2
                            }
                        }
                    }
                }
            ]
        }

    An example of specifying API version along with service type:

    .. code-block:: json

        # In this example we will launch CinderVolumes.create_and_attach_volume
        # scenario on Cinder V2
        {
            "version": 2,
            "title": "Launch CinderVolumes.create_and_attach_volume on V2",
            "subtasks": [
                {
                    "title": "Create and attach volume",
                    "scenario": {
                        "CinderVolumes.create_and_attach_volume": {
                            "size": 10,
                            "image": {
                                "name": "^cirros.*-disk$"
                            },
                            "flavor": {
                                "name": "m1.tiny"
                            },
                            "create_volume_params": {
                                "availability_zone": "nova"
                            }
                        }
                    },
                    "runner": {
                        "constant": {
                            "times": 5,
                            "concurrency": 1
                        }
                    },
                    "contexts": {
                        "users": {
                            "tenants": 2,
                            "users_per_tenant": 2
                        },
                        "api_versions": {
                            "cinder": {
                                "version": 2,
                                "service_type": "volumev2"
                            }
                        }
                    }
                }
            ]
        }

    Also, it possible to use service name as an identifier of service endpoint,
    but an admin user is required (Keystone can return map of service
    names - types, but such API is permitted only for admin). An example:

    .. code-block:: json

        # Similar to the previous example, but `service_name` argument is used
        # instead of `service_type`
        {
            "version": 2,
            "title": "Launch CinderVolumes.create_and_attach_volume on V2",
            "subtasks": [
                {
                    "title": "Create and attach volume",
                    "scenario": {
                        "CinderVolumes.create_and_attach_volume": {
                            "size": 10,
                            "image": {
                                "name": "^cirros.*-disk$"
                            },
                            "flavor": {
                                "name": "m1.tiny"
                            },
                            "create_volume_params": {
                                "availability_zone": "nova"
                            }
                        }
                    },
                    "runner": {
                        "constant": {
                            "times": 5,
                            "concurrency": 1
                        }
                    },
                    "contexts": {
                        "users": {
                            "tenants": 2,
                            "users_per_tenant": 2
                        },
                        "api_versions": {
                            "cinder": {
                                "version": 2,
                                "service_name": "cinderv2"
                            }
                        }
                    }
                }
            ]
        }

    """
    VERSION_SCHEMA = {
        "anyOf": [
            {"type": "string", "description": "a string-like version."},
            {"type": "number", "description": "a number-like version."}
        ]
    }
    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "patternProperties": {
            "^[a-z]+$": {
                "type": "object",
                "oneOf": [
                    {
                        "description": "version only",
                        "properties": {
                            "version": VERSION_SCHEMA,
                        },
                        "required": ["version"],
                        "additionalProperties": False
                    },
                    {
                        "description": "version and service_name",
                        "properties": {
                            "version": VERSION_SCHEMA,
                            "service_name": {"type": "string"}
                        },
                        "required": ["service_name"],
                        "additionalProperties": False
                    },
                    {
                        "description": "version and service_type",
                        "properties": {
                            "version": VERSION_SCHEMA,
                            "service_type": {"type": "string"}
                        },
                        "required": ["service_type"],
                        "additionalProperties": False
                    }
                ],
            }
        },
        "minProperties": 1,
        "additionalProperties": False
    }

    config: dict[str, dict[str, str | int]]

    def _prefetch_discovery(self):
        """Warm the version-discovery cache once for the scenario's services.

        openstacksdk resolves a service proxy's endpoint and API version with
        an on-the-wire discovery request the first time the proxy is accessed.
        Doing it here, in the context and before the credentials are pickled to
        worker processes, populates the picklable
        ``credential.discovery_cache`` so no discovery round-trip happens per
        worker or iteration.

        The services to warm are the workload scenario's ``required_services``
        that are backed by a ported (openstacksdk) client. A legacy
        ``python-*client`` wrapper resolves its version itself, so warming the
        SDK connection's discovery for it would be wasted work. Each ported
        client is warmed under its ``sdk_service_type`` proxy; keystone is a
        no-op there since it pins its endpoint via ``endpoint_override`` and
        never discovers. Discovery is user-independent, so it is fetched with a
        single credential and shared with the rest (one request per service,
        not one per user). Runs after ``api_info`` is finalized so connections
        are built with the pinned versions.
        """
        scenario_name = self.context.get("scenario_name")
        if not scenario_name:
            return
        try:
            scenario_cls = scenario.Scenario.get(scenario_name)
        except exceptions.PluginNotFound:
            return
        service_types = set()
        for name, _args, kwargs in scenario_cls._meta_get("validators"):
            if name != "required_services":
                continue
            services = kwargs.get("services", [])
            if not isinstance(services, (list, tuple)):
                services = [services]
            for service in services:
                try:
                    client_cls = osclients.BaseClient.get(service)
                except exceptions.PluginNotFound:
                    continue
                # Only ported clients resolve their version through the SDK
                # connection's discovery; legacy OSClient wrappers do not (this
                # is the same split Clients dispatches on).
                if issubclass(client_cls, osclients.OSClient):
                    continue
                sdk_type = client_cls.spec.sdk_service_type
                if sdk_type:
                    service_types.add(sdk_type)
        if not service_types:
            return

        credentials = [u["credential"] for u in self.context["users"]]
        admin_cred = self.context.get("admin", {}).get("credential")
        if admin_cred:
            credentials.append(admin_cred)
        if not credentials:
            return
        connection = osclients.Clients(credentials[0])._conn
        for service_type in service_types:
            try:
                # Accessing the proxy resolves its endpoint and version, which
                # is the discovery request we want to warm and cache.
                getattr(connection, service_type.replace("-", "_"))
            except Exception:
                LOG.debug(f"Failed to prefetch {service_type} version "
                          f"discovery; it will be resolved lazily per worker "
                          f"instead.", exc_info=True)
        discovered = credentials[0].discovery_cache
        for credential in credentials[1:]:
            credential.discovery_cache.update(discovered)

    def setup(self):
        # FIXME(andreykurilin): move all checks to validate method.

        # use admin only when `service_name` is presented
        admin_clients = osclients.Clients(
            self.context.get("admin", {}).get("credential"))
        clients = osclients.Clients(random.choice(
            self.context["users"])["credential"])
        services = clients.keystone.service_catalog.get_endpoints()
        services_from_admin: dict[str, str] | None = None
        for client_name, conf in self.config.items():
            if "service_type" in conf and conf["service_type"] not in services:
                raise exceptions.ValidationError(
                    "There is no service with '%s' type in your environment."
                    % conf["service_type"])
            elif "service_name" in conf:
                if not self.context.get("admin", {}).get("credential"):
                    raise exceptions.ContextSetupFailure(
                        ctx_name=self.get_name(),
                        msg="Setting 'service_name' is admin only operation.")
                if not services_from_admin:
                    services_from_admin = dict(
                        (s.name, s.type)
                        for s in admin_clients.keystone.list_services())
                if conf["service_name"] not in services_from_admin:
                    raise exceptions.ValidationError(
                        "There is no '%s' service in your environment"
                        % conf["service_name"])

                # TODO(boris-42): Use separate key ["openstack"]["versions"]
                self.context["config"]["api_versions@openstack"][client_name][
                    "service_type"] = services_from_admin[conf["service_name"]]

        admin_cred = self.context.get("admin", {}).get("credential")
        if admin_cred:
            admin_cred["api_info"].update(
                self.context["config"]["api_versions@openstack"]
            )
        for user in self.context["users"]:
            user["credential"]["api_info"].update(
                self.context["config"]["api_versions@openstack"]
            )

        self._prefetch_discovery()

    def cleanup(self):
        # nothing to do here
        pass
