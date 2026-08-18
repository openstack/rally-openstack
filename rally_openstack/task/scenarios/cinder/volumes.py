# Copyright 2013 Huawei Technologies Co.,LTD.
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

import random
import typing as t

from rally import exceptions
from rally.common import logging
from rally.task import atomic
from rally.task import types
from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.common.services.storage import block
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.cinder import utils as cinder_utils
from rally_openstack.task.scenarios.glance import images
from rally_openstack.task.scenarios.nova import utils as nova_utils


LOG = logging.getLogger(__name__)

"""Scenarios for Cinder Volumes."""


@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_list_volume",
                    platform="openstack")
class CreateAndListVolume(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        detailed: bool = True,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Create a volume and list all volumes.

        Measure the "cinder volume-list" command performance.

        If you have only 1 user in your context, you will
        add 1 volume on every iteration. So you will have more
        and more volumes and will be able to measure the
        performance of the "cinder volume-list" command depending on
        the number of images owned by users.

        :param size: volume size, in GB
        :param detailed: determines whether the volume listing should contain
                         detailed information about all of them
        :param image: image to be used to create volume
        :param kwargs: optional args to create a volume
        """
        if image:
            kwargs["imageRef"] = image

        self.cinder.create_volume(size, **kwargs)
        self.cinder.list_volumes(detailed)


@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_get_volume",
                    platform="openstack")
class CreateAndGetVolume(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Create a volume and get the volume.

        Measure the "cinder show" command performance.

        :param size: volume size, in GB
        :param image: image to be used to create volume
        :param kwargs: optional args to create a volume
        """
        if image:
            kwargs["imageRef"] = image

        volume = self.cinder.create_volume(size, **kwargs)
        self.cinder.get_volume(volume.id)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="CinderVolumes.list_volumes",
                    platform="openstack")
class ListVolumes(cinder_utils.CinderBasic):

    def run(
        self,
        detailed: bool = True,
        search_opts: dict[str, t.Any] | None = None,
        marker: str | None = None,
        limit: int | None = None,
        sort: str | list[str] | None = None,
    ) -> None:
        """List all volumes.

        This simple scenario tests the cinder list command by listing
        all the volumes.

        :param detailed: True if detailed information about volumes
                         should be listed
        :param search_opts: Search options to filter out volumes.
        :param marker: Begin returning volumes that appear later in the volume
                       list than that represented by this volume id.(For V2 or
                       higher)
        :param limit: Maximum number of volumes to return.
        :param sort: Sort information, as "key[:dir]" entries: either a
                     comma-separated string or a list of them
        """

        self.cinder.list_volumes(detailed, search_opts=search_opts,
                                 marker=marker, limit=limit, sort=sort)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="CinderVolumes.list_types", platform="openstack")
class ListTypes(cinder_utils.CinderBasic):

    def run(
        self,
        search_opts: dict[str, t.Any] | None = None,
        is_public: bool | None = None,
    ) -> None:
        """List all volume types.

        This simple scenario tests the cinder type-list command by listing
        all the volume types.

        :param search_opts: Options used when search for volume types
        :param is_public: If query public volume type
        """

        self.cinder.list_types(search_opts, is_public=is_public)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="CinderVolumes.list_transfers", platform="openstack")
class ListTransfers(cinder_utils.CinderBasic):

    def run(
        self,
        detailed: bool = True,
        search_opts: dict[str, t.Any] | None = None,
    ) -> None:
        """List all transfers.

        This simple scenario tests the "cinder transfer-list" command by
        listing all the volume transfers.

        :param detailed: If True, detailed information about volume transfer
                         should be listed
        :param search_opts: Search options to filter out volume transfers.
        """

        self.cinder.list_transfers(detailed, search_opts=search_opts)


@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_volume_kwargs")
@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="update_volume_kwargs")
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_update_volume",
                    platform="openstack")
