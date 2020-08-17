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

import itertools

from rally.common import cfg
from rally.common import logging
from rally import exceptions
from rally.task import atomic
from rally.task import service

from rally_openstack.common import consts
from rally_openstack.common.services.network import net_utils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


def _args_adapter(arguments_map):
    def wrapper(func):
        def decorator(*args, **kwargs):
            for source, dest in arguments_map.items():
                if source in kwargs:
                    if dest in kwargs:
                        raise TypeError(
                            f"{func.__name__}() accepts either {dest} keyword "
                            f"argument or {source} but both were specified.")
                    kwargs[dest] = kwargs.pop(source)
            return func(*args, **kwargs)
        return decorator
    return wrapper


_NETWORK_ARGS_MAP = {
    "provider:network_type": "provider_network_type",
    "provider:physical_network": "provider_physical_network",
    "provider:segmentation_id": "provider_segmentation_id",
    "router:external": "router_external"
}


def _create_network_arg_adapter():
    """A decorator for converting neutron's create kwargs to look pythonic."""
    return _args_adapter(_NETWORK_ARGS_MAP)


class _NoneObj(object):
    def __len__(self):
        return 0


_NONE = _NoneObj()


def _clean_dict(**kwargs):
    """Builds a dict object from keyword arguments ignoring nullable values."""
    return dict((k, v) for k, v in kwargs.items() if v != _NONE)


