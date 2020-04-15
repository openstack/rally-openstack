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


"""List and compare most used OpenStack cloud resources."""

import argparse
import io
import json
import subprocess
import sys

from ansible.module_utils.basic import AnsibleModule

from rally.cli import cliutils
from rally.common.plugin import discover
from rally import plugins

try:
    from rally_openstack.common import consts
    from rally_openstack.common import credential
except ImportError:
    # backward compatibility for stable branches
    from rally_openstack import consts
    from rally_openstack import credential


def skip_if_service(service):
    def wrapper(func):
        def inner(self):
            if service in self.clients.services().values():
                return []
            return func(self)
        return inner
    return wrapper


class ResourceManager(object):

    REQUIRED_SERVICE = None
    STR_ATTRS = ("id", "name")

    def __init__(self, clients):
        self.clients = clients

    def is_available(self):
        if self.REQUIRED_SERVICE:
            return self.REQUIRED_SERVICE in self.clients.services().values()
        return True

    @property
    def client(self):
        return getattr(self.clients, self.__class__.__name__.lower())()

    def get_resources(self):
        all_resources = []
        cls = self.__class__.__name__.lower()
        for prop in dir(self):
            if not prop.startswith("list_"):
                continue
            f = getattr(self, prop)
            resources = f() or []
            resource_name = prop[5:][:-1]
            for raw_res in resources:
                res = {"cls": cls, "resource_name": resource_name,
                       "id": {}, "props": {}}
                if not isinstance(raw_res, dict):
                    raw_res = {k: getattr(raw_res, k) for k in dir(raw_res)
                               if not k.startswith("_")
                               if not callable(getattr(raw_res, k))}
                for key, value in raw_res.items():
                    if key.startswith("_"):
                        continue
                    if key in self.STR_ATTRS:
                        res["id"][key] = value
                    else:
                        try:
                            res["props"][key] = json.dumps(value, indent=2)
                        except TypeError:
                            res["props"][key] = str(value)
                if not res["id"] and not res["props"]:
                    print("1: %s" % raw_res)
                    print("2: %s" % cls)
                    print("3: %s" % resource_name)
                    raise ValueError("Failed to represent resource %r" %
                                     raw_res)
                all_resources.append(res)
        return all_resources


class Keystone(ResourceManager):

    REQUIRED_SERVICE = consts.Service.KEYSTONE

    def list_users(self):
        return self.client.users.list()

    def list_tenants(self):
        if hasattr(self.client, "projects"):
            return self.client.projects.list()  # V3
        return self.client.tenants.list()  # V2

    def list_roles(self):
        return self.client.roles.list()


class Magnum(ResourceManager):

    REQUIRED_SERVICE = consts.Service.MAGNUM

    def list_cluster_templates(self):
        result = []
        marker = None
        while True:
            ct_list = self.client.cluster_templates.list(marker=marker)
            if not ct_list:
                break
            result.extend(ct_list)
            marker = ct_list[-1].uuid
        return result

    def list_clusters(self):
        result = []
        marker = None
        while True:
            clusters = self.client.clusters.list(marker=marker)
            if not clusters:
                break
            result.extend(clusters)
            marker = clusters[-1].uuid
        return result


class Mistral(ResourceManager):

    REQUIRED_SERVICE = consts.Service.MISTRAL

    def list_workbooks(self):
        return self.client.workbooks.list()

    def list_workflows(self):
        return self.client.workflows.list()

    def list_executions(self):
        return self.client.executions.list()


class Nova(ResourceManager):

    REQUIRED_SERVICE = consts.Service.NOVA

    def list_flavors(self):
        return self.client.flavors.list()

    def list_aggregates(self):
        return self.client.aggregates.list()

    def list_hypervisors(self):
        return self.client.hypervisors.list()

    def list_agents(self):
        return self.client.agents.list()

    def list_keypairs(self):
        return self.client.keypairs.list()

    def list_servers(self):
        return self.client.servers.list(
            search_opts={"all_tenants": True})

    def list_server_groups(self):
        return self.client.server_groups.list(all_projects=True)

    def list_services(self):
        return self.client.services.list()

    def list_availability_zones(self):
        return self.client.availability_zones.list()


