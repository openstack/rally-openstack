# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import copy
from unittest import mock

from rally_openstack.task.contexts.nova import servers
from rally_openstack.task.scenarios.nova import utils as nova_utils
from tests.unit import fakes
from tests.unit import test

CTX = "rally_openstack.task.contexts.nova"
SCN = "rally_openstack.task.scenarios"
TYP = "rally_openstack.task.types"


class ServerGeneratorTestCase(test.ScenarioTestCase):

    def _gen_tenants(self, count):
        tenants = {}
        for id_ in range(count):
            tenants[str(id_)] = {"name": str(id_)}
        return tenants

    def test_init(self):
        tenants_count = 2
        servers_per_tenant = 5
        self.context.update({
            "config": {
                "servers": {
                    "servers_per_tenant": servers_per_tenant,
                }
            },
            "tenants": self._gen_tenants(tenants_count)})

        inst = servers.ServerGenerator(self.context)
        self.assertEqual({"auto_assign_nic": False, "servers_per_tenant": 5},
                         inst.config)

    @mock.patch("%s.nova.utils.NovaScenario._boot_servers" % SCN,
                return_value=[
                    fakes.FakeServer(id="uuid"),
                    fakes.FakeServer(id="uuid"),
                    fakes.FakeServer(id="uuid"),
                    fakes.FakeServer(id="uuid"),
                    fakes.FakeServer(id="uuid")
                ])
    @mock.patch("%s.GlanceImage" % TYP)
    @mock.patch("%s.Flavor" % TYP)
    def test_setup(self, mock_flavor, mock_glance_image,
                   mock_nova_scenario__boot_servers):

        tenants_count = 2
        users_per_tenant = 5
        servers_per_tenant = 5

        tenants = self._gen_tenants(tenants_count)
        users = []
        for id_ in tenants.keys():
            for i in range(users_per_tenant):
                users.append({"id": i, "tenant_id": id_,
                              "credential": mock.MagicMock()})

        self.context.update({
            "config": {
                "users": {
                    "tenants": 2,
                    "users_per_tenant": 5,
                    "concurrent": 10,
                },
                "servers": {
                    "auto_assign_nic": True,
                    "servers_per_tenant": 5,
                    "image": {
                        "name": "cirros-0.5.2-x86_64-uec",
                    },
                    "flavor": {
                        "name": "m1.tiny",
                    },
                    "nics": ["foo", "bar"]
                },
            },
            "admin": {
                "credential": mock.MagicMock()
            },
            "users": users,
            "tenants": tenants
        })

        new_context = copy.deepcopy(self.context)
        for id_ in new_context["tenants"]:
            new_context["tenants"][id_].setdefault("servers", [])
            for i in range(servers_per_tenant):
                new_context["tenants"][id_]["servers"].append("uuid")

        servers_ctx = servers.ServerGenerator(self.context)
        servers_ctx.setup()
        self.assertEqual(new_context, self.context)
        image_id = mock_glance_image.return_value.pre_process.return_value
        flavor_id = mock_flavor.return_value.pre_process.return_value
        servers_ctx_config = self.context["config"]["servers"]
        expected_auto_nic = servers_ctx_config.get("auto_assign_nic", False)
        expected_requests = servers_ctx_config.get("servers_per_tenant", False)
        called_times = len(tenants)
        mock_calls = [mock.call(image_id, flavor_id,
                                auto_assign_nic=expected_auto_nic,
                                nics=[{"net-id": "foo"}, {"net-id": "bar"}],
                                requests=expected_requests)
                      for i in range(called_times)]
        mock_nova_scenario__boot_servers.assert_has_calls(mock_calls)

    @mock.patch("%s.servers.resource_manager.cleanup" % CTX)
    def test_cleanup(self, mock_cleanup):

        tenants_count = 2
        users_per_tenant = 5
        servers_per_tenant = 5

        tenants = self._gen_tenants(tenants_count)
        users = []
        for id_ in tenants.keys():
            for i in range(users_per_tenant):
                users.append({"id": i, "tenant_id": id_,
                              "credential": "credential"})
            tenants[id_].setdefault("servers", [])
            for j in range(servers_per_tenant):
                tenants[id_]["servers"].append("uuid")

        self.context.update({
            "config": {
                "users": {
                    "tenants": 2,
                    "users_per_tenant": 5,
                    "concurrent": 10,
                },
                "servers": {
                    "servers_per_tenant": 5,
                    "image": {
                        "name": "cirros-0.5.2-x86_64-uec",
                    },
                    "flavor": {
                        "name": "m1.tiny",
                    },
                },
            },
            "admin": {
                "credential": mock.MagicMock()
            },
            "users": users,
            "tenants": tenants
        })

        servers_ctx = servers.ServerGenerator(self.context)
        servers_ctx.cleanup()

        mock_cleanup.assert_called_once_with(
            names=["nova.servers"],
            users=self.context["users"],
            superclass=nova_utils.NovaScenario,
            task_id=self.context["owner_id"])
