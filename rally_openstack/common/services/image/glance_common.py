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

from __future__ import annotations

import typing as t

from rally.task import atomic

from rally_openstack.common.services.image import image as image_service


if t.TYPE_CHECKING:
    from rally_openstack.common.clients import glance


class GlanceMixin(atomic.ActionTimerMixin):

    _ng_cache: glance.Glance | None = None

    @property
    def _ng(self) -> glance.Glance:
        """openstacksdk-backed image client, pinned to this version."""
        if self._ng_cache is None:
            self._ng_cache = self._clients.glance(self.version, legacy=False)
        return self._ng_cache

    def get_image(self, image):
        """Get specified image.

        :param image: ID or object with ID of image to obtain.
        """
        return self._ng.get_image(image)

    def delete_image(self, image_id):
        """Delete image."""
        self._ng.delete_image(image_id)

    def download_image(self, image_id, do_checksum=True):
        """Retrieve data of an image.

        :param image_id: ID of the image to download.
        :param do_checksum: Deprecated and ignored. The openstacksdk verifies
            the hash whenever the image advertises one.
        :returns: number of bytes downloaded
        """
        return self._ng.download_image(image_id)


class UnifiedGlanceMixin:

    @staticmethod
    def _unify_image(image):
        return image_service.UnifiedImage(id=image.id, name=image.name,
                                          status=image.status,
                                          visibility=image.visibility)

    def get_image(self, image):
        """Get specified image.

        :param image: ID or object with ID of image to obtain.
        """
        image_obj = self._impl.get_image(image=image)
        return self._unify_image(image_obj)

    def delete_image(self, image_id):
        """Delete image."""
        self._impl.delete_image(image_id=image_id)

    def download_image(self, image_id, do_checksum=True):
        """Download data for an image.

        :param image_id: image id to look up
        :param do_checksum: Deprecated and ignored. The openstacksdk verifies
            the hash whenever the image advertises one.
        :returns: number of bytes downloaded
        """
        return self._impl.download_image(image_id, do_checksum=do_checksum)
