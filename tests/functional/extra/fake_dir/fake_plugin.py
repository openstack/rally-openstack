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

from rally_openstack import osclients
from rally_openstack import scenario


@osclients.configure("fakedummy", default_version="1",
                     default_service_type="dummy",
                     supported_versions=["1", "2"])
class FakeDummy(osclients.OSClient):
    def create_client(self, version=None, service_type=None):
        version = self.choose_version(version)
        service_type = self.choose_service_type(service_type)
        return {"version": version, "service_type": service_type}


@osclients.configure("faileddummy", default_version="1",
                     default_service_type="faileddummy",
                     supported_versions=["1", "2"])
class FailedDummy(osclients.OSClient):
    def create_client(self, version=None, service_type=None):
        raise Exception("Failed Dummy")


@scenario.configure(name="FakeDummy.openstack_api")
class FakeDummyOpenstackAPI(scenario.OpenStackScenario):

    def run(self):
        admin_client = self.admin_clients("fakedummy")
        self.assertEqual("dummyv2", admin_client["service_type"])
        self.assertEqual("2", admin_client["version"])

        client = self.clients("fakedummy")
        self.assertEqual("dummyv2", client["service_type"])
        self.assertEqual("2", client["version"])