class Neutron(ResourceManager):

    REQUIRED_SERVICE = consts.Service.NEUTRON

    def has_extension(self, name):
        extensions = self.client.list_extensions().get("extensions", [])
        return any(ext.get("alias") == name for ext in extensions)

    def list_networks(self):
        return self.client.list_networks()["networks"]

    def list_subnets(self):
        return self.client.list_subnets()["subnets"]

    def list_routers(self):
        return self.client.list_routers()["routers"]

    def list_ports(self):
        return self.client.list_ports()["ports"]

    def list_floatingips(self):
        return self.client.list_floatingips()["floatingips"]

    def list_security_groups(self):
        return self.client.list_security_groups()["security_groups"]

    def list_trunks(self):
        if self.has_extension("trunks"):
            return self.client.list_trunks()["trunks"]

    def list_health_monitors(self):
        if self.has_extension("lbaas"):
            return self.client.list_health_monitors()["health_monitors"]

    def list_pools(self):
        if self.has_extension("lbaas"):
            return self.client.list_pools()["pools"]

    def list_vips(self):
        if self.has_extension("lbaas"):
            return self.client.list_vips()["vips"]

    def list_bgpvpns(self):
        if self.has_extension("bgpvpn"):
            return self.client.list_bgpvpns()["bgpvpns"]


class Glance(ResourceManager):

    REQUIRED_SERVICE = consts.Service.GLANCE

    def list_images(self):
        return self.client.images.list()


class Heat(ResourceManager):

    REQUIRED_SERVICE = consts.Service.HEAT

    def list_resource_types(self):
        return self.client.resource_types.list()

    def list_stacks(self):
        return self.client.stacks.list()


class Cinder(ResourceManager):

    REQUIRED_SERVICE = consts.Service.CINDER

    def list_availability_zones(self):
        return self.client.availability_zones.list()

    def list_backups(self):
        return self.client.backups.list()

    def list_volume_snapshots(self):
        return self.client.volume_snapshots.list()

    def list_volume_types(self):
        return self.client.volume_types.list()

    def list_encryption_types(self):
        return self.client.volume_encryption_types.list()

    def list_transfers(self):
        return self.client.transfers.list()

    def list_volumes(self):
        return self.client.volumes.list(search_opts={"all_tenants": True})

    def list_qos(self):
        return self.client.qos_specs.list()


class Senlin(ResourceManager):

    REQUIRED_SERVICE = consts.Service.SENLIN

    def list_clusters(self):
        return self.client.clusters()

    def list_profiles(self):
        return self.client.profiles()


class Manila(ResourceManager):

    REQUIRED_SERVICE = consts.Service.MANILA

    def list_shares(self):
        return self.client.shares.list(detailed=False,
                                       search_opts={"all_tenants": True})

    def list_share_networks(self):
        return self.client.share_networks.list(
            detailed=False, search_opts={"all_tenants": True})

    def list_share_servers(self):
        return self.client.share_servers.list(
            search_opts={"all_tenants": True})


class Gnocchi(ResourceManager):

    REQUIRED_SERVICE = consts.Service.GNOCCHI

    def list_resources(self):
        result = []
        marker = None
        while True:
            resources = self.client.resource.list(marker=marker)
            if not resources:
                break
            result.extend(resources)
            marker = resources[-1]["id"]
        return result

    def list_archive_policy_rules(self):
        return self.client.archive_policy_rule.list()

    def list_archive_policys(self):
        return self.client.archive_policy.list()

    def list_resource_types(self):
        return self.client.resource_type.list()

    def list_metrics(self):
        result = []
        marker = None
        while True:
            metrics = self.client.metric.list(marker=marker)
            if not metrics:
                break
            result.extend(metrics)
            marker = metrics[-1]["id"]
        return result


class Ironic(ResourceManager):

    REQUIRED_SERVICE = consts.Service.IRONIC

    def list_nodes(self):
        return self.client.node.list()


