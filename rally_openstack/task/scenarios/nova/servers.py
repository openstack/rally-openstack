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

import typing as t

import jsonschema

from rally import exceptions as rally_exceptions
from rally.common import logging
from rally.task import types
from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.common.services.storage import block
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.cinder import utils as cinder_utils
from rally_openstack.task.scenarios.neutron import utils as neutron_utils
from rally_openstack.task.scenarios.nova import utils


"""Scenarios for Nova servers."""


LOG = logging.getLogger(__name__)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_list_server",
                    platform="openstack")
class BootAndListServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        detailed: bool = True,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server from an image and then list all servers.

        Measure the "nova list" command performance.

        If you have only 1 user in your context, you will
        add 1 server on every iteration. So you will have more
        and more servers and will be able to measure the
        performance of the "nova list" command depending on
        the number of servers owned by users.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param detailed: True if the server listing should contain
                         detailed information about all of them
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        msg = ("Servers isn't created")
        self.assertTrue(server, err_msg=msg)

        pool_list = self._list_servers(detailed)
        msg = ("Server not included into list of available servers\n"
               f"Booted server: {server}\n"
               f"Pool of servers: {pool_list}")
        self.assertIn(server, pool_list, err_msg=msg)


@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="NovaServers.list_servers", platform="openstack")
class ListServers(utils.NovaScenario):

    def run(self, detailed: bool = True) -> None:
        """List all servers.

        This simple scenario test the nova list command by listing
        all the servers.

        :param detailed: True if detailed information about servers
                         should be listed
        """
        self._list_servers(detailed)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_delete_server",
                    platform="openstack")
class BootAndDeleteServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Boot and delete a server.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between volume creation and deletion
        (of random duration from [min_sleep, max_sleep]).

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_delete_multiple_servers",
                    platform="openstack")
class BootAndDeleteMultipleServers(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        count: t.Annotated[int, scenario.Field(ge=1)] = 2,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Boot multiple servers in a single request and delete them.

        Deletion is done in parallel with one request per server, not
        with a single request for all servers.

        :param image: The image to boot from
        :param flavor: Flavor used to boot instance
        :param count: Number of instances to boot
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for instance creation
        """
        servers = self._boot_servers(image, flavor, 1, instances_amount=count,
                                     **kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self._delete_servers(servers, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image", validate_disk=False)
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova", "cinder"]},
                    name="NovaServers.boot_server_from_volume_and_delete",
                    platform="openstack")
class BootServerFromVolumeAndDelete(utils.NovaScenario,
                                    cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        volume_type: str | None = None,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        force_delete: bool = False,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server from volume and then delete it.

        The scenario first creates a volume and then a server.
        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between volume creation and deletion
        (of random duration from [min_sleep, max_sleep]).

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param volume_size: volume size (in GB)
        :param volume_type: specifies volume type when there are
                            multiple backends
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param force_delete: True if force_delete should be used
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        :param kwargs: Optional additional arguments for server creation
                       (deprecated)
        """
        boot_server_kwargs = boot_server_kwargs or kwargs
        create_volume_kwargs = create_volume_kwargs or {}

        volume = self.cinder.create_volume(volume_size, imageRef=image,
                                           volume_type=volume_type,
                                           **create_volume_kwargs)
        block_device_mapping = {"vda": "%s:::0" % volume.id}
        server = self._boot_server(None, flavor,
                                   block_device_mapping=block_device_mapping,
                                   **boot_server_kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_bounce_server",
                    platform="openstack")
class BootAndBounceServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        force_delete: bool = False,
        actions: list[dict[str, int]] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server and run specified actions against it.

        Actions should be passed into the actions parameter. Available actions
        are 'hard_reboot', 'soft_reboot', 'stop_start', 'rescue_unrescue',
        'pause_unpause', 'suspend_resume', 'lock_unlock' and 'shelve_unshelve'.
        Delete server after all actions were completed.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param force_delete: True if force_delete should be used
        :param actions: list of action dictionaries, where each action
                        dictionary speicifes an action to be performed
                        in the following format:
                        {"action_name": <no_of_iterations>}
        :param kwargs: Optional additional arguments for server creation
        """
        action_builder = self._bind_actions()
        actions = actions or []
        try:
            action_builder.validate(actions)
        except jsonschema.exceptions.ValidationError as error:
            raise rally_exceptions.InvalidConfigException(
                "Invalid server actions configuration '%(actions)s' due to: "
                "%(error)s" % {"actions": str(actions), "error": str(error)})
        server = self._boot_server(image, flavor, **kwargs)
        for action in action_builder.build_actions(actions, server):
            action()
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_lock_unlock_and_delete",
                    platform="openstack")
class BootLockUnlockAndDelete(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server, lock it, then unlock and delete it.

        Optional 'min_sleep' and 'max_sleep' parameters allow the
        scenario to simulate a pause between locking and unlocking the
        server (of random duration from min_sleep to max_sleep).

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param min_sleep: Minimum sleep time between locking and unlocking
                          in seconds
        :param max_sleep: Maximum sleep time between locking and unlocking
                          in seconds
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._lock_server(server)
        self.sleep_between(min_sleep, max_sleep)
        self._unlock_server(server)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova", "glance"]},
                    name="NovaServers.snapshot_server",
                    platform="openstack")
class SnapshotServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server, make its snapshot and delete both.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """

        server = self._boot_server(image, flavor, **kwargs)
        image = self._create_image(server)
        self._delete_server(server, force=force_delete)

        server = self._boot_server(image.id, flavor, **kwargs)
        self._delete_server(server, force=force_delete)
        self._delete_image(image)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_server",
                    platform="openstack")
class BootServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        auto_assign_nic: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server.

        Assumes that cleanup is done elsewhere.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param auto_assign_nic: True if NICs should be assigned
        :param kwargs: Optional additional arguments for server creation
        """
        self._boot_server(image, flavor,
                          auto_assign_nic=auto_assign_nic, **kwargs)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image", validate_disk=False)
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova", "cinder"]},
                    name="NovaServers.boot_server_from_volume",
                    platform="openstack")
class BootServerFromVolume(utils.NovaScenario, cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        volume_type: str | None = None,
        auto_assign_nic: bool = False,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server from volume.

        The scenario first creates a volume and then a server.
        Assumes that cleanup is done elsewhere.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param volume_size: volume size (in GB)
        :param volume_type: specifies volume type when there are
                            multiple backends
        :param auto_assign_nic: True if NICs should be assigned
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        :param kwargs: Optional additional arguments for server creation
                       (deprecated)
        """

        boot_server_kwargs = boot_server_kwargs or kwargs
        create_volume_kwargs = create_volume_kwargs or {}

        volume = self.cinder.create_volume(volume_size, imageRef=image,
                                           volume_type=volume_type,
                                           **create_volume_kwargs)
        block_device_mapping = {"vda": "%s:::0" % volume.id}
        self._boot_server(None, flavor, auto_assign_nic=auto_assign_nic,
                          block_device_mapping=block_device_mapping,
                          **boot_server_kwargs)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=(consts.Service.NOVA))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.resize_server", platform="openstack")
class ResizeServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        to_flavor: t.Annotated[str, types.Convert("nova_flavor")],
        confirm: bool = True,
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server, then resize and delete it.

        This test will confirm the resize by default,
        or revert the resize if confirm is set to false.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param to_flavor: flavor to be used to resize the booted instance
        :param confirm: perform resize confirm action right after requesting
            a resize. If False, resize revert action will be performed.
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._resize(server, to_flavor)
        if confirm:
            self._resize_confirm(server)
        else:
            self._resize_revert(server)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.resize_shutoff_server",
                    platform="openstack")
class ResizeShutoffServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        to_flavor: t.Annotated[str, types.Convert("nova_flavor")],
        confirm: bool = True,
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server and stop it, then resize and delete it.

        This test will confirm the resize by default,
        or revert the resize if confirm is set to false.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param to_flavor: flavor to be used to resize the booted instance
        :param confirm: True if need to confirm resize else revert resize
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._stop_server(server)
        self._resize(server, to_flavor)

        if confirm:
            self._resize_confirm(server, "SHUTOFF")
        else:
            self._resize_revert(server, "SHUTOFF")
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["cinder", "nova"]},
    name="NovaServers.boot_server_attach_created_volume_and_resize",
    platform="openstack")
class BootServerAttachCreatedVolumeAndResize(utils.NovaScenario,
                                             cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        to_flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        force_delete: bool = False,
        confirm: bool = True,
        do_delete: bool = True,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        create_volume_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Create a VM from image, attach a volume to it and resize.

        Simple test to create a VM and attach a volume, then resize the VM,
        detach the volume then delete volume and VM.
        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between attaching a volume and running resize
        (of random duration from range [min_sleep, max_sleep]).
        :param image: Glance image name to use for the VM
        :param flavor: VM flavor name
        :param to_flavor: flavor to be used to resize the booted instance
        :param volume_size: volume size (in GB)
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param force_delete: True if force_delete should be used
        :param confirm: True if need to confirm resize else revert resize
        :param do_delete: True if resources needs to be deleted explicitly
                        else use rally cleanup to remove resources
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        """
        boot_server_kwargs = boot_server_kwargs or {}
        create_volume_kwargs = create_volume_kwargs or {}

        server = self._boot_server(image, flavor, **boot_server_kwargs)
        volume = self.cinder.create_volume(volume_size, **create_volume_kwargs)

        self._attach_volume(server, volume)
        self.sleep_between(min_sleep, max_sleep)
        self._resize(server, to_flavor)

        if confirm:
            self._resize_confirm(server)
        else:
            self._resize_revert(server)

        if do_delete:
            self._detach_volume(server, volume)
            self.cinder.delete_volume(volume)
            self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["cinder", "nova"]},
    name="NovaServers.boot_server_attach_created_volume_and_extend",
    platform="openstack")
class BootServerAttachCreatedVolumeAndExtend(utils.NovaScenario,
                                             cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        new_volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        force_delete: bool = False,
        do_delete: bool = True,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        create_volume_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Create a VM from image, attach a volume then extend volume

        Simple test to create a VM and attach a volume, then extend the
        volume while its running, detach the volume then delete volume
        and VM.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between attaching a volume and running resize
        (of random duration from range [min_sleep, max_sleep]).

        :param image: Glance image name to use for the VM
        :param flavor: VM flavor name
        :param volume_size: volume size (in GB)
        :param new_volume_size: new volume size (in GB)
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param force_delete: True if force_delete should be used
        :param do_delete: True if resources needs to be deleted explicitly
                        else use rally cleanup to remove resources
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        """
        boot_server_kwargs = boot_server_kwargs or {}
        create_volume_kwargs = create_volume_kwargs or {}

        server = self._boot_server(image, flavor, **boot_server_kwargs)
        volume = self.cinder.create_volume(volume_size, **create_volume_kwargs)

        self._attach_volume(server, volume)
        self.sleep_between(min_sleep, max_sleep)
        self.cinder.extend_volume(volume, new_size=new_volume_size)

        if do_delete:
            self._detach_volume(server, volume)
            self.cinder.delete_volume(volume)
            self._delete_server(server, force=force_delete)


@validation.add("number", param_name="volume_num", minval=1,
                integer_only=True)
@validation.add("number", param_name="volume_size", minval=1,
                integer_only=True)
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image", validate_disk=False)
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    context={"cleanup@openstack": ["cinder", "nova"]},
    name="NovaServers.boot_server_attach_volume_and_list_attachments",
    platform="openstack")
