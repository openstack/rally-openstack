# Copyright 2015 Mirantis Inc.
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

from unittest import mock

import ddt

from rally import exceptions
from rally_openstack.task.scenarios.manila import shares
from tests.unit import test


@ddt.ddt
class ManilaSharesTestCase(test.ScenarioTestCase):

    @ddt.data(
        {"share_proto": "nfs", "size": 3},
        {"share_proto": "cifs", "size": 4,
         "share_network": "foo", "share_type": "bar"},
    )
    def test_create_and_delete_share(self, params):
        fake_share = mock.MagicMock()
        scenario = shares.CreateAndDeleteShare(self.context)
        scenario._create_share = mock.MagicMock(return_value=fake_share)
        scenario.sleep_between = mock.MagicMock()
        scenario._delete_share = mock.MagicMock()

        scenario.run(min_sleep=3, max_sleep=4, **params)

        scenario._create_share.assert_called_once_with(**params)
        scenario.sleep_between.assert_called_once_with(3, 4)
        scenario._delete_share.assert_called_once_with(fake_share)

    def create_env(self, scenario):
        fake_share = mock.MagicMock()
        scenario = shares.CreateShareAndAccessFromVM(self.context)
        self.ip = {"id": "foo_id", "ip": "foo_ip", "is_floating": True}
        scenario._boot_server_with_fip = mock.Mock(
            return_value=("foo_server", self.ip))
        scenario._delete_server_with_fip = mock.Mock()
        scenario._run_command = mock.MagicMock(
            return_value=(0, "{\"foo\": 42}", "foo_err"))
        scenario.add_output = mock.Mock()
        self.context.update({"user": {"keypair": {"name": "keypair_name"},
                                      "credential": mock.MagicMock()}})
        scenario._create_share = mock.MagicMock(return_value=fake_share)
        scenario._delete_share = mock.MagicMock()
        scenario._export_location = mock.MagicMock(return_value="fake")
        scenario._allow_access_share = mock.MagicMock()

        return scenario, fake_share

    @ddt.data(
        {"image": "some_image",
         "flavor": "m1.small", "username": "chuck norris"}
    )
    @mock.patch("rally.task.utils.get_from_manager")
    @mock.patch("rally.task.utils.wait_for_status")
    def test_create_share_and_access_from_vm(
            self,
            params,
            mock_rally_task_utils_wait_for_status,
            mock_rally_task_utils_get_from_manager):
        scenario, fake_share = self.create_env(
            shares.CreateShareAndAccessFromVM(self.context))
        scenario.run(**params)

        scenario._create_share.assert_called_once_with(
            share_proto="nfs", size=1)
        scenario._delete_share.assert_called_once_with(fake_share)
        scenario._allow_access_share.assert_called_once_with(
            fake_share, "ip", "foo_ip", "rw")
        scenario._export_location.assert_called_once_with(fake_share)
        scenario._boot_server_with_fip.assert_called_once_with(
            "some_image", "m1.small", use_floating_ip=True,
            floating_network=None, key_name="keypair_name",
            userdata="#cloud-config\npackages:\n - nfs-common")
        mock_rally_task_utils_wait_for_status.assert_called_once_with(
            "foo_server", ready_statuses=["ACTIVE"], update_resource=mock.ANY)
        scenario._delete_server_with_fip.assert_called_once_with(
            "foo_server", {"id": "foo_id", "ip": "foo_ip",
                           "is_floating": True},
            force_delete=False)
        scenario.add_output.assert_called_with(
            complete={"chart_plugin": "TextArea",
                      "data": [
                          "foo_err"],
                      "title": "Script StdErr"})

    @ddt.data(
        {"image": "some_image",
         "flavor": "m1.small", "username": "chuck norris"}
    )
    @mock.patch("rally.task.utils.get_from_manager")
    @mock.patch("rally.task.utils.wait_for_status")
    def test_create_share_and_access_from_vm_command_timeout(
            self,
            params,
            mock_rally_task_utils_wait_for_status,
            mock_rally_task_utils_get_from_manager):
        scenario, fake_share = self.create_env(
            shares.CreateShareAndAccessFromVM(self.context))

        scenario._run_command.side_effect = exceptions.SSHTimeout()
        self.assertRaises(exceptions.SSHTimeout,
                          scenario.run,
                          "foo_flavor", "foo_image", "foo_interpreter",
                          "foo_script", "foo_username")
        scenario._delete_server_with_fip.assert_called_once_with(
            "foo_server", self.ip, force_delete=False)
        self.assertFalse(scenario.add_output.called)
        scenario._delete_share.assert_called_once_with(fake_share)

    @ddt.data(
        {"image": "some_image",
         "flavor": "m1.small", "username": "chuck norris"}
    )
    @mock.patch("rally.task.utils.get_from_manager")
    @mock.patch("rally.task.utils.wait_for_status")
    def test_create_share_and_access_from_vm_wait_timeout(
            self,
            params,
            mock_rally_task_utils_wait_for_status,
            mock_rally_task_utils_get_from_manager):
        scenario, fake_share = self.create_env(
            shares.CreateShareAndAccessFromVM(self.context))

        mock_rally_task_utils_wait_for_status.side_effect = \
            exceptions.TimeoutException(
                resource_type="foo_resource",
                resource_name="foo_name",
                resource_id="foo_id",
                desired_status="foo_desired_status",
                resource_status="foo_resource_status",
                timeout=2)
        self.assertRaises(exceptions.TimeoutException,
                          scenario.run,
                          "foo_flavor", "foo_image", "foo_interpreter",
                          "foo_script", "foo_username")
        scenario._delete_server_with_fip.assert_called_once_with(
            "foo_server", self.ip, force_delete=False)
        self.assertFalse(scenario.add_output.called)
        scenario._delete_share.assert_called_once_with(fake_share)

    @ddt.data(
        {"output": (0, "", ""),
         "expected": [{"complete": {"chart_plugin": "TextArea",
                                    "data": [""],
                                    "title": "Script StdOut"}}]},
        {"output": (1, "x y z", "error message"),
         "raises": exceptions.ScriptError},
        {"output": (0, "[1, 2, 3, 4]", ""), "expected": []}
    )
    @ddt.unpack
    def test_create_share_and_access_from_vm_add_output(self, output,
                                                        expected=None,
                                                        raises=None):
        scenario, fake_share = self.create_env(
            shares.CreateShareAndAccessFromVM(self.context))

        scenario._run_command.return_value = output
        kwargs = {"flavor": "foo_flavor",
                  "image": "foo_image",
                  "username": "foo_username",
                  "password": "foo_password",
                  "use_floating_ip": "use_fip",
                  "floating_network": "ext_network",
                  "force_delete": "foo_force"}
        if raises:
            self.assertRaises(raises, scenario.run, **kwargs)
            self.assertFalse(scenario.add_output.called)
        else:
            scenario.run(**kwargs)
            calls = [mock.call(**kw) for kw in expected]
            scenario.add_output.assert_has_calls(calls, any_order=True)

            scenario._create_share.assert_called_once_with(
                share_proto="nfs", size=1)
            scenario._delete_share.assert_called_once_with(fake_share)
            scenario._allow_access_share.assert_called_once_with(
                fake_share, "ip", "foo_ip", "rw")
            scenario._export_location.assert_called_once_with(fake_share)
            scenario._boot_server_with_fip.assert_called_once_with(
                "foo_image", "foo_flavor", use_floating_ip="use_fip",
                floating_network="ext_network", key_name="keypair_name",
                userdata="#cloud-config\npackages:\n - nfs-common")
            scenario._delete_server_with_fip.assert_called_once_with(
                "foo_server",
                {"id": "foo_id", "ip": "foo_ip", "is_floating": True},
                force_delete="foo_force")

    @ddt.data(
        {},
        {"detailed": True},
        {"detailed": False},
        {"search_opts": None},
        {"search_opts": {}},
        {"search_opts": {"foo": "bar"}},
        {"detailed": True, "search_opts": None},
        {"detailed": False, "search_opts": None},
        {"detailed": True, "search_opts": {"foo": "bar"}},
        {"detailed": False, "search_opts": {"quuz": "foo"}},
    )
    @ddt.unpack
    def test_list_shares(self, detailed=True, search_opts=None):
        scenario = shares.ListShares(self.context)
        scenario._list_shares = mock.MagicMock()

        scenario.run(detailed=detailed, search_opts=search_opts)

        scenario._list_shares.assert_called_once_with(
            detailed=detailed, search_opts=search_opts)

    @ddt.data(
        {"params": {"share_proto": "nfs"}, "new_size": 4},
        {
            "params": {
                "share_proto": "cifs",
                "size": 4,
                "snapshot_id": "snapshot_foo",
                "description": "foo_description",
                "metadata": {"foo_metadata": "foo"},
                "share_network": "foo_network",
                "share_type": "foo_type",
                "is_public": True,
                "availability_zone": "foo_avz",
                "share_group_id": "foo_group_id"
            },
            "new_size": 8
        }
    )
    @ddt.unpack
    def test_create_and_extend_shares(self, params, new_size):
        size = params.get("size", 1)
        share_group_id = params.get("share_group_id", None)
        snapshot_id = params.get("snapshot_id", None)
        description = params.get("description", None)
        metadata = params.get("metadata", None)
        share_network = params.get("share_network", None)
        share_type = params.get("share_type", None)
        is_public = params.get("is_public", False)
        availability_zone = params.get("availability_zone", None)

        fake_share = mock.MagicMock()
        scenario = shares.CreateAndExtendShare(self.context)
        scenario._create_share = mock.MagicMock(return_value=fake_share)
        scenario._extend_share = mock.MagicMock()

        scenario.run(new_size=new_size, **params)

        scenario._create_share.assert_called_with(
            share_proto=params["share_proto"],
            size=size,
            snapshot_id=snapshot_id,
            description=description,
            metadata=metadata,
            share_network=share_network,
            share_type=share_type,
            is_public=is_public,
            availability_zone=availability_zone,
            share_group_id=share_group_id
        )
        scenario._extend_share.assert_called_with(fake_share, new_size)

    @ddt.data(
        {"params": {"share_proto": "nfs"}, "new_size": 4},
        {
            "params": {
                "share_proto": "cifs",
                "size": 4,
                "snapshot_id": "snapshot_foo",
                "description": "foo_description",
                "metadata": {"foo_metadata": "foo"},
                "share_network": "foo_network",
                "share_type": "foo_type",
                "is_public": True,
                "availability_zone": "foo_avz",
                "share_group_id": "foo_group_id"
            },
            "new_size": 8
        }
    )
    @ddt.unpack
    def test_create_and_shrink_shares(self, params, new_size):
        size = params.get("size", 2)
        share_group_id = params.get("share_group_id", None)
        snapshot_id = params.get("snapshot_id", None)
        description = params.get("description", None)
        metadata = params.get("metadata", None)
        share_network = params.get("share_network", None)
        share_type = params.get("share_type", None)
        is_public = params.get("is_public", False)
        availability_zone = params.get("availability_zone", None)

        fake_share = mock.MagicMock()
        scenario = shares.CreateAndShrinkShare(self.context)
        scenario._create_share = mock.MagicMock(return_value=fake_share)
        scenario._shrink_share = mock.MagicMock()

        scenario.run(new_size=new_size, **params)

        scenario._create_share.assert_called_with(
            share_proto=params["share_proto"],
            size=size,
            snapshot_id=snapshot_id,
            description=description,
            metadata=metadata,
            share_network=share_network,
            share_type=share_type,
            is_public=is_public,
            availability_zone=availability_zone,
            share_group_id=share_group_id
        )
        scenario._shrink_share.assert_called_with(fake_share, new_size)

    @ddt.data(
        {
            "share_proto": "nfs",
            "size": 3,
            "access": "127.0.0.1",
            "access_type": "ip"
        },
        {
            "access": "1.2.3.4",
            "access_type": "ip",
            "access_level": "ro",
            "share_proto": "cifs",
            "size": 4,
            "snapshot_id": "snapshot_foo",
            "description": "foo_description",
            "metadata": {"foo_metadata": "foo"},
            "share_network": "foo_network",
            "share_type": "foo_type",
            "is_public": True,
            "availability_zone": "foo_avz",
            "share_group_id": "foo_group_id"
        }
    )
    def test_create_share_and_allow_and_deny_access(self, params):
        access = params["access"]
        access_type = params["access_type"]
        access_level = params.get("access_level", "rw")
        size = params.get("size", 1)
        share_group_id = params.get("share_group_id", None)
        snapshot_id = params.get("snapshot_id", None)
        description = params.get("description", None)
        metadata = params.get("metadata", None)
        share_network = params.get("share_network", None)
        share_type = params.get("share_type", None)
        is_public = params.get("is_public", False)
        availability_zone = params.get("availability_zone", None)
        fake_share = mock.MagicMock()
        fake_access = {"id": "foo"}

        scenario = shares.CreateShareThenAllowAndDenyAccess(self.context)
        scenario._create_share = mock.MagicMock(return_value=fake_share)
        scenario._allow_access_share = mock.MagicMock(return_value=fake_access)
        scenario._deny_access_share = mock.MagicMock()

        scenario.run(**params)

        scenario._create_share.assert_called_with(
            share_proto=params["share_proto"],
            size=size,
            snapshot_id=snapshot_id,
            description=description,
            metadata=metadata,
            share_network=share_network,
            share_type=share_type,
            is_public=is_public,
            availability_zone=availability_zone,
            share_group_id=share_group_id
        )
        scenario._allow_access_share.assert_called_with(
            fake_share, access_type, access, access_level)
        scenario._deny_access_share.assert_called_with(
            fake_share, fake_access["id"])

    @ddt.data(
        {},
        {"description": "foo_description"},
        {"neutron_net_id": "foo_neutron_net_id"},
        {"neutron_subnet_id": "foo_neutron_subnet_id"},
        {"nova_net_id": "foo_nova_net_id"},
        {"description": "foo_description",
         "neutron_net_id": "foo_neutron_net_id",
         "neutron_subnet_id": "foo_neutron_subnet_id",
         "nova_net_id": "foo_nova_net_id"},
    )
    def test_create_share_network_and_delete(self, params):
        fake_sn = mock.MagicMock()
        scenario = shares.CreateShareNetworkAndDelete(self.context)
        scenario._create_share_network = mock.MagicMock(return_value=fake_sn)
        scenario._delete_share_network = mock.MagicMock()
        expected_params = {
            "description": None,
            "neutron_net_id": None,
            "neutron_subnet_id": None,
            "nova_net_id": None,
        }
        expected_params.update(params)

        scenario.run(**params)

        scenario._create_share_network.assert_called_once_with(
            **expected_params)
        scenario._delete_share_network.assert_called_once_with(fake_sn)

    @ddt.data(
        {},
        {"description": "foo_description"},
        {"neutron_net_id": "foo_neutron_net_id"},
        {"neutron_subnet_id": "foo_neutron_subnet_id"},
        {"nova_net_id": "foo_nova_net_id"},
        {"description": "foo_description",
         "neutron_net_id": "foo_neutron_net_id",
         "neutron_subnet_id": "foo_neutron_subnet_id",
         "nova_net_id": "foo_nova_net_id"},
    )
    def test_create_share_network_and_list(self, params):
        scenario = shares.CreateShareNetworkAndList(self.context)
        fake_network = mock.Mock()
        scenario._create_share_network = mock.Mock(
            return_value=fake_network)
        scenario._list_share_networks = mock.Mock(
            return_value=[fake_network,
                          mock.Mock(),
                          mock.Mock()])
        expected_create_params = {
            "description": params.get("description"),
            "neutron_net_id": params.get("neutron_net_id"),
            "neutron_subnet_id": params.get("neutron_subnet_id"),
            "nova_net_id": params.get("nova_net_id"),
        }
        expected_list_params = {
            "detailed": params.get("detailed", True),
            "search_opts": params.get("search_opts"),
        }
        expected_create_params.update(params)

        scenario.run(**params)

        scenario._create_share_network.assert_called_once_with(
            **expected_create_params)
        scenario._list_share_networks.assert_called_once_with(
            **expected_list_params)

    @ddt.data(
        {},
        {"search_opts": None},
        {"search_opts": {}},
        {"search_opts": {"foo": "bar"}},
    )
    def test_list_share_servers(self, search_opts):
        scenario = shares.ListShareServers(self.context)
        scenario.context = {"admin": {"credential": "fake_credential"}}
        scenario._list_share_servers = mock.MagicMock()

        scenario.run(search_opts=search_opts)

        scenario._list_share_servers.assert_called_once_with(
            search_opts=search_opts)

    @ddt.data(
        {"security_service_type": "fake_type"},
        {"security_service_type": "fake_type",
         "dns_ip": "fake_dns_ip",
         "server": "fake_server",
         "domain": "fake_domain",
         "user": "fake_user",
         "password": "fake_password",
         "description": "fake_description"},
    )
    def test_create_security_service_and_delete(self, params):
        fake_ss = mock.MagicMock()
        scenario = shares.CreateSecurityServiceAndDelete(self.context)
        scenario._create_security_service = mock.MagicMock(
            return_value=fake_ss)
        scenario._delete_security_service = mock.MagicMock()
        expected_params = {
            "security_service_type": params.get("security_service_type"),
            "dns_ip": params.get("dns_ip"),
            "server": params.get("server"),
            "domain": params.get("domain"),
            "user": params.get("user"),
            "password": params.get("password"),
            "description": params.get("description"),
        }

        scenario.run(**params)

        scenario._create_security_service.assert_called_once_with(
            **expected_params)
        scenario._delete_security_service.assert_called_once_with(fake_ss)

    @ddt.data("ldap", "kerberos", "active_directory")
    def test_attach_security_service_to_share_network(self,
                                                      security_service_type):
        scenario = shares.AttachSecurityServiceToShareNetwork(self.context)
        scenario._create_share_network = mock.MagicMock()
        scenario._create_security_service = mock.MagicMock()
        scenario._add_security_service_to_share_network = mock.MagicMock()

        scenario.run(security_service_type=security_service_type)

        scenario._create_share_network.assert_called_once_with()
        scenario._create_security_service.assert_called_once_with(
            security_service_type=security_service_type)
        scenario._add_security_service_to_share_network.assert_has_calls([
            mock.call(scenario._create_share_network.return_value,
                      scenario._create_security_service.return_value)])

    @ddt.data(
        {"share_proto": "nfs", "size": 3, "detailed": True},
        {"share_proto": "cifs", "size": 4, "detailed": False,
         "share_network": "foo", "share_type": "bar"},
    )
    def test_create_and_list_share(self, params):
        scenario = shares.CreateAndListShare()
        scenario._create_share = mock.MagicMock()
        scenario.sleep_between = mock.MagicMock()
        scenario._list_shares = mock.MagicMock()

        scenario.run(min_sleep=3, max_sleep=4, **params)

        detailed = params.pop("detailed")
        scenario._create_share.assert_called_once_with(**params)
        scenario.sleep_between.assert_called_once_with(3, 4)
        scenario._list_shares.assert_called_once_with(detailed=detailed)

    @ddt.data(
        ({}, 0, 0),
        ({}, 1, 1),
        ({}, 2, 2),
        ({}, 3, 0),
        ({"sets": 5, "set_size": 8, "delete_size": 10}, 1, 1),
    )
    @ddt.unpack
    def test_set_and_delete_metadata(self, params, iteration, share_number):
        scenario = shares.SetAndDeleteMetadata()
        share_list = [{"id": "fake_share_%s_id" % d} for d in range(3)]
        scenario.context = {"tenant": {"shares": share_list}}
        scenario.context["iteration"] = iteration
        scenario._set_metadata = mock.MagicMock()
        scenario._delete_metadata = mock.MagicMock()
        expected_set_params = {
            "share": share_list[share_number],
            "sets": params.get("sets", 10),
            "set_size": params.get("set_size", 3),
            "key_min_length": params.get("key_min_length", 1),
            "key_max_length": params.get("key_max_length", 256),
            "value_min_length": params.get("value_min_length", 1),
            "value_max_length": params.get("value_max_length", 1024),
        }

        scenario.run(**params)

        scenario._set_metadata.assert_called_once_with(**expected_set_params)
        scenario._delete_metadata.assert_called_once_with(
            share=share_list[share_number],
            keys=scenario._set_metadata.return_value,
            delete_size=params.get("delete_size", 3),
        )