class Sahara(ResourceManager):

    REQUIRED_SERVICE = consts.Service.SAHARA

    def list_node_group_templates(self):
        return self.client.node_group_templates.list()


class Murano(ResourceManager):

    REQUIRED_SERVICE = consts.Service.MURANO

    def list_environments(self):
        return self.client.environments.list()

    def list_packages(self):
        return self.client.packages.list(include_disabled=True)


class Designate(ResourceManager):

    REQUIRED_SERVICE = consts.Service.DESIGNATE

    def list_zones(self):
        return self.clients.designate("2").zones.list()

    def list_recordset(self):
        client = self.clients.designate("2")
        results = []
        results.extend(client.recordsets.list(zone_id)
                       for zone_id in client.zones.list())
        return results


class Trove(ResourceManager):

    REQUIRED_SERVICE = consts.Service.TROVE

    def list_backups(self):
        return self.client.backup.list()

    def list_clusters(self):
        return self.client.cluster.list()

    def list_configurations(self):
        return self.client.configuration.list()

    def list_databases(self):
        return self.client.database.list()

    def list_datastore(self):
        return self.client.datastore.list()

    def list_instances(self):
        return self.client.list(include_clustered=True)

    def list_modules(self):
        return self.client.module.list(datastore="all")


class Monasca(ResourceManager):

    REQUIRED_SERVICE = consts.Service.MONASCA

    def list_metrics(self):
        return self.client.metrics.list()


class Watcher(ResourceManager):

    REQUIRED_SERVICE = consts.Service.WATCHER

    REPR_KEYS = ("uuid", "name")

    def list_audits(self):
        return self.client.audit.list()

    def list_audit_templates(self):
        return self.client.audit_template.list()

    def list_goals(self):
        return self.client.goal.list()

    def list_strategies(self):
        return self.client.strategy.list()

    def list_action_plans(self):
        return self.client.action_plan.list()


class Octavia(ResourceManager):

    REQUIRED_SERVICE = consts.Service.OCTAVIA

    def list_load_balancers(self):
        return self.client.load_balancer_list()["loadbalancers"]

    def list_listeners(self):
        return self.client.listener_list()["listeners"]

    def list_pools(self):
        return self.client.pool_list()["pools"]

    def list_l7policies(self):
        return self.client.l7policy_list()["l7policies"]

    def list_health_monitors(self):
        return self.client.health_monitor_list()["healthmonitors"]

    def list_amphoras(self):
        return self.client.amphora_list()["amphorae"]


class CloudResources(object):
    """List and compare cloud resources.

    resources = CloudResources(auth_url=..., ...)
    saved_list = resources.list()

    # Do something with the cloud ...

    changes = resources.compare(saved_list)
    has_changed = any(changes)
    removed, added = changes
    """

    def __init__(self, **kwargs):
        self.clients = credential.OpenStackCredential(**kwargs).clients()

    def list(self):
        managers_classes = discover.itersubclasses(ResourceManager)
        resources = []
        for cls in managers_classes:
            manager = cls(self.clients)
            if manager.is_available():
                resources.extend(manager.get_resources())
        return resources

    def compare(self, with_list):
        def make_uuid(res):
            return"%s.%s:%s" % (
                res["cls"], res["resource_name"],
                ";".join(["%s=%s" % (k, v)
                          for k, v in sorted(res["id"].items())]))

        current_resources = dict((make_uuid(r), r) for r in self.list())
        saved_resources = dict((make_uuid(r), r) for r in with_list)

        removed = set(saved_resources.keys()) - set(current_resources.keys())
        removed = [saved_resources[k] for k in sorted(removed)]
        added = set(current_resources.keys()) - set(saved_resources.keys())
        added = [current_resources[k] for k in sorted(added)]

        return removed, added