class CreateAndUpdateVolume(cinder_utils.CinderBasic):

    def run(
        self,
        size: int,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        update_volume_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Create a volume and update its name and description.

        :param size: volume size (integer, in GB)
        :param image: image to be used to create volume
        :param create_volume_kwargs: dict, to be used to create volume
        :param update_volume_kwargs: dict, to be used to update volume
               update_volume_kwargs["update_name"]=True, if updating the
               name of volume.
               update_volume_kwargs["description"]="desp", if updating the
               description of volume.
        """
        create_volume_kwargs = create_volume_kwargs or {}
        update_volume_kwargs = update_volume_kwargs or {}
        if image:
            create_volume_kwargs["imageRef"] = image

        if update_volume_kwargs.pop("update_name", False):
            update_volume_kwargs["name"] = self.generate_random_name()

        volume = self.cinder.create_volume(size, **create_volume_kwargs)
        self.cinder.update_volume(volume, **update_volume_kwargs)


@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_delete_volume",
                    platform="openstack")
class CreateAndDeleteVolume(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        **kwargs: t.Any,
    ) -> None:
        """Create and then delete a volume.

        Good for testing a maximal bandwidth of cloud. Optional 'min_sleep'
        and 'max_sleep' parameters allow the scenario to simulate a pause
        between volume creation and deletion (of random duration from
        [min_sleep, max_sleep]).

        :param size: volume size, in GB
        :param image: image to be used to create volume
        :param min_sleep: minimum sleep time between volume creation and
                          deletion (in seconds)
        :param max_sleep: maximum sleep time between volume creation and
                          deletion (in seconds)
        :param kwargs: optional args to create a volume
        """
        if image:
            kwargs["imageRef"] = image

        volume = self.cinder.create_volume(size, **kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self.cinder.delete_volume(volume)


@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_volume",
                    platform="openstack")
class CreateVolume(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Create a volume.

        Good test to check how influence amount of active volumes on
        performance of creating new.

        :param size: volume size, in GB
        :param image: image to be used to create volume
        :param kwargs: optional args to create a volume
        """
        if image:
            kwargs["imageRef"] = image

        self.cinder.create_volume(size, **kwargs)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts", contexts=("volumes"))
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.modify_volume_metadata",
                    platform="openstack")
class ModifyVolumeMetadata(cinder_utils.CinderBasic):

    def run(
        self,
        sets: t.Annotated[int, scenario.Field(ge=0)] = 10,
        set_size: t.Annotated[int, scenario.Field(ge=0)] = 3,
        deletes: t.Annotated[int, scenario.Field(ge=0)] = 5,
        delete_size: t.Annotated[int, scenario.Field(ge=0)] = 3,
    ) -> None:
        """Modify a volume's metadata.

        This requires a volume to be created with the volumes
        context. Additionally, ``sets * set_size`` must be greater
        than or equal to ``deletes * delete_size``.

        :param sets: how many set_metadata operations to perform
        :param set_size: number of metadata keys to set in each
                         set_metadata operation
        :param deletes: how many delete_metadata operations to perform
        :param delete_size: number of metadata keys to delete in each
                            delete_metadata operation
        """
        if sets * set_size < deletes * delete_size:
            raise exceptions.InvalidArgumentsException(
                "Not enough metadata keys will be created: "
                "Setting %(num_keys)s keys, but deleting %(num_deletes)s" %
                {"num_keys": sets * set_size,
                 "num_deletes": deletes * delete_size})

        volume = random.choice(self.context["tenant"]["volumes"])
        keys = self.cinder.set_metadata(volume["id"], sets=sets,
                                        set_size=set_size)
        self.cinder.delete_metadata(volume["id"], keys=keys,
                                    deletes=deletes,
                                    delete_size=delete_size)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_extend_volume",
                    platform="openstack")
class CreateAndExtendVolume(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        new_size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        **kwargs: t.Any,
    ) -> None:
        """Create and extend a volume and then delete it.


        :param size: volume size, in GB
        :param new_size: size to extend the volume to, in GB.
                         Notice: should be bigger volume size
        :param min_sleep: minimum sleep time between volume extension and
                          deletion (in seconds)
        :param max_sleep: maximum sleep time between volume extension and
                          deletion (in seconds)
        :param kwargs: optional args to extend the volume
        """
        volume = self.cinder.create_volume(size, **kwargs)
        self.cinder.extend_volume(volume, new_size=new_size)
        self.sleep_between(min_sleep, max_sleep)
        self.cinder.delete_volume(volume)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("required_contexts", contexts=("volumes"))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_from_volume_and_delete_volume",
                    platform="openstack")
