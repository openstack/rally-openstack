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

from rally_openstack.common.services.image import glance_v2
from tests.unit import test


PATH = "rally_openstack.common.services.image"


@ddt.ddt
class GlanceV2ServiceTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.clients = mock.MagicMock()
        self.gc = self.clients.glance.return_value
        self.name_generator = mock.MagicMock()
        self.service = glance_v2.GlanceV2Service(
            self.clients, name_generator=self.name_generator)

    def test_upload_data(self):
        self.service.upload_data("foo", image_location="location")
        self.gc.upload_image.assert_called_once_with("foo", data="location")

    def test_create_image(self):
        for image_name in ("image_name", None):
            with self.subTest(image_name=image_name):
                self.gc.create_image.reset_mock()

                image = self.service.create_image(
                    image_name=image_name,
                    container_format="container_format",
                    image_location="location",
                    disk_format="disk_format",
                    visibility="public",
                    properties={"fakeprop": "fake"})

                self.gc.create_image.assert_called_once_with(
                    image_name or self.name_generator.return_value,
                    location="location",
                    container_format="container_format",
                    disk_format="disk_format",
                    visibility="public",
                    min_disk=0,
                    min_ram=0,
                    properties={"fakeprop": "fake"})
                self.assertEqual(
                    self.gc.create_image.return_value, image)

    def test_update_image(self):
        for image_name in ("image_name", None):
            with self.subTest(image_name=image_name):
                self.gc.update_image.reset_mock()

                image = self.service.update_image(image_id="image_id",
                                                  image_name=image_name,
                                                  min_disk=0,
                                                  min_ram=0,
                                                  remove_props=None)
                self.assertEqual(self.gc.update_image.return_value, image)
                self.gc.update_image.assert_called_once_with(
                    "image_id",
                    name=image_name or self.name_generator.return_value,
                    min_disk=0,
                    min_ram=0,
                    remove_properties=None)

    def test_list_images(self):
        self.assertEqual(self.gc.list_images.return_value,
                         self.service.list_images())
        self.gc.list_images.assert_called_once_with(
            status="active", visibility=None, owner=None)

    def test_list_images_with_filters(self):
        self.service.list_images(visibility="public", owner="tenant_id")
        self.gc.list_images.assert_called_once_with(
            status="active", visibility="public", owner="tenant_id")

    def test_set_visibility(self):
        self.service.set_visibility(image_id="image_id")
        self.gc.update_image.assert_called_once_with(
            "image_id", visibility="shared")

    def test_deactivate_image(self):
        self.service.deactivate_image("image_id")
        self.gc.deactivate_image.assert_called_once_with("image_id")

    def test_reactivate_image(self):
        self.service.reactivate_image("image_id")
        self.gc.reactivate_image.assert_called_once_with("image_id")

    def test_create_image_for_import(self):
        for image_name in ("image_name", None):
            with self.subTest(image_name=image_name):
                self.gc.create_image_record.reset_mock()

                image = self.service.create_image_for_import(
                    image_name=image_name,
                    container_format="container_format",
                    disk_format="disk_format",
                    visibility="public",
                    properties={"fakeprop": "fake"})

                self.gc.create_image_record.assert_called_once_with(
                    image_name or self.name_generator.return_value,
                    container_format="container_format",
                    disk_format="disk_format",
                    visibility="public",
                    min_disk=0,
                    min_ram=0,
                    properties={"fakeprop": "fake"})
                self.assertEqual(
                    self.gc.create_image_record.return_value, image)

    def test_stage_image_data(self):
        self.service.stage_image_data("foo", image_location="location")
        self.gc.stage_image.assert_called_once_with("foo", data="location")

    def test_import_image(self):
        result = self.service.import_image(
            image_id="image_id",
            import_method="web-download",
            import_uri="http://example.com/image.qcow2",
            stores=["store1"],
            all_stores=False)

        self.gc.import_image.assert_called_once_with(
            "image_id",
            data="http://example.com/image.qcow2",
            method="web-download",
            stores=["store1"],
            all_stores=False)
        self.assertEqual(self.gc.import_image.return_value, result)

    def test_stage_and_import_image(self):
        result = self.service.stage_and_import_image(
            image_id="image_id",
            image_location="/path/to/image.qcow2",
            import_method="glance-direct",
            stores=["store1"],
            all_stores=False)

        self.gc.import_image.assert_called_once_with(
            "image_id",
            data="/path/to/image.qcow2",
            method="glance-direct",
            stores=["store1"],
            all_stores=False)
        self.assertEqual(self.gc.import_image.return_value, result)

    def test_stage_and_import_image_wrong_method(self):
        self.assertRaises(ValueError, self.service.stage_and_import_image,
                          image_id="image_id",
                          image_location="/path/to/image.qcow2",
                          import_method="web-download")