class BootServerAttachVolumeAndListAttachments(utils.NovaScenario,
                                               cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec = 1,
        volume_num: t.Annotated[int, scenario.Field(ge=1)] = 2,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        create_volume_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Create a VM, attach N volume to it and list server's attachemnt.

        Measure the "nova volume-attachments" command performance.

        :param image: Glance image name to use for the VM
        :param flavor: VM flavor name
        :param volume_size: volume size (in GB), default 1G
        :param volume_num: the num of attached volume
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        """
        boot_server_kwargs = boot_server_kwargs or {}
        create_volume_kwargs = create_volume_kwargs or {}

        server = self._boot_server(image, flavor, **boot_server_kwargs)
        attachments = []
        for i in range(volume_num):
            volume = self.cinder.create_volume(volume_size,
                                               **create_volume_kwargs)
            attachments.append(self._attach_volume(server, volume))

        list_attachments = self._list_attachments(server.id)

        for attachment in attachments:
            msg = ("attachment not included into list of available "
                   f"attachments\n attachment: {attachment}\n"
                   f"list attachments: {list_attachments}")
            self.assertIn(attachment, list_attachments, err_msg=msg)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image", validate_disk=False)
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova", "cinder"]},
                    name="NovaServers.boot_server_from_volume_and_resize",
                    platform="openstack")
class BootServerFromVolumeAndResize(utils.NovaScenario,
                                    cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        to_flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        force_delete: bool = False,
        confirm: bool = True,
        do_delete: bool = True,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        create_volume_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Boot a server from volume, then resize and delete it.

        The scenario first creates a volume and then a server.
        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between volume creation and deletion
        (of random duration from [min_sleep, max_sleep]).

        This test will confirm the resize by default,
        or revert the resize if confirm is set to false.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param to_flavor: flavor to be used to resize the booted instance
        :param volume_size: volume size (in GB)
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param force_delete: True if force_delete should be used
        :param confirm: True if need to confirm resize else revert resize
        :param do_delete: True if resources needs to be deleted explicitly
                        else use rally cleanup to remove resources
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        """
        boot_server_kwargs = boot_server_kwargs or {}
        create_volume_kwargs = create_volume_kwargs or {}

        if boot_server_kwargs.get("block_device_mapping"):
            LOG.warning("Using already existing volume is not permitted.")

        volume = self.cinder.create_volume(volume_size, imageRef=image,
                                           **create_volume_kwargs)
        boot_server_kwargs["block_device_mapping"] = {
            "vda": "%s:::0" % volume.id}

        server = self._boot_server(None, flavor, **boot_server_kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self._resize(server, to_flavor)

        if confirm:
            self._resize_confirm(server)
        else:
            self._resize_revert(server)

        if do_delete:
            self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.suspend_and_resume_server",
                    platform="openstack")
class SuspendAndResumeServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Create a server, suspend, resume and then delete it

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._suspend_server(server)
        self._resume_server(server)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.pause_and_unpause_server",
                    platform="openstack")
class PauseAndUnpauseServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Create a server, pause, unpause and then delete it

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._pause_server(server)
        self._unpause_server(server)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.shelve_and_unshelve_server",
                    platform="openstack")
class ShelveAndUnshelveServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        force_delete: bool = False,
        **kwargs: t.Any,
    ) -> None:
        """Create a server, shelve, unshelve and then delete it

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param force_delete: True if force_delete should be used
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._shelve_server(server)
        self._unshelve_server(server)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_live_migrate_server",
                    platform="openstack")
class BootAndLiveMigrateServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        block_migration: bool = False,
        disk_over_commit: bool = False,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        **kwargs: t.Any,
    ) -> None:
        """Live Migrate a server.

        This scenario launches a VM on a compute node available in
        the availability zone and then migrates the VM to another
        compute node on the same availability zone.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between VM booting and running live migration
        (of random duration from range [min_sleep, max_sleep]).

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param block_migration: Specifies the migration type
        :param disk_over_commit: Specifies whether to allow overcommit
                                 on migrated instance or not
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self.sleep_between(min_sleep, max_sleep)

        self._live_migrate(server, block_migration, disk_over_commit)

        self._delete_server(server)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image", validate_disk=False)
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(
    context={"cleanup@openstack": ["nova", "cinder"]},
    name="NovaServers.boot_server_from_volume_and_live_migrate",
    platform="openstack")
