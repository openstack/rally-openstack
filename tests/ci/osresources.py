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

"""List OpenStack resources and detect the ones a Rally task left behind."""

import argparse
import dataclasses
import functools
import json
import sys
import typing as t
from collections import abc

from openstack import exceptions as sdk_exceptions
from openstack import proxy as sdk_proxy

from rally import api
from rally import plugins
from rally.env import env_mgr

from rally_openstack.common import consts
from rally_openstack.common import credential
from rally_openstack.common import osclients


if t.TYPE_CHECKING:
    from openstack.baremetal.v1 import node as ironic_node
    from openstack.block_storage.v3 import _proxy as cinder_proxy
    from openstack.block_storage.v3 import backup as cinder_backup
    from openstack.block_storage.v3 import snapshot as cinder_snapshot
    from openstack.block_storage.v3 import transfer as cinder_transfer
    from openstack.block_storage.v3 import type as cinder_type
    from openstack.block_storage.v3 import volume as cinder_volume
    from openstack.compute.v2 import aggregate as nova_aggregate
    from openstack.compute.v2 import flavor as nova_flavor
    from openstack.compute.v2 import keypair as nova_keypair
    from openstack.compute.v2 import server as nova_server
    from openstack.compute.v2 import server_group as nova_server_group
    from openstack.container_infrastructure_management.v1 import (
        cluster as magnum_cluster,
    )
    from openstack.container_infrastructure_management.v1 import (
        cluster_template as magnum_cluster_template,
    )
    from openstack.dns.v2 import recordset as designate_recordset
    from openstack.dns.v2 import zone as designate_zone
    from openstack.identity.v3 import _proxy as keystone_proxy
    from openstack.identity.v3 import credential as keystone_credential
    from openstack.identity.v3 import domain as keystone_domain
    from openstack.identity.v3 import project as keystone_project
    from openstack.identity.v3 import role as keystone_role
    from openstack.identity.v3 import service as keystone_service
    from openstack.identity.v3 import user as keystone_user
    from openstack.image.v2 import _proxy as glance_proxy
    from openstack.image.v2 import image as glance_image
    from openstack.key_manager.v1 import container as barbican_container
    from openstack.key_manager.v1 import order as barbican_order
    from openstack.key_manager.v1 import secret as barbican_secret
    from openstack.load_balancer.v2 import health_monitor as octavia_hm
    from openstack.load_balancer.v2 import l7_policy as octavia_l7_policy
    from openstack.load_balancer.v2 import listener as octavia_listener
    from openstack.load_balancer.v2 import load_balancer as octavia_lb
    from openstack.load_balancer.v2 import pool as octavia_pool
    from openstack.message.v2 import queue as zaqar_queue
    from openstack.network.v2 import bgpvpn as neutron_bgpvpn
    from openstack.network.v2 import firewall_group as neutron_fw_group
    from openstack.network.v2 import firewall_policy as neutron_fw_policy
    from openstack.network.v2 import firewall_rule as neutron_fw_rule
    from openstack.network.v2 import network as neutron_network
    from openstack.network.v2 import port as neutron_port
    from openstack.network.v2 import router as neutron_router
    from openstack.network.v2 import security_group as neutron_sg
    from openstack.network.v2 import subnet as neutron_subnet
    from openstack.network.v2 import tap_mirror as neutron_tap_mirror
    from openstack.network.v2 import trunk as neutron_trunk
    from openstack.object_store.v1 import container as swift_container
    from openstack.shared_file_system.v2 import share as manila_share
    from openstack.shared_file_system.v2 import (
        share_network as manila_share_network,
    )


@dataclasses.dataclass(frozen=True, order=True, kw_only=True)
class Resource:
    service: str
    kind: str
    id: str
    name: str | None = None


