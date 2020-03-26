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
import datetime as dt
import os
from unittest import mock

from rally_openstack.task.ui.charts import osprofilerchart as osp_chart
from tests.unit import test


PATH = "rally_openstack.task.ui.charts.osprofilerchart"
CHART_PATH = "%s.OSProfilerChart" % PATH


class OSProfilerChartTestCase(test.TestCase):

    def test__datetime_json_serialize(self):
        ts = dt.datetime(year=2018, month=7, day=3, hour=2)
        self.assertEqual("2018-07-03T02:00:00",
                         osp_chart._datetime_json_serialize(ts))
        self.assertEqual("A", osp_chart._datetime_json_serialize("A"))

    def test__return_raw_response_for_complete_data(self):
        title = "TITLE"
        trace_id = "trace-id"
        r = osp_chart.OSProfilerChart._return_raw_response_for_complete_data(
            {"title": title, "data": {"trace_id": trace_id}}
        )
        self.assertEqual(
            {"title": title, "widget": "TextArea", "data": [trace_id]},
            r
        )

    def test__generate_osprofiler_report(self):
        data = {"ts": dt.datetime(year=2018, month=7, day=3, hour=2)}

        mock_open = mock.mock_open(read_data="local=$LOCAL | data=$DATA")
        with mock.patch.object(osp_chart, "open", mock_open):
            r = osp_chart.OSProfilerChart._generate_osprofiler_report(data)
        self.assertEqual(
            "local=false | data={\n    \"ts\": \"2018-07-03T02:00:00\"\n}",
            r
        )
        self.assertEqual(1, mock_open.call_count)
        m_args, _m_kwargs = mock_open.call_args_list[0]
        self.assertTrue(os.path.exists(m_args[0]))

    def test__fetch_osprofiler_data(self):
        connection_str = "https://example.com"
        trace_id = "trace-id"

        mock_osp_drivers = mock.Mock()
        mock_osp_driver = mock_osp_drivers.base
        with mock.patch.dict(
                "sys.modules", {"osprofiler.drivers": mock_osp_drivers}):
            r = osp_chart.OSProfilerChart._fetch_osprofiler_data(
                connection_str, trace_id)
            self.assertIsNotNone(r)

        mock_osp_driver.get_driver.assert_called_once_with(connection_str)
        engine = mock_osp_driver.get_driver.return_value
        engine.get_report.assert_called_once_with(trace_id)
        self.assertEqual(engine.get_report.return_value, r)

        mock_osp_driver.get_driver.side_effect = Exception("Something")
        with mock.patch.dict(
                "sys.modules", {"osprofiler.drivers": mock_osp_drivers}):
            r = osp_chart.OSProfilerChart._fetch_osprofiler_data(
                connection_str, trace_id)
            self.assertIsNone(r)

    @mock.patch("%s.charts.OutputEmbeddedExternalChart" % PATH)
    @mock.patch("%s.charts.OutputEmbeddedChart" % PATH)
    @mock.patch("%s._return_raw_response_for_complete_data" % CHART_PATH)
    @mock.patch("%s._fetch_osprofiler_data" % CHART_PATH)
    @mock.patch("%s._generate_osprofiler_report" % CHART_PATH)
    def test_render_complete_data(
            self, mock__generate_osprofiler_report,
            mock__fetch_osprofiler_data,
            mock__return_raw_response_for_complete_data,
            mock_output_embedded_chart,
            mock_output_embedded_external_chart
    ):
        trace_id = "trace-id"
        title = "TITLE"

        # case 1: no connection-id, so data fpr text chart should be returned
        pdata = {"data": {"trace_id": trace_id}, "title": title}
        self.assertEqual(
            mock__return_raw_response_for_complete_data.return_value,
            osp_chart.OSProfilerChart.render_complete_data(
                copy.deepcopy(pdata))
        )
        mock__return_raw_response_for_complete_data.assert_called_once_with(
            pdata
        )
        mock__return_raw_response_for_complete_data.reset_mock()

        # case 2: check support for an old format when `trace_id` key is a list
        pdata = {"data": {"trace_id": [trace_id]}, "title": title}
        self.assertEqual(
            mock__return_raw_response_for_complete_data.return_value,
            osp_chart.OSProfilerChart.render_complete_data(
                copy.deepcopy(pdata))
        )
        pdata["data"]["trace_id"] = pdata["data"]["trace_id"][0]
        mock__return_raw_response_for_complete_data.assert_called_once_with(
            pdata
        )
        mock__return_raw_response_for_complete_data.reset_mock()

        # case 3: connection-id is provided, but osp backed is not available
        mock__fetch_osprofiler_data.return_value = None
        pdata = {"data": {"trace_id": trace_id, "conn_str": "conn"},
                 "title": title}
        self.assertEqual(
            mock__return_raw_response_for_complete_data.return_value,
            osp_chart.OSProfilerChart.render_complete_data(
                copy.deepcopy(pdata))
        )
        mock__return_raw_response_for_complete_data.assert_called_once_with(
            pdata
        )
        mock__return_raw_response_for_complete_data.reset_mock()

        # case 4: connection-id is provided
        mock__fetch_osprofiler_data.return_value = "OSP_DATA"
        mock__generate_osprofiler_report.return_value = "DD"
        pdata = {"data": {"trace_id": trace_id, "conn_str": "conn"},
                 "title": title}
        self.assertEqual(
            mock_output_embedded_chart.render_complete_data.return_value,
            osp_chart.OSProfilerChart.render_complete_data(
                copy.deepcopy(pdata))
        )
        mock_output_embedded_chart.render_complete_data.\
            assert_called_once_with({"title": "%s : %s" % (title, trace_id),
                                     "widget": "EmbeddedChart",
                                     "data": "DD"})
        self.assertFalse(mock__return_raw_response_for_complete_data.called)
        mock_output_embedded_chart.render_complete_data.reset_mock()

        # case 5: connection-id is provided with workload-id an
        pdata = {"data": {"trace_id": trace_id,
                          "conn_str": "conn",
                          "workload_uuid": "W_ID",
                          "iteration": 777},
                 "title": title}

        mock_open = mock.mock_open()
        with mock.patch.object(osp_chart, "open", mock_open):
            with mock.patch("%s.CONF.openstack" % PATH) as mock_cfg_os:
                mock_cfg_os.osprofiler_chart_mode = "/path"

                r = osp_chart.OSProfilerChart.render_complete_data(
                    copy.deepcopy(pdata))

        mock_external_chat = mock_output_embedded_external_chart
        self.assertEqual(
            mock_external_chat.render_complete_data.return_value,
            r
        )
        mock_external_chat.render_complete_data.\
            assert_called_once_with({"title": "%s : %s" % (title, trace_id),
                                     "widget": "EmbeddedChart",
                                     "data": "/path/w_W_ID-777.html"})
        self.assertFalse(mock__return_raw_response_for_complete_data.called)
