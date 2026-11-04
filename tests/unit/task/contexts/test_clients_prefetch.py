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

from unittest import mock

import ddt

from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.common import credential
from rally_openstack.task import scenario
from rally_openstack.task.contexts import clients_prefetch
from tests.unit import test


@validation.add("required_services",
                services=[consts.Service.NOVA, consts.Service.GLANCE,
                          consts.Service.NEUTRON, "unknown"])
@validation.add("required_services", services=[consts.Service.NEUTRON])
@scenario.configure(name="ClientsPrefetchTestCase.mixed_services",
                    platform="openstack")
class MixedServicesScenario(scenario.OpenStackScenario):
    """Requires legacy, ported and unknown services."""

    def run(self) -> None:
        pass


@validation.add("required_services", services=[consts.Service.NOVA])
@scenario.configure(name="ClientsPrefetchTestCase.legacy_services",
                    platform="openstack")
class LegacyServicesScenario(scenario.OpenStackScenario):
    """Requires only services backed by a legacy python-*client."""

    def run(self) -> None:
        pass


class FakeProxy:
    """An openstacksdk proxy whose discovery fills the session cache."""

    def __init__(self, session, service_type, skip_discovery, error):
        self._session = session
        self._service_type = service_type
        self.skip_discovery = skip_discovery
        self._error = error

    def get_endpoint_data(self):
        if self._error:
            raise self._error
        url = f"https://{self._service_type}.example.com/"
        self._session._discovery_cache[url] = {"service": self._service_type}


class FakeConnection:
    """An openstacksdk Connection exposing the image and network proxies."""

    def __init__(self, session, skip_discovery, errors):
        self.session = session
        self.accessed = []
        self._proxies = {
            name: FakeProxy(session, name, name in skip_discovery,
                            errors.get(name))
            for name in ("image", "network")
        }

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        self.accessed.append(name)
        if name not in self._proxies:
            raise AttributeError(name)
        return self._proxies[name]


def _credential(username):
    return credential.OpenStackCredential(
        "https://keystone.example.com/v3", username, "secret", "project",
        api_info={"keystone": {"version": 3}})


@ddt.ddt
class ClientsPrefetchTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.skip_discovery = set()
        self.errors = {}
        self.connections = []

        def connection(session, **kwargs):
            conn = FakeConnection(session, self.skip_discovery, self.errors)
            self.connections.append(conn)
            return conn

        patcher = mock.patch("openstack.connection.Connection",
                             side_effect=connection)
        patcher.start()
        self.addCleanup(patcher.stop)

    @ddt.data(True, False)
    def test_setup(self, with_admin):
        self.skip_discovery.add("image")
        users = [_credential("u1"), _credential("u2")]
        creds = ([_credential("admin")] if with_admin else []) + users
        ctx = {"scenario_name": "ClientsPrefetchTestCase.mixed_services",
               "users": [{"credential": u} for u in users]}
        if with_admin:
            ctx["admin"] = {"credential": creds[0]}

        clients_prefetch.ClientsPrefetch(ctx).setup()

        self.assertEqual(1, len(self.connections))
        conn = self.connections[0]
        self.assertIs(creds[0].discovery_cache, conn.session._discovery_cache)
        self.assertEqual(["image", "network"], sorted(conn.accessed))
        expected = {"https://network.example.com/": {"service": "network"}}
        for cred in creds:
            self.assertEqual(expected, cred.discovery_cache)

    def test_setup_tolerates_discovery_errors(self):
        self.errors["network"] = RuntimeError("boom")
        users = [_credential("u1"), _credential("u2")]
        ctx = {"scenario_name": "ClientsPrefetchTestCase.mixed_services",
               "users": [{"credential": u} for u in users]}

        clients_prefetch.ClientsPrefetch(ctx).setup()

        self.assertEqual(["image", "network"],
                         sorted(self.connections[0].accessed))
        self.assertEqual(
            {"https://image.example.com/": {"service": "image"}},
            users[1].discovery_cache)

    @ddt.data(
        {"users": [],
         "scenario_name": "ClientsPrefetchTestCase.mixed_services"},
        {"users": [{"credential": _credential("u1")}]},
        {"users": [{"credential": _credential("u1")}],
         "scenario_name": "ClientsPrefetchTestCase.unknown"},
        {"users": [{"credential": _credential("u1")}],
         "scenario_name": "ClientsPrefetchTestCase.legacy_services"},
    )
    def test_setup_without_services_to_warm(self, ctx):
        clients_prefetch.ClientsPrefetch(ctx).setup()

        self.assertEqual([], [name for conn in self.connections
                              for name in conn.accessed])
        for user in ctx["users"]:
            self.assertEqual({}, user["credential"].discovery_cache)