class BootServerFromVolumeAndLiveMigrate(utils.NovaScenario,
                                         cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        volume_type: str | None = None,
        block_migration: bool = False,
        disk_over_commit: bool = False,
        force_delete: bool = False,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server from volume and then migrate it.

        The scenario first creates a volume and a server booted from
        the volume on a compute node available in the availability zone and
        then migrates the VM to another compute node on the same availability
        zone.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between VM booting and running live migration
        (of random duration from range [min_sleep, max_sleep]).

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param volume_size: volume size (in GB)
        :param volume_type: specifies volume type when there are
                            multiple backends
        :param block_migration: Specifies the migration type
        :param disk_over_commit: Specifies whether to allow overcommit
                                 on migrated instance or not
        :param force_delete: True if force_delete should be used
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        :param kwargs: Optional additional arguments for server creation
                       (deprecated)
        """
        boot_server_kwargs = boot_server_kwargs or kwargs
        create_volume_kwargs = create_volume_kwargs or {}

        volume = self.cinder.create_volume(volume_size, imageRef=image,
                                           volume_type=volume_type,
                                           **create_volume_kwargs)
        block_device_mapping = {"vda": "%s:::0" % volume.id}
        server = self._boot_server(None, flavor,
                                   block_device_mapping=block_device_mapping,
                                   **boot_server_kwargs)
        self.sleep_between(min_sleep, max_sleep)

        self._live_migrate(server, block_migration, disk_over_commit)

        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(
    context={"cleanup@openstack": ["cinder", "nova"]},
    name="NovaServers.boot_server_attach_created_volume_and_live_migrate",
    platform="openstack")
class BootServerAttachCreatedVolumeAndLiveMigrate(utils.NovaScenario,
                                                  cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        block_migration: bool = False,
        disk_over_commit: bool = False,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
    ) -> None:
        """Create a VM, attach a volume to it and live migrate.

        Simple test to create a VM and attach a volume, then migrate the VM,
        detach the volume and delete volume/VM.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between attaching a volume and running live
        migration (of random duration from range [min_sleep, max_sleep]).

        :param image: Glance image name to use for the VM
        :param flavor: VM flavor name
        :param size: volume size (in GB)
        :param block_migration: Specifies the migration type
        :param disk_over_commit: Specifies whether to allow overcommit
                                 on migrated instance or not
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        :param min_sleep: Minimum sleep time in seconds
        :param max_sleep: Maximum sleep time in seconds
        """

        if boot_server_kwargs is None:
            boot_server_kwargs = {}
        if create_volume_kwargs is None:
            create_volume_kwargs = {}

        server = self._boot_server(image, flavor, **boot_server_kwargs)
        volume = self.cinder.create_volume(size, **create_volume_kwargs)

        self._attach_volume(server, volume)

        self.sleep_between(min_sleep, max_sleep)

        self._live_migrate(server, block_migration, disk_over_commit)

        self._detach_volume(server, volume)

        self.cinder.delete_volume(volume)
        self._delete_server(server)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_migrate_server",
                    platform="openstack")
class BootAndMigrateServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        **kwargs: t.Any,
    ) -> None:
        """Migrate a server.

        This scenario launches a VM on a compute node available in
        the availability zone, and then migrates the VM
        to another compute node on the same availability zone.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._migrate(server)
        # NOTE(wtakase): This is required because cold migration and resize
        #                share same code path.
        confirm = kwargs.get("confirm", True)
        if confirm:
            self._resize_confirm(server, status="ACTIVE")
        else:
            self._resize_revert(server, status="ACTIVE")
        self._delete_server(server)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="from_image")
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="to_image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack",
                admin=True, users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_rebuild_server",
                    platform="openstack")