class ResourceManager:
    """Base for listing resources of one service.

    Every ``list_<kinds>`` method returns either openstacksdk objects, which
    are turned into :class:`Resource` of the singular ``<kind>``, or ready
    :class:`Resource` objects for everything else.
    """

    SERVICE: t.ClassVar[str]
    # catalog service types under which the service can be registered
    SERVICE_TYPES: t.ClassVar[tuple[str, ...]]

    def __init__(self, clients: osclients.Clients) -> None:
        self.clients = clients
        self.conn = clients._conn

    def is_available(self) -> bool:
        catalog = self.clients.services()
        return any(stype in catalog for stype in self.SERVICE_TYPES)

    def list_all(self) -> list[Resource]:
        if not self.is_available():
            return []
        resources = []
        for method in dir(self):
            if not method.startswith("list_") or method == "list_all":
                continue
            kind = method.removeprefix("list_")
            if kind.endswith("ies"):
                kind = f"{kind[:-3]}y"
            else:
                kind = kind.removesuffix("s")
            for item in getattr(self, method)():
                if not isinstance(item, Resource):
                    item = Resource(service=self.SERVICE, kind=kind,
                                    id=item.id, name=item.name)
                resources.append(item)
        return resources

    @staticmethod
    def _get(
        proxy: sdk_proxy.Proxy,
        path: str,
        key: str,
        params: dict[str, t.Any] | None = None,
    ) -> list[dict[str, t.Any]]:
        """Call an API that openstacksdk does not wrap with needed params."""
        response = proxy.get(path, params=params)
        sdk_exceptions.raise_from_response(response)
        return response.json()[key]


class Keystone(ResourceManager):

    SERVICE = "keystone"
    SERVICE_TYPES = ("identity",)

    @property
    def identity(self) -> "keystone_proxy.Proxy":
        return t.cast("keystone_proxy.Proxy", self.conn.identity)

    def list_users(self) -> abc.Iterator["keystone_user.User"]:
        return self.identity.users()

    def list_projects(self) -> abc.Iterator["keystone_project.Project"]:
        return self.identity.projects()

    def list_domains(self) -> abc.Iterator["keystone_domain.Domain"]:
        return self.identity.domains()

    def list_roles(self) -> abc.Iterator["keystone_role.Role"]:
        return self.identity.roles()

    def list_services(self) -> abc.Iterator["keystone_service.Service"]:
        return self.identity.services()

    def list_credentials(
        self,
    ) -> abc.Iterator["keystone_credential.Credential"]:
        # EC2 credentials are stored as credentials of the 'ec2' type
        return self.identity.credentials()


class Nova(ResourceManager):

    SERVICE = "nova"
    SERVICE_TYPES = ("compute",)

    def list_servers(self) -> abc.Iterator["nova_server.Server"]:
        return self.conn.compute.servers(all_projects=True)

    def list_server_groups(
        self,
    ) -> abc.Iterator["nova_server_group.ServerGroup"]:
        return self.conn.compute.server_groups(all_projects=True)

    def list_flavors(self) -> abc.Iterator["nova_flavor.Flavor"]:
        # 'none' makes nova return both public and private flavors to admin
        return self.conn.compute.flavors(is_public="none")

    def list_aggregates(self) -> abc.Iterator["nova_aggregate.Aggregate"]:
        return self.conn.compute.aggregates()

    def list_keypairs(self) -> abc.Iterator["nova_keypair.Keypair"]:
        return self.conn.compute.keypairs()


class Neutron(ResourceManager):

    SERVICE = "neutron"
    SERVICE_TYPES = ("network",)

    @functools.cached_property
    def _extensions(self) -> set[str]:
        return {e.alias for e in self.conn.network.extensions()}

    def _has_extension(self, alias: str) -> bool:
        return alias in self._extensions

    def list_networks(self) -> abc.Iterator["neutron_network.Network"]:
        return self.conn.network.networks()

    def list_subnets(self) -> abc.Iterator["neutron_subnet.Subnet"]:
        return self.conn.network.subnets()

    def list_routers(self) -> abc.Iterator["neutron_router.Router"]:
        return self.conn.network.routers()

    def list_ports(self) -> abc.Iterator["neutron_port.Port"]:
        return self.conn.network.ports()

    def list_floating_ips(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="floating_ip", id=fip.id,
                     name=fip.floating_ip_address)
            for fip in self.conn.network.ips()
        ]

    def list_security_groups(
        self,
    ) -> abc.Iterator["neutron_sg.SecurityGroup"]:
        return self.conn.network.security_groups()

    def list_trunks(self) -> abc.Iterator["neutron_trunk.Trunk"]:
        if not self._has_extension("trunk"):
            return iter([])
        return self.conn.network.trunks()

    def list_bgpvpns(self) -> abc.Iterator["neutron_bgpvpn.BgpVpn"]:
        if not self._has_extension("bgpvpn"):
            return iter([])
        return self.conn.network.bgpvpns()

    def list_firewall_groups(
        self,
    ) -> abc.Iterator["neutron_fw_group.FirewallGroup"]:
        if not self._has_extension("fwaas_v2"):
            return iter([])
        return self.conn.network.firewall_groups()

    def list_firewall_policies(
        self,
    ) -> abc.Iterator["neutron_fw_policy.FirewallPolicy"]:
        if not self._has_extension("fwaas_v2"):
            return iter([])
        return self.conn.network.firewall_policies()

    def list_firewall_rules(
        self,
    ) -> abc.Iterator["neutron_fw_rule.FirewallRule"]:
        if not self._has_extension("fwaas_v2"):
            return iter([])
        return self.conn.network.firewall_rules()

    def list_tap_mirrors(
        self,
    ) -> abc.Iterator["neutron_tap_mirror.TapMirror"]:
        if not self._has_extension("tap-mirror"):
            return iter([])
        return self.conn.network.tap_mirrors()


