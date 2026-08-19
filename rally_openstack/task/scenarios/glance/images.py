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

import typing as t

from rally.common import logging
from rally.task import types
from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.common.clients import glance
from rally_openstack.common.services.image import image as image_service
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.nova import utils as nova_utils


LOG = logging.getLogger(__name__)

"""Scenarios for Glance images."""


class GlanceBasic(scenario.OpenStackScenario):
    """Deprecated base class for Glance scenarios."""

    _deprecation_logged = False

    def __init__(
        self,
        context: dict[str, t.Any] | None = None,
        admin_clients: t.Any = None,
        clients: t.Any = None,
    ) -> None:
        if not GlanceBasic._deprecation_logged:
            LOG.warning(
                "The GlanceBasic scenario base class is deprecated and will "
                "be removed. Subclass rally_openstack.task.scenario."
                "OpenStackScenario and use the `_clients.glance` attribute "
                "instead."
            )
            GlanceBasic._deprecation_logged = True
        super().__init__(context, admin_clients, clients)
        if hasattr(self, "_admin_clients"):
            self.admin_glance = image_service.Image(
                self._admin_clients, name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions())
        if hasattr(self, "_clients"):
            self.glance = image_service.Image(
                self._clients, name_generator=self.generate_random_name,
                atomic_inst=self.atomic_actions())


@validation.add("required_services", services=[consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["glance"]},
                    name="GlanceImages.create_and_list_image",
                    platform="openstack")
class CreateAndListImage(scenario.OpenStackScenario):

    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
        properties: glance.ImageProperties | None = None,
    ) -> None:
        """Create an image and then list all images.

        Measure the "glance image-list" command performance.

        If you have only 1 user in your context, you will
        add 1 image on every iteration. So you will have more
        and more images and will be able to measure the
        performance of the "glance image-list" command depending on
        the number of images owned by users.

        :param container_format: container format of image
        :param image_location: image file location
        :param disk_format: disk format of image
        :param visibility: The access permission for the created image
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: A dict of image metadata properties to set
                           on the image
        """
        image = self._clients.glance.create_image(
            location=image_location,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)
        self.assertTrue(image)
        image_list = self._clients.glance.list_images()
        self.assertIn(image.id, [i.id for i in image_list])


@validation.add("required_services", services=[consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["glance"]},
                    name="GlanceImages.create_and_get_image",
                    platform="openstack")
class CreateAndGetImage(scenario.OpenStackScenario):

    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
        properties: glance.ImageProperties | None = None,
    ) -> None:
        """Create and get detailed information of an image.

        :param container_format: container format of image
        :param image_location: image file location
        :param disk_format: disk format of image
        :param visibility: The access permission for the created image
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: A dict of image metadata properties to set
                           on the image
        """
        image = self._clients.glance.create_image(
            location=image_location,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)
        self.assertTrue(image)
        image_info = self._clients.glance.get_image(image)
        self.assertEqual(image.id, image_info.id)


@validation.add("required_services", services=[consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="GlanceImages.list_images",
                    platform="openstack")
class ListImages(scenario.OpenStackScenario):

    def run(self) -> None:
        """List all images.

        This simple scenario tests the glance image-list command by listing
        all the images.

        Suppose if we have 2 users in context and each has 2 images
        uploaded for them we will be able to test the performance of
        glance image-list command in this case.
        """
        self._clients.glance.list_images()


@validation.add("required_services", services=[consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["glance"]},
                    name="GlanceImages.create_and_delete_image",
                    platform="openstack")
class CreateAndDeleteImage(scenario.OpenStackScenario):

    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
        properties: glance.ImageProperties | None = None,
    ) -> None:
        """Create and then delete an image.

        :param container_format: container format of image
        :param image_location: image file location
        :param disk_format: disk format of image
        :param visibility: The access permission for the created image
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: A dict of image metadata properties to set
                           on the image
        """
        image = self._clients.glance.create_image(
            location=image_location,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)
        self._clients.glance.delete_image(image.id)


@validation.add("restricted_parameters", param_names=["image_name", "name"])
@validation.add("flavor_exists", param_name="flavor")
@validation.add("required_services", services=[consts.Service.GLANCE,
                                               consts.Service.NOVA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["glance", "nova"]},
                    name="GlanceImages.create_image_and_boot_instances",
                    platform="openstack")
