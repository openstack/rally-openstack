# Copyright 2014: Mirantis Inc.
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

from rally.common import cfg
from rally.common import logging
from rally.task import utils as task_utils

from rally_openstack.common.services.identity import identity
from rally_openstack.common.services.image import glance_v2
from rally_openstack.common.services.image import image
from rally_openstack.common.services.network import neutron
from rally_openstack.task.cleanup import base
from rally_openstack.task.scenarios.nova import utils as nova_utils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def get_order(start):
    return iter(range(start, start + 99))


class SynchronizedDeletion(object):

    def is_deleted(self):
        return True


class QuotaMixin(SynchronizedDeletion, base.ResourceManager):
    # NOTE(andreykurilin): Quotas resources are quite complex in terms of
    #   cleanup. First of all, they do not have name, id fields at all. There
    #   is only one identifier - reference to Keystone Project/Tenant. Also,
    #   we should remove them in case of existing users case... To cover both
    #   cases we should use project name as name field (it will allow to pass
    #   existing users case) and project id as id of resource

    def list(self):
        if not self.tenant_uuid:
            return []
        client = self._admin_required and self.admin or self.user
        project = identity.Identity(client).get_project(self.tenant_uuid)
        return [project]


# MAGNUM

_magnum_order = get_order(80)


class MagnumMixin(base.ResourceManager):

    def id(self):
        """Returns id of resource."""
        return self.raw_resource.uuid

    def list(self):
        result = []
        marker = None
        while True:
            resources = self._manager().list(marker=marker)
            if not resources:
                break
            result.extend(resources)
            marker = resources[-1].uuid
        return result


@base.resource("magnum", "clusters", order=next(_magnum_order),
               tenant_resource=True)
class MagnumCluster(MagnumMixin):
    """Resource class for Magnum cluster."""


@base.resource("magnum", "cluster_templates", order=next(_magnum_order),
               tenant_resource=True)
class MagnumClusterTemplate(MagnumMixin):
    """Resource class for Magnum cluster_template."""


# HEAT

@base.resource("heat", "stacks", order=100, tenant_resource=True)
class HeatStack(base.ResourceManager):
    def name(self):
        return self.raw_resource.stack_name


# NOVA

_nova_order = get_order(200)


@base.resource("nova", "servers", order=next(_nova_order),
               tenant_resource=True)
class NovaServer(base.ResourceManager):
    def list(self):
        """List all servers."""
        clients = (self._admin_required and self.admin or self.user)
        nc = getattr(clients, self._service)()
        return nova_utils.list_servers(
            nc,
            # we need details to get locked states
            detailed=True
        )

    def delete(self):
        if getattr(self.raw_resource, "OS-EXT-STS:locked", False):
            self.raw_resource.unlock()
        super(NovaServer, self).delete()


@base.resource("nova", "server_groups", order=next(_nova_order),
               tenant_resource=True)
class NovaServerGroups(base.ResourceManager):
    pass


@base.resource("nova", "keypairs", order=next(_nova_order))
class NovaKeypair(SynchronizedDeletion, base.ResourceManager):
    pass


@base.resource("nova", "quotas", order=next(_nova_order),
               admin_required=True, tenant_resource=True)
class NovaQuotas(QuotaMixin):
    pass


@base.resource("nova", "flavors", order=next(_nova_order),
               admin_required=True, perform_for_admin_only=True)
class NovaFlavors(base.ResourceManager):
    pass

    def is_deleted(self):
        from novaclient import exceptions as nova_exc

        try:
            self._manager().get(self.name())
        except nova_exc.NotFound:
            return True

        return False


@base.resource("nova", "aggregates", order=next(_nova_order),
               admin_required=True, perform_for_admin_only=True)
class NovaAggregate(SynchronizedDeletion, base.ResourceManager):

    def delete(self):
        for host in self.raw_resource.hosts:
            self.raw_resource.remove_host(host)
        super(NovaAggregate, self).delete()


