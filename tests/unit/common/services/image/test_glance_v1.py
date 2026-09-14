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

from rally_openstack.common.clients import glance
from rally_openstack.common.services.image import glance_v1
from rally_openstack.common.services.image import image
from tests.unit import test


PATH = ("rally_openstack.common.services.image.glance_common."
        "UnifiedGlanceMixin._unify_image")


@ddt.ddt
class GlanceV1ServiceTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.clients = mock.MagicMock()
        self.gc = self.clients.glance.return_value
        self.name_generator = mock.MagicMock()
        self.service = glance_v1.GlanceV1Service(
            self.clients, name_generator=self.name_generator)

    def test_create_image(self):
        for is_public, visibility in ((True, glance.Visibility.PUBLIC),
                                      (False, glance.Visibility.PRIVATE)):
            with self.subTest(is_public=is_public):
                self.gc.create_image.reset_mock()

                image = self.service.create_image(
                    image_name="image_name",
                    container_format="container_format",
                    image_location="image_location",
                    disk_format="disk_format",
                    is_public=is_public,
                    properties={"fakeprop": "fake"})

                self.gc.create_image.assert_called_once_with(
                    "image_name",
                    location="image_location",
                    container_format="container_format",
                    disk_format="disk_format",
                    visibility=visibility,
                    min_disk=0,
                    min_ram=0,
                    properties={"fakeprop": "fake"})
                self.assertEqual(
                    self.gc.create_image.return_value, image)

    @ddt.data({"image_name": None},
              {"image_name": "test_image_name"})
    @ddt.unpack
    def test_update_image(self, image_name):
        image_id = "image_id"
        expected_image_name = image_name or self.name_generator.return_value

        image = self.service.update_image(image_id=image_id,
                                          image_name=image_name,
                                          min_disk=0,
                                          min_ram=0)
        self.assertEqual(self.gc.update_image.return_value, image)
        self.gc.update_image.assert_called_once_with(
            image_id, name=expected_image_name, min_disk=0, min_ram=0)

    def test_list_images(self):
        for is_public, visibility in ((True, glance.Visibility.PUBLIC),
                                      (False, glance.Visibility.PRIVATE),
                                      (None, None)):
            with self.subTest(is_public=is_public):
                self.gc.list_images.reset_mock()
                self.service.list_images(is_public=is_public, status="active",
                                         owner="owner")
                self.gc.list_images.assert_called_once_with(
                    status="active", visibility=visibility, owner="owner")

    def test_set_visibility(self):
        self.service.set_visibility(image_id="image_id")
        self.gc.update_image.assert_called_once_with(
            "image_id", visibility=glance.Visibility.PUBLIC)


@ddt.ddt
class UnifiedGlanceV1ServiceTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.clients = mock.MagicMock()
        self.service = glance_v1.UnifiedGlanceV1Service(self.clients)
        self.service._impl = mock.create_autospec(self.service._impl)

    @ddt.data({"visibility": "public"},
              {"visibility": "private"})
    @ddt.unpack
    @mock.patch(PATH)
    def test_create_image(self, mock_image__unify_image, visibility):
        image_name = "image_name"
        container_format = "container_format"
        image_location = "image_location"
        disk_format = "disk_format"
        properties = {"fakeprop": "fake"}

        image = self.service.create_image(image_name=image_name,
                                          container_format=container_format,
                                          image_location=image_location,
                                          disk_format=disk_format,
                                          visibility=visibility,
                                          properties=properties)

        is_public = visibility == "public"
        callargs = {"image_name": image_name,
                    "container_format": container_format,
                    "image_location": image_location,
                    "disk_format": disk_format,
                    "is_public": is_public,
                    "min_disk": 0,
                    "min_ram": 0,
                    "properties": properties}
        self.service._impl.create_image.assert_called_once_with(**callargs)
        self.assertEqual(mock_image__unify_image.return_value, image)

    @mock.patch(PATH)
    def test_update_image(self, mock_image__unify_image):
        image_id = "image_id"
        image_name = "image_name"
        callargs = {"image_id": image_id,
                    "image_name": image_name,
                    "min_disk": 0,
                    "min_ram": 0}

        image = self.service.update_image(image_id,
                                          image_name=image_name)

        self.assertEqual(mock_image__unify_image.return_value, image)
        self.service._impl.update_image.assert_called_once_with(**callargs)

    @mock.patch(PATH)
    def test_list_images(self, mock_image__unify_image):
        images = [mock.MagicMock()]
        self.service._impl.list_images.return_value = images

        status = "active"
        visibility = "public"
        is_public = visibility == "public"
        self.assertEqual([mock_image__unify_image.return_value],
                         self.service.list_images(status,
                                                  visibility=visibility))
        self.service._impl.list_images.assert_called_once_with(
            status=status,
            is_public=is_public)

    def test_set_visibility(self):
        image_id = "image_id"
        visibility = "private"
        is_public = visibility == "public"
        self.service.set_visibility(image_id=image_id, visibility=visibility)
        self.service._impl.set_visibility.assert_called_once_with(
            image_id=image_id, is_public=is_public)

    def test_set_visibility_failure(self):
        image_id = "image_id"
        visibility = "error"
        self.assertRaises(image.VisibilityException,
                          self.service.set_visibility,
                          image_id=image_id,
                          visibility=visibility)

    def test_create_image_for_import_not_supported(self):
        # Verify NotImplementedError is raised for V1 API
        exc = self.assertRaises(NotImplementedError,
                                self.service.create_image_for_import,
                                image_name="test",
                                container_format="bare",
                                disk_format="qcow2")
        self.assertIn("Glance V1", str(exc))
        self.assertIn("import", str(exc).lower())

    def test_stage_image_data_not_supported(self):
        # Verify NotImplementedError is raised for V1 API
        exc = self.assertRaises(NotImplementedError,
                                self.service.stage_image_data,
                                image_id="image_id",
                                image_location="/path/to/image")
        self.assertIn("staging", str(exc).lower())
        self.assertIn("Glance V1", str(exc))

    def test_import_image_not_supported(self):
        # Verify NotImplementedError is raised for V1 API
        exc = self.assertRaises(NotImplementedError,
                                self.service.import_image,
                                image_id="image_id")
        self.assertIn("import", str(exc).lower())
        self.assertIn("Glance V1", str(exc))

    def test_stage_and_import_image_not_supported(self):
        # Verify NotImplementedError is raised for V1 API
        exc = self.assertRaises(NotImplementedError,
                                self.service.stage_and_import_image,
                                image_id="image_id",
                                image_location="/path/to/image")
        self.assertIn("import", str(exc).lower())
        self.assertIn("Glance V1", str(exc))
