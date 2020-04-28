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

import abc

from neutronclient.common import exceptions as neutron_exceptions

from rally.common import cfg
from rally.common import logging
from rally import exceptions

from rally_openstack.common import consts
from rally_openstack.common.services.network import net_utils
from rally_openstack.common.services.network import neutron


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def generate_cidr(start_cidr="10.2.0.0/24"):
    """Generate next CIDR for network or subnet, without IP overlapping.

    This is process and thread safe, because `cidr_incr' points to
    value stored directly in RAM. This guarantees that CIDRs will be
    serial and unique even under hard multiprocessing/threading load.

    :param start_cidr: start CIDR str
    :returns: next available CIDR str
    """
    ip_version, cidr = net_utils.generate_cidr(start_cidr=start_cidr)
    return cidr


class NetworkWrapperException(exceptions.RallyException):
    error_code = 532
    msg_fmt = "%(message)s"


class NetworkWrapper(object, metaclass=abc.ABCMeta):
    """Base class for network service implementations.

    We actually have two network services implementations, with different API:
    NovaNetwork and Neutron. The idea is (at least to try) to use unified
    service, which hides most differences and routines behind the scenes.
    This allows to significantly re-use and simplify code.
    """
    START_CIDR = "10.2.0.0/24"
    START_IPV6_CIDR = "dead:beaf::/64"
    SERVICE_IMPL = None

    def __init__(self, clients, owner, config=None):
        """Returns available network wrapper instance.

        :param clients: rally.plugins.openstack.osclients.Clients instance
        :param owner: The object that owns resources created by this
                      wrapper instance. It will be used to generate
                      random names, so must implement
                      rally.common.utils.RandomNameGeneratorMixin
        :param config: The configuration of the network
                       wrapper. Currently only two config options are
                       recognized, 'start_cidr' and 'start_ipv6_cidr'.
        :returns: NetworkWrapper subclass instance
        """
        self.clients = clients
        if hasattr(clients, self.SERVICE_IMPL):
            self.client = getattr(clients, self.SERVICE_IMPL)()
        else:
            self.client = clients(self.SERVICE_IMPL)
        self.config = config or {}
        self.owner = owner
        self.start_cidr = self.config.get("start_cidr", self.START_CIDR)
        self.start_ipv6_cidr = self.config.get(
            "start_ipv6_cidr", self.START_IPV6_CIDR)

    @abc.abstractmethod
    def create_network(self):
        """Create network."""

    @abc.abstractmethod
    def delete_network(self):
        """Delete network."""

    @abc.abstractmethod
    def list_networks(self):
        """List networks."""

    @abc.abstractmethod
    def create_floating_ip(self):
        """Create floating IP."""

    @abc.abstractmethod
    def delete_floating_ip(self):
        """Delete floating IP."""

    @abc.abstractmethod
    def supports_extension(self):
        """Checks whether a network extension is supported."""