# NEUTRON

_neutron_order = get_order(300)


class NeutronMixin(SynchronizedDeletion, base.ResourceManager):

    @property
    def _neutron(self):
        return neutron.NeutronService(
            self._admin_required and self.admin or self.user)

    def _manager(self):
        client = self._admin_required and self.admin or self.user
        return getattr(client, self._service)()

    def id(self):
        return self.raw_resource["id"]

    def name(self):
        return self.raw_resource["name"]

    def delete(self):
        key = "delete_%s" % self._resource
        delete_method = getattr(
            self._neutron, key, getattr(self._manager(), key)
        )
        delete_method(self.id())

    @property
    def _plural_key(self):
        if self._resource.endswith("y"):
            return self._resource[:-1] + "ies"
        else:
            return self._resource + "s"

    def list(self):
        list_method = getattr(self._manager(), "list_%s" % self._plural_key)
        result = list_method(tenant_id=self.tenant_uuid)[self._plural_key]
        if self.tenant_uuid:
            result = [r for r in result if r["tenant_id"] == self.tenant_uuid]

        return result


class NeutronLbaasV1Mixin(NeutronMixin):

    def list(self):
        if self._neutron.supports_extension("lbaas", silent=True):
            return super(NeutronLbaasV1Mixin, self).list()
        return []


@base.resource("neutron", "vip", order=next(_neutron_order),
               tenant_resource=True)
class NeutronV1Vip(NeutronLbaasV1Mixin):
    pass


@base.resource("neutron", "health_monitor", order=next(_neutron_order),
               tenant_resource=True)
class NeutronV1Healthmonitor(NeutronLbaasV1Mixin):
    pass


@base.resource("neutron", "pool", order=next(_neutron_order),
               tenant_resource=True)
class NeutronV1Pool(NeutronLbaasV1Mixin):
    pass


class NeutronLbaasV2Mixin(NeutronMixin):

    def list(self):
        if self._neutron.supports_extension("lbaasv2", silent=True):
            return super(NeutronLbaasV2Mixin, self).list()
        return []


@base.resource("neutron", "loadbalancer", order=next(_neutron_order),
               tenant_resource=True)
class NeutronV2Loadbalancer(NeutronLbaasV2Mixin):

    def is_deleted(self):
        try:
            self._manager().show_loadbalancer(self.id())
        except Exception as e:
            return getattr(e, "status_code", 400) == 404

        return False

# OCTAVIA


class OctaviaMixIn(NeutronMixin):

    @property
    def _client(self):
        # TODO(andreykurilin): use proper helper class from
        #     rally_openstack.common.services as soon as it will have unified
        #     style of arguments across all methods
        client = self.admin or self.user
        return getattr(client, self._service)()

    def delete(self):
        from octaviaclient.api.v2 import octavia as octavia_exc

        delete_method = getattr(self._client, "%s_delete" % self._resource)
        try:
            return delete_method(self.id())
        except octavia_exc.OctaviaClientException as e:
            if e.code == 409 and "Invalid state PENDING_DELETE" in e.message:
                # NOTE(andreykurilin): it is not ok. Probably this resource
                #    is not properly cleanup-ed (without wait-for loop)
                #    during the workload. No need to fail, continue silently.
                return
            raise

    def is_deleted(self):
        from osc_lib import exceptions as osc_exc

        show_method = getattr(self._client, "%s_show" % self._resource)
        try:
            show_method(self.id())
        except osc_exc.NotFound:
            return True
        return False

    def list(self):
        list_method = getattr(self._client, "%s_list" % self._resource)
        return list_method()[self._plural_key.replace("_", "")]


@base.resource("octavia", "load_balancer", order=next(_neutron_order),
               tenant_resource=True)