class CreateFromVolumeAndDeleteVolume(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        **kwargs: t.Any,
    ) -> None:
        """Create volume from volume and then delete it.

        Scenario for testing volume clone.Optional 'min_sleep' and 'max_sleep'
        parameters allow the scenario to simulate a pause between volume
        creation and deletion (of random duration from [min_sleep, max_sleep]).

        :param size: volume size, in GB.
                     Should be equal or bigger source volume size

        :param min_sleep: minimum sleep time between volume creation and
                          deletion (in seconds)
        :param max_sleep: maximum sleep time between volume creation and
                          deletion (in seconds)
        :param kwargs: optional args to create a volume
        """
        source_vol = random.choice(self.context["tenant"]["volumes"])
        volume = self.cinder.create_volume(size, source_volid=source_vol["id"],
                                           **kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self.cinder.delete_volume(volume)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("required_contexts", contexts=("volumes"))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_delete_snapshot",
                    platform="openstack")
class CreateAndDeleteSnapshot(cinder_utils.CinderBasic):

    def run(
        self,
        force: bool = False,
        min_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        max_sleep: t.Annotated[float, scenario.Field(ge=0)] = 0,
        **kwargs: t.Any,
    ) -> None:
        """Create and then delete a volume-snapshot.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between snapshot creation and deletion
        (of random duration from [min_sleep, max_sleep]).

        :param force: when set to True, allows snapshot of a volume when
                      the volume is attached to an instance
        :param min_sleep: minimum sleep time between snapshot creation and
                          deletion (in seconds)
        :param max_sleep: maximum sleep time between snapshot creation and
                          deletion (in seconds)
        :param kwargs: optional args to create a snapshot
        """
        volume = random.choice(self.context["tenant"]["volumes"])
        snapshot = self.cinder.create_snapshot(volume["id"], force=force,
                                               **kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self.cinder.delete_snapshot(snapshot)


@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_volume_params")
@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder", "nova"]},
                    name="CinderVolumes.create_and_attach_volume",
                    platform="openstack")
class CreateAndAttachVolume(cinder_utils.CinderBasic,
                            nova_utils.NovaScenario):

    @logging.log_deprecated_args(
        "Use 'create_vm_params' for additional instance parameters.",
        "0.2.0", ["kwargs"], once=True)
    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        create_volume_params: dict[str, t.Any] | None = None,
        force_delete: bool = False,
        create_vm_params: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Create a VM and attach a volume to it.

        Simple test to create a VM and attach a volume, then
        detach the volume and delete volume/VM.

        :param size: volume size, in GB
        :param image: Glance image name to use for the VM
        :param flavor: VM flavor name
        :param create_volume_params: optional arguments for volume creation
        :param create_vm_params: optional arguments for VM creation
        :param force_delete: True if force_delete should be used
        :param kwargs: (deprecated) optional arguments for VM creation
        """

        create_volume_params = create_volume_params or {}

        if kwargs and create_vm_params:
            raise ValueError("You can not set both 'kwargs' "
                             "and 'create_vm_params' attributes."
                             "Please use 'create_vm_params'.")

        create_vm_params = create_vm_params or kwargs or {}

        server = self._boot_server(image, flavor, **create_vm_params)
        volume = self.cinder.create_volume(size, **create_volume_params)

        self._attach_volume(server, volume)
        self._detach_volume(server, volume)

        self.cinder.delete_volume(volume)
        self._delete_server(server, force=force_delete)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_vm_params")
@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("volume_type_exists", param_name="volume_type", nullable=True)
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder", "nova"]},
                    name="CinderVolumes.create_snapshot_and_attach_volume",
                    platform="openstack")
class CreateSnapshotAndAttachVolume(cinder_utils.CinderBasic,
                                    nova_utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        volume_type: str | None = None,
        size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec | None = None,
        create_vm_params: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Create vm, volume, snapshot and attach/detach volume.

        :param image: Glance image name to use for the VM
        :param flavor: VM flavor name
        :param volume_type: Name of volume type to use
        :param size: volume size, in GB.
                     default values: {"min": 1, "max": 5}
        :param create_vm_params: optional arguments for VM creation
        :param kwargs: Optional parameters used during volume
                       snapshot creation.
        """
        if size is None:
            size = {"min": 1, "max": 5}

        volume = self.cinder.create_volume(size, volume_type=volume_type)
        snapshot = self.cinder.create_snapshot(volume.id, force=False,
                                               **kwargs)
        create_vm_params = create_vm_params or {}

        server = self._boot_server(image, flavor, **create_vm_params)

        self._attach_volume(server, volume)
        self._detach_volume(server, volume)

        self.cinder.delete_snapshot(snapshot)
        self.cinder.delete_volume(volume)
        self._delete_server(server)


