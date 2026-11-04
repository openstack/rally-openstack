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
import json
import traceback
import typing as t

from rally.common import cfg
from rally.common import logging
from rally.env import platform

from rally_openstack.common import credential
from rally_openstack.common import osclients


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


@platform.configure(name="existing", platform="openstack")
class OpenStack(platform.Platform):
    """Default plugin for OpenStack platform

    It may be used to test any existing OpenStack API compatible cloud.
    """

    VERSION_SCHEMA = {
        "anyOf": [
            {"type": "string", "description": "a string-like version."},
            {"type": "number", "description": "a number-like version."}
        ]
    }

    CONFIG_SCHEMA = {
        "type": "object",
        "definitions": {
            "user": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "project_name": {"type": "string"},
                    "tenant_name": {"type": "string"},
                    "domain_name": {"type": "string"},
                    "user_domain_name": {"type": "string"},
                    "project_domain_name": {"type": "string"},
                },
                "additionalProperties": False,
                "anyOf": [
                    {
                        "description": "Keystone V2.0 (old-style)",
                        "required": ["username", "password", "tenant_name"]
                    },
                    {
                        "description": "Keystone V3.0 (modern terms)",
                        "required": ["username", "password", "project_name"]
                    }
                ]
            },
            "api_info": {
                "type": "object",
                "patternProperties": {
                    "^(?!neutron)([a-z]+)$": {
                        "type": "object",
                        "properties": {
                            "version": VERSION_SCHEMA,
                            "service_type": {"type": "string"}
                        },
                        "minProperties": 1,
                        "additionalProperties": False
                    },
                    "^neutron$": {
                        "type": "object",
                        "properties": {
                            "version": VERSION_SCHEMA,
                            "service_type": {"type": "string"},
                            "pre_newton": {
                                "type": "boolean",
                                "description": "Whether Neutron API is older "
                                               "then OpenStack Newton or not. "
                                               "Based on this option, some "
                                               "external fields for "
                                               "identifying resources can be "
                                               "applied."
                            }
                        },
                        "minProperties": 1,
                        "additionalProperties": False
                    }
                },
                "additionalProperties": False
            }
        },
        "properties": {
            "auth_url": {"type": "string"},
            "region_name": {"type": "string"},
            "endpoint": {"type": ["string", "null"]},
            "endpoint_type": {"enum": ["public", "internal", "admin", None]},
            "https_insecure": {"type": "boolean"},
            "https_cacert": {"type": "string"},
            "https_cert": {"type": "string"},
            "https_key": {"type": "string"},
            "profiler_hmac_key": {"type": ["string", "null"]},
            "profiler_conn_str": {"type": ["string", "null"]},
            "admin": {"$ref": "#/definitions/user"},
            "users": {
                "type": "array",
                "items": {"$ref": "#/definitions/user"},
                "minItems": 1
            },
            "api_info": {"$ref": "#/definitions/api_info"}
        },
        "anyOf": [
            {
                "description": "The case when the admin is specified and the "
                               "users can be created via 'users@openstack' "
                               "context or 'existing_users' will be used.",
                "required": ["admin", "auth_url"]},
            {
                "description": "The case when the only existing users are "
                               "specified.",
                "required": ["users", "auth_url"]}
        ],
        "additionalProperties": False
    }

    def create(self) -> tuple[dict[str, t.Any], dict[str, t.Any]]:
        defaults = {
            "region_name": None,
            "endpoint_type": None,
            "domain_name": None,
            "user_domain_name": cfg.CONF.openstack.user_domain,
            "project_domain_name": cfg.CONF.openstack.project_domain,
            "https_insecure": False,
            "https_cacert": None
        }

        """Converts creds of real OpenStack to internal presentation."""
        new_data = copy.deepcopy(self.spec)
        if "endpoint" in new_data:
            LOG.warning("endpoint is deprecated and not used.")
            del new_data["endpoint"]
        admin = new_data.pop("admin", None)
        users = new_data.pop("users", [])
        api_info = new_data.pop("api_info", None)

        # NOTE(andreykurilin): rally core reads 'tenant_name' from the stored
        #   credentials (`rally deployment use/show`), so it is kept as a copy
        #   of 'project_name' until rally core switches to the latter.
        if admin:
            admin["project_name"] = admin.get(
                "project_name", admin.get("tenant_name"))
            admin["tenant_name"] = admin["project_name"]
            admin.update(new_data)
            for k, v in defaults.items():
                admin.setdefault(k, v)
        for user in users:
            user["project_name"] = user.get(
                "project_name", user.get("tenant_name"))
            user["tenant_name"] = user["project_name"]
            user.update(new_data)
            for k, v in defaults.items():
                user.setdefault(k, v)
        platform_data = {"admin": admin, "users": users}
        if api_info:
            platform_data["api_info"] = api_info
        return platform_data, {}

    def destroy(self) -> None:
        # NOTE(boris-42): No action need to be performed.
        pass

    def cleanup(self, task_uuid: str | None = None) -> platform.CleanupInfo:
        return {
            "message": "Coming soon!",
            "discovered": 0,
            "deleted": 0,
            "failed": 0,
            "resources": {},
            "errors": []
        }

    def check_health(self) -> platform.HealthInfo:
        """Check whatever platform is alive."""

        # it should never happen
        if not self.platform_data:
            return platform.HealthInfo(available=False)

        users_to_check = self.platform_data["users"]
        if self.platform_data["admin"]:
            users_to_check.append(self.platform_data["admin"])
        clients = None
        for user in users_to_check:
            user["api_info"] = self.platform_data.get("api_info", {})
            try:
                clients = osclients.Clients(
                    credential.OpenStackCredential(**user))
                if self.platform_data["admin"] == user:
                    clients.verified_keystone()
                else:
                    clients.keystone.auth_ref
            except osclients.exceptions.RallyException as e:
                # all rally native exceptions should provide user-friendly
                # messages
                return platform.HealthInfo(
                    available=False,
                    message=e.format_message(),
                    traceback=traceback.format_exc()
                )
            except Exception:
                d = copy.deepcopy(user)
                d["password"] = "***"
                if logging.is_debug():
                    LOG.exception("Something unexpected had happened while "
                                  "validating OpenStack credentials.")
                if self.platform_data["admin"] == user:
                    user_role = "admin"
                else:
                    user_role = "user"
                return platform.HealthInfo(
                    available=False,
                    message=f"Bad {user_role} creds: \n"
                            f"{json.dumps(d, indent=2, sort_keys=True)}",
                    traceback=traceback.format_exc(),
                )

        for name in self.platform_data.get("api_info", {}):
            if name == "keystone":
                continue
            if not hasattr(clients, name):
                return platform.HealthInfo(
                    available=False,
                    message=f"There is no OSClient plugin '{name}' for "
                            f"communicating with OpenStack API."
                )
            client = getattr(clients, name)
            try:
                client.spec.validate_version(client.choose_version())
                client.create_client()
            except osclients.exceptions.RallyException as e:
                return platform.HealthInfo(
                    available=False,
                    message=f"Invalid setting for '{name}': "
                            f"{e.format_message()}"
                )
            except Exception:
                return platform.HealthInfo(
                    available=False,
                    message=f"Can not create '{name}' with "
                            f"{client.choose_version()} version.",
                    traceback=traceback.format_exc()
                )

        return platform.HealthInfo(available=True)

    def info(self) -> platform.PlatformInfo:
        """Return information about cloud as dict."""
        # it should never happen
        if not self.platform_data:
            return platform.PlatformInfo(info={})

        active_user = (self.platform_data["admin"]
                       or self.platform_data["users"][0])
        services = []
        clients = osclients.Clients(
            credential.OpenStackCredential(**active_user))
        for stype, name in clients.services().items():
            if name == "__unknown__":
                # `__unknown__` name misleads, let's just not include it...
                services.append({"type": stype})
            else:
                services.append({"type": stype, "name": name})

        return {
            "info": {
                "services": sorted(services, key=lambda x: x["type"])
            }
        }

    def _get_validation_context(self) -> dict[str, t.Any]:
        return {"users@openstack": {}}

    @classmethod
    def create_spec_from_sys_environ(
        cls, sys_environ: t.Mapping[str, str]
    ) -> platform.SysEnvSpec:
        """Create a spec based on system environment.

        * OS_AUTH_URL - The auth url for OpenStack cluster. Supported both
          versioned and unversioned urls.

        * OS_USERNAME - A user name with admin role to use.

        * OS_PASSWORD - A password for selected user.

        * OS_PROJECT_NAME - Project name to scope to

        * OS_TENANT_NAME - Project name to scope to (an alternative for
          $OS_PROJECT_NAME)

        * OS_USER_DOMAIN_NAME - User domain name (in case of Keystone V3)

        * OS_PROJECT_DOMAIN_NAME - Domain name containing project (in case of
          Keystone V3)

        * OS_IDENTITY_API_VERSION - Keystone API version. Keystone V3 is used
          unless it is set to 2

        * OS_ENDPOINT_TYPE - Type of endpoint. Valid endpoint types: admin,
          public, internal

        * OS_INTERFACE - Type of endpoint (an alternative for OS_ENDPOINT_TYPE)

        * OS_REGION_NAME - Authentication region name

        * OS_CACERT - A path to CA certificate bundle file

        * OS_CERT - A path to Client certificate bundle file

        * OS_KEY - A path to Client certificate key file

        * OS_INSECURE - Disable server certificate verification

        * OSPROFILER_HMAC_KEY - HMAC key to use for encrypting context while
          using osprofiler

        * OSPROFILER_CONN_STR - A connection string for OSProfiler collector
          to grep profiling results while building html task reports

        """

        from oslo_utils import strutils  # type: ignore[import-untyped]

        required_env_vars = ["OS_AUTH_URL", "OS_USERNAME", "OS_PASSWORD"]
        missing_env_vars = [v for v in required_env_vars if
                            v not in sys_environ]
        if missing_env_vars:
            return {"available": False,
                    "message": "The following variable(s) are missed: %s" %
                               missing_env_vars}
        project_name = sys_environ.get("OS_PROJECT_NAME",
                                       sys_environ.get("OS_TENANT_NAME"))
        if project_name is None:
            return {"available": False,
                    "message": "One of OS_PROJECT_NAME or OS_TENANT_NAME "
                               "should be specified."}

        endpoint_type = sys_environ.get("OS_ENDPOINT_TYPE",
                                        sys_environ.get("OS_INTERFACE"))
        if endpoint_type and "URL" in endpoint_type:
            endpoint_type = endpoint_type.replace("URL", "")

        spec: dict[str, t.Any] = {
            "auth_url": sys_environ["OS_AUTH_URL"],
            "admin": {
                "username": sys_environ["OS_USERNAME"],
                "password": sys_environ["OS_PASSWORD"],
                "project_name": project_name
            },
            "endpoint_type": endpoint_type,
            "region_name": sys_environ.get("OS_REGION_NAME", ""),
            "https_cacert": sys_environ.get("OS_CACERT", ""),
            "https_cert": sys_environ.get("OS_CERT", ""),
            "https_key": sys_environ.get("OS_KEY", ""),
            "https_insecure": strutils.bool_from_string(
                sys_environ.get("OS_INSECURE")),
            "profiler_hmac_key": sys_environ.get("OSPROFILER_HMAC_KEY"),
            "profiler_conn_str": sys_environ.get("OSPROFILER_CONN_STR"),
        }

        identity_api_version = sys_environ.get(
            "OS_IDENTITY_API_VERSION", sys_environ.get("IDENTITY_API_VERSION"))
        if identity_api_version == "2":
            spec["api_info"] = {
                "keystone": {
                    "version": 2,
                    "service_type": "identity"
                }
            }
        else:
            spec["admin"]["user_domain_name"] = sys_environ.get(
                "OS_USER_DOMAIN_NAME") or "Default"
            spec["admin"]["project_domain_name"] = sys_environ.get(
                "OS_PROJECT_DOMAIN_NAME") or "Default"
            spec["api_info"] = {
                "keystone": {
                    "version": 3,
                    "service_type": "identityv3"
                }
            }

        return {"spec": spec, "available": True, "message": "Available"}

    @classmethod
    def _get_doc(cls) -> str:
        doc = (cls.__doc__ or "").strip()

        env_vars_docs = cls.create_spec_from_sys_environ.__doc__ or ""
        env_vars_description = "\n".join(
            line for line in env_vars_docs.split("\n")[1:]
        )
        doc += (f"\n\n**The following environment variables are expected for "
                f"creation a Rally environment using system environment "
                f"variables**\n{env_vars_description}")
        return doc