class OctaviaLoadBalancers(OctaviaMixIn):
    def delete(self):
        from octaviaclient.api.v2 import octavia as octavia_exc

        delete_method = getattr(self._client, "load_balancer_delete")
        try:
            return delete_method(self.id(), cascade=True)
        except octavia_exc.OctaviaClientException as e:
            if e.code == 409 and "Invalid state PENDING_DELETE" in e.message:
                # NOTE(andreykurilin): it is not ok. Probably this resource
                #    is not properly cleanup-ed (without wait-for loop)
                #    during the workload. No need to fail, continue silently.
                return
            raise


@base.resource("octavia", "pool", order=next(_neutron_order),
               tenant_resource=True)
class OctaviaPools(OctaviaMixIn):
    pass


@base.resource("octavia", "listener", order=next(_neutron_order),
               tenant_resource=True)
class OctaviaListeners(OctaviaMixIn):
    pass


@base.resource("octavia", "l7policy", order=next(_neutron_order),
               tenant_resource=True)
class OctaviaL7Policies(OctaviaMixIn):
    pass


@base.resource("octavia", "health_monitor", order=next(_neutron_order),
               tenant_resource=True)
class OctaviaHealthMonitors(OctaviaMixIn):
    pass


@base.resource("neutron", "bgpvpn", order=next(_neutron_order),
               admin_required=True, perform_for_admin_only=True)
class NeutronBgpvpn(NeutronMixin):
    def list(self):
        if self._neutron.supports_extension("bgpvpn", silent=True):
            return self._manager().list_bgpvpns()["bgpvpns"]
        return []


@base.resource("neutron", "floatingip", order=next(_neutron_order),
               tenant_resource=True)
class NeutronFloatingIP(NeutronMixin):
    def name(self):
        return self.raw_resource.get("description", "")

    def list(self):
        if CONF.openstack.pre_newton_neutron:
            # NOTE(andreykurilin): Neutron API of pre-newton openstack
            #   releases does not support description field in Floating IPs.
            #   We do not want to remove not-rally resources, so let's just do
            #   nothing here and move pre-newton logic into separate plugins
            return []
        return super(NeutronFloatingIP, self).list()


@base.resource("neutron", "trunk", order=next(_neutron_order),
               tenant_resource=True)
class NeutronTrunk(NeutronMixin):
    # Trunks must be deleted before the parent/subports are deleted

    def list(self):
        try:
            return super(NeutronTrunk, self).list()
        except Exception as e:
            if getattr(e, "status_code", 400) == 404:
                return []
            raise


@base.resource("neutron", "port", order=next(_neutron_order),
               tenant_resource=True)
class NeutronPort(NeutronMixin):
    # NOTE(andreykurilin): port is the kind of resource that can be created
    #   automatically. In this case it doesn't have name field which matches
    #   our resource name templates.

    def __init__(self, *args, **kwargs):
        super(NeutronPort, self).__init__(*args, **kwargs)
        self._cache = {}

    @property
    def ROUTER_INTERFACE_OWNERS(self):
        return self._neutron.ROUTER_INTERFACE_OWNERS

    @property
    def ROUTER_GATEWAY_OWNER(self):
        return self._neutron.ROUTER_GATEWAY_OWNER

    def _get_resources(self, resource):
        if resource not in self._cache:
            getter = getattr(self._neutron, "list_%s" % resource)
            resources = getter(tenant_id=self.tenant_uuid)
            self._cache[resource] = [r for r in resources
                                     if r["tenant_id"] == self.tenant_uuid]
        return self._cache[resource]

    def list(self):
        ports = self._get_resources("ports")
        for port in ports:
            if not port.get("name"):
                parent_name = None
                if (port["device_owner"] in self.ROUTER_INTERFACE_OWNERS
                        or port["device_owner"] == self.ROUTER_GATEWAY_OWNER):
                    # first case is a port created while adding an interface to
                    #   the subnet
                    # second case is a port created while adding gateway for
                    #   the network
                    port_router = [r for r in self._get_resources("routers")
                                   if r["id"] == port["device_id"]]
                    if port_router:
                        parent_name = port_router[0]["name"]
                if parent_name:
                    port["parent_name"] = parent_name
        return ports

    def name(self):
        return self.raw_resource.get("parent_name",
                                     self.raw_resource.get("name", ""))

    def delete(self):
        found = self._neutron.delete_port(self.raw_resource)
        if not found:
            # Port can be already auto-deleted, skip silently
            LOG.debug(f"Port {self.id()} was not deleted. Skip silently "
                      f"because port can be already auto-deleted.")