@service.service(service_name="neutron", service_type="network", version="2.0")
class NeutronService(service.Service):
    """A helper class for Neutron API"""

    def __init__(self, *args, **kwargs):
        super(NeutronService, self).__init__(*args, **kwargs)
        self._cached_supported_extensions = None
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self._clients.neutron()
        return self._client

    def create_network_topology(
            self, network_create_args=None,
            router_create_args=None, router_per_subnet=False,
            subnet_create_args=None, subnets_count=1, subnets_dualstack=False
    ):
        """Create net infrastructure(network, router, subnets).

        :param network_create_args: A dict with creation arguments for a
            network. The format is equal to the create_network method
        :param router_create_args: A dict with creation arguments for an
            external router that will add an interface to each created subnet.
            The format is equal to the create_subnet method
            In case of None value (default behaviour), no router is created.
        :param router_per_subnet: whether or not to create router per subnet
            or use one router for all subnets.
        :param subnet_create_args: A dict with creation arguments for
            subnets. The format is equal to the create_subnet method.
        :param subnets_count: Number of subnets to create per network.
            Defaults to 1
        :param subnets_dualstack: Whether subnets should be of both IPv4 and
            IPv6 (i.e first subnet will be created for IPv4, the second for
            IPv6, the third for IPv4,..). If subnet_create_args includes one of
            ('cidr', 'start_cidr', 'ip_version') keys, subnets_dualstack
            parameter will be ignored.
        """
        subnet_create_args = dict(subnet_create_args or {})

        network = self.create_network(**(network_create_args or {}))
        subnet_create_args["network_id"] = network["id"]

        routers = []
        if router_create_args is not None:
            for i in range(subnets_count if router_per_subnet else 1):
                routers.append(self.create_router(**router_create_args))

        subnets = []
        ip_versions = itertools.cycle([4, 6] if subnets_dualstack else [4])
        use_subnets_dualstack = (
            "cidr" not in subnet_create_args
            and "start_cidr" not in subnet_create_args
            and "ip_version" not in subnet_create_args
        )

        for i in range(subnets_count):
            if use_subnets_dualstack:
                subnet_create_args["ip_version"] = next(ip_versions)
            if routers:
                if router_per_subnet:
                    router = routers[i]
                else:
                    router = routers[0]
                subnet_create_args["router_id"] = router["id"]

            subnets.append(self.create_subnet(**subnet_create_args))

        network["subnets"] = [s["id"] for s in subnets]

        return {
            "network": network,
            "subnets": subnets,
            "routers": routers
        }

    def delete_network_topology(self, topo):
        """Delete network topology

        This method was developed to provide a backward compatibility with old
        neutron helpers. It is not recommended way and we suggest to use
        cleanup manager instead.

        :param topo: Network topology as create_network_topology returned
        """
        for router in topo["routers"]:
            self.remove_gateway_from_router(router["id"])

        network_id = topo["network"]["id"]

        for port in self.list_ports(network_id=network_id):
            self.delete_port(port)

        for subnet in self.list_subnets(network_id=network_id):
            self.delete_subnet(subnet["id"])

        self.delete_network(network_id)

        for router in topo["routers"]:
            self.delete_router(router["id"])

    @atomic.action_timer("neutron.create_network")
    @_create_network_arg_adapter()
    def create_network(self,
                       project_id=_NONE,
                       admin_state_up=_NONE,
                       dns_domain=_NONE,
                       mtu=_NONE,
                       port_security_enabled=_NONE,
                       provider_network_type=_NONE,
                       provider_physical_network=_NONE,
                       provider_segmentation_id=_NONE,
                       qos_policy_id=_NONE,
                       router_external=_NONE,
                       segments=_NONE,
                       shared=_NONE,
                       vlan_transparent=_NONE,
                       description=_NONE,
                       availability_zone_hints=_NONE):
        """Create neutron network.

        :param project_id: The ID of the project that owns the resource. Only
            administrative and users with advsvc role can specify a project ID
            other than their own. You cannot change this value through
            authorization policies.
        :param admin_state_up: The administrative state of the network,
            which is up (true) or down (false).
        :param dns_domain: A valid DNS domain.
        :param mtu: The maximum transmission unit (MTU) value to address
            fragmentation. Minimum value is 68 for IPv4, and 1280 for IPv6.
        :param port_security_enabled: The port security status of the network.
            Valid values are enabled (true) and disabled (false). This value is
            used as the default value of port_security_enabled field of a
            newly created port.
        :param provider_network_type: The type of physical network that this
            network should be mapped to. For example, flat, vlan, vxlan,
            or gre. Valid values depend on a networking back-end.
        :param provider_physical_network: The physical network where this
            network should be implemented. The Networking API v2.0 does not
            provide a way to list available physical networks.
            For example, the Open vSwitch plug-in configuration file defines
            a symbolic name that maps to specific bridges on each compute host.
        :param provider_segmentation_id: The ID of the isolated segment on the
            physical network. The network_type attribute defines the
            segmentation model. For example, if the network_type value is vlan,
            this ID is a vlan identifier. If the network_type value is gre,
            this ID is a gre key.
        :param qos_policy_id: The ID of the QoS policy associated with the
            network.
        :param router_external: Indicates whether the network has an external
            routing facility that’s not managed by the networking service.
        :param segments: A list of provider segment objects.
        :param shared: Indicates whether this resource is shared across all
            projects. By default, only administrative users can change
            this value.
        :param vlan_transparent: Indicates the VLAN transparency mode of the
            network, which is VLAN transparent (true) or not VLAN
            transparent (false).
        :param description: A human-readable description for the resource.
            Default is an empty string.
        :param availability_zone_hints: The availability zone candidate for
            the network.
        :returns: neutron network dict
        """
        body = _clean_dict(
            name=self.generate_random_name(),
            tenant_id=project_id,
            admin_state_up=admin_state_up,
            dns_domain=dns_domain,
            mtu=mtu,
            port_security_enabled=port_security_enabled,
            qos_policy_id=qos_policy_id,
            segments=segments,
            shared=shared,
            vlan_transparent=vlan_transparent,
            description=description,
            availability_zone_hints=availability_zone_hints,
            **{
                "provider:network_type": provider_network_type,
                "provider:physical_network": provider_physical_network,
                "provider:segmentation_id": provider_segmentation_id,
                "router:external": router_external
            }
        )
        resp = self.client.create_network({"network": body})
        return resp["network"]

    @atomic.action_timer("neutron.show_network")
    def get_network(self, network_id, fields=_NONE):
        """Get network by ID

        :param network_id: Network ID to fetch data for
        :param fields: The fields that you want the server to return. If no
            fields list is specified, the networking API returns all
            attributes allowed by the policy settings. By using fields
            parameter, the API returns only the requested set of attributes.
        """
        body = _clean_dict(fields=fields)
        resp = self.client.show_network(network_id, **body)
        return resp["network"]

    def find_network(self, network_id_or_name, external=_NONE):
        """Find network by identifier (id or name)

        :param network_id_or_name: Network ID or name
        :param external: check target network is external or not
        """
        network = None
        for net in self.list_networks():
            if network_id_or_name in (net["name"], net["id"]):
                network = net
                break
        if network is None:
            raise exceptions.GetResourceFailure(
                resource="network",
                err=f"no name or id matches {network_id_or_name}")
        if external:
            if not network.get("router:external", False):
                raise exceptions.NotFoundException(
                    f"Network '{network['name']} (id={network['id']})' is not "
                    f"external.")
        return network

    @atomic.action_timer("neutron.update_network")
    @_create_network_arg_adapter()
    def update_network(self,
                       network_id,
                       name=_NONE,
                       admin_state_up=_NONE,
                       dns_domain=_NONE,
                       mtu=_NONE,
                       port_security_enabled=_NONE,
                       provider_network_type=_NONE,
                       provider_physical_network=_NONE,
                       provider_segmentation_id=_NONE,
                       qos_policy_id=_NONE,
                       router_external=_NONE,
                       segments=_NONE,
                       shared=_NONE,
                       description=_NONE,
                       is_default=_NONE):
        """Update neutron network.

        :param network_id: ID of the network to update
        :param name: Human-readable name of the network.
        :param admin_state_up: The administrative state of the network,
            which is up (true) or down (false).
        :param dns_domain: A valid DNS domain.
        :param mtu: The maximum transmission unit (MTU) value to address
            fragmentation. Minimum value is 68 for IPv4, and 1280 for IPv6.
        :param port_security_enabled: The port security status of the network.
            Valid values are enabled (true) and disabled (false). This value is
            used as the default value of port_security_enabled field of a
            newly created port.
        :param provider_network_type: The type of physical network that this
            network should be mapped to. For example, flat, vlan, vxlan,
            or gre. Valid values depend on a networking back-end.
        :param provider_physical_network: The physical network where this
            network should be implemented. The Networking API v2.0 does not
            provide a way to list available physical networks.
            For example, the Open vSwitch plug-in configuration file defines
            a symbolic name that maps to specific bridges on each compute host.
        :param provider_segmentation_id: The ID of the isolated segment on the
            physical network. The network_type attribute defines the
            segmentation model. For example, if the network_type value is vlan,
            this ID is a vlan identifier. If the network_type value is gre,
            this ID is a gre key.
        :param qos_policy_id: The ID of the QoS policy associated with the
            network.
        :param router_external: Indicates whether the network has an external
            routing facility that’s not managed by the networking service.
        :param segments: A list of provider segment objects.
        :param shared: Indicates whether this resource is shared across all
            projects. By default, only administrative users can change
            this value.
        :param description: A human-readable description for the resource.
            Default is an empty string.
        :param is_default: The network is default or not.
        :returns: neutron network dict
        """
        body = _clean_dict(
            name=name,
            admin_state_up=admin_state_up,
            dns_domain=dns_domain,
            mtu=mtu,
            port_security_enabled=port_security_enabled,
            qos_policy_id=qos_policy_id,
            segments=segments,
            shared=shared,
            description=description,
            is_default=is_default,
            **{
                "provider:network_type": provider_network_type,
                "provider:physical_network": provider_physical_network,
                "provider:segmentation_id": provider_segmentation_id,
                "router:external": router_external
            }
        )
        if not body:
            raise TypeError("No updates for a network.")
        resp = self.client.update_network(network_id, {"network": body})
        return resp["network"]

    @atomic.action_timer("neutron.delete_network")
    def delete_network(self, network_id):
        """Delete network

        :param network_id: Network ID
        """
        self.client.delete_network(network_id)

    @atomic.action_timer("neutron.list_networks")
    def list_networks(self, name=_NONE, router_external=_NONE, status=_NONE,
                      **kwargs):
        """List networks.

        :param name: Filter the list result by the human-readable name of the
            resource.
        :param router_external: Filter the network list result based on whether
            the network has an external routing facility that’s not managed by
            the networking service.
        :param status: Filter the network list result by network status.
            Values are ACTIVE, DOWN, BUILD or ERROR.
        :param kwargs: additional network list filters
        """
        kwargs["router:external"] = router_external
        filters = _clean_dict(name=name, status=status, **kwargs)
        return self.client.list_networks(**filters)["networks"]

    IPv4_DEFAULT_DNS_NAMESERVERS = ["8.8.8.8", "8.8.4.4"]
    IPv6_DEFAULT_DNS_NAMESERVERS = ["dead:beaf::1", "dead:beaf::2"]

    @atomic.action_timer("neutron.create_subnet")
    def create_subnet(self, network_id, router_id=_NONE, project_id=_NONE,
                      enable_dhcp=_NONE,
                      dns_nameservers=_NONE, allocation_pools=_NONE,
                      host_routes=_NONE, ip_version=_NONE, gateway_ip=_NONE,
                      cidr=_NONE, start_cidr=_NONE, prefixlen=_NONE,
                      ipv6_address_mode=_NONE, ipv6_ra_mode=_NONE,
                      segment_id=_NONE, subnetpool_id=_NONE,
                      use_default_subnetpool=_NONE, service_types=_NONE,
                      dns_publish_fixed_ip=_NONE):
        """Create neutron subnet.

        :param network_id: The ID of the network to which the subnet belongs.
        :param router_id: An external router and add as an interface to subnet.
        :param project_id: The ID of the project that owns the resource.
            Only administrative and users with advsvc role can specify a
            project ID other than their own. You cannot change this value
            through authorization policies.
        :param enable_dhcp: Indicates whether dhcp is enabled or disabled for
            the subnet. Default is true.
        :param dns_nameservers: List of dns name servers associated with the
            subnet. Default is a list of Google DNS
        :param allocation_pools: Allocation pools with start and end IP
            addresses for this subnet. If allocation_pools are not specified,
            OpenStack Networking automatically allocates pools for covering
            all IP addresses in the CIDR, excluding the address reserved for
            the subnet gateway by default.
        :param host_routes: Additional routes for the subnet. A list of
            dictionaries with destination and nexthop parameters. Default
            value is an empty list.
        :param gateway_ip: Gateway IP of this subnet. If the value is null that
            implies no gateway is associated with the subnet. If the gateway_ip
            is not specified, OpenStack Networking allocates an address from
            the CIDR for the gateway for the subnet by default.
        :param ip_version: The IP protocol version. Value is 4 or 6. If CIDR
            is specified, the value automatically can be detected from it,
            otherwise defaults to 4.
            Also, check start_cidr param description.
        :param cidr: The CIDR of the subnet. If not specified, it will be
            auto-generated based on start_cidr and ip_version parameters.
        :param start_cidr:
        :param prefixlen: he prefix length to use for subnet allocation from a
            subnet pool. If not specified, the default_prefixlen value of the
            subnet pool will be used.
        :param ipv6_address_mode: The IPv6 address modes specifies mechanisms
            for assigning IP addresses. Value is slaac, dhcpv6-stateful,
            dhcpv6-stateless.
        :param ipv6_ra_mode: The IPv6 router advertisement specifies whether
            the networking service should transmit ICMPv6 packets, for a
            subnet. Value is slaac, dhcpv6-stateful, dhcpv6-stateless.
        :param segment_id: The ID of a network segment the subnet is
            associated with. It is available when segment extension is enabled.
        :param subnetpool_id: The ID of the subnet pool associated with the
            subnet.
        :param use_default_subnetpool: Whether to allocate this subnet from
            the default subnet pool.
        :param service_types: The service types associated with the subnet.
        :param dns_publish_fixed_ip: Whether to publish DNS records for IPs
            from this subnet. Default is false.
        """

        if cidr == _NONE:
            ip_version, cidr = net_utils.generate_cidr(
                ip_version=ip_version, start_cidr=(start_cidr or None))
        if ip_version == _NONE:
            ip_version = net_utils.get_ip_version(cidr)

        if dns_nameservers == _NONE:
            if ip_version == 4:
                dns_nameservers = self.IPv4_DEFAULT_DNS_NAMESERVERS
            else:
                dns_nameservers = self.IPv6_DEFAULT_DNS_NAMESERVERS

        body = _clean_dict(
            name=self.generate_random_name(),
            network_id=network_id,
            tenant_id=project_id,
            enable_dhcp=enable_dhcp,
            dns_nameservers=dns_nameservers,
            allocation_pools=allocation_pools,
            host_routes=host_routes,
            ip_version=ip_version,
            gateway_ip=gateway_ip,
            cidr=cidr,
            prefixlen=prefixlen,
            ipv6_address_mode=ipv6_address_mode,
            ipv6_ra_mode=ipv6_ra_mode,
            segment_id=segment_id,
            subnetpool_id=subnetpool_id,
            use_default_subnetpool=use_default_subnetpool,
            service_types=service_types,
            dns_publish_fixed_ip=dns_publish_fixed_ip
        )

        subnet = self.client.create_subnet({"subnet": body})["subnet"]
        if router_id:
            self.add_interface_to_router(router_id=router_id,
                                         subnet_id=subnet["id"])
        return subnet

    @atomic.action_timer("neutron.show_subnet")
    def get_subnet(self, subnet_id):
        """Get subnet

        :param subnet_id: Subnet ID
        """
        return self.client.show_subnet(subnet_id)["subnet"]

    @atomic.action_timer("neutron.update_subnet")
    def update_subnet(self, subnet_id, name=_NONE, enable_dhcp=_NONE,
                      dns_nameservers=_NONE, allocation_pools=_NONE,
                      host_routes=_NONE, gateway_ip=_NONE, description=_NONE,
                      service_types=_NONE, segment_id=_NONE,
                      dns_publish_fixed_ip=_NONE):
        """Update neutron subnet.

        :param subnet_id: The ID of the subnet to update.
        :param name: Human-readable name of the resource.
        :param description: A human-readable description for the resource.
            Default is an empty string.
        :param enable_dhcp: Indicates whether dhcp is enabled or disabled for
            the subnet. Default is true.
        :param dns_nameservers: List of dns name servers associated with the
            subnet. Default is a list of Google DNS
        :param allocation_pools: Allocation pools with start and end IP
            addresses for this subnet. If allocation_pools are not specified,
            OpenStack Networking automatically allocates pools for covering
            all IP addresses in the CIDR, excluding the address reserved for
            the subnet gateway by default.
        :param host_routes: Additional routes for the subnet. A list of
            dictionaries with destination and nexthop parameters. Default
            value is an empty list.
        :param gateway_ip: Gateway IP of this subnet. If the value is null that
            implies no gateway is associated with the subnet. If the gateway_ip
            is not specified, OpenStack Networking allocates an address from
            the CIDR for the gateway for the subnet by default.
        :param segment_id: The ID of a network segment the subnet is
            associated with. It is available when segment extension is enabled.
        :param service_types: The service types associated with the subnet.
        :param dns_publish_fixed_ip: Whether to publish DNS records for IPs
            from this subnet. Default is false.
        """

        body = _clean_dict(
            name=name,
            enable_dhcp=enable_dhcp,
            dns_nameservers=dns_nameservers,
            allocation_pools=allocation_pools,
            host_routes=host_routes,
            gateway_ip=gateway_ip,
            segment_id=segment_id,
            service_types=service_types,
            dns_publish_fixed_ip=dns_publish_fixed_ip,
            description=description
        )

        if not body:
            raise TypeError("No updates for a subnet.")

        resp = self.client.update_subnet(subnet_id, {"subnet": body})["subnet"]
        return resp

    @atomic.action_timer("neutron.delete_subnet")
    def delete_subnet(self, subnet_id):
        """Delete subnet

        :param subnet_id: Subnet ID
        """
        self.client.delete_subnet(subnet_id)

    @atomic.action_timer("neutron.list_subnets")
    def list_subnets(self, network_id=_NONE, **filters):
        """List subnets.

        :param network_id: Filter the subnet list result by the ID of the
            network to which the subnet belongs.
        :param filters: additional subnet list filters
        """
        if network_id:
            filters["network_id"] = network_id
        return self.client.list_subnets(**filters)["subnets"]

    @atomic.action_timer("neutron.create_router")
    def create_router(self, project_id=_NONE, admin_state_up=_NONE,
                      description=_NONE, discover_external_gw=False,
                      external_gateway_info=_NONE, distributed=_NONE, ha=_NONE,
                      availability_zone_hints=_NONE, service_type_id=_NONE,
                      flavor_id=_NONE, enable_snat=_NONE):
        """Create router.

        :param project_id: The ID of the project that owns the resource. Only
            administrative and users with advsvc role can specify a project ID
            other than their own. You cannot change this value through
            authorization policies.
        :param admin_state_up: The administrative state of the resource, which
            is up (true) or down (false). Default is true.
        :param description: A human-readable description for the resource.
        :param discover_external_gw: Take one of available external networks
            and use it as external gateway. The parameter can not be used in
            combination of external_gateway_info parameter.
        :param external_gateway_info: The external gateway information of
            the router. If the router has an external gateway, this would be
            a dict with network_id, enable_snat and external_fixed_ips.
        :param distributed: true indicates a distributed router. It is
            available when dvr extension is enabled.
        :param ha: true indicates a highly-available router. It is available
            when l3-ha extension is enabled.
        :param availability_zone_hints: The availability zone candidates for
            the router. It is available when router_availability_zone extension
            is enabled.
        :param service_type_id: The ID of the service type associated with
            the router.
        :param flavor_id: The ID of the flavor associated with the router.
        :param enable_snat: Whether to include `enable_snat: True` to
            external_gateway_info or not. By default, it is enabled if a user
            is admin and "ext-gw-mode" extension presents
        """

        if external_gateway_info is _NONE and discover_external_gw:
            for external_network in self.list_networks(router_external=True):
                external_gateway_info = {"network_id": external_network["id"]}
                if enable_snat is _NONE:
                    permission = self._clients.credential.permission
                    is_admin = permission == consts.EndpointPermission.ADMIN
                    if (self.supports_extension("ext-gw-mode", silent=True)
                            and is_admin):
                        external_gateway_info["enable_snat"] = True
                elif enable_snat:
                    external_gateway_info["enable_snat"] = True
                break

        body = _clean_dict(
            name=self.generate_random_name(),
            # tenant_id should work for both new and old neutron instances
            tenant_id=project_id,
            external_gateway_info=external_gateway_info,
            description=description,
            distributed=distributed,
            ha=ha,
            availability_zone_hints=availability_zone_hints,
            service_type_id=service_type_id,
            flavor_id=flavor_id,
            admin_state_up=admin_state_up
        )

        resp = self.client.create_router({"router": body})
        return resp["router"]

    @atomic.action_timer("neutron.show_router")
    def get_router(self, router_id, fields=_NONE):
        """Get router details

        :param router_id: Router ID
        :param fields: The fields that you want the server to return. If no
            fields list is specified, the networking API returns all
            attributes allowed by the policy settings. By using fields
            parameter, the API returns only the requested set of attributes.
        """
        body = _clean_dict(fields=fields)
        return self.client.show_router(router_id, **body)["router"]

    @atomic.action_timer("neutron.add_interface_router")
    def add_interface_to_router(self, router_id, subnet_id=_NONE,
                                port_id=_NONE):
        """Add interface to router.

        :param router_id: The ID of the router.
        :param subnet_id: The ID of the subnet. One of subnet_id or port_id
            must be specified.
        :param port_id: The ID of the port. One of subnet_id or port_id must
            be specified.
        """
        if (subnet_id and port_id) or (not subnet_id and not port_id):
            raise TypeError("One of subnet_id or port_id must be specified "
                            "while adding interface to router.")
        body = _clean_dict(subnet_id=subnet_id, port_id=port_id)
        return self.client.add_interface_router(router_id, body)

    @atomic.action_timer("neutron.remove_interface_router")
    def remove_interface_from_router(self, router_id, subnet_id=_NONE,
                                     port_id=_NONE):
        """Remove interface from router

        :param router_id: The ID of the router.
        :param subnet_id: The ID of the subnet. One of subnet_id or port_id
            must be specified.
        :param port_id: The ID of the port. One of subnet_id or port_id must
            be specified.
        """
        from neutronclient.common import exceptions as neutron_exceptions

        if (subnet_id and port_id) or (not subnet_id and not port_id):
            raise TypeError("One of subnet_id or port_id must be specified "
                            "to remove interface from router.")

        body = _clean_dict(subnet_id=subnet_id, port_id=port_id)

        try:
            self.client.remove_interface_router(router_id, body)
        except (neutron_exceptions.BadRequest,
                neutron_exceptions.NotFound):
            # Some neutron plugins don't use router as
            # the device ID. Also, some plugin doesn't allow
            # to update the ha router interface as there is
            # an internal logic to update the interface/data model
            # instead.
            LOG.exception("Failed to remove an interface from a router.")

    @atomic.action_timer("neutron.add_gateway_router")
    def add_gateway_to_router(self, router_id, network_id, enable_snat=None,
                              external_fixed_ips=None):
        """Adds an external network gateway to the specified router.

        :param router_id: Router ID
        :param enable_snat: whether SNAT should occur on the external gateway
            or not
        """
        gw_info = {"network_id": network_id}
        if enable_snat is not None:
            if self.supports_extension("ext-gw-mode", silent=True):
                gw_info["enable_snat"] = enable_snat
        if external_fixed_ips is not None:
            gw_info["external_fixed_ips"] = external_fixed_ips
        self.client.add_gateway_router(router_id, gw_info)

    @atomic.action_timer("neutron.remove_gateway_router")
    def remove_gateway_from_router(self, router_id):
        """Removes an external network gateway from the specified router.

        :param router_id: Router ID
        """
        self.client.remove_gateway_router(router_id)

    @atomic.action_timer("neutron.update_router")
    def update_router(self, router_id, name=_NONE, admin_state_up=_NONE,
                      description=_NONE, external_gateway_info=_NONE,
                      distributed=_NONE, ha=_NONE):
        """Update router.

        :param router_id: The ID of the router to update.
        :param name: Human-readable name of the resource.
        :param admin_state_up: The administrative state of the resource, which
            is up (true) or down (false). Default is true.
        :param description: A human-readable description for the resource.
        :param external_gateway_info: The external gateway information of
            the router. If the router has an external gateway, this would be
            a dict with network_id, enable_snat and external_fixed_ips.
        :param distributed: true indicates a distributed router. It is
            available when dvr extension is enabled.
        :param ha: true indicates a highly-available router. It is available
            when l3-ha extension is enabled.
        """
        body = _clean_dict(
            name=name,
            external_gateway_info=external_gateway_info,
            description=description,
            distributed=distributed,
            ha=ha,
            admin_state_up=admin_state_up
        )

        if not body:
            raise TypeError("No updates for a router.")

        return self.client.update_router(router_id, {"router": body})["router"]

    @atomic.action_timer("neutron.delete_router")
    def delete_router(self, router_id):
        """Delete router

        :param router_id: Router ID
        """
        self.client.delete_router(router_id)

    @staticmethod
    def _filter_routers(routers, subnet_ids):
        for router in routers:
            gtw_info = router["external_gateway_info"]
            if gtw_info is None:
                continue
            if any(fixed_ip["subnet_id"] in subnet_ids
                   for fixed_ip in gtw_info["external_fixed_ips"]):
                yield router

    @atomic.action_timer("neutron.list_routers")
    def list_routers(self, subnet_ids=_NONE, **kwargs):
        """List routers.

        :param subnet_ids: Filter routers by attached subnet(s). Can be a
            string or and an array with strings.
        :param kwargs: additional router list filters
        """
        routers = self.client.list_routers(**kwargs)["routers"]
        if subnet_ids != _NONE:
            routers = list(self._filter_routers(routers,
                                                subnet_ids=subnet_ids))
        return routers

    @atomic.action_timer("neutron.create_port")
    def create_port(self, network_id, **kwargs):
        """Create neutron port.

        :param network_id: neutron network dict
        :param kwargs: other optional neutron port creation params
            (name is restricted param)
        :returns: neutron port dict
        """
        kwargs["name"] = self.generate_random_name()
        body = _clean_dict(
            network_id=network_id,
            **kwargs
        )
        return self.client.create_port({"port": body})["port"]

    @atomic.action_timer("neutron.show_port")
    def get_port(self, port_id, fields=_NONE):
        """Get port details

        :param port_id: Port ID
        :param fields: The fields that you want the server to return. If no
            fields list is specified, the networking API returns all
            attributes allowed by the policy settings. By using fields
            parameter, the API returns only the requested set of attributes.
        """
        body = _clean_dict(fields=fields)
        return self.client.show_port(port_id, **body)["port"]

    @atomic.action_timer("neutron.update_port")
    def update_port(self, port_id, **kwargs):
        """Update neutron port.

        :param port_id: The ID of the port to update.
        :param kwargs: other optional neutron port creation params
            (name is restricted param)
        :returns: neutron port dict
        """
        body = _clean_dict(**kwargs)
        if not body:
            raise TypeError("No updates for a port.")
        return self.client.update_port(port_id, {"port": body})["port"]

    ROUTER_INTERFACE_OWNERS = ("network:router_interface",
                               "network:router_interface_distributed",
                               "network:ha_router_replicated_interface")

    ROUTER_GATEWAY_OWNER = "network:router_gateway"

    @atomic.action_timer("neutron.delete_port")
    def delete_port(self, port):
        """Delete port.

        :param port: Port ID or object
        :returns bool: False if neutron returns NotFound error on port delete
        """

        from neutronclient.common import exceptions as neutron_exceptions

        if not isinstance(port, dict):
            port = {"id": port, "device_owner": False}

        if (port["device_owner"] in self.ROUTER_INTERFACE_OWNERS
                or port["device_owner"] == self.ROUTER_GATEWAY_OWNER):

            if port["device_owner"] == self.ROUTER_GATEWAY_OWNER:
                self.remove_gateway_from_router(port["device_id"])

            self.remove_interface_from_router(
                router_id=port["device_id"], port_id=port["id"])
        else:
            try:
                self.client.delete_port(port["id"])
            except neutron_exceptions.PortNotFoundClient:
                # port is auto-removed
                return False
        return True

    @atomic.action_timer("neutron.list_ports")
    def list_ports(self, network_id=_NONE, device_id=_NONE, device_owner=_NONE,
                   status=_NONE, **kwargs):
        """List ports.

        :param network_id: Filter the list result by the ID of the attached
            network.
        :param device_id: Filter the port list result by the ID of the device
            that uses this port. For example, a server instance or a logical
            router.
        :param device_owner: Filter the port result list by the entity type
            that uses this port. For example, compute:nova (server instance),
            network:dhcp (DHCP agent) or network:router_interface
            (router interface).
        :param status: Filter the port list result by the port status.
            Values are ACTIVE, DOWN, BUILD and ERROR.
        :param kwargs: additional port list filters
        """
        filters = _clean_dict(
            network_id=network_id,
            device_id=device_id,
            device_owner=device_owner,
            status=status,
            **kwargs
        )
        return self.client.list_ports(**filters)["ports"]

    @atomic.action_timer("neutron.create_floating_ip")
    def create_floatingip(self, floating_network=None, project_id=_NONE,
                          fixed_ip_address=_NONE, floating_ip_address=_NONE,
                          port_id=_NONE, subnet_id=_NONE, dns_domain=_NONE,
                          dns_name=_NONE):
        """Create floating IP with floating_network.

        :param floating_network: external network associated with floating IP.
        :param project_id: The ID of the project.
        :param fixed_ip_address: The fixed IP address that is associated with
            the floating IP. If an internal port has multiple associated IP
            addresses, the service chooses the first IP address unless you
            explicitly define a fixed IP address in the fixed_ip_address
            parameter.
        :param floating_ip_address: The floating IP address. Default policy
            settings enable only administrative users to set floating IP
            addresses and some non-administrative users might require a
            floating IP address. If you do not specify a floating IP address
            in the request, the operation automatically allocates one.
        :param port_id: The ID of a port associated with the floating IP.
            To associate the floating IP with a fixed IP at creation time,
            you must specify the identifier of the internal port.
        :param subnet_id: The subnet ID on which you want to create the
            floating IP.
        :param dns_domain: A valid DNS domain.
        :param dns_name: A valid DNS name.
        """

        from neutronclient.common import exceptions as neutron_exceptions

        if isinstance(floating_network, dict):
            net_id = floating_network["id"]
        elif floating_network:
            net_id = self.find_network(floating_network, external=True)["id"]
        else:
            ext_networks = self.list_networks(router_external=True)
            if not ext_networks:
                raise exceptions.NotFoundException(
                    "Failed to allocate floating IP since no external "
                    "networks found.")
            net_id = ext_networks[0]["id"]

        description = _NONE
        api_info = self._clients.credential.api_info.get("neutron", {})
        if (not api_info.get("pre_newton", False)
                and not CONF.openstack.pre_newton_neutron):
            description = self.generate_random_name()

        body = _clean_dict(
            tenant_id=project_id,
            description=description,
            floating_network_id=net_id,
            fixed_ip_address=fixed_ip_address,
            floating_ip_address=floating_ip_address,
            port_id=port_id,
            subnet_id=subnet_id,
            dns_domain=dns_domain,
            dns_name=dns_name
        )

        try:
            resp = self.client.create_floatingip({"floatingip": body})
            return resp["floatingip"]
        except neutron_exceptions.BadRequest as e:
            error = "%s" % e
            if "Unrecognized attribute" in error and "'description'" in error:
                LOG.info("It looks like you have Neutron API of pre-Newton "
                         "OpenStack release. Setting "
                         "openstack.pre_newton_neutron option via Rally "
                         "configuration should fix an issue.")
            raise

    @atomic.action_timer("neutron.show_floating_ip")
    def get_floatingip(self, floatingip_id, fields=_NONE):
        """Get floating IP details

        :param floatingip_id: Floating IP ID
        :param fields: The fields that you want the server to return. If no
            fields list is specified, the networking API returns all
            attributes allowed by the policy settings. By using fields
            parameter, the API returns only the requested set of attributes.
        """
        body = _clean_dict(fields=fields)
        resp = self.client.show_floatingip(floatingip_id, **body)
        return resp["floatingip"]

    @atomic.action_timer("neutron.update_floating_ip")
    def update_floatingip(self, floating_ip_id, fixed_ip_address=_NONE,
                          port_id=_NONE, description=_NONE):
        """Update floating IP.

        :param floating_ip_id: The ID of the floating IP to update.
        :param fixed_ip_address: The fixed IP address that is associated with
            the floating IP. If an internal port has multiple associated IP
            addresses, the service chooses the first IP address unless you
            explicitly define a fixed IP address in the fixed_ip_address
            parameter.
        :param port_id: The ID of a port associated with the floating IP.
            To associate the floating IP with a fixed IP at creation time,
            you must specify the identifier of the internal port.
        :param description: A human-readable description for the resource.
            Default is an empty string.
        """

        body = _clean_dict(
            description=description,
            fixed_ip_address=fixed_ip_address,
            port_id=port_id
        )

        if not body:
            raise TypeError("No updates for a floating ip.")

        return self.client.update_floatingip(
            floating_ip_id, {"floatingip": body})["floatingip"]

    @atomic.action_timer("neutron.delete_floating_ip")
    def delete_floatingip(self, floatingip_id):
        """Delete floating IP.

        :param floatingip_id: floating IP id
        """
        self.client.delete_floatingip(floatingip_id)

    @atomic.action_timer("neutron.associate_floating_ip")
    def associate_floatingip(self, port_id=None, device_id=None,
                             floatingip_id=None, floating_ip_address=None,
                             fixed_ip_address=None):
        """Add floating IP to an instance

        :param port_id: ID of the port to associate floating IP with
        :param device_id: ID of the device to find port to use
        :param floatingip_id: ID of the floating IP
        :param floating_ip_address: IP address to find floating IP to use
        :param fixed_ip_address: The fixed IP address to associate with the
            floating ip
        """
        if (device_id is None and port_id is None) or (device_id and port_id):
            raise TypeError("One of device_id or port_id must be specified.")

        if ((floating_ip_address is None and floatingip_id is None)
                or (floating_ip_address and floatingip_id)):
            raise TypeError("One of floating_ip_address or floatingip_id "
                            "must be specified.")

        if port_id is None:
            ports = self.list_ports(device_id=device_id)
            if not ports:
                raise exceptions.GetResourceFailure(
                    resource="port",
                    err=f"device '{device_id}' have no ports associated.")
            port_id = ports[0]["id"]

        if floatingip_id is None:
            filtered_fips = self.list_floatingips(
                floating_ip_address=floating_ip_address)
            if not filtered_fips:
                raise exceptions.GetResourceFailure(
                    resource="floating ip",
                    err=f"There is no floating ip with '{floating_ip_address}'"
                        f" address.")

            floatingip_id = filtered_fips[0]["id"]

        additional = {}
        if fixed_ip_address:
            additional["fixed_ip_address"] = fixed_ip_address
        return self.update_floatingip(floatingip_id, port_id=port_id,
                                      **additional)

    @atomic.action_timer("neutron.dissociate_floating_ip")
    def dissociate_floatingip(self, floatingip_id=None,
                              floating_ip_address=None):
        """Remove floating IP from an instance

        :param floatingip_id: ID of the floating IP
        :param floating_ip_address: IP address to find floating IP to use
        """
        if ((floating_ip_address is None and floatingip_id is None)
                or (floating_ip_address and floatingip_id)):
            raise TypeError("One of floating_ip_address or floatingip_id "
                            "must be specified.")

        if floatingip_id is None:
            filtered_fips = self.list_floatingips(
                floating_ip_address=floating_ip_address)
            if not filtered_fips:
                raise exceptions.GetResourceFailure(
                    resource="floating ip",
                    err=f"There is no floating ip with '{floating_ip_address}'"
                        f" address.")

            floatingip_id = filtered_fips[0]["id"]

        return self.update_floatingip(floatingip_id, port_id=None)

    @atomic.action_timer("neutron.list_floating_ips")
    def list_floatingips(self, router_id=_NONE, port_id=_NONE, status=_NONE,
                         description=_NONE, floating_network_id=_NONE,
                         floating_ip_address=_NONE, fixed_ip_address=_NONE,
                         **kwargs):
        """List floating IPs.

        :param router_id: Filter the floating IP list result by the ID of the
            router for the floating IP.
        :param port_id: Filter the floating IP list result by the ID of a port
            associated with the floating IP.
        :param status: Filter the floating IP list result by the status of the
            floating IP. Values are ACTIVE, DOWN and ERROR.
        :param description: Filter the list result by the human-readable
            description of the resource. (available only for OpenStack Newton+)
        :param floating_network_id: Filter the floating IP list result by the
            ID of the network associated with the floating IP.
        :param fixed_ip_address: Filter the floating IP list result by the
            fixed IP address that is associated with the floating IP address.
        :param floating_ip_address: Filter the floating IP list result by the
            floating IP address.
        :param kwargs: additional floating IP list filters
        """
        filters = _clean_dict(
            router_id=router_id,
            port_id=port_id,
            status=status,
            description=description,
            floating_network_id=floating_network_id,
            floating_ip_address=floating_ip_address,
            fixed_ip_address=fixed_ip_address,
            **kwargs
        )
        resp = self.client.list_floatingips(**filters)
        return resp["floatingips"]

    @atomic.action_timer("neutron.create_security_group")
    def create_security_group(self, name=None, project_id=_NONE,
                              description=_NONE, stateful=_NONE):
        """Create a security group

        :param name: Human-readable name of the resource.
        :param project_id: The ID of the project.
        :param description: A human-readable description for the resource.
            Default is an empty string.
        :param stateful: Indicates if the security group is stateful or
            stateless.
        """
        body = _clean_dict(
            name=name or self.generate_random_name(),
            tenant_id=project_id,
            description=description,
            stateful=stateful
        )
        resp = self.client.create_security_group({"security_group": body})
        return resp["security_group"]

    @atomic.action_timer("neutron.show_security_group")
    def get_security_group(self, security_group_id, fields=_NONE):
        """Get security group

        :param security_group_id: Security group ID
        :param fields: The fields that you want the server to return. If no
            fields list is specified, the networking API returns all
            attributes allowed by the policy settings. By using fields
            parameter, the API returns only the requested set of attributes.
        """
        body = _clean_dict(fields=fields)
        resp = self.client.show_security_group(security_group_id, **body)
        return resp["security_group"]

    @atomic.action_timer("neutron.update_security_group")
    def update_security_group(self, security_group_id, name=_NONE,
                              description=_NONE, stateful=_NONE):
        """Update a security group

        :param security_group_id: Security group ID
        :param name: Human-readable name of the resource.
        :param description: A human-readable description for the resource.
            Default is an empty string.
        :param stateful: Indicates if the security group is stateful or
            stateless.
        """
        body = _clean_dict(
            name=name,
            description=description,
            stateful=stateful
        )
        if not body:
            raise TypeError("No updates for a security group.")

        resp = self.client.update_security_group(security_group_id,
                                                 {"security_group": body})
        return resp["security_group"]

    @atomic.action_timer("neutron.delete_security_group")
    def delete_security_group(self, security_group_id):
        """Delete security group.

        :param security_group_id: Security group ID
        """
        return self.client.delete_security_group(security_group_id)

    @atomic.action_timer("neutron.list_security_groups")
    def list_security_groups(self, name=_NONE, **kwargs):
        """List security groups.

        :param name: Filter the list result by the human-readable name of the
        resource.
        :param kwargs: additional security group list filters
        """
        if name:
            kwargs["name"] = name
        resp = self.client.list_security_groups(**kwargs)
        return resp["security_groups"]

    @atomic.action_timer("neutron.create_security_group_rule")
    def create_security_group_rule(self,
                                   security_group_id,
                                   direction="ingress",
                                   protocol="tcp",
                                   ethertype=_NONE,
                                   port_range_min=_NONE,
                                   port_range_max=_NONE,
                                   remote_ip_prefix=_NONE,
                                   description=_NONE):
        """Create security group rule.

        :param security_group_id: The security group ID to associate with this
            security group rule.
        :param direction: Ingress or egress, which is the direction in which
            the security group rule is applied.
        :param protocol: The IP protocol can be represented by a string, an
            integer, or null. Valid string or integer values are any or 0, ah
            or 51, dccp or 33, egp or 8, esp or 50, gre or 47, icmp or 1,
            icmpv6 or 58, igmp or 2, ipip or 4, ipv6-encap or 41,
            ipv6-frag or 44, ipv6-icmp or 58, ipv6-nonxt or 59,
            ipv6-opts or 60, ipv6-route or 43, ospf or 89, pgm or 113,
            rsvp or 46, sctp or 132, tcp or 6, udp or 17, udplite or 136,
            vrrp or 112. Additionally, any integer value between [0-255] is
            also valid. The string any (or integer 0) means all IP protocols.
            See the constants in neutron_lib.constants for the most
            up-to-date list of supported strings.
        :param ethertype: Must be IPv4 or IPv6, and addresses represented in
            CIDR must match the ingress or egress rules.
        :param port_range_min: The minimum port number in the range that is
            matched by the security group rule. If the protocol is TCP, UDP,
            DCCP, SCTP or UDP-Lite this value must be less than or equal to
            the port_range_max attribute value. If the protocol is ICMP, this
            value must be an ICMP type.
        :param port_range_max: The maximum port number in the range that is
            matched by the security group rule. If the protocol is TCP, UDP,
            DCCP, SCTP or UDP-Lite this value must be greater than or equal to
            the port_range_min attribute value. If the protocol is ICMP, this
            value must be an ICMP code.
        :param remote_ip_prefix: The remote IP prefix that is matched by this
            security group rule.
        :param description: A human-readable description for the resource.
            Default is an empty string.
        """
        body = _clean_dict(
            security_group_id=security_group_id,
            direction=direction,
            protocol=protocol,
            ethertype=ethertype,
            port_range_min=port_range_min,
            port_range_max=port_range_max,
            remote_ip_prefix=remote_ip_prefix,
            description=description
        )
        return self.client.create_security_group_rule(
            {"security_group_rule": body})["security_group_rule"]

    @atomic.action_timer("neutron.show_security_group_rule")
    def get_security_group_rule(self, security_group_rule_id, verbose=_NONE,
                                fields=_NONE):
        """Get security group details

        :param security_group_rule_id: Security group rule ID
        :param verbose: Show detailed information.
        :param fields: The fields that you want the server to return. If no
            fields list is specified, the networking API returns all
            attributes allowed by the policy settings. By using fields
            parameter, the API returns only the requested set of attributes.
        """
        body = _clean_dict(verbose=verbose, fields=fields)
        resp = self.client.show_security_group_rule(
            security_group_rule_id, **body)
        return resp["security_group_rule"]

    @atomic.action_timer("neutron.delete_security_group_rule")
    def delete_security_group_rule(self, security_group_rule_id):
        """Delete a given security group rule.

        :param security_group_rule_id: Security group rule ID
        """
        self.client.delete_security_group_rule(
            security_group_rule_id)

    @atomic.action_timer("neutron.list_security_group_rules")
    def list_security_group_rules(
            self, security_group_id=_NONE, protocol=_NONE, direction=_NONE,
            port_range_min=_NONE, port_range_max=_NONE, description=_NONE,
            **kwargs):
        """List all security group rules.

        :param security_group_id: Filter the security group rule list result
            by the ID of the security group that associates with this security
            group rule.
        :param protocol: Filter the security group rule list result by the IP
            protocol.
        :param direction: Filter the security group rule list result by the
            direction in which the security group rule is applied, which is
            ingress or egress.
        :param port_range_min: Filter the security group rule list result by
            the minimum port number in the range that is matched by the
            security group rule.
        :param port_range_max: Filter the security group rule list result by
            the maximum port number in the range that is matched by the
            security group rule.
        :param description:  Filter the list result by the human-readable
            description of the resource.
        :param kwargs: additional security group rule list filters
        :return: list of security group rules
        """
        filters = _clean_dict(
            security_group_id=security_group_id,
            protocol=protocol,
            direction=direction,
            port_range_min=port_range_min,
            port_range_max=port_range_max,
            description=description,
            **kwargs
        )
        resp = self.client.list_security_group_rules(**filters)
        return resp["security_group_rules"]

    @atomic.action_timer("neutron.list_agents")
    def list_agents(self, **kwargs):
        """Fetches agents.

        :param kwargs: filters
        :returns: user agents list
        """
        return self.client.list_agents(**kwargs)["agents"]

    @atomic.action_timer("neutron.list_extension")
    def list_extensions(self):
        """List neutron extensions."""
        return self.client.list_extensions()["extensions"]

    @property
    def cached_supported_extensions(self):
        """Return cached list of extension if exist or fetch it if is missed"""
        if self._cached_supported_extensions is None:
            self._cached_supported_extensions = self.list_extensions()
        return self._cached_supported_extensions

    def supports_extension(self, extension, silent=False):
        """Check whether a neutron extension is supported.

        :param extension: Extension to check
        :param silent: Return boolean result of the search instead of raising
            an exception
        """
        exist = any(ext.get("alias") == extension
                    for ext in self.cached_supported_extensions)
        if not silent and not exist:
            raise exceptions.NotFoundException(
                message=f"Neutron driver does not support {extension}")

        return exist
