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

import netaddr

from rally.common import logging
from rally.common import utils


LOG = logging.getLogger(__name__)


_IPv4_START_CIDR = "10.2.0.0/24"
_IPv6_START_CIDR = "dead:beaf::/64"

_IPv4_CIDR_INCR = utils.RAMInt()
_IPv6_CIDR_INCR = utils.RAMInt()


def get_ip_version(ip):
    return netaddr.IPNetwork(ip).version


def generate_cidr(ip_version=None, start_cidr=None):
    """Generate next CIDR for network or subnet, without IP overlapping.

    This is process and thread safe, because `cidr_incr' points to
    value stored directly in RAM. This guarantees that CIDRs will be
    serial and unique even under hard multiprocessing/threading load.

    :param ip_version: version of IP to take default value for start_cidr
    :param start_cidr: start CIDR str
    """
    if start_cidr is None:
        if ip_version == 6:
            start_cidr = _IPv6_START_CIDR
        else:
            start_cidr = _IPv4_START_CIDR

    ip_version = get_ip_version(start_cidr)
    if ip_version == 4:
        cidr = str(netaddr.IPNetwork(start_cidr).next(next(_IPv4_CIDR_INCR)))
    else:
        cidr = str(netaddr.IPNetwork(start_cidr).next(next(_IPv6_CIDR_INCR)))
    LOG.debug("CIDR generated: %s" % cidr)
    return ip_version, cidr