def _print_tabular_resources(resources, table_label):
    def dict_formatter(d):
        return "\n".join("%s:%s" % (k, v) for k, v in d.items())

    out = io.StringIO()

    cliutils.print_list(
        objs=[dict(r) for r in resources],
        fields=("cls", "resource_name", "id", "fields"),
        field_labels=("service", "resource type", "id", "fields"),
        table_label=table_label,
        formatters={"id": lambda d: dict_formatter(d["id"]),
                    "fields": lambda d: dict_formatter(d["props"])},
        out=out
    )
    out.write("\n")
    print(out.getvalue())


def dump_resources(resources_mgr, json_output):
    resources_list = resources_mgr.list()
    _print_tabular_resources(resources_list, "Available resources.")

    if json_output:
        with open(json_output, "w") as f:
            f.write(json.dumps(resources_list))
    return 0, resources_list


def check_resource(resources_mgs, compare_with, json_output):
    with open(compare_with) as f:
        compare_to = f.read()
    compare_to = json.loads(compare_to)
    changes = resources_mgs.compare(with_list=compare_to)
    removed, added = changes

    # Cinder has a feature - cache images for speeding-up time of creating
    # volumes from images. let's put such cache-volumes into expected list
    volume_names = [
        "image-%s" % i["id"]["id"] for i in compare_to
        if i["cls"] == "glance" and i["resource_name"] == "image"]

    # filter out expected additions
    expected = []
    for resource in added:
        if (False  # <- makes indent of other cases similar
                or (resource["cls"] == "keystone"
                    and resource["resource_name"] == "role"
                    and resource["id"].get("name") == "_member_")
                or (resource["cls"] == "neutron"
                    and resource["resource_name"] == "security_group"
                    and resource["id"].get("name") == "default")
                or (resource["cls"] == "cinder"
                    and resource["resource_name"] == "volume"
                    and resource["id"].get("name") in volume_names)

                or resource["cls"] == "murano"

                # Glance has issues with uWSGI integration...
                # or resource["cls"] == "glance"

                or resource["cls"] == "gnocchi"):

            expected.append(resource)

    for resource in expected:
        added.remove(resource)

    if removed:
        _print_tabular_resources(removed, "Removed resources")

    if added:
        _print_tabular_resources(added, "Added resources (unexpected)")

    if expected:
        _print_tabular_resources(expected, "Added resources (expected)")

    result = {"removed": removed, "added": added, "expected": expected}
    if json_output:
        with open(json_output, "w") as f:
            f.write(json.dumps(result, indent=4))

    rc = 1 if any(changes) else 0
    return rc, result


@plugins.ensure_plugins_are_loaded
def main(json_output, compare_with):

    out = subprocess.check_output(
        ["rally", "env", "show", "--only-spec", "--env", "devstack"])
    config = json.loads(out.decode("utf-8"))
    config = config["existing@openstack"]
    config.update(config.pop("admin"))
    if "users" in config:
        del config["users"]

    resources = CloudResources(**config)

    if compare_with:
        return check_resource(resources, compare_with, json_output)
    else:
        return dump_resources(resources, json_output)


def ansible_main():
    module = AnsibleModule(
        argument_spec=dict(
            json_output=dict(required=False, type="str"),
            compare_with=dict(required=False, type="path")
        )
    )

    rc, json_result = main(
        json_output=module.params.get("json_output"),
        compare_with=module.params.get("compare_with")
    )
    if rc:
        module.fail_json(
            msg="Unexpected changes of resources are detected.",
            rc=1,
            resources=json_result
        )

    module.exit_json(rc=0, changed=True, resources=json_result)


def cli_main():
    parser = argparse.ArgumentParser(
        description=("Save list of OpenStack cloud resources or compare "
                     "with previously saved list."))

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dump-list",
                       type=str,
                       metavar="<path/to/output/list.json>",
                       help="dump resources to given file in JSON format")
    group.add_argument("--compare-with-list",
                       type=str,
                       metavar="<path/to/existent/list.json>",
                       help=("compare current resources with a list from "
                             "given JSON file"))
    args = parser.parse_args()

    rc, _json_result = main(
        json_output=args.dump_list, compare_with=args.compare_with_list)

    return rc


if __name__ == "__main__":
    if sys.stdin.isatty():
        cli_main()
    else:
        ansible_main()
