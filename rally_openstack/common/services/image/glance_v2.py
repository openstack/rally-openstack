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

import os
import time

from rally.common import cfg
from rally.common import utils as rutils
from rally.task import atomic
from rally.task import utils
import requests

from rally_openstack.common import service
from rally_openstack.common.services.image import glance_common
from rally_openstack.common.services.image import image


CONF = cfg.CONF


@service.service("glance", service_type="image", version="2")
class GlanceV2Service(service.Service, glance_common.GlanceMixin):

    @atomic.action_timer("glance_v2.upload_data")
    def upload_data(self, image_id, image_location):
        """Upload the data for an image.

        :param image_id: Image ID to upload data to.
        :param image_location: Location of the data to upload to.
        """
        image_location = os.path.expanduser(image_location)
        image_data = None
        response = None
        try:
            if os.path.isfile(image_location):
                image_data = open(image_location, "rb")
            else:
                response = requests.get(image_location, stream=True,
                                        verify=False)
                image_data = response.raw
            self._clients.glance("2").images.upload(image_id, image_data)
        finally:
            if image_data is not None:
                image_data.close()
            if response is not None:
                response.close()

    @atomic.action_timer("glance_v2.create_image")
    def create_image(self, image_name=None, container_format=None,
                     image_location=None, disk_format=None,
                     visibility=None, min_disk=0,
                     min_ram=0, properties=None):
        """Creates new image.

        :param image_name: Image name for which need to be created
        :param container_format: Container format
        :param image_location: The new image's location
        :param disk_format: Disk format
        :param visibility: The created image's visible status.
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: Dict of image properties
        """
        image_name = image_name or self.generate_random_name()

        properties = properties or {}
        image_obj = self._clients.glance("2").images.create(
            name=image_name,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            **properties)

        rutils.interruptable_sleep(CONF.openstack.
                                   glance_image_create_prepoll_delay)

        start = time.time()
        image_obj = utils.wait_for_status(
            image_obj.id, ["queued"],
            update_resource=self.get_image,
            timeout=CONF.openstack.glance_image_create_timeout,
            check_interval=CONF.openstack.glance_image_create_poll_interval)
        timeout = time.time() - start

        self.upload_data(image_obj.id, image_location=image_location)

        image_obj = utils.wait_for_status(
            image_obj, ["active"],
            update_resource=self.get_image,
            timeout=timeout,
            check_interval=CONF.openstack.glance_image_create_poll_interval)
        return image_obj

    @atomic.action_timer("glance_v2.create_image_for_import")
    def create_image_for_import(self, image_name=None, container_format=None,
                                disk_format=None, visibility=None,
                                min_disk=0, min_ram=0, properties=None):
        """Create an image in queued state for import.

        Unlike create_image(), this does NOT upload data - it creates
        the image record in 'queued'

        :param image_name: Image name
        :param container_format: Container format
        :param disk_format: Disk format
        :param visibility: Image visibility
        :param min_disk: Minimum disk size
        :param min_ram: Minimum RAM
        :param properties: Dict of image properties
        :returns: Created image object in 'queued' state
        """
        image_name = image_name or self.generate_random_name()
        properties = properties or {}

        image_obj = self._clients.glance("2").images.create(
            name=image_name,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            **properties)

        rutils.interruptable_sleep(CONF.openstack.
                                   glance_image_create_prepoll_delay)

        # Wait for queued state
        image_obj = utils.wait_for_status(
            image_obj.id, ["queued"],
            update_resource=self.get_image,
            timeout=CONF.openstack.glance_image_create_timeout,
            check_interval=CONF.openstack.glance_image_create_poll_interval)

        return image_obj

    @atomic.action_timer("glance_v2.stage_image_data")
    def stage_image_data(self, image_id, image_location):
        """Stage image data to Glance staging area.

        :param image_id: ID of image to stage data for
        :param image_location: Location of the data (path or URL)
        """
        image_location = os.path.expanduser(image_location)
        image_data = None
        response = None
        try:
            if os.path.isfile(image_location):
                image_data = open(image_location, "rb")
            else:
                response = requests.get(image_location, stream=True,
                                        verify=False)
                image_data = response.raw
            self._clients.glance("2").images.stage(image_id, image_data)
        finally:
            if image_data is not None:
                image_data.close()
            if response is not None:
                response.close()

    @atomic.action_timer("glance_v2.import_image")
    def import_image(self, image_id, import_method="glance-direct",
                     import_uri=None, stores=None, all_stores=True):
        """Import image data using specified import method.

        :param image_id: ID of image to import data for
        :param import_method: Import method ('glance-direct', 'web-download')
        :param import_uri: URI for supported methods
        :param stores: List of stores to import to (multistore)
        :param all_stores: Import to all stores if True
        :returns: Image object after successful import
        """
        # Trigger the import (returns immediately with 202 Accepted)
        client = self._clients.glance("2")

        try:
            import_params = {}

            # Handle method-specific parameters
            if import_method in ["web-download", "glance-download"]:
                if not import_uri:
                    raise ValueError(
                        f"{import_method} requires import_uri parameter")
                import_params["uri"] = import_uri

            # Handle store parameters
            if stores:
                import_params["stores"] = stores
            elif all_stores:
                import_params["all_stores"] = True

            client.images.image_import(
                image_id,
                method=import_method,
                **import_params
            )
        except AttributeError:
            # Fallback for older glanceclient
            raise NotImplementedError(
                "Image import requires python-glanceclient >= 2.9.0")

        # Poll until import completes (image becomes 'active')
        image_obj = utils.wait_for_status(
            image_id,
            ready_statuses=["active"],
            failure_statuses=["killed", "deleted", "pending_delete", "error"],
            update_resource=self.get_image,
            timeout=CONF.openstack.glance_image_import_timeout,
            check_interval=CONF.openstack.glance_image_import_poll_interval)

        return image_obj

    @atomic.action_timer("glance_v2.stage_and_import_image")
    def stage_and_import_image(self, image_id, image_location,
                               import_method="glance-direct",
                               stores=None, all_stores=True):
        """Stage and import image data in one operation.

        This is a convenience method combining stage_image_data
        and import_image with a single atomic timer.
        Only applicable for glance-direct method.

        :param image_id: ID of image to import
        :param image_location: Location of the data (path or URL)
        :param import_method: Import method (must be 'glance-direct')
        :param stores: List of stores for multistore
        :param all_stores: Import to all stores
        :returns: Imported image object in 'active' state
        """
        if import_method != "glance-direct":
            raise ValueError(
                "stage_and_import_image only supports 'glance-direct' method")

        self.stage_image_data(image_id, image_location)
        return self.import_image(image_id, import_method=import_method,
                                 stores=stores, all_stores=all_stores)

    @atomic.action_timer("glance_v2.update_image")
    def update_image(self, image_id, image_name=None, min_disk=0,
                     min_ram=0, remove_props=None):
        """Update image.

        :param image_id: ID of image to update
        :param image_name: Image name to be updated to
        :param min_disk: The min disk of updated image
        :param min_ram: The min ram of updated image
        :param remove_props: List of property names to remove
        """
        image_name = image_name or self.generate_random_name()

        return self._clients.glance("2").images.update(
            image_id=image_id,
            name=image_name,
            min_disk=min_disk,
            min_ram=min_ram,
            remove_props=remove_props)

    @atomic.action_timer("glance_v2.list_images")
    def list_images(self, status="active", visibility=None, owner=None):
        """List images.

        :param status: Filter in images for the specified status
        :param visibility: Filter in images for the specified visibility
        :param owner: Filter in images for tenant ID
        """
        filters = {"status": status}
        if visibility:
            filters["visibility"] = visibility
        if owner:
            filters["owner"] = owner
        # NOTE(boris-42): image.list() is lazy method which doesn't query API
        #                 until it's used, do not remove list().
        return list(self._clients.glance("2").images.list(filters=filters))

    @atomic.action_timer("glance_v2.set_visibility")
    def set_visibility(self, image_id, visibility="shared"):
        """Update visibility.

        :param image_id: ID of image to update
        :param visibility: The visibility of specified image
        """
        self._clients.glance("2").images.update(image_id,
                                                visibility=visibility)

    @atomic.action_timer("glance_v2.deactivate_image")
    def deactivate_image(self, image_id):
        """deactivate image."""
        self._clients.glance("2").images.deactivate(image_id)

    @atomic.action_timer("glance_v2.reactivate_image")
    def reactivate_image(self, image_id):
        """reactivate image."""
        self._clients.glance("2").images.reactivate(image_id)


