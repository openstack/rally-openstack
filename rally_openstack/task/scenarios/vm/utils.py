# Copyright 2013: Mirantis Inc.
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

import io
import os.path
import subprocess
import sys

import netaddr

from rally.common import cfg
from rally.common import logging
from rally.task import atomic
from rally.task import utils
from rally.utils import sshutils

from rally_openstack.task.scenarios.nova import utils as nova_utils

LOG = logging.getLogger(__name__)


CONF = cfg.CONF


class Host(object):

    ICMP_UP_STATUS = "ICMP UP"
    ICMP_DOWN_STATUS = "ICMP DOWN"

    name = "ip"

    def __init__(self, ip):
        self.ip = netaddr.IPAddress(ip)
        self.status = self.ICMP_DOWN_STATUS

    @property
    def id(self):
        return self.ip.format()

    @classmethod
    def update_status(cls, server):
        """Check ip address is pingable and update status."""
        ping = "ping" if server.ip.version == 4 else "ping6"
        if sys.platform.startswith("linux"):
            cmd = [ping, "-c1", "-w1", server.ip.format()]
        else:
            cmd = [ping, "-c1", server.ip.format()]

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        proc.wait()
        LOG.debug("Host %s is ICMP %s"
                  % (server.ip.format(), proc.returncode and "down" or "up"))
        if proc.returncode == 0:
            server.status = cls.ICMP_UP_STATUS
        else:
            server.status = cls.ICMP_DOWN_STATUS
        return server

    def __eq__(self, other):
        if not isinstance(other, Host):
            raise TypeError("%s should be an instance of %s" % (
                other, Host.__class__.__name__))
        return self.ip == other.ip and self.status == other.status

    def __ne__(self, other):
        return not self.__eq__(other)


class VMScenario(nova_utils.NovaScenario):
    """Base class for VM scenarios with basic atomic actions.

    VM scenarios are scenarios executed inside some launched VM instance.
    """

    USER_RWX_OTHERS_RX_ACCESS_MODE = 0o755

    RESOURCE_NAME_PREFIX = "rally_vm_"

    @atomic.action_timer("vm.run_command_over_ssh")
    def _run_command_over_ssh(self, ssh, command):
        """Run command inside an instance.

        This is a separate function so that only script execution is timed.

        :param ssh: A SSHClient instance.
        :param command: Dictionary specifying command to execute.
            See `rally info find VMTasks.boot_runcommand_delete' parameter
            `command' docstring for explanation.

        :returns: tuple (exit_status, stdout, stderr)
        """
        cmd, stdin = [], None

        interpreter = command.get("interpreter") or []
        if interpreter:
            if isinstance(interpreter, str):
                interpreter = [interpreter]
            elif type(interpreter) != list:
                raise ValueError("command 'interpreter' value must be str "
                                 "or list type")
            cmd.extend(interpreter)

        remote_path = command.get("remote_path") or []
        if remote_path:
            if isinstance(remote_path, str):
                remote_path = [remote_path]
            elif type(remote_path) != list:
                raise ValueError("command 'remote_path' value must be str "
                                 "or list type")
            cmd.extend(remote_path)
            if command.get("local_path"):
                ssh.put_file(os.path.expanduser(
                    command["local_path"]), remote_path[-1],
                    mode=self.USER_RWX_OTHERS_RX_ACCESS_MODE)

        if command.get("script_file"):
            stdin = open(os.path.expanduser(command["script_file"]), "rb")

        elif command.get("script_inline"):
            stdin = io.StringIO(command["script_inline"])

        cmd.extend(command.get("command_args") or [])

        return ssh.execute(cmd, stdin=stdin)

    def _boot_server_with_fip(self, image, flavor, use_floating_ip=True,
                              floating_network=None, create_floating_ip_args=None, **kwargs):
        """Boot server prepared for SSH actions."""
        kwargs["auto_assign_nic"] = True
        server = self._boot_server(image, flavor, **kwargs)

        if not server.networks:
            raise RuntimeError(
                "Server `%s' is not connected to any network. "
                "Use network context for auto-assigning networks "
                "or provide `nics' argument with specific net-id." %
                server.name)

        if use_floating_ip:
            fip = self._attach_floating_ip(server, floating_network, create_floating_ip_args)
        else:
            internal_network = list(server.networks)[0]
            fip = {"ip": server.addresses[internal_network][0]["addr"]}

        return server, {"ip": fip.get("ip"),
                        "id": fip.get("id"),
                        "is_floating": use_floating_ip}

    def _attach_floating_ip(self, server, floating_network, create_floating_ip_args):
        internal_network = list(server.networks)[0]
        fixed_ip = server.addresses[internal_network][0]["addr"]

        floatingip = None
        if create_floating_ip_args is not None:
            floatingip = self.neutron.create_floatingip(
                floating_network=floating_network, **create_floating_ip_args)
        else:
            floatingip = self.neutron.create_floatingip(
                floating_network=floating_network)
        self._associate_floating_ip(server, floatingip, fixed_address=fixed_ip)

        return {"id": floatingip["id"],
                "ip": floatingip["floating_ip_address"]}

    def _delete_floating_ip(self, server, fip):
        with logging.ExceptionLogger(
                LOG, "Unable to delete IP: %s" % fip["ip"]):
            if self.check_ip_address(fip["ip"])(server):
                self._dissociate_floating_ip(server, fip)
                self.neutron.delete_floatingip(fip["id"])

    def _delete_server_with_fip(self, server, fip, force_delete=False):
        if fip["is_floating"]:
            self._delete_floating_ip(server, fip)
        return self._delete_server(server, force=force_delete)

    @atomic.action_timer("vm.wait_for_ssh")
    def _wait_for_ssh(self, ssh, timeout=120, interval=1):
        ssh.wait(timeout, interval)

    @atomic.action_timer("vm.wait_for_ping")
    def _wait_for_ping(self, server_ip):
        server = Host(server_ip)
        utils.wait_for_status(
            server,
            ready_statuses=[Host.ICMP_UP_STATUS],
            update_resource=Host.update_status,
            timeout=CONF.openstack.vm_ping_timeout,
            check_interval=CONF.openstack.vm_ping_poll_interval
        )

    def _run_command(self, server_ip, port, username, password, command,
                     pkey=None, timeout=120, interval=1):
        """Run command via SSH on server.

        Create SSH connection for server, wait for server to become available
        (there is a delay between server being set to ACTIVE and sshd being
        available). Then call run_command_over_ssh to actually execute the
        command.

        :param server_ip: server ip address
        :param port: ssh port for SSH connection
        :param username: str. ssh username for server
        :param password: Password for SSH authentication
        :param command: Dictionary specifying command to execute.
            See `rally info find VMTasks.boot_runcommand_delete' parameter
            `command' docstring for explanation.
        :param pkey: key for SSH authentication
        :param timeout: wait for ssh timeout. Default is 120 seconds
        :param interval: ssh retry interval. Default is 1 second

        :returns: tuple (exit_status, stdout, stderr)
        """
        pkey = pkey if pkey else self.context["user"]["keypair"]["private"]
        ssh = sshutils.SSH(username, server_ip, port=port,
                           pkey=pkey, password=password)
        try:
            self._wait_for_ssh(ssh, timeout, interval)
            return self._run_command_over_ssh(ssh, command)
        finally:
            try:
                ssh.close()
            except AttributeError:
                pass