class Cinder(ResourceManager):

    SERVICE = "cinder"
    SERVICE_TYPES = ("block-storage", "volumev3")

    @property
    def block_storage(self) -> "cinder_proxy.Proxy":
        return t.cast("cinder_proxy.Proxy", self.conn.block_storage)

    def list_volumes(self) -> abc.Iterator["cinder_volume.Volume"]:
        return self.block_storage.volumes(all_projects=True)

    def list_snapshots(self) -> abc.Iterator["cinder_snapshot.Snapshot"]:
        return self.block_storage.snapshots(all_projects=True)

    def list_backups(self) -> abc.Iterator["cinder_backup.Backup"]:
        return self.block_storage.backups(all_projects=True)

    def list_transfers(self) -> abc.Iterator["cinder_transfer.Transfer"]:
        return self.block_storage.transfers(all_projects=True)

    def list_volume_types(self) -> abc.Iterator["cinder_type.Type"]:
        return self.block_storage.types()

    def list_qos_specs(self) -> list[Resource]:
        # openstacksdk lists qos specs only in its most recent releases
        return [
            Resource(service=self.SERVICE, kind="qos_spec", id=q["id"],
                     name=q["name"])
            for q in self._get(
                self.block_storage, "/qos-specs", "qos_specs")
        ]


class Glance(ResourceManager):

    SERVICE = "glance"
    SERVICE_TYPES = ("image",)

    def list_images(self) -> abc.Iterator["glance_image.Image"]:
        image = t.cast("glance_proxy.Proxy", self.conn.image)
        return image.images(visibility="all")


class Heat(ResourceManager):

    SERVICE = "heat"
    SERVICE_TYPES = ("orchestration",)

    def list_stacks(self) -> list[Resource]:
        # openstacksdk does not let admin list stacks of all projects
        stacks = self._get(self.conn.orchestration, "/stacks", "stacks",
                           params={"global_tenant": True})
        return [
            Resource(service=self.SERVICE, kind="stack", id=s["id"],
                     name=s["stack_name"])
            for s in stacks
        ]


class Octavia(ResourceManager):

    SERVICE = "octavia"
    SERVICE_TYPES = ("load-balancer",)

    def list_load_balancers(self) -> abc.Iterator["octavia_lb.LoadBalancer"]:
        return self.conn.load_balancer.load_balancers()

    def list_listeners(self) -> abc.Iterator["octavia_listener.Listener"]:
        return self.conn.load_balancer.listeners()

    def list_pools(self) -> abc.Iterator["octavia_pool.Pool"]:
        return self.conn.load_balancer.pools()

    def list_l7_policies(
        self,
    ) -> abc.Iterator["octavia_l7_policy.L7Policy"]:
        return self.conn.load_balancer.l7_policies()

    def list_health_monitors(
        self,
    ) -> abc.Iterator["octavia_hm.HealthMonitor"]:
        return self.conn.load_balancer.health_monitors()


class Barbican(ResourceManager):

    SERVICE = "barbican"
    SERVICE_TYPES = ("key-manager",)

    def list_secrets(self) -> abc.Iterator["barbican_secret.Secret"]:
        return self.conn.key_manager.secrets()

    def list_containers(
        self,
    ) -> abc.Iterator["barbican_container.Container"]:
        return self.conn.key_manager.containers()

    def list_orders(self) -> abc.Iterator["barbican_order.Order"]:
        return self.conn.key_manager.orders()


class Designate(ResourceManager):

    SERVICE = "designate"
    SERVICE_TYPES = ("dns",)

    def list_zones(self) -> abc.Iterator["designate_zone.Zone"]:
        return self.conn.dns.zones(all_projects=True)

    def list_recordsets(self) -> list["designate_recordset.Recordset"]:
        # openstacksdk fails to list recordsets without a zone
        return [
            recordset
            for zone in self.conn.dns.zones(all_projects=True)
            for recordset in self.conn.dns.recordsets(
                zone, all_projects=True)
        ]