@service.compat_layer(GlanceV2Service)
class UnifiedGlanceV2Service(glance_common.UnifiedGlanceMixin, image.Image):
    """Compatibility layer for Glance V2."""

    @staticmethod
    def _check_v2_visibility(visibility):
        visibility_values = ["public", "private", "shared", "community"]
        if visibility and visibility not in visibility_values:
            raise image.VisibilityException(
                message="Improper visibility value: %s in glance_v2"
                        % visibility)

    def create_image(self, image_name=None, container_format=None,
                     image_location=None, disk_format=None,
                     visibility=None, min_disk=0,
                     min_ram=0, properties=None):
        """Creates new image.

        :param image_name: Image name for which need to be created
        :param container_format: Container format
        :param image_location: The new image's location
        :param disk_format: Disk format
        :param visibility: The access permission for the created image.
        :param min_disk: The min disk of created images
        :param min_ram: The min ram of created images
        :param properties: Dict of image properties
        """
        image_obj = self._impl.create_image(
            image_name=image_name,
            container_format=container_format,
            image_location=image_location,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)
        return self._unify_image(image_obj)

    def update_image(self, image_id, image_name=None, min_disk=0,
                     min_ram=0, remove_props=None):
        """Update image.

        :param image_id: ID of image to update
        :param image_name: Image name to be updated to
        :param min_disk: The min disk of updated image
        :param min_ram: The min ram of updated image
        :param remove_props: List of property names to remove
        """
        image_obj = self._impl.update_image(
            image_id=image_id,
            image_name=image_name,
            min_disk=min_disk,
            min_ram=min_ram,
            remove_props=remove_props)
        return self._unify_image(image_obj)

    def list_images(self, status="active", visibility=None, owner=None):
        """List images.

        :param status: Filter in images for the specified status
        :param visibility: Filter in images for the specified visibility
        :param owner: Filter in images for tenant ID
        """
        self._check_v2_visibility(visibility)

        images = self._impl.list_images(
            status=status, visibility=visibility, owner=owner)
        return [self._unify_image(i) for i in images]

    def set_visibility(self, image_id, visibility="shared"):
        """Update visibility.

        :param image_id: ID of image to update
        :param visibility: The visibility of specified image
        """
        self._check_v2_visibility(visibility)

        self._impl.set_visibility(image_id=image_id, visibility=visibility)

    def create_image_for_import(self, image_name=None, container_format=None,
                                disk_format=None, visibility=None,
                                min_disk=0, min_ram=0, properties=None):
        """Create image for import (unified interface).

        :param image_name: Image name
        :param container_format: Container format
        :param disk_format: Disk format
        :param visibility: Image visibility
        :param min_disk: Minimum disk size
        :param min_ram: Minimum RAM
        :param properties: Dict of image properties
        """
        self._check_v2_visibility(visibility)

        image_obj = self._impl.create_image_for_import(
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            min_disk=min_disk,
            min_ram=min_ram,
            properties=properties)
        return self._unify_image(image_obj)

    def stage_image_data(self, image_id, image_location):
        """Stage image data (unified interface).

        :param image_id: ID of image to stage data for
        :param image_location: Location of the data (path or URL)
        """
        self._impl.stage_image_data(image_id=image_id,
                                    image_location=image_location)

    def import_image(self, image_id, import_method="glance-direct",
                     import_uri=None, stores=None, all_stores=True):
        """Import image data (unified interface).

        :param image_id: ID of image to import
        :param import_method: Import method ('glance-direct', 'web-download')
        :param import_uri: URI for supported import methods
        :param stores: List of stores for multistore
        :param all_stores: Import to all stores
        """
        image_obj = self._impl.import_image(
            image_id=image_id,
            import_method=import_method,
            import_uri=import_uri,
            stores=stores,
            all_stores=all_stores)
        return self._unify_image(image_obj)

    def stage_and_import_image(self, image_id, image_location,
                               import_method="glance-direct",
                               stores=None, all_stores=True):
        """Stage and import image (unified interface).

        :param image_id: ID of image to import
        :param image_location: Location of the data (path or URL)
        :param import_method: Import method (must be 'glance-direct')
        :param stores: List of stores for multistore
        :param all_stores: Import to all stores
        """
        image_obj = self._impl.stage_and_import_image(
            image_id=image_id,
            image_location=image_location,
            import_method=import_method,
            stores=stores,
            all_stores=all_stores)
        return self._unify_image(image_obj)