@ddt.ddt
class UnifiedGlanceV2ServiceTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        self.clients = mock.MagicMock()
        self.service = glance_v2.UnifiedGlanceV2Service(self.clients)
        self.service._impl = mock.create_autospec(self.service._impl)

    @mock.patch("%s.glance_common.UnifiedGlanceMixin._unify_image" % PATH)
    def test_create_image(self, mock_image__unify_image):
        image_name = "image_name"
        container_format = "container_format"
        image_location = "image_location"
        disk_format = "disk_format"
        visibility = "public"
        properties = {"fakeprop": "fake"}
        callargs = {"image_name": image_name,
                    "container_format": container_format,
                    "image_location": image_location,
                    "disk_format": disk_format,
                    "visibility": visibility,
                    "min_disk": 0,
                    "min_ram": 0,
                    "properties": properties}

        image = self.service.create_image(image_name=image_name,
                                          container_format=container_format,
                                          image_location=image_location,
                                          disk_format=disk_format,
                                          visibility=visibility,
                                          properties=properties)

        self.assertEqual(mock_image__unify_image.return_value, image)
        self.service._impl.create_image.assert_called_once_with(**callargs)

    @mock.patch("%s.glance_common.UnifiedGlanceMixin._unify_image" % PATH)
    def test_update_image(self, mock_image__unify_image):
        image_id = "image_id"
        image_name = "image_name"
        callargs = {"image_id": image_id,
                    "image_name": image_name,
                    "min_disk": 0,
                    "min_ram": 0,
                    "remove_props": None}

        image = self.service.update_image(image_id,
                                          image_name=image_name)

        self.assertEqual(mock_image__unify_image.return_value, image)
        self.service._impl.update_image.assert_called_once_with(**callargs)

    @mock.patch("%s.glance_common.UnifiedGlanceMixin._unify_image" % PATH)
    def test_list_images(self, mock_image__unify_image):
        images = [mock.MagicMock()]
        self.service._impl.list_images.return_value = images

        status = "active"
        self.assertEqual([mock_image__unify_image.return_value],
                         self.service.list_images(owner="foo",
                                                  visibility="shared"))
        self.service._impl.list_images.assert_called_once_with(
            status=status,
            visibility="shared",
            owner="foo"
        )

    def test_set_visibility(self):
        image_id = "image_id"
        visibility = "private"

        self.service.set_visibility(image_id=image_id, visibility=visibility)
        self.service._impl.set_visibility.assert_called_once_with(
            image_id=image_id, visibility=visibility)

    def test_stage_image_data(self):
        image_id = "image_id"
        image_location = "/path/to/image.qcow2"

        self.service.stage_image_data(image_id=image_id,
                                      image_location=image_location)
        self.service._impl.stage_image_data.assert_called_once_with(
            image_id=image_id,
            image_location=image_location)

    @mock.patch("%s.glance_common.UnifiedGlanceMixin._unify_image" % PATH)
    def test_create_image_for_import(self, mock_image__unify_image):
        image_name = "image_name"
        container_format = "container_format"
        disk_format = "disk_format"
        visibility = "public"
        properties = {"fakeprop": "fake"}
        callargs = {"image_name": image_name,
                    "container_format": container_format,
                    "disk_format": disk_format,
                    "visibility": visibility,
                    "min_disk": 0,
                    "min_ram": 0,
                    "properties": properties}

        image = self.service.create_image_for_import(
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            properties=properties)

        self.assertEqual(mock_image__unify_image.return_value, image)
        self.service._impl.create_image_for_import.assert_called_once_with(
            **callargs)

    def test_create_image_for_import_invalid_visibility(self):
        # Verify VisibilityException is raised for invalid visibility
        from rally_openstack.common.services.image import image as image_module

        exc = self.assertRaises(image_module.VisibilityException,
                                self.service.create_image_for_import,
                                image_name="test",
                                container_format="bare",
                                disk_format="qcow2",
                                visibility="invalid_value")
        self.assertIn("Improper visibility value", str(exc))

    @ddt.data(
        {"import_method": "glance-direct", "import_uri": None},
        {"import_method": "web-download",
         "import_uri": "http://example.com/image.qcow2"},
        {"import_method": "glance-download",
         "import_uri": "glance://remote/image-id"},
        {"import_method": "copy-image", "import_uri": None},
    )
    @ddt.unpack
    @mock.patch("%s.glance_common.UnifiedGlanceMixin._unify_image" % PATH)
    def test_import_image(self, mock_image__unify_image, import_method,
                          import_uri):
        image_id = "image_id"
        stores = ["store1"]
        callargs = {"image_id": image_id,
                    "import_method": import_method,
                    "import_uri": import_uri,
                    "stores": stores,
                    "all_stores": False}

        image = self.service.import_image(
            image_id=image_id,
            import_method=import_method,
            import_uri=import_uri,
            stores=stores,
            all_stores=False)

        self.assertEqual(mock_image__unify_image.return_value, image)
        self.service._impl.import_image.assert_called_once_with(**callargs)

    @mock.patch("%s.glance_common.UnifiedGlanceMixin._unify_image" % PATH)
    def test_stage_and_import_image(self, mock_image__unify_image):
        image_id = "image_id"
        image_location = "/path/to/image.qcow2"
        stores = ["store1", "store2"]
        callargs = {"image_id": image_id,
                    "image_location": image_location,
                    "import_method": "glance-direct",
                    "stores": stores,
                    "all_stores": False}

        image = self.service.stage_and_import_image(
            image_id=image_id,
            image_location=image_location,
            import_method="glance-direct",
            stores=stores,
            all_stores=False)

        self.assertEqual(mock_image__unify_image.return_value, image)
        self.service._impl.stage_and_import_image.assert_called_once_with(
            **callargs)
