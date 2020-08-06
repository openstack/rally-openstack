# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
# Author: Endre Karlson <endre.karlson@hp.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import random

from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.designate import utils


"""Basic scenarios for Designate."""


@validation.add("required_services",
                services=[consts.Service.DESIGNATE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["designate"]},
                    name="DesignateBasic.create_and_list_zones",
                    platform="openstack")
class CreateAndListZones(utils.DesignateScenario):

    def run(self):
        """Create a zone and list all zones.

        Measure the "openstack zone list" command performance.

        If you have only 1 user in your context, you will
        add 1 zone on every iteration. So you will have more
        and more zone and will be able to measure the
        performance of the "openstack zone list" command depending on
        the number of zones owned by users.
        """
        zone = self._create_zone()
        self.assertTrue(zone)
        list_zones = self._list_zones()
        self.assertIn(zone, list_zones)


@validation.add("required_services",
                services=[consts.Service.DESIGNATE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="DesignateBasic.list_zones", platform="openstack")
class ListZones(utils.DesignateScenario):

    def run(self):
        """List Designate zones.

        This simple scenario tests the openstack zone list command by listing
        all the zones.
        """

        self._list_zones()


@validation.add("required_services",
                services=[consts.Service.DESIGNATE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["designate"]},
                    name="DesignateBasic.create_and_delete_zone",
                    platform="openstack")
class CreateAndDeleteZone(utils.DesignateScenario):

    def run(self):
        """Create and then delete a zone.

        Measure the performance of creating and deleting zones
        with different level of load.
        """
        zone = self._create_zone()
        self._delete_zone(zone["id"])


@validation.add("required_services",
                services=[consts.Service.DESIGNATE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="DesignateBasic.list_recordsets",
                    platform="openstack")
class ListRecordsets(utils.DesignateScenario):

    def run(self, zone_id):
        """List Designate recordsets.

        This simple scenario tests the openstack recordset list command by
        listing all the recordsets in a zone.

        :param zone_id: Zone ID
        """

        self._list_recordsets(zone_id)


@validation.add("required_services",
                services=[consts.Service.DESIGNATE])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=("zones"))
@scenario.configure(context={"cleanup@openstack": ["designate"]},
                    name="DesignateBasic.create_and_delete_recordsets",
                    platform="openstack")
class CreateAndDeleteRecordsets(utils.DesignateScenario):

    def run(self, recordsets_per_zone=5):
        """Create and then delete recordsets.

        Measure the performance of creating and deleting recordsets
        with different level of load.

        :param recordsets_per_zone: recordsets to create pr zone.
        """
        zone = random.choice(self.context["tenant"]["zones"])

        recordsets = []

        for i in range(recordsets_per_zone):
            recordset = self._create_recordset(zone)
            recordsets.append(recordset)

        for recordset in recordsets:
            self._delete_recordset(
                zone["id"], recordset["id"])


@validation.add("required_services",
                services=[consts.Service.DESIGNATE])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=("zones"))
@scenario.configure(context={"cleanup@openstack": ["designate"]},
                    name="DesignateBasic.create_and_list_recordsets",
                    platform="openstack")
class CreateAndListRecordsets(utils.DesignateScenario):

    def run(self, recordsets_per_zone=5):
        """Create and then list recordsets.

        If you have only 1 user in your context, you will
        add 1 recordset on every iteration. So you will have more
        and more recordsets and will be able to measure the
        performance of the "openstack recordset list" command depending on
        the number of zones/recordsets owned by users.

        :param recordsets_per_zone: recordsets to create pr zone.
        """
        zone = random.choice(self.context["tenant"]["zones"])

        for i in range(recordsets_per_zone):
            self._create_recordset(zone)

        self._list_recordsets(zone["id"])
