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

import json
from unittest import mock

import ddt
import jsonschema

from rally import exceptions
from rally.env import env_mgr
from rally.env import platform

from rally_openstack.common import credential
from rally_openstack.common import osclients
from rally_openstack.environment.platforms import existing
from tests.unit import fakes
from tests.unit import test


def _user(username):
    return {"auth_url": "http://example.com", "username": username,
            "password": "12345", "project_name": "project"}


class PlatformBaseTestCase(test.TestCase):

    def _check_schema(self, schema, obj):
        jsonschema.validate(obj, schema)

    def _check_health_schema(self, obj):
        self._check_schema(env_mgr.EnvManager._HEALTH_FORMAT, obj)

    def _check_cleanup_schema(self, obj):
        self._check_schema(env_mgr.EnvManager._CLEANUP_FORMAT, obj)

    def _check_info_schema(self, obj):
        self._check_schema(env_mgr.EnvManager._INFO_FORMAT, obj)


@ddt.ddt
class ExistingPlatformTestCase(PlatformBaseTestCase):

    def test_validate_spec_schema(self):
        spec = {
            "existing@openstack": {
                "auth_url": "url",
                "admin": {
                    "username": "admin",
                    "password": "password123",
                    "tenant_name": "admin"
                },
                "users": [{
                    "username": "admin",
                    "password": "password123",
                    "tenant_name": "admin"
                }]
            }
        }
        result = platform.Platform.validate("existing@openstack", {},
                                            spec, spec["existing@openstack"])
        self.assertEqual([], result)

    def test_validate_invalid_spec(self):
        spec = {
            "existing@openstack": {
                "something_wrong": {
                    "username": "not_an_admin",
                    "password": "password123",
                    "project_name": "not_an_admin"
                }
            }
        }
        result = platform.Platform.validate("existing@openstack", {},
                                            spec, spec["existing@openstack"])
        self.assertNotEqual([], result)

    def test_validate_spec_schema_with_api_info(self):
        spec = {
            "existing@openstack": {
                "auth_url": "url",
                "admin": {
                    "username": "admin",
                    "password": "password123",
                    "tenant_name": "admin"
                },
                "api_info": {
                    "nova": {"version": 1},
                    "cinder": {"version": 2, "service_type": "volumev2"}
                }
            }
        }
        result = platform.Platform.validate("existing@openstack", {},
                                            spec, spec["existing@openstack"])
        self.assertEqual([], result)

    def test_create_users_only(self):

        spec = {
            "auth_url": "https://best",
            "endpoint": "check_that_its_poped",
            "users": [
                {"project_name": "a", "username": "a", "password": "a"},
                {"project_name": "b", "username": "b", "password": "b"}
            ]
        }

        self.assertEqual(
            ({
                "admin": None,
                "users": [
                    {
                        "auth_url": "https://best", "endpoint_type": None,
                        "region_name": None,
                        "domain_name": None,
                        "user_domain_name": "default",
                        "project_domain_name": "default",
                        "https_insecure": False, "https_cacert": None,
                        "project_name": "a", "tenant_name": "a",
                        "username": "a", "password": "a"
                    },
                    {
                        "auth_url": "https://best", "endpoint_type": None,
                        "region_name": None,
                        "domain_name": None,
                        "user_domain_name": "default",
                        "project_domain_name": "default",
                        "https_insecure": False, "https_cacert": None,
                        "project_name": "b", "tenant_name": "b",
                        "username": "b", "password": "b"
                    }
                ]
            }, {}),
            existing.OpenStack(spec).create())

    def test_create_admin_only(self):
        spec = {
            "auth_url": "https://best",
            "endpoint_type": "public",
            "https_insecure": True,
            "https_cacert": "/my.ca",
            "profiler_hmac_key": "key",
            "profiler_conn_str": "http://prof",
            "admin": {
                "domain_name": "d", "user_domain_name": "d",
                "project_domain_name": "d", "project_name": "d",
                "username": "d", "password": "d"
            }
        }
        self.assertEqual(
            (
                {
                    "admin": {
                        "auth_url": "https://best",
                        "endpoint_type": "public",
                        "https_insecure": True, "https_cacert": "/my.ca",
                        "profiler_hmac_key": "key",
                        "profiler_conn_str": "http://prof",
                        "region_name": None, "domain_name": "d",
                        "user_domain_name": "d", "project_domain_name": "d",
                        "project_name": "d", "tenant_name": "d",
                        "username": "d", "password": "d"
                    },
                    "users": []
                },
                {}
            ),
            existing.OpenStack(spec).create())

    def test_create_with_legacy_tenant_name(self):
        spec = {
            "auth_url": "https://best",
            "admin": {"tenant_name": "t", "username": "a", "password": "a"},
            "users": [{"tenant_name": "u", "username": "u", "password": "u"}]
        }

        platform_data, _ = existing.OpenStack(spec).create()

        self.assertEqual("t", platform_data["admin"]["project_name"])
        self.assertEqual("t", platform_data["admin"]["tenant_name"])
        self.assertEqual("u", platform_data["users"][0]["project_name"])
        self.assertEqual("u", platform_data["users"][0]["tenant_name"])

    def test_create_spec_from_sys_environ(self):
        sys_env = {
            "OS_IDENTITY_API_VERSION": "2",
            "OS_AUTH_URL": "https://example.com",
            "OS_USERNAME": "user",
            "OS_PASSWORD": "pass",
            "OS_TENANT_NAME": "projectX",
            "OS_INTERFACE": "publicURL",
            "OS_REGION_NAME": "Region1",
            "OS_CACERT": "Cacert",
            "OS_CERT": "cert",
            "OS_KEY": "key",
            "OS_INSECURE": True,
            "OSPROFILER_HMAC_KEY": "hmackey",
            "OSPROFILER_CONN_STR": "https://example2.com",
        }

        result = existing.OpenStack.create_spec_from_sys_environ(sys_env)
        self.assertTrue(result["available"])
        self.assertEqual(
            {
                "admin": {
                    "username": "user",
                    "project_name": "projectX",
                    "password": "pass"
                },
                "auth_url": "https://example.com",
                "endpoint_type": "public",
                "region_name": "Region1",
                "https_cacert": "Cacert",
                "https_cert": "cert",
                "https_key": "key",
                "https_insecure": True,
                "profiler_hmac_key": "hmackey",
                "profiler_conn_str": "https://example2.com",
                "api_info": {
                    "keystone": {
                        "version": 2,
                        "service_type": "identity"
                    }
                }
            }, result["spec"])

        sys_env.pop("OS_IDENTITY_API_VERSION")
        sys_env["OS_PROJECT_DOMAIN_NAME"] = "pdom"

        result = existing.OpenStack.create_spec_from_sys_environ(sys_env)

        self.assertEqual(
            {
                "admin": {
                    "username": "user",
                    "project_name": "projectX",
                    "user_domain_name": "Default",
                    "password": "pass",
                    "project_domain_name": "pdom"
                },
                "endpoint_type": "public",
                "auth_url": "https://example.com",
                "region_name": "Region1",
                "https_cacert": "Cacert",
                "https_cert": "cert",
                "https_key": "key",
                "https_insecure": True,
                "profiler_hmac_key": "hmackey",
                "profiler_conn_str": "https://example2.com",
                "api_info": {
                    "keystone": {
                        "version": 3,
                        "service_type": "identityv3"
                    }
                }
            }, result["spec"])

    def test_create_spec_from_sys_environ_fails_with_missing_vars(self):
        sys_env = {"OS_AUTH_URL": "https://example.com"}
        result = existing.OpenStack.create_spec_from_sys_environ(sys_env)
        self.assertFalse(result["available"])
        self.assertIn("OS_USERNAME", result["message"])
        self.assertIn("OS_PASSWORD", result["message"])
        self.assertNotIn("OS_AUTH_URL", result["message"])

        sys_env = {"OS_AUTH_URL": "https://example.com",
                   "OS_USERNAME": "user",
                   "OS_PASSWORD": "pass"}
        result = existing.OpenStack.create_spec_from_sys_environ(sys_env)
        self.assertFalse(result["available"])
        self.assertIn("OS_PROJECT_NAME or OS_TENANT_NAME", result["message"])

    def test_destroy(self):
        self.assertIsNone(existing.OpenStack({}).destroy())

    def test_cleanup(self):
        result1 = existing.OpenStack({}).cleanup()
        result2 = existing.OpenStack({}).cleanup(task_uuid="any")
        self.assertEqual(result1, result2)
        self.assertEqual(
            {
                "message": "Coming soon!",
                "discovered": 0,
                "deleted": 0,
                "failed": 0,
                "resources": {},
                "errors": []
            },
            result1
        )
        self._check_cleanup_schema(result1)

    @ddt.data(
        ({}, (3, 0), [], ["identity"]),
        ({"glance": {"version": 2}, "neutron": {"service_type": "network"}},
         (3, 0), [], ["identity", "image", "network"]),
        ({"glance": {"version": 1}, "keystone": {"version": 2}},
         (2, 0), [("glance", 1), ("keystone", 2)],
         ["identity", "identity", "image"]),
        ({}, (2, 0), [("keystone", 2)], ["identity"]),
    )
    @ddt.unpack
    def test_check_health(self, api_info, identity_version, deprecated,
                          accessed):
        cloud = fakes.FakeOpenStack(self)
        cloud.identity_version = identity_version
        pdata = {"admin": _user("admin"),
                 "users": [_user("u1"), _user("u2")],
                 "api_info": api_info}

        result = existing.OpenStack({}, platform_data=pdata).check_health()

        self._check_health_schema(result)
        expected = {"available": True}
        if deprecated:
            expected["message"] = "\n".join(
                osclients.BaseClient.get(name).spec.get_deprecation(version)
                for name, version in deprecated)
        self.assertEqual(expected, result)
        self.assertEqual(accessed, cloud.accessed)

    @ddt.data(
        ({"api_info": {"fakeclient": {"version": 1}}},
         "There is no OSClient plugin 'fakeclient' for communicating with "
         "OpenStack API."),
        ({"api_info": {"glance": {"version": 5}}},
         "Invalid setting for 'glance': Validation error: '5' is not "
         "supported. Should be one of '('1', '2')'"),
        ({"api_info": {"glance": {}},
          "errors": {"image": exceptions.RallyException("unreachable")}},
         "Invalid setting for 'glance': unreachable"),
        ({"api_info": {"glance": {}}, "errors": {"image": RuntimeError()}},
         "Can not create 'glance' with 2 version."),
        ({"admins": set()}, "user 'admin' doesn't have 'admin' role"),
        ({"auth_error": RuntimeError("bad password")},
         "Failed to authenticate to http://example.com for user 'u1' in "
         "project 'project': [RuntimeError] bad password"),
        ({"identity_version": None, "api_info": {"keystone": {"version": 3}}},
         "Invalid setting for 'keystone': Unable to determine the identity "
         "API version."),
        ({"users": [], "admin": None},
         "There are no OpenStack credentials to check."),
        ({"users": [{"auth_url": "http://example.com", "username": "u1",
                     "password": "12345"}]},
         "Bad user creds: \n" + json.dumps(
             {"api_info": {}, "auth_url": "http://example.com",
              "password": "***", "username": "u1"},
             indent=2, sort_keys=True)),
    )
    @ddt.unpack
    def test_check_health_failed(self, case, message):
        cloud = fakes.FakeOpenStack(self)
        cloud.errors = case.get("errors", {})
        cloud.admins = case.get("admins", cloud.admins)
        cloud.auth_error = case.get("auth_error")
        cloud.identity_version = case.get("identity_version",
                                          cloud.identity_version)
        pdata = {"admin": case.get("admin", _user("admin")),
                 "users": case.get("users", [_user("u1")]),
                 "api_info": case.get("api_info", {})}

        result = existing.OpenStack({}, platform_data=pdata).check_health()

        self._check_health_schema(result)
        self.assertFalse(result["available"])
        self.assertEqual(message, result["message"])

    @mock.patch("rally_openstack.common.osclients.Clients")
    def test_info(self, mock_clients):
        mock_clients.return_value.services.return_value = {
            "foo": "bar",
            "volumev4": "__unknown__"}
        platform_data = {"admin": None, "users": [_user("u1")]}
        p = existing.OpenStack({}, platform_data=platform_data)

        result = p.info()
        mock_clients.assert_called_once_with(
            credential.OpenStackCredential(**platform_data["users"][0]))
        mock_clients.return_value.services.assert_called_once_with()
        self.assertEqual(
            {
                "info": {
                    "services": [{"type": "foo", "name": "bar"},
                                 {"type": "volumev4"}]}},
            result)
        self._check_info_schema(result)
