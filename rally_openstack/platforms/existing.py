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

from rally.common import cfg
from rally.common import logging
from rally.env import platform
from rally_openstack import osclients


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
                "oneOf": [
                    {
                        "description": "Keystone V2.0",
                        "properties": {
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                            "tenant_name": {"type": "string"},
                        },
                        "required": ["username", "password", "tenant_name"],
                        "additionalProperties": False
                    },
                    {
                        "description": "Keystone V3.0",
                        "properties": {
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                            "project_name": {"type": "string"},
                            "domain_name": {"type": "string"},
                            "user_domain_name": {"type": "string"},
                            "project_domain_name": {"type": "string"},
                        },
                        "required": ["username", "password", "project_name"],
                        "additionalProperties": False
                    }
                ],
            },
            "api_info": {
                "type": "object",
                "patternProperties": {
                    "^[a-z]+$": {
                        "type": "object",
                        "properties": {
                            "version": VERSION_SCHEMA,
                            "service_type": {"type": "string"}
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

    def create(self):
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

        if new_data.get("https_cert") and new_data.get("https_key"):
            new_data["https_cert"] = (new_data["https_cert"],
                                      new_data.pop("https_key"))

        if admin:
            if "project_name" in admin:
                admin["tenant_name"] = admin.pop("project_name")
            admin.update(new_data)
            for k, v in defaults.items():
                admin.setdefault(k, v)
        for user in users:
            if "project_name" in user:
                user["tenant_name"] = user.pop("project_name")
            user.update(new_data)
            for k, v in defaults.items():
                user.setdefault(k, v)
        platform_data = {"admin": admin, "users": users}
        if api_info:
            platform_data["api_info"] = api_info
        return platform_data, {}

    def destroy(self):
        # NOTE(boris-42): No action need to be performed.
        pass

    def cleanup(self, task_uuid=None):
        return {
            "message": "Coming soon!",
            "discovered": 0,
            "deleted": 0,
            "failed": 0,
            "resources": {},
            "errors": []
        }

    def check_health(self):
        """Check whatever platform is alive."""

        users_to_check = self.platform_data["users"]
        if self.platform_data["admin"]:
            users_to_check.append(self.platform_data["admin"])
        clients = None
        for user in users_to_check:
            user["api_info"] = self.platform_data.get("api_info", {})
            try:
                clients = osclients.Clients(user)
                if self.platform_data["admin"] == user:
                    clients.verified_keystone()
                else:
                    clients.keystone()
            except osclients.exceptions.RallyException as e:
                # all rally native exceptions should provide user-friendly
                # messages
                return {"available": False, "message": e.format_message(),
                        # traceback is redundant here. Remove as soon as min
                        #   required rally version will be updated
                        #   More details here:
                        #       https://review.openstack.org/597197
                        "traceback": traceback.format_exc()}
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
                return {
                    "available": False,
                    "message": (
                        "Bad %s creds: \n%s"
                        % (user_role,
                           json.dumps(d, indent=2, sort_keys=True))),
                    "traceback": traceback.format_exc()
                }

        for name in self.platform_data.get("api_info", {}):
            if name == "keystone":
                continue
            if not hasattr(clients, name):
                return {
                    "available": False,
                    "message": ("There is no OSClient plugin '%s' for"
                                " communicating with OpenStack API."
                                % name)}
            client = getattr(clients, name)
            try:
                client.validate_version(client.choose_version())
                client.create_client()
            except osclients.exceptions.RallyException as e:
                return {
                    "available": False,
                    "message": ("Invalid setting for '%(client)s':"
                                " %(error)s") % {
                        "client": name, "error": e.format_message()}
                }
            except Exception:
                return {
                    "available": False,
                    "message": ("Can not create '%(client)s' with"
                                " %(version)s version.") % {
                        "client": name,
                        "version": client.choose_version()},
                    "traceback": traceback.format_exc()
                }

        return {"available": True}

    def info(self):
        """Return information about cloud as dict."""
        active_user = (self.platform_data["admin"] or
                       self.platform_data["users"][0])
        services = []
        for stype, name in osclients.Clients(active_user).services().items():
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

    def _get_validation_context(self):
        return {"users@openstack": {}}

    @classmethod
    def create_spec_from_sys_environ(cls, sys_environ):
        """Create a spec based on system environment.

        .. envvar:: OS_AUTH_URL
            The auth url for OpenStack cluster. Supported both versioned and
            unversioned urls.

        .. envvar:: OS_USERNAME
            A user name with admin role to use.

        .. envvar:: OS_PASSWORD
            A password for selected user.

        .. envvar:: OS_PROJECT_NAME
            Project name to scope to

        .. envvar:: OS_TENANT_NAME
            Project name to scope to (an alternative for $OS_PROJECT_NAME)

        .. envvar:: OS_USER_DOMAIN_NAME
            User domain name (in case of Keystone V3)

        .. envvar:: OS_PROJECT_DOMAIN_NAME
            Domain name containing project (in case of Keystone V3)

        .. envvar:: OS_ENDPOINT_TYPE
             Type of endpoint. Valid endpoint types: admin, public, internal

        .. envvar:: OS_INTERFACE
             Type of endpoint (an alternative for $OS_INTERFACE)

        .. envvar:: OS_REGION_NAME
             Authentication region name

        .. envvar:: OS_CACERT
             A path to CA certificate bundle file

        .. envvar:: OS_CERT
             A path to Client certificate bundle file

        .. envvar:: OS_KEY
             A path to Client certificate key file

        .. envvar:: OS_INSECURE
             Disable server certificate verification

        .. envvar:: OSPROFILER_HMAC_KEY
             HMAC key to use for encrypting context while using osprofiler

        .. envvar:: OSPROFILER_CONN_STR
             A connection string for OSProfiler collector to grep profiling
             results while building html task reports
        """

        from oslo_utils import strutils

        required_env_vars = ["OS_AUTH_URL", "OS_USERNAME", "OS_PASSWORD"]
        missing_env_vars = [v for v in required_env_vars if
                            v not in sys_environ]
        if missing_env_vars:
            return {"available": False,
                    "message": "The following variable(s) are missed: %s" %
                               missing_env_vars}
        tenant_name = sys_environ.get("OS_PROJECT_NAME",
                                      sys_environ.get("OS_TENANT_NAME"))
        if tenant_name is None:
            return {"available": False,
                    "message": "One of OS_PROJECT_NAME or OS_TENANT_NAME "
                               "should be specified."}

        endpoint_type = sys_environ.get("OS_ENDPOINT_TYPE",
                                        sys_environ.get("OS_INTERFACE"))
        if endpoint_type and "URL" in endpoint_type:
            endpoint_type = endpoint_type.replace("URL", "")

        spec = {
            "auth_url": sys_environ["OS_AUTH_URL"],
            "admin": {
                "username": sys_environ["OS_USERNAME"],
                "password": sys_environ["OS_PASSWORD"],
                "tenant_name": tenant_name
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
            "api_info": {
                "keystone": {
                    "version": 2,
                    "service_type": "identity"
                }
            }
        }

        user_domain_name = sys_environ.get("OS_USER_DOMAIN_NAME")
        project_domain_name = sys_environ.get("OS_PROJECT_DOMAIN_NAME")
        identity_api_version = sys_environ.get(
            "OS_IDENTITY_API_VERSION", sys_environ.get("IDENTITY_API_VERSION"))
        if (identity_api_version == "3" or
                (identity_api_version is None and
                 (user_domain_name or project_domain_name))):
            # it is Keystone v3 and it has another config scheme
            spec["admin"]["project_name"] = spec["admin"].pop("tenant_name")
            spec["admin"]["user_domain_name"] = user_domain_name or "Default"
            project_domain_name = project_domain_name or "Default"
            spec["admin"]["project_domain_name"] = project_domain_name
            spec["api_info"] = {
                "keystone": {
                    "version": 3,
                    "service_type": "identityv3"
                }
            }

        return {"spec": spec, "available": True, "message": "Available"}

    @classmethod
    def _get_doc(cls):
        doc = cls.__doc__.strip()
        doc += "\n **Create a spec based on system environment.**\n"
        # cut the first line since we already included the first line of it.
        doc += "\n".join(
            [line.strip() for line in
             cls.create_spec_from_sys_environ.__doc__.split("\n")][1:])
        return doc
