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
import os

from rally.common import cfg
from rally.common import logging
from rally.common import opts
from rally.common.plugin import plugin
from rally.task.processing import charts


OPTS = {
    "openstack": [
        cfg.StrOpt(
            "osprofiler_chart_mode",
            default=None,
            help="Mode of embedding OSProfiler's chart. Can be 'text' "
                 "(embed only trace id), 'raw' (embed raw osprofiler's native "
                 "report) or a path to directory (raw osprofiler's native "
                 "reports for each iteration will be saved separately there "
                 "to decrease the size of rally report itself)")
    ]
}


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def _datetime_json_serialize(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    else:
        return obj


@plugin.configure(name="OSProfiler")
class OSProfilerChart(charts.OutputEmbeddedChart,
                      charts.OutputEmbeddedExternalChart,
                      charts.OutputTextArea):
    """Chart for embedding OSProfiler data."""

    @classmethod
    def _fetch_osprofiler_data(cls, connection_str, trace_id):
        from osprofiler.drivers import base
        from osprofiler import opts as osprofiler_opts

        opts.register_opts(osprofiler_opts.list_opts())  # noqa

        try:  # noqa
            engine = base.get_driver(connection_str)
        except Exception:
            msg = "Error while fetching OSProfiler results."
            if logging.is_debug():
                LOG.exception(msg)
            else:
                LOG.error(msg)
            return None

        return engine.get_report(trace_id)

    @classmethod
    def _generate_osprofiler_report(cls, osp_data):
        from osprofiler import cmd

        path = "%s/template.html" % os.path.dirname(cmd.__file__)
        with open(path) as f:
            html_obj = f.read()

        osp_data = json.dumps(osp_data,
                              indent=4,
                              separators=(",", ": "),
                              default=_datetime_json_serialize)
        return html_obj.replace("$DATA", osp_data).replace("$LOCAL", "false")

    @classmethod
    def _return_raw_response_for_complete_data(cls, data):
        return charts.OutputTextArea.render_complete_data({
            "title": data["title"],
            "widget": "TextArea",
            "data": [data["data"]["trace_id"]]
        })

    @classmethod
    def render_complete_data(cls, data):
        mode = CONF.openstack.osprofiler_chart_mode

        if isinstance(data["data"]["trace_id"], list):
            # NOTE(andreykurilin): it is an adoption for the format that we
            #   used  before rally-openstack 1.5.0 .
            data["data"]["trace_id"] = data["data"]["trace_id"][0]

        if data["data"].get("conn_str") and mode != "text":
            osp_data = cls._fetch_osprofiler_data(
                data["data"]["conn_str"],
                trace_id=data["data"]["trace_id"]
            )
            if not osp_data:
                # for some reasons we failed to fetch data from OSProfiler's
                # backend. in this case we can display just trace ID
                return cls._return_raw_response_for_complete_data(data)

            osp_report = cls._generate_osprofiler_report(osp_data)
            title = "{0} : {1}".format(data["title"],
                                       data["data"]["trace_id"])

            if (mode and mode != "raw") and "workload_uuid" in data["data"]:
                # NOTE(andreykurilin): we need to rework our charts plugin
                #   mechanism so it is available out of box
                workload_uuid = data["data"]["workload_uuid"]
                iteration = data["data"]["iteration"]
                file_name = "w_%s-%s.html" % (workload_uuid, iteration)
                path = os.path.join(mode, file_name)
                with open(path, "w") as f:
                    f.write(osp_report)
                return charts.OutputEmbeddedExternalChart.render_complete_data(
                    {
                        "title": title,
                        "widget": "EmbeddedChart",
                        "data": path
                    }
                )
            else:
                return charts.OutputEmbeddedChart.render_complete_data(
                    {"title": title,
                     "widget": "EmbeddedChart",
                     "data": osp_report}
                )

        return cls._return_raw_response_for_complete_data(data)