class BootAndRebuildServer(utils.NovaScenario):

    def run(
        self,
        from_image: t.Annotated[str, types.Convert("glance_image")],
        to_image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        **kwargs: t.Any,
    ) -> None:
        """Rebuild a server.

        This scenario launches a VM, then rebuilds that VM with a
        different image.

        :param from_image: image to be used to boot an instance
        :param to_image: image to be used to rebuild the instance
        :param flavor: flavor to be used to boot an instance
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(from_image, flavor, **kwargs)
        self._rebuild_server(server, to_image)
        self._delete_server(server)


@logging.log_deprecated_args(
    "Use 'floating_network' for additional instance parameters.",
    "2.1.0", ["create_floating_ip_args"], once=True)
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(
    context={"cleanup@openstack": ["nova", "neutron.floatingip"]},
    name="NovaServers.boot_and_associate_floating_ip",
    platform="openstack")
class BootAndAssociateFloatingIp(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        floating_network: str | None = None,
        create_floating_ip_args: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server and associate a floating IP to it.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param floating_network: external network associated with floating IP.
        :param create_floating_ip_args: Optional additional dict for specifying
            external network associated with floating IP ('ext_network' key).
        :param kwargs: Optional additional arguments for server creation
        """
        if floating_network is None and create_floating_ip_args:
            if "ext_network" in create_floating_ip_args:
                # the old way (network wrapper)
                floating_network = create_floating_ip_args["ext_network"]
            elif "floating_network" in create_floating_ip_args:
                # the semi-old way - the time when network wrapper was replaced
                #   by network service, but this compatibility layer was not
                #   provided
                floating_network = create_floating_ip_args["floating_network"]
        server = self._boot_server(image, flavor, **kwargs)
        floatingip = self.neutron.create_floatingip(
            floating_network=floating_network
        )
        self._associate_floating_ip(server, floatingip)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.NEUTRON])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova", "neutron"]},
                    name="NovaServers.boot_server_and_attach_interface",
                    platform="openstack")
class BootServerAndAttachInterface(  # type: ignore[misc]
        utils.NovaScenario, neutron_utils.NeutronScenario):
    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        network_create_args: dict[str, t.Any] | None = None,
        subnet_create_args: dict[str, t.Any] | None = None,
        subnet_cidr_start: str | None = None,
        boot_server_args: dict[str, t.Any] | None = None,
    ) -> None:
        """Create server and subnet, then attach the interface to it.

        This scenario measures the "nova interface-attach" command performance.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param network_create_args: dict, POST /v2.0/networks request
                                    options.
        :param subnet_create_args: dict, POST /v2.0/subnets request options
        :param subnet_cidr_start: str, start value for subnets CIDR
        :param boot_server_args: Optional additional arguments for
                                 server creation
        """
        network = self._get_or_create_network(network_create_args)
        self._create_subnet(network, subnet_create_args, subnet_cidr_start)

        server = self._boot_server(image, flavor, **(boot_server_args or {}))
        self._attach_interface(server, net_id=network["network"]["id"])


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_show_server",
                    platform="openstack")
class BootAndShowServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        **kwargs: t.Any,
    ) -> None:
        """Show server details.

        This simple scenario tests the nova show command by retrieving
        the server details.
        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param kwargs: Optional additional arguments for server creation

        :returns: Server details
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._show_server(server)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_get_console_output",
                    platform="openstack")
class BootAndGetConsoleOutput(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        length: int | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Get text console output from server.

        This simple scenario tests the nova console-log command by retrieving
        the text console log output.
        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param length: The number of tail log lines you would like to retrieve.
                       None (default value) or -1 means unlimited length.
        :param kwargs: Optional additional arguments for server creation

        :returns: Text console log output for server
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._get_server_console_output(server, length)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_update_server",
                    platform="openstack")
class BootAndUpdateServer(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        description: str | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server, then update its name and description.

        The scenario first creates a server, then update it.
        Assumes that cleanup is done elsewhere.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param description: update the server description
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._update_server(server, description)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova", "cinder"]},
                    name="NovaServers.boot_server_from_volume_snapshot",
                    platform="openstack")
class BootServerFromVolumeSnapshot(utils.NovaScenario,
                                   cinder_utils.CinderBasic):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        volume_type: str | None = None,
        auto_assign_nic: bool = False,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        boot_server_kwargs: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server from a snapshot.

        The scenario first creates a volume and creates a
        snapshot from this volume, then boots a server from
        the created snapshot.
        Assumes that cleanup is done elsewhere.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param volume_size: volume size (in GB)
        :param volume_type: specifies volume type when there are
                            multiple backends
        :param auto_assign_nic: True if NICs should be assigned
        :param boot_server_kwargs: optional arguments for VM creation
        :param create_volume_kwargs: optional arguments for volume creation
        :param kwargs: Optional additional arguments for server creation
                       (deprecated)
        """
        boot_server_kwargs = boot_server_kwargs or kwargs
        create_volume_kwargs = create_volume_kwargs or {}

        volume = self.cinder.create_volume(volume_size, imageRef=image,
                                           volume_type=volume_type,
                                           **create_volume_kwargs)
        snapshot = self.cinder.create_snapshot(volume.id, force=False)
        block_device_mapping = {"vda": "%s:snap::1" % snapshot.id}
        self._boot_server(None, flavor, auto_assign_nic=auto_assign_nic,
                          block_device_mapping=block_device_mapping,
                          **boot_server_kwargs)