@base.resource("neutron", "subnet", order=next(_neutron_order),
               tenant_resource=True)
class NeutronSubnet(NeutronMixin):
    pass


@base.resource("neutron", "network", order=next(_neutron_order),
               tenant_resource=True)
class NeutronNetwork(NeutronMixin):
    pass


@base.resource("neutron", "router", order=next(_neutron_order),
               tenant_resource=True)
class NeutronRouter(NeutronMixin):
    pass


@base.resource("neutron", "security_group", order=next(_neutron_order),
               tenant_resource=True)
class NeutronSecurityGroup(NeutronMixin):
    def list(self):
        try:
            tenant_sgs = super(NeutronSecurityGroup, self).list()
            # NOTE(pirsriva): Filter out "default" security group deletion
            # by non-admin role user
            return filter(lambda r: r["name"] != "default",
                          tenant_sgs)
        except Exception as e:
            if getattr(e, "status_code", 400) == 404:
                return []
            raise


@base.resource("neutron", "quota", order=next(_neutron_order),
               admin_required=True, tenant_resource=True)
class NeutronQuota(QuotaMixin):

    def delete(self):
        self.admin.neutron().delete_quota(self.tenant_uuid)


# CINDER

_cinder_order = get_order(400)


@base.resource("cinder", "backups", order=next(_cinder_order),
               tenant_resource=True)
class CinderVolumeBackup(base.ResourceManager):
    pass


@base.resource("cinder", "volume_types", order=next(_cinder_order),
               admin_required=True, perform_for_admin_only=True)
class CinderVolumeType(base.ResourceManager):
    pass


@base.resource("cinder", "volume_snapshots", order=next(_cinder_order),
               tenant_resource=True)
class CinderVolumeSnapshot(base.ResourceManager):
    pass


@base.resource("cinder", "transfers", order=next(_cinder_order),
               tenant_resource=True)
class CinderVolumeTransfer(base.ResourceManager):
    pass


@base.resource("cinder", "volumes", order=next(_cinder_order),
               tenant_resource=True)
class CinderVolume(base.ResourceManager):
    pass


@base.resource("cinder", "image_volumes_cache", order=next(_cinder_order),
               admin_required=True, perform_for_admin_only=True)
class CinderImageVolumeCache(base.ResourceManager):

    def _glance(self):
        return image.Image(self.admin)

    def _manager(self):
        return self.admin.cinder().volumes

    def list(self):
        images = dict(("image-%s" % i.id, i)
                      for i in self._glance().list_images())
        return [{"volume": v, "image": images[v.name]}
                for v in self._manager().list(search_opts={"all_tenants": 1})
                if v.name in images]

    def name(self):
        return self.raw_resource["image"].name

    def id(self):
        return self.raw_resource["volume"].id


@base.resource("cinder", "quotas", order=next(_cinder_order),
               admin_required=True, tenant_resource=True)
class CinderQuotas(QuotaMixin, base.ResourceManager):
    pass


@base.resource("cinder", "qos_specs", order=next(_cinder_order),
               admin_required=True, perform_for_admin_only=True)
class CinderQos(base.ResourceManager):
    pass

# MANILA


_manila_order = get_order(450)


@base.resource("manila", "shares", order=next(_manila_order),
               tenant_resource=True)
class ManilaShare(base.ResourceManager):
    pass