class Manila(ResourceManager):

    SERVICE = "manila"
    SERVICE_TYPES = ("shared-file-system", "sharev2")

    def list_shares(self) -> abc.Iterator["manila_share.Share"]:
        return self.conn.shared_file_system.shares(all_projects=True)

    def list_share_networks(
        self,
    ) -> abc.Iterator["manila_share_network.ShareNetwork"]:
        return self.conn.shared_file_system.share_networks(all_projects=True)

    def list_security_services(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="security_service",
                     id=s["id"], name=s["name"])
            for s in self._get(
                self.conn.shared_file_system, "/security-services",
                "security_services", params={"all_tenants": 1})
        ]

    def list_share_servers(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="share_server", id=s["id"])
            for s in self._get(
                self.conn.shared_file_system, "/share-servers",
                "share_servers")
        ]


class Ironic(ResourceManager):

    SERVICE = "ironic"
    SERVICE_TYPES = ("baremetal",)

    def list_nodes(self) -> abc.Iterator["ironic_node.Node"]:
        return self.conn.baremetal.nodes()


class Swift(ResourceManager):

    SERVICE = "swift"
    SERVICE_TYPES = ("object-store",)

    def list_containers(self) -> abc.Iterator["swift_container.Container"]:
        return self.conn.object_store.containers()


class Magnum(ResourceManager):

    SERVICE = "magnum"
    SERVICE_TYPES = ("container-infra",)

    def list_clusters(self) -> abc.Iterator["magnum_cluster.Cluster"]:
        return self.conn.container_infrastructure_management.clusters()

    def list_cluster_templates(
        self,
    ) -> abc.Iterator["magnum_cluster_template.ClusterTemplate"]:
        return (
            self.conn.container_infrastructure_management.cluster_templates())


class Mistral(ResourceManager):

    SERVICE = "mistral"
    SERVICE_TYPES = ("workflowv2", "workflow")

    def _list(
        self, kind: str, params: dict[str, t.Any] | None = None,
    ) -> list[Resource]:
        # openstacksdk neither lists workbooks nor resources of all projects
        return [
            Resource(service=self.SERVICE, kind=kind, id=item["id"],
                     name=item.get("name"))
            for item in self._get(self.conn.workflow, f"/{kind}s", f"{kind}s",
                                  params=params)
        ]

    def list_workbooks(self) -> list[Resource]:
        # mistral lists workbooks only of the current project
        return self._list("workbook")

    def list_workflows(self) -> list[Resource]:
        return self._list("workflow", params={"all_projects": True})

    def list_executions(self) -> list[Resource]:
        return self._list("execution", params={"all_projects": True})


class Zaqar(ResourceManager):

    SERVICE = "zaqar"
    SERVICE_TYPES = ("messaging",)

    def list_queues(self) -> abc.Iterator["zaqar_queue.Queue"]:
        # zaqar's version document links to "/v2/" relative to the host root,
        # so version discovery drops the path prefix the API is mounted under
        # (e.g. "/messaging" in devstack). An absolute URL skips discovery.
        endpoint = self.conn.endpoint_for("messaging")
        if endpoint is None:
            raise sdk_exceptions.EndpointNotFound(
                "No messaging endpoint in the catalog")
        return self.conn.message.queues(
            base_path=f"{endpoint.rstrip('/')}/v2/queues")


class Gnocchi(ResourceManager):
    """Gnocchi is not covered by openstacksdk, so use its native client."""

    SERVICE = "gnocchi"
    SERVICE_TYPES = ("metric",)

    def _paginate(self, manager: t.Any) -> list[dict[str, t.Any]]:
        result: list[dict[str, t.Any]] = []
        marker = None
        while True:
            page = manager.list(marker=marker)
            if not page:
                return result
            result.extend(page)
            marker = page[-1]["id"]

    def list_archive_policies(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="archive_policy",
                     id=p["name"], name=p["name"])
            for p in self.clients.gnocchi().archive_policy.list()
        ]

    def list_archive_policy_rules(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="archive_policy_rule",
                     id=r["name"], name=r["name"])
            for r in self.clients.gnocchi().archive_policy_rule.list()
        ]

    def list_resource_types(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="resource_type",
                     id=r["name"], name=r["name"])
            for r in self.clients.gnocchi().resource_type.list()
        ]

    def list_resources(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="resource", id=r["id"])
            for r in self._paginate(self.clients.gnocchi().resource)
        ]

    def list_metrics(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="metric", id=m["id"],
                     name=m.get("name"))
            for m in self._paginate(self.clients.gnocchi().metric)
        ]