class NeutronWrapper(NetworkWrapper):
    SERVICE_IMPL = consts.Service.NEUTRON
    SUBNET_IP_VERSION = 4
    SUBNET_IPV6_VERSION = 6
    LB_METHOD = "ROUND_ROBIN"
    LB_PROTOCOL = "HTTP"

    def __init__(self, *args, **kwargs):
        super(NeutronWrapper, self).__init__(*args, **kwargs)

        class _SingleClientWrapper(object):
            def neutron(_self):
                return self.client

            @property
            def credential(_self):
                return self.clients.credential

        self.neutron = neutron.NeutronService(
            clients=_SingleClientWrapper(),
            name_generator=self.owner.generate_random_name,
            atomic_inst=getattr(self.owner, "_atomic_actions", [])
        )

    @property
    def external_networks(self):
        return self.neutron.list_networks(router_external=True)

    @property
    def ext_gw_mode_enabled(self):
        """Determine if the ext-gw-mode extension is enabled.

        Without this extension, we can't pass the enable_snat parameter.
        """
        return self.neutron.supports_extension("ext-gw-mode", silent=True)

    def get_network(self, net_id=None, name=None):
        net = None
        try:
            if net_id:
                net = self.neutron.get_network(net_id)
            else:
                networks = self.neutron.list_networks(name=name)
                if networks:
                    net = networks[0]
        except neutron_exceptions.NeutronClientException:
            pass

        if net:
            return {"id": net["id"],
                    "name": net["name"],
                    "tenant_id": net.get("tenant_id",
                                         net.get("project_id", None)),
                    "status": net["status"],
                    "external": net.get("router:external", False),
                    "subnets": net.get("subnets", []),
                    "router_id": None}
        else:
            raise NetworkWrapperException(
                "Network not found: %s" % (name or net_id))

    def create_router(self, external=False, **kwargs):
        """Create neutron router.

        :param external: bool, whether to set setup external_gateway_info
        :param **kwargs: POST /v2.0/routers request options
        :returns: neutron router dict
        """
        kwargs.pop("name", None)
        if "tenant_id" in kwargs and "project_id" not in kwargs:
            kwargs["project_id"] = kwargs.pop("tenant_id")

        return self.neutron.create_router(
            discover_external_gw=external, **kwargs)

    def create_v1_pool(self, tenant_id, subnet_id, **kwargs):
        """Create LB Pool (v1).

        :param tenant_id: str, pool tenant id
        :param subnet_id: str, neutron subnet-id
        :param **kwargs: extra options
        :returns: neutron lb-pool dict
        """
        pool_args = {
            "pool": {
                "tenant_id": tenant_id,
                "name": self.owner.generate_random_name(),
                "subnet_id": subnet_id,
                "lb_method": kwargs.get("lb_method", self.LB_METHOD),
                "protocol": kwargs.get("protocol", self.LB_PROTOCOL)
            }
        }
        return self.client.create_pool(pool_args)

    def _generate_cidr(self, ip_version=4):
        # TODO(amaretskiy): Generate CIDRs unique for network, not cluster
        ip_version, cidr = net_utils.generate_cidr(
            start_cidr=self.start_cidr if ip_version == 4
            else self.start_ipv6_cidr)
        return cidr

    def _create_network_infrastructure(self, tenant_id, **kwargs):
        """Create network.

        The following keyword arguments are accepted:

        * add_router: Deprecated, please use router_create_args instead.
                      Create an external router and add an interface to each
                      subnet created. Default: False
        * subnets_num: Number of subnets to create per network. Default: 0
        * dualstack: Whether subnets should be of both IPv4 and IPv6
        * dns_nameservers: Nameservers for each subnet. Default:
                           8.8.8.8, 8.8.4.4
        * network_create_args: Additional network creation arguments.
        * router_create_args: Additional router creation arguments.

        :param tenant_id: str, tenant ID
        :param kwargs: Additional options, left open-ended for compatbilitiy.
                       See above for recognized keyword args.
        :returns: dict, network data
        """
        network_args = dict(kwargs.get("network_create_args", {}))
        network_args["project_id"] = tenant_id

        router_args = dict(kwargs.get("router_create_args", {}))
        add_router = kwargs.get("add_router", False)
        if not (router_args or add_router):
            router_args = None
        else:
            router_args["project_id"] = tenant_id
            router_args["discover_external_gw"] = router_args.pop(
                "external", False) or add_router
        subnet_create_args = {"project_id": tenant_id}
        if "dns_nameservers" in kwargs:
            subnet_create_args["dns_nameservers"] = kwargs["dns_nameservers"]

        net_topo = self.neutron.create_network_topology(
            network_create_args=network_args,
            router_create_args=router_args,
            subnet_create_args=subnet_create_args,
            subnets_dualstack=kwargs.get("dualstack", False),
            subnets_count=kwargs.get("subnets_num", 0)
        )
        network = net_topo["network"]
        subnets = net_topo["subnets"]
        if net_topo["routers"]:
            router = net_topo["routers"][0]
        else:
            router = None

        return {
            "network": {
                "id": network["id"],
                "name": network["name"],
                "status": network["status"],
                "subnets": [s["id"] for s in subnets],
                "external": network.get("router:external", False),
                "router_id": router and router["id"] or None,
                "tenant_id": tenant_id
            },
            "subnets": subnets,
            "router": router
        }

    def create_network(self, tenant_id, **kwargs):
        """Create network.

        The following keyword arguments are accepted:

        * add_router: Deprecated, please use router_create_args instead.
                      Create an external router and add an interface to each
                      subnet created. Default: False
        * subnets_num: Number of subnets to create per network. Default: 0
        * dualstack: Whether subnets should be of both IPv4 and IPv6
        * dns_nameservers: Nameservers for each subnet. Default:
                           8.8.8.8, 8.8.4.4
        * network_create_args: Additional network creation arguments.
        * router_create_args: Additional router creation arguments.

        :param tenant_id: str, tenant ID
        :param kwargs: Additional options, left open-ended for compatbilitiy.
                       See above for recognized keyword args.
        :returns: dict, network data
        """
        return self._create_network_infrastructure(
            tenant_id, **kwargs)["network"]

    def delete_v1_pool(self, pool_id):
        """Delete LB Pool (v1)

        :param pool_id: str, Lb-Pool-id
        """
        self.client.delete_pool(pool_id)

    def delete_network(self, network):
        """Delete network

        :param network: network object returned by create_network method
        """

        router = {"id": network["router_id"]} if network["router_id"] else None
        # delete_network_topology uses only IDs, but let's transmit as much as
        # possible info
        topo = {
            "network": {
                "id": network["id"],
                "name": network["name"],
                "status": network["status"],
                "subnets": network["subnets"],
                "router:external": network["external"]
            },
            "subnets": [{"id": s} for s in network["subnets"]],
            "routers": [router] if router else []
        }

        self.neutron.delete_network_topology(topo)

    def _delete_subnet(self, subnet_id):
        self.neutron.delete_subnet(subnet_id)

    def list_networks(self):
        return self.neutron.list_networks()

    def create_port(self, network_id, **kwargs):
        """Create neutron port.

        :param network_id: neutron network id
        :param **kwargs: POST /v2.0/ports request options
        :returns: neutron port dict
        """
        return self.neutron.create_port(network_id=network_id, **kwargs)

    def create_floating_ip(self, ext_network=None,
                           tenant_id=None, port_id=None, **kwargs):
        """Create Neutron floating IP.

        :param ext_network: floating network name or dict
        :param tenant_id: str tenant id
        :param port_id: str port id
        :param **kwargs: for compatibility, not used here
        :returns: floating IP dict
        """
        if not tenant_id:
            raise ValueError("Missed tenant_id")
        try:
            fip = self.neutron.create_floatingip(
                floating_network=ext_network, project_id=tenant_id,
                port_id=port_id)
        except (exceptions.NotFoundException,
                exceptions.GetResourceFailure) as e:
            raise NetworkWrapperException(str(e)) from None
        return {"id": fip["id"], "ip": fip["floating_ip_address"]}

    def delete_floating_ip(self, fip_id, **kwargs):
        """Delete floating IP.

        :param fip_id: int floating IP id
        :param **kwargs: for compatibility, not used here
        """
        self.neutron.delete_floatingip(fip_id)

    def supports_extension(self, extension):
        """Check whether a neutron extension is supported

        :param extension: str, neutron extension
        :returns: result tuple
        :rtype: (bool, string)
        """
        try:
            self.neutron.supports_extension(extension)
        except exceptions.NotFoundException as e:
            return False, str(e)

        return True, ""


def wrap(clients, owner, config=None):
    """Returns available network wrapper instance.

    :param clients: rally.plugins.openstack.osclients.Clients instance
    :param owner: The object that owns resources created by this
                  wrapper instance. It will be used to generate random
                  names, so must implement
                  rally.common.utils.RandomNameGeneratorMixin
    :param config: The configuration of the network wrapper. Currently
                   only one config option is recognized, 'start_cidr',
                   and only for Nova network.
    :returns: NetworkWrapper subclass instance
    """
    if hasattr(clients, "services"):
        services = clients.services()
    else:
        services = clients("services")

    if consts.Service.NEUTRON in services.values():
        return NeutronWrapper(clients, owner, config=config)
    LOG.warning("NovaNetworkWrapper is deprecated since 0.9.0")