@base.resource("manila", "share_networks", order=next(_manila_order),
               tenant_resource=True)
class ManilaShareNetwork(base.ResourceManager):
    pass


@base.resource("manila", "security_services", order=next(_manila_order),
               tenant_resource=True)
class ManilaSecurityService(base.ResourceManager):
    pass


# GLANCE

@base.resource("glance", "images", order=500, tenant_resource=True)
class GlanceImage(base.ResourceManager):

    def _client(self):
        return image.Image(self.admin or self.user)

    def list(self):
        images = (self._client().list_images(owner=self.tenant_uuid)
                  + self._client().list_images(status="deactivated",
                                               owner=self.tenant_uuid))
        return images

    def delete(self):
        client = self._client()
        if self.raw_resource.status == "deactivated":
            glancev2 = glance_v2.GlanceV2Service(self.admin or self.user)
            glancev2.reactivate_image(self.raw_resource.id)
        client.delete_image(self.raw_resource.id)
        task_utils.wait_for_status(
            self.raw_resource, ["deleted"],
            check_deletion=True,
            update_resource=self._client().get_image,
            timeout=CONF.openstack.glance_image_delete_timeout,
            check_interval=CONF.openstack.glance_image_delete_poll_interval)


# CEILOMETER

@base.resource("ceilometer", "alarms", order=700, tenant_resource=True)
class CeilometerAlarms(SynchronizedDeletion, base.ResourceManager):

    def id(self):
        return self.raw_resource.alarm_id

    def list(self):
        query = [{
            "field": "project_id",
            "op": "eq",
            "value": self.tenant_uuid
        }]
        return self._manager().list(q=query)


# ZAQAR

@base.resource("zaqar", "queues", order=800)
class ZaqarQueues(SynchronizedDeletion, base.ResourceManager):

    def list(self):
        return self.user.zaqar().queues()


# DESIGNATE
_designate_order = get_order(900)


class DesignateResource(SynchronizedDeletion, base.ResourceManager):

    # TODO(boris-42): This should be handled somewhere else.
    NAME_PREFIX = "s_rally_"

    def _manager(self, resource=None):
        # Map resource names to api / client version
        resource = resource or self._resource
        version = {
            "domains": "1",
            "servers": "1",
            "records": "1",
            "recordsets": "2",
            "zones": "2"
        }[resource]

        client = self._admin_required and self.admin or self.user
        return getattr(getattr(client, self._service)(version), resource)

    def id(self):
        """Returns id of resource."""
        return self.raw_resource["id"]

    def name(self):
        """Returns name of resource."""
        return self.raw_resource["name"]

    def list(self):
        return [item for item in self._manager().list()
                if item["name"].startswith(self.NAME_PREFIX)]


@base.resource("designate", "servers", order=next(_designate_order),
               admin_required=True, perform_for_admin_only=True, threads=1)
class DesignateServer(DesignateResource):
    pass


@base.resource("designate", "zones", order=next(_designate_order),
               tenant_resource=True, threads=1)
class DesignateZones(DesignateResource):

    def list(self):
        marker = None
        criterion = {"name": "%s*" % self.NAME_PREFIX}

        while True:
            items = self._manager().list(marker=marker, limit=100,
                                         criterion=criterion)
            if not items:
                break
            for item in items:
                yield item
            marker = items[-1]["id"]


# SWIFT

_swift_order = get_order(1000)


class SwiftMixin(SynchronizedDeletion, base.ResourceManager):

    def _manager(self):
        client = self._admin_required and self.admin or self.user
        return getattr(client, self._service)()

    def id(self):
        return self.raw_resource

    def name(self):
        # NOTE(stpierre): raw_resource is a list of either [container
        # name, object name] (as in SwiftObject) or just [container
        # name] (as in SwiftContainer).
        return self.raw_resource[-1]

    def delete(self):
        delete_method = getattr(self._manager(), "delete_%s" % self._resource)
        # NOTE(weiwu): *self.raw_resource is required because for deleting
        # container we are passing only container name, to delete object we
        # should pass as first argument container and second is object name.
        delete_method(*self.raw_resource)