class Watcher(ResourceManager):
    """Watcher is not covered by openstacksdk, so use its native client."""

    SERVICE = "watcher"
    SERVICE_TYPES = ("infra-optim",)

    def list_audit_templates(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="audit_template",
                     id=a.uuid, name=a.name)
            for a in self.clients.watcher().audit_template.list(limit=0)
        ]

    def list_audits(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="audit", id=a.uuid,
                     name=a.name)
            for a in self.clients.watcher().audit.list(limit=0)
        ]

    def list_action_plans(self) -> list[Resource]:
        return [
            Resource(service=self.SERVICE, kind="action_plan", id=a.uuid)
            for a in self.clients.watcher().action_plan.list(limit=0)
        ]


def list_resources(clients: osclients.Clients) -> list[Resource]:
    resources = []
    for cls in ResourceManager.__subclasses__():
        manager = cls(clients)
        resources.extend(manager.list_all())
    return sorted(resources)


def _is_expected(resource: Resource, baseline: list[Resource]) -> bool:
    """Whether a resource appears in a cloud on its own, not via Rally."""
    if resource.service == "neutron" and resource.kind == "security_group":
        # neutron creates a default group for every project that touches the
        # network API and keeps it after the project is deleted
        return resource.name == "default"
    if resource.service == "cinder" and resource.kind == "volume":
        # the image volume cache of cinder names volumes after the images
        # they hold, rally cleans up the cache only for its own images
        return resource.name in {
            f"image-{r.id}" for r in baseline
            if r.service == "glance" and r.kind == "image"}
    if resource.service == "gnocchi":
        # ceilometer keeps pushing resources and metrics into gnocchi
        return resource.kind in ("resource", "metric")
    return False


def _print_resources(title: str, resources: list[Resource]) -> None:
    print(f"{title} ({len(resources)}):")
    for r in resources:
        print(f"  {r.service}.{r.kind} id={r.id} name={r.name}")


def save(clients: osclients.Clients, path: str) -> int:
    resources = list_resources(clients)
    _print_resources("Available resources", resources)
    with open(path, "w") as f:
        json.dump([dataclasses.asdict(r) for r in resources], f, indent=2)
    return 0


def compare(
    clients: osclients.Clients,
    baseline_path: str,
    output_path: str | None,
    no_fail: bool,
) -> int:
    with open(baseline_path) as f:
        baseline = [Resource(**r) for r in json.load(f)]
    current = list_resources(clients)

    baseline_keys = set(baseline)
    current_keys = set(current)
    removed = sorted(baseline_keys - current_keys)
    added = sorted(current_keys - baseline_keys)
    expected = [r for r in added if _is_expected(r, baseline)]
    unexpected = [r for r in added if r not in expected]

    _print_resources("Removed resources", removed)
    _print_resources("Added resources (unexpected)", unexpected)
    _print_resources("Added resources (expected)", expected)

    if output_path:
        with open(output_path, "w") as f:
            json.dump(
                {key: [dataclasses.asdict(r) for r in value]
                 for key, value in (("removed", removed),
                                    ("added", unexpected),
                                    ("expected", expected))},
                f, indent=2)

    if removed or unexpected:
        print("Unexpected changes of resources are detected.")
        if no_fail:
            print("Ignoring them as requested by --no-fail.")
            return 0
        return 1
    return 0


@plugins.ensure_plugins_are_loaded
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-name", default="devstack",
        help="Rally environment to take admin credentials from.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    save_parser = subparsers.add_parser(
        "save", help="Store the list of available resources.")
    save_parser.add_argument("path")

    compare_parser = subparsers.add_parser(
        "compare", help="Compare available resources with a stored list.")
    compare_parser.add_argument("baseline")
    compare_parser.add_argument(
        "--output", help="Store found changes to this file.")
    compare_parser.add_argument(
        "--no-fail", action="store_true",
        help="Report found changes without failing.")

    args = parser.parse_args()

    # init Rally API as it makes all work for logging and config initialization
    api.API()

    env_data = env_mgr.EnvManager.get(args.env_name).data
    admin = env_data["platforms"]["openstack"]["platform_data"]["admin"]
    clients = osclients.Clients(credential.OpenStackCredential(
        permission=consts.EndpointPermission.ADMIN, **admin))

    if args.action == "save":
        return save(clients, args.path)
    return compare(clients, args.baseline, args.output, args.no_fail)


if __name__ == "__main__":
    sys.exit(main())