@validation.add("image_valid_on_flavor", flavor_param="flavor",
                image_param="image")
@validation.add("required_services", services=[consts.Service.NOVA,
                                               consts.Service.CINDER])
@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_volume_kwargs")
@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_snapshot_kwargs")
@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_vm_params")
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder", "nova"]},
                    name="CinderVolumes.create_nested_snapshots"
                         "_and_attach_volume",
                    platform="openstack")
class CreateNestedSnapshotsAndAttachVolume(cinder_utils.CinderBasic,
                                           nova_utils.NovaScenario):

    def run(
        self,
        image: t.Annotated[str, types.Convert("glance_image")],
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        size: t.Annotated[
            int, scenario.Field(ge=1)] | block.VolumeSizeSpec | None = None,
        nested_level: t.Annotated[int, scenario.Field(ge=1)] = 1,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        create_snapshot_kwargs: dict[str, t.Any] | None = None,
        create_vm_params: dict[str, t.Any] | None = None,
    ) -> None:
        """Create a volume from snapshot and attach/detach the volume

        This scenario create vm, volume, create it's snapshot, attach volume,
        then create new volume from existing snapshot and so on,
        with defined nested level, after all detach and delete them.
        volume->snapshot->volume->snapshot->volume ...

        :param image: Glance image name to use for the VM
        :param flavor: VM flavor name
        :param size: volume size, in GB
                     default values: {"min": 1, "max": 5}
        :param nested_level: amount of nested levels
        :param create_volume_kwargs: optional args to create a volume
        :param create_snapshot_kwargs: optional args to create a snapshot
        :param create_vm_params: optional arguments for VM creation
        """
        if size is None:
            size = {"min": 1, "max": 5}

        # NOTE: Volume size cannot be smaller than the snapshot size, so
        #       volume with specified size should be created to avoid
        #       size mismatching between volume and snapshot due random
        #       size in _create_volume method.
        if isinstance(size, dict):
            size = random.randint(size["min"], size["max"])

        create_volume_kwargs = create_volume_kwargs or {}
        create_snapshot_kwargs = create_snapshot_kwargs or {}
        create_vm_params = create_vm_params or {}

        server = self._boot_server(image, flavor, **create_vm_params)

        source_vol = self.cinder.create_volume(size, **create_volume_kwargs)
        snapshot = self.cinder.create_snapshot(source_vol.id, force=False,
                                               **create_snapshot_kwargs)
        self._attach_volume(server, source_vol)

        nes_objs = [(server, source_vol, snapshot)]
        for i in range(nested_level - 1):
            volume = self.cinder.create_volume(size, snapshot_id=snapshot.id)
            snapshot = self.cinder.create_snapshot(volume.id, force=False,
                                                   **create_snapshot_kwargs)
            self._attach_volume(server, volume)

            nes_objs.append((server, volume, snapshot))

        nes_objs.reverse()
        for server, volume, snapshot in nes_objs:
            self._detach_volume(server, volume)
            self.cinder.delete_snapshot(snapshot)
            self.cinder.delete_volume(volume)
        self._delete_server(server)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("required_contexts", contexts=("volumes"))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_list_snapshots",
                    platform="openstack")
class CreateAndListSnapshots(cinder_utils.CinderBasic,
                             nova_utils.NovaScenario):

    def run(
        self,
        force: bool = False,
        detailed: bool = True,
        **kwargs: t.Any,
    ) -> None:
        """Create and then list a volume-snapshot.

        :param force: when set to True, allows snapshot of a volume when
                      the volume is attached to an instance
        :param detailed: True if detailed information about snapshots
                         should be listed
        :param kwargs: optional args to create a snapshot
        """
        volume = random.choice(self.context["tenant"]["volumes"])
        self.cinder.create_snapshot(volume["id"], force=force, **kwargs)
        self.cinder.list_snapshots(detailed)


