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

import ddt

from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.common import credential
from rally_openstack.task import scenario
from rally_openstack.task.contexts import clients_prefetch
from tests.unit import fakes
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


def _credential(username):
    return credential.OpenStackCredential(
        "https://keystone.example.com/v3", username, "secret", "project",
        api_info={"keystone": {"version": 3}})


@ddt.ddt
class ClientsPrefetchTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        self.cloud = fakes.FakeOpenStack(self)

    @ddt.data(True, False)
    def test_setup(self, with_admin):
        self.cloud.skip_discovery.add("image")
        users = [_credential("u1"), _credential("u2")]
        creds = ([_credential("admin")] if with_admin else []) + users
        ctx = {"scenario_name": "ClientsPrefetchTestCase.mixed_services",
               "users": [{"credential": u} for u in users]}
        if with_admin:
            ctx["admin"] = {"credential": creds[0]}

        clients_prefetch.ClientsPrefetch(ctx).setup()

        self.assertEqual(1, len(self.cloud.connections))
        self.assertIs(creds[0].discovery_cache,
                      self.cloud.connections[0].session._discovery_cache)
        self.assertEqual(["image", "network"], self.cloud.accessed)
        expected = {"https://network.example.com/": {"service": "network"}}
        for cred in creds:
            self.assertEqual(expected, cred.discovery_cache)

    def test_setup_tolerates_discovery_errors(self):
        self.cloud.errors["network"] = RuntimeError("boom")
        users = [_credential("u1"), _credential("u2")]
        ctx = {"scenario_name": "ClientsPrefetchTestCase.mixed_services",
               "users": [{"credential": u} for u in users]}

        clients_prefetch.ClientsPrefetch(ctx).setup()

        self.assertEqual(["image", "network"], self.cloud.accessed)
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

        self.assertEqual([], self.cloud.accessed)
        for user in ctx["users"]:
            self.assertEqual({}, user["credential"].discovery_cache)