@logging.log_deprecated_args(
    "Use 'floating_network' for additional instance parameters.",
    "2.1.0", ["create_floating_ip_args"], once=True)
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(
    context={"cleanup@openstack": ["nova", "neutron.floatingip"]},
    name="NovaServers.boot_server_associate_and_dissociate_floating_ip",
    platform="openstack")
class BootServerAssociateAndDissociateFloatingIP(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        floating_network: str | None = None,
        create_floating_ip_args: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Boot a server associate and dissociate a floating IP from it.

        The scenario first boot a server and create a floating IP. then
        associate the floating IP to the server.Finally dissociate the floating
        IP.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param floating_network: external network associated with floating IP.
        :param create_floating_ip_args: Optional additional dict for specifying
            external network associated with floating IP ('ext_network' key).
        :param kwargs: Optional additional arguments for server creation
        """
        if floating_network is None and create_floating_ip_args:
            if "ext_network" in create_floating_ip_args:
                # the old way (network wrapper)
                floating_network = create_floating_ip_args["ext_network"]
            elif "floating_network" in create_floating_ip_args:
                # the semi-old way - the time when network wrapper was replaced
                #   by network service, but this compatibility layer was not
                #   provided
                floating_network = create_floating_ip_args["floating_network"]
        server = self._boot_server(image, flavor, **kwargs)
        floatingip = self.neutron.create_floatingip(
            floating_network=floating_network
        )
        self._associate_floating_ip(server, floatingip)
        self._dissociate_floating_ip(server, floatingip)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=["network"])
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_server_and_list_interfaces",
                    platform="openstack")
class BootServerAndListInterfaces(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        **kwargs: t.Any,
    ) -> None:
        """Boot a server and list interfaces attached to it.

        Measure the "nova boot" and "nova interface-list" command performance.

        :param image: ID of the image to be used for server creation
        :param flavor: ID of the flavor to be used for server creation
        :param kwargs: Optional arguments for booting the instance
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._list_interfaces(server)


@validation.add(
    "enum", param_name="console_type",
    values=["novnc", "xvpvnc", "spice-html5", "rdp-html5", "serial", "webmks"])
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["nova"]},
                    name="NovaServers.boot_and_get_console_url",
                    platform="openstack")
class BootAndGetConsoleUrl(utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        console_type: str,
        **kwargs: t.Any,
    ) -> None:
        """Retrieve a console url of a server.

        This simple scenario tests retrieving the console url of a server.

        :param image: image to be used to boot an instance
        :param flavor: flavor to be used to boot an instance
        :param console_type: type can be novnc/xvpvnc for protocol vnc;
                             spice-html5 for protocol spice; rdp-html5 for
                             protocol rdp; serial for protocol serial.
                             webmks for protocol mks (since version 2.8).
        :param kwargs: Optional additional arguments for server creation
        """
        server = self._boot_server(image, flavor, **kwargs)
        self._get_console_url_server(server, console_type)