@validation.add("required_services", services=[consts.Service.CINDER,
                                               consts.Service.GLANCE])
@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder", "glance"]},
                    name="CinderVolumes.create_and_upload_volume_to_image",
                    platform="openstack")
class CreateAndUploadVolumeToImage(cinder_utils.CinderBasic,
                                   images.GlanceBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        force: bool = False,
        container_format: str = "bare",
        disk_format: str = "raw",
        do_delete: bool = True,
        **kwargs: t.Any,
    ) -> None:
        """Create and upload a volume to image.

        :param size: volume size, in GB
        :param image: image to be used to create volume.
        :param force: when set to True volume that is attached to an instance
                      could be uploaded to image
        :param container_format: image container format
        :param disk_format: disk format for image
        :param do_delete: deletes image and volume after uploading if True
        :param kwargs: optional args to create a volume
        """
        if image:
            kwargs["imageRef"] = image
        volume = self.cinder.create_volume(size, **kwargs)
        image = self.cinder.upload_volume_to_image(
            volume, force=force, container_format=container_format,
            disk_format=disk_format
        )

        if do_delete:
            self.cinder.delete_volume(volume)
            self.glance.delete_image(image.id)


@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_volume_kwargs")
@validation.add("restricted_parameters", param_names="name",
                subdict="create_backup_kwargs")
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_cinder_services", services="cinder-backup")
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_volume_backup",
                    platform="openstack")
class CreateVolumeBackup(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        do_delete: bool = True,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        create_backup_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Create a volume backup.

        :param size: volume size in GB
        :param do_delete: if True, a volume and a volume backup will
                          be deleted after creation.
        :param create_volume_kwargs: optional args to create a volume
        :param create_backup_kwargs: optional args to create a volume backup
        """
        create_volume_kwargs = create_volume_kwargs or {}
        create_backup_kwargs = create_backup_kwargs or {}

        volume = self.cinder.create_volume(size, **create_volume_kwargs)
        backup = self.cinder.create_backup(volume.id, **create_backup_kwargs)

        if do_delete:
            self.cinder.delete_volume(volume)
            self.cinder.delete_backup(backup)


@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_volume_kwargs")
@validation.add("restricted_parameters", param_names="name",
                subdict="create_backup_kwargs")
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_cinder_services", services="cinder-backup")
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_restore_volume_backup",
                    platform="openstack")
class CreateAndRestoreVolumeBackup(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        do_delete: bool = True,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        create_backup_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Restore volume backup.

        :param size: volume size in GB
        :param do_delete: if True, the volume and the volume backup will
                          be deleted after creation.
        :param create_volume_kwargs: optional args to create a volume
        :param create_backup_kwargs: optional args to create a volume backup
        """
        create_volume_kwargs = create_volume_kwargs or {}
        create_backup_kwargs = create_backup_kwargs or {}

        volume = self.cinder.create_volume(size, **create_volume_kwargs)
        backup = self.cinder.create_backup(volume.id, **create_backup_kwargs)
        self.cinder.restore_backup(backup.id)

        if do_delete:
            self.cinder.delete_volume(volume)
            self.cinder.delete_backup(backup)


@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_volume_kwargs")
@validation.add("restricted_parameters", param_names="name",
                subdict="create_backup_kwargs")
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_cinder_services", services="cinder-backup")
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_list_volume_backups",
                    platform="openstack")