class CreateImageAndBootInstances(nova_utils.NovaScenario):

    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        flavor: t.Annotated[str, types.Convert("nova_flavor")],
        number_instances: t.Annotated[int, scenario.Field(ge=1)],
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
        properties: glance.ImageProperties | None = None,
        boot_server_kwargs: dict[str, t.Any] | None = None,
    ) -> None:
        """Create an image and boot several instances from it.

        :param container_format: container format of image
        :param image_location: image file location
        :param disk_format: disk format of image
        :param visibility: The access permission for the created image
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: A dict of image metadata properties to set
                           on the image
        :param flavor: Nova flavor to be used to launch an instance
        :param number_instances: number of Nova servers to boot
        :param boot_server_kwargs: optional parameters to boot server
        """

        image = self._clients.glance.create_image(
            location=image_location,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)

        self._boot_servers(image.id, flavor, number_instances,
                           **(boot_server_kwargs or {}))


@validation.add("required_services", services=[consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["glance"]},
                    name="GlanceImages.create_and_update_image",
                    platform="openstack")
class CreateAndUpdateImage(scenario.OpenStackScenario):

    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        remove_props: list[str] | None = None,
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        create_min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        create_min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
        create_properties: glance.ImageProperties | None = None,
        update_min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        update_min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
    ) -> None:
        """Create an image then update it.

        Measure the "glance image-create" and "glance image-update" commands
        performance.

        :param container_format: container format of image
        :param image_location: image file location
        :param disk_format: disk format of image
        :param remove_props: List of property names to remove.
                             (It is only supported by Glance v2.)
        :param visibility: The access permission for the created image
        :param create_min_disk: The min disk of created images
        :param create_min_ram: The min ram of created images
        :param create_properties: A dict of image metadata properties to set
                                  on the created image
        :param update_min_disk: The min disk of updated images
        :param update_min_ram: The min ram of updated images
        """
        image = self._clients.glance.create_image(
            location=image_location,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=create_min_disk,
            min_ram=create_min_ram,
            properties=create_properties)

        self._clients.glance.update_image(
            image.id,
            min_disk=update_min_disk,
            min_ram=update_min_ram,
            remove_properties=remove_props)


@validation.add("required_services", services=(consts.Service.GLANCE, ))
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_api_versions", component="glance", versions=["2"])
@scenario.configure(context={"cleanup@openstack": ["glance"]},
                    name="GlanceImages.create_and_deactivate_image",
                    platform="openstack")
class CreateAndDeactivateImage(scenario.OpenStackScenario):
    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
    ) -> None:
        """Create an image, then deactivate it.

        :param container_format: container format of image
        :param image_location: image file location
        :param disk_format: disk format of image
        :param visibility: The access permission for the created image
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        """
        image = self._clients.glance.create_image(
            location=image_location,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram)
        self._clients.glance.deactivate_image(image.id)


@validation.add("required_services", services=[consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup@openstack": ["glance"]},
                    name="GlanceImages.create_and_download_image",
                    platform="openstack")
class CreateAndDownloadImage(scenario.OpenStackScenario):

    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
        properties: glance.ImageProperties | None = None,
    ) -> None:
        """Create an image, then download data of the image.

        :param container_format: container format of image
        :param image_location: image file location
        :param disk_format: disk format of image
        :param visibility: The access permission for the created image
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: A dict of image metadata properties to set
                           on the image
        """
        image = self._clients.glance.create_image(
            location=image_location,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)

        self._clients.glance.download_image(image.id)


@validation.add("required_services", services=[consts.Service.GLANCE])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_api_versions", component="glance", versions=["2"])
@scenario.configure(context={"cleanup@openstack": ["glance"]},
                    name="GlanceImages.import_and_delete_image",
                    platform="openstack")
class ImportAndDeleteImage(scenario.OpenStackScenario):

    def run(
        self,
        container_format: glance.ContainerFormat,
        image_location: t.Annotated[str, types.Convert("path_or_url")],
        disk_format: glance.DiskFormat,
        visibility: glance.Visibility = glance.Visibility.PRIVATE,
        min_disk: t.Annotated[int, scenario.Field(ge=0)] = 0,
        min_ram: t.Annotated[int, scenario.Field(ge=0)] = 0,
        properties: glance.ImageProperties | None = None,
        stores: list[str] | None = None,
        all_stores: bool = True,
        import_method: glance.ImportMethod = (
            glance.ImportMethod.GLANCE_DIRECT),
    ) -> None:
        """Import image using specific method, then delete it.

        This scenario tests the Glance v2 interoperable image import
        workflow. Each phase is measured separately.

        :param container_format: container format of image
        :param image_location: image file location (path or URL)
        :param disk_format: disk format of image
        :param visibility: The access permission for the created image
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: Image metadata properties to set
                           on the image
        :param stores: List of specific stores for multistore deployments
        :param all_stores: Import to all available stores
        :param import_method: Import method to use
        """
        # Create image in queued state
        image = self._clients.glance.create_image_record(
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)

        image = self._clients.glance.import_image(
            image,
            data=image_location,
            method=import_method,
            stores=stores,
            all_stores=all_stores)

        self._clients.glance.delete_image(image)
