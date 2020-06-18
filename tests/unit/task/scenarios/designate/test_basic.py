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

from unittest import mock

from rally import exceptions
from rally_openstack.task.scenarios.designate import basic
from tests.unit import test

BASE = "rally_openstack.task.scenarios.designate.basic"


class DesignateBasicTestCase(test.ScenarioTestCase):

    @mock.patch("%s.CreateAndListZones._list_zones" % BASE)
    @mock.patch("%s.CreateAndListZones._create_zone" % BASE)
    def test_create_and_list_zones(self,
                                   mock__create_zone,
                                   mock__list_zones):
        mock__create_zone.return_value = "Area_51"
        mock__list_zones.return_value = ["Area_51",
                                         "Siachen",
                                         "Bagram"]
        # Positive case:
        basic.CreateAndListZones(self.context).run()
        mock__create_zone.assert_called_once_with()
        mock__list_zones.assert_called_once_with()

        # Negative case: zone isn't created
        mock__create_zone.return_value = None
        self.assertRaises(exceptions.RallyAssertionError,
                          basic.CreateAndListZones(self.context).run)
        mock__create_zone.assert_called_with()

        # Negative case: created zone not in the list of available zones
        mock__create_zone.return_value = "HAARP"
        self.assertRaises(exceptions.RallyAssertionError,
                          basic.CreateAndListZones(self.context).run)
        mock__create_zone.assert_called_with()
        mock__list_zones.assert_called_with()

    @mock.patch("%s.CreateAndDeleteZone._delete_zone" % BASE)
    @mock.patch("%s.CreateAndDeleteZone._create_zone" % BASE,
                return_value={"id": "123"})
    def test_create_and_delete_zone(self,
                                    mock__create_zone,
                                    mock__delete_zone):
        basic.CreateAndDeleteZone(self.context).run()

        mock__create_zone.assert_called_once_with()
        mock__delete_zone.assert_called_once_with("123")

    @mock.patch("%s.ListZones._list_zones" % BASE)
    def test_list_zones(self, mock_list_zones__list_zones):
        basic.ListZones(self.context).run()
        mock_list_zones__list_zones.assert_called_once_with()

    @mock.patch("%s.ListRecordsets._list_recordsets" % BASE)
    def test_list_recordsets(self, mock__list_recordsets):
        basic.ListRecordsets(self.context).run("123")
        mock__list_recordsets.assert_called_once_with("123")

    @mock.patch("%s.CreateAndDeleteRecordsets._delete_recordset" % BASE)
    @mock.patch("%s.CreateAndDeleteRecordsets._create_recordset" % BASE,
                return_value={"id": "321"})
    def test_create_and_delete_recordsets(self,
                                          mock__create_recordset,
                                          mock__delete_recordset):
        zone = {"id": "1234"}
        self.context.update({
            "tenant": {
                "zones": [zone]
            }
        })

        recordsets_per_zone = 5

        basic.CreateAndDeleteRecordsets(self.context).run(
            recordsets_per_zone=recordsets_per_zone)
        self.assertEqual(mock__create_recordset.mock_calls,
                         [mock.call(zone)]
                         * recordsets_per_zone)
        self.assertEqual(mock__delete_recordset.mock_calls,
                         [mock.call(zone["id"],
                                    "321")]
                         * recordsets_per_zone)

    @mock.patch("%s.CreateAndListRecordsets._list_recordsets" % BASE)
    @mock.patch("%s.CreateAndListRecordsets._create_recordset" % BASE)
    def test_create_and_list_recordsets(self,
                                        mock__create_recordset,
                                        mock__list_recordsets):
        zone = {"id": "1234"}
        self.context.update({
            "tenant": {
                "zones": [zone]
            }
        })
        recordsets_per_zone = 5

        basic.CreateAndListRecordsets(self.context).run(
            recordsets_per_zone=recordsets_per_zone)
        self.assertEqual(mock__create_recordset.mock_calls,
                         [mock.call(zone)]
                         * recordsets_per_zone)
        mock__list_recordsets.assert_called_once_with(zone["id"])