@base.resource("swift", "object", order=next(_swift_order),
               tenant_resource=True)
class SwiftObject(SwiftMixin):

    def list(self):
        object_list = []
        containers = self._manager().get_account(full_listing=True)[1]
        for con in containers:
            objects = self._manager().get_container(con["name"],
                                                    full_listing=True)[1]
            for obj in objects:
                raw_resource = [con["name"], obj["name"]]
                object_list.append(raw_resource)
        return object_list


@base.resource("swift", "container", order=next(_swift_order),
               tenant_resource=True)
class SwiftContainer(SwiftMixin):

    def list(self):
        containers = self._manager().get_account(full_listing=True)[1]
        return [[con["name"]] for con in containers]


# MISTRAL

_mistral_order = get_order(1100)


@base.resource("mistral", "workbooks", order=next(_mistral_order),
               tenant_resource=True)
class MistralWorkbooks(SynchronizedDeletion, base.ResourceManager):
    def delete(self):
        self._manager().delete(self.raw_resource.name)


@base.resource("mistral", "workflows", order=next(_mistral_order),
               tenant_resource=True)
class MistralWorkflows(SynchronizedDeletion, base.ResourceManager):
    pass


@base.resource("mistral", "executions", order=next(_mistral_order),
               tenant_resource=True)
class MistralExecutions(SynchronizedDeletion, base.ResourceManager):

    def name(self):
        # NOTE(andreykurilin): Mistral Execution doesn't have own name which
        #   we can use for filtering, but it stores workflow id and name, even
        #   after workflow deletion.
        return self.raw_resource.workflow_name


# IRONIC

_ironic_order = get_order(1300)


@base.resource("ironic", "node", admin_required=True,
               order=next(_ironic_order), perform_for_admin_only=True)
class IronicNodes(base.ResourceManager):

    def id(self):
        return self.raw_resource.uuid


# GNOCCHI

_gnocchi_order = get_order(1400)


class GnocchiMixin(base.ResourceManager):

    def name(self):
        return self.raw_resource["name"]

    def id(self):
        return self.raw_resource["name"]


@base.resource("gnocchi", "archive_policy_rule", order=next(_gnocchi_order),
               admin_required=True, perform_for_admin_only=True)
class GnocchiArchivePolicyRule(GnocchiMixin):
    pass


@base.resource("gnocchi", "archive_policy", order=next(_gnocchi_order),
               admin_required=True, perform_for_admin_only=True)
class GnocchiArchivePolicy(GnocchiMixin):
    pass


@base.resource("gnocchi", "resource_type", order=next(_gnocchi_order),
               admin_required=True, perform_for_admin_only=True)
class GnocchiResourceType(GnocchiMixin):
    pass


@base.resource("gnocchi", "metric", order=next(_gnocchi_order),
               tenant_resource=True)
class GnocchiMetric(GnocchiMixin):

    def id(self):
        return self.raw_resource["id"]

    def list(self):
        result = []
        marker = None
        while True:
            metrics = self._manager().list(marker=marker)
            if not metrics:
                break
            result.extend(metrics)
            marker = metrics[-1]["id"]
        if self.tenant_uuid:
            result = [r for r in result
                      if r["creator"].partition(":")[2] == self.tenant_uuid]

        return result


@base.resource("gnocchi", "resource", order=next(_gnocchi_order),
               tenant_resource=True)
class GnocchiResource(GnocchiMixin):
    def id(self):
        return self.raw_resource["id"]

    def name(self):
        return self.raw_resource["original_resource_id"]

    def is_deleted(self):
        from gnocchiclient import exceptions as gnocchi_exc
        try:
            self._manager().get(self.raw_resource["type"], self.id())
        except gnocchi_exc.NotFound:
            return True
        return False

    def list(self):
        result = []
        marker = None
        while True:
            resources = self._manager().list(marker=marker)
            if not resources:
                break
            result.extend(resources)
            marker = resources[-1]["id"]

        return result