class CreateAndListVolumeBackups(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        detailed: bool = True,
        do_delete: bool = True,
        create_volume_kwargs: dict[str, t.Any] | None = None,
        create_backup_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Create and then list a volume backup.

        :param size: volume size in GB
        :param detailed: True if detailed information about backup
                         should be listed
        :param do_delete: if True, a volume backup will be deleted
        :param create_volume_kwargs: optional args to create a volume
        :param create_backup_kwargs: optional args to create a volume backup
        """
        create_volume_kwargs = create_volume_kwargs or {}
        create_backup_kwargs = create_backup_kwargs or {}

        volume = self.cinder.create_volume(size, **create_volume_kwargs)
        backup = self.cinder.create_backup(volume.id, **create_backup_kwargs)
        self.cinder.list_backups(detailed)

        if do_delete:
            self.cinder.delete_volume(volume)
            self.cinder.delete_backup(backup)


@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_volume_and_clone",
                    platform="openstack")
class CreateVolumeAndClone(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        nested_level: t.Annotated[int, scenario.Field(ge=1)] = 1,
        **kwargs: t.Any,
    ) -> None:
        """Create a volume, then clone it to another volume.

        This creates a volume, then clone it to anothor volume,
        and then clone the new volume to next volume...

           1. create source volume (from image)
           2. clone source volume to volume1
           3. clone volume1 to volume2
           4. clone volume2 to volume3
           5. ...

        :param size: volume size, in GB
        :param image: image to be used to create initial volume
        :param nested_level: amount of nested levels
        :param kwargs: optional args to create volumes
        """
        if image:
            kwargs["imageRef"] = image

        source_vol = self.cinder.create_volume(size, **kwargs)

        kwargs.pop("imageRef", None)
        for i in range(nested_level):
            with atomic.ActionTimer(self, "cinder.clone_volume"):
                source_vol = self.cinder.create_volume(
                    source_vol.size, source_volid=source_vol.id,
                    **kwargs)


@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("restricted_parameters", param_names=["name", "display_name"],
                subdict="create_snapshot_kwargs")
@validation.add("required_contexts", contexts=("volumes"))
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_volume_from_snapshot",
                    platform="openstack")
class CreateVolumeFromSnapshot(cinder_utils.CinderBasic):

    def run(
        self,
        do_delete: bool = True,
        create_snapshot_kwargs: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Create a volume-snapshot, then create a volume from this snapshot.

        :param do_delete: if True, a snapshot and a volume will
                          be deleted after creation.
        :param create_snapshot_kwargs: optional args to create a snapshot
        :param kwargs: optional args to create a volume
        """
        create_snapshot_kwargs = create_snapshot_kwargs or {}
        src_volume = random.choice(self.context["tenant"]["volumes"])

        snapshot = self.cinder.create_snapshot(src_volume["id"],
                                               **create_snapshot_kwargs)
        volume = self.cinder.create_volume(src_volume["size"],
                                           snapshot_id=snapshot.id,
                                           **kwargs)

        if do_delete:
            self.cinder.delete_volume(volume)
            self.cinder.delete_snapshot(snapshot)


@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_volume_"
                         "and_update_readonly_flag",
                    platform="openstack")
class CreateVolumeAndUpdateReadonlyFlag(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        read_only: bool = True,
        **kwargs: t.Any,
    ) -> None:
        """Create a volume and then update its readonly flag.

        :param size: volume size (integer, in GB)
        :param image: image to be used to create volume
        :param read_only: The value to indicate whether to update volume to
            read-only access mode
        :param kwargs: optional args to create a volume
        """
        if image:
            kwargs["imageRef"] = image
        volume = self.cinder.create_volume(size, **kwargs)
        self.cinder.update_readonly_flag(volume.id, read_only=read_only)


@validation.add("restricted_parameters", param_names=["name", "display_name"])
@validation.add("image_exists", param_name="image", nullable=True)
@validation.add("required_services", services=[consts.Service.CINDER])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["cinder"]},
                    name="CinderVolumes.create_and_accept_transfer",
                    platform="openstack")
class CreateAndAcceptTransfer(cinder_utils.CinderBasic):

    def run(
        self,
        size: t.Annotated[int, scenario.Field(ge=1)] | block.VolumeSizeSpec,
        image: t.Annotated[str, types.Convert("glance_image")] | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Create a volume transfer, then accept it

        Measure the "cinder transfer-create" and "cinder transfer-accept"
        command performace.
        :param size: volume size (integer, in GB)
        :param image: image to be used to create initial volume
        :param kwargs: optional args to create a volume
        """
        if image:
            kwargs["imageRef"] = image
        volume = self.cinder.create_volume(size, **kwargs)
        transfer = self.cinder.transfer_create(volume.id)
        self.cinder.transfer_accept(transfer.id, auth_key=transfer.auth_key)