# WATCHER

_watcher_order = get_order(1500)


class WatcherMixin(SynchronizedDeletion, base.ResourceManager):

    def id(self):
        return self.raw_resource.uuid

    def list(self):
        return self._manager().list(limit=0)

    def is_deleted(self):
        from watcherclient.common.apiclient import exceptions
        try:
            self._manager().get(self.id())
            return False
        except exceptions.NotFound:
            return True


@base.resource("watcher", "audit_template", order=next(_watcher_order),
               admin_required=True, perform_for_admin_only=True)
class WatcherTemplate(WatcherMixin):
    pass


@base.resource("watcher", "action_plan", order=next(_watcher_order),
               admin_required=True, perform_for_admin_only=True)
class WatcherActionPlan(WatcherMixin):

    def name(self):
        return base.NoName(self._resource)


@base.resource("watcher", "audit", order=next(_watcher_order),
               admin_required=True, perform_for_admin_only=True)
class WatcherAudit(WatcherMixin):

    def name(self):
        return self.raw_resource.uuid


# KEYSTONE

_keystone_order = get_order(9000)


class KeystoneMixin(SynchronizedDeletion):

    def _manager(self):
        return identity.Identity(self.admin)

    def delete(self):
        delete_method = getattr(self._manager(), "delete_%s" % self._resource)
        delete_method(self.id())

    def list(self):
        resources = self._resource + "s"
        return getattr(self._manager(), "list_%s" % resources)()


@base.resource("keystone", "user", order=next(_keystone_order),
               admin_required=True, perform_for_admin_only=True)
class KeystoneUser(KeystoneMixin, base.ResourceManager):
    pass


@base.resource("keystone", "project", order=next(_keystone_order),
               admin_required=True, perform_for_admin_only=True)
class KeystoneProject(KeystoneMixin, base.ResourceManager):
    pass


@base.resource("keystone", "service", order=next(_keystone_order),
               admin_required=True, perform_for_admin_only=True)
class KeystoneService(KeystoneMixin, base.ResourceManager):
    pass


@base.resource("keystone", "role", order=next(_keystone_order),
               admin_required=True, perform_for_admin_only=True)
class KeystoneRole(KeystoneMixin, base.ResourceManager):
    pass


# NOTE(andreykurilin): unfortunately, ec2 credentials doesn't have name
#   and id fields. It makes impossible to identify resources belonging to
#   particular task.
@base.resource("keystone", "ec2", tenant_resource=True,
               order=next(_keystone_order))
class KeystoneEc2(SynchronizedDeletion, base.ResourceManager):
    def _manager(self):
        return identity.Identity(self.user)

    def id(self):
        return "n/a"

    def name(self):
        return base.NoName(self._resource)

    @property
    def user_id(self):
        return self.user.keystone.auth_ref.user_id

    def list(self):
        return self._manager().list_ec2credentials(self.user_id)

    def delete(self):
        self._manager().delete_ec2credential(
            self.user_id, access=self.raw_resource.access)

# BARBICAN


@base.resource("barbican", "secrets", order=1500, admin_required=True,
               perform_for_admin_only=True)
class BarbicanSecrets(base.ResourceManager):

    def id(self):
        return self.raw_resource.secret_ref

    def is_deleted(self):
        try:
            self._manager().get(self.id()).status
        except Exception:
            return True

        return False


@base.resource("barbican", "containers", order=1500, admin_required=True,
               perform_for_admin_only=True)
class BarbicanContainers(base.ResourceManager):
    pass


@base.resource("barbican", "orders", order=1500, admin_required=True,
               perform_for_admin_only=True)
class BarbicanOrders(base.ResourceManager):
    pass
