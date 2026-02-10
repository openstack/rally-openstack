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
import fixtures

from rally_openstack.common.services.image import glance_v2
from tests.unit import test


PATH = "rally_openstack.common.services.image"


@ddt.ddt
class GlanceV2ServiceTestCase(test.TestCase):
    def setUp(self):
        super(GlanceV2ServiceTestCase, self).setUp()
        self.clients = mock.MagicMock()
        self.gc = self.clients.glance.return_value
        self.name_generator = mock.MagicMock()
        self.service = glance_v2.GlanceV2Service(
            self.clients, name_generator=self.name_generator)
        self.mock_wait_for_status = fixtures.MockPatch(
            "rally.task.utils.wait_for_status")
        self.useFixture(self.mock_wait_for_status)

    def _get_temp_file_name(self):
        # return a temp file that will be cleaned automatically
        temp_dir = self.useFixture(fixtures.TempDir())
        return temp_dir.join("temp-file-name")

    @ddt.data({"location": "image_location", "temp": False},
              {"location": "image location", "temp": True})
    @ddt.unpack
    @mock.patch("requests.get")
    def test_upload(self, mock_requests_get, location, temp):
        image_id = "foo"

        # override the location with a private temp file
        if temp:
            location = self._get_temp_file_name()

        self.service.upload_data(image_id, image_location=location)

        mock_requests_get.assert_called_once_with(location, stream=True,
                                                  verify=False)
        self.gc.images.upload.assert_called_once_with(
            image_id, mock_requests_get.return_value.raw)

    @mock.patch("requests.get")
    def test_upload_from_file(self, mock_requests_get):
        image_id = "foo"
        # Create an actual file so os.path.isfile() returns True
        location = self._get_temp_file_name()
        with open(location, "wb") as f:
            f.write(b"fake image data")

        self.service.upload_data(image_id, image_location=location)

        self.assertFalse(mock_requests_get.called)
        self.gc.images.upload.assert_called_once_with(image_id, mock.ANY)

    @mock.patch("%s.glance_v2.GlanceV2Service.upload_data" % PATH)
    def test_create_image(self, mock_upload_data):
        image_name = "image_name"
        container_format = "container_format"
        disk_format = "disk_format"
        visibility = "public"
        properties = {"fakeprop": "fake"}
        location = "location"

        image = self.service.create_image(
            image_name=image_name,
            container_format=container_format,
            image_location=location,
            disk_format=disk_format,
            visibility=visibility,
            properties=properties)

        call_args = {"container_format": container_format,
                     "disk_format": disk_format,
                     "name": image_name,
                     "visibility": visibility,
                     "min_disk": 0,
                     "min_ram": 0,
                     "fakeprop": "fake"}
        self.gc.images.create.assert_called_once_with(**call_args)
        self.assertEqual(image, self.mock_wait_for_status.mock.return_value)
        mock_upload_data.assert_called_once_with(
            self.mock_wait_for_status.mock.return_value.id,
            image_location=location)

    def test_update_image(self):
        image_id = "image_id"
        image_name1 = self.name_generator.return_value
        image_name2 = "image_name"
        min_disk = 0
        min_ram = 0
        remove_props = None

        # case: image_name is None:
        call_args1 = {"image_id": image_id,
                      "name": image_name1,
                      "min_disk": min_disk,
                      "min_ram": min_ram,
                      "remove_props": remove_props}
        image1 = self.service.update_image(image_id=image_id,
                                           image_name=None,
                                           min_disk=min_disk,
                                           min_ram=min_ram,
                                           remove_props=remove_props)
        self.assertEqual(self.gc.images.update.return_value, image1)
        self.gc.images.update.assert_called_once_with(**call_args1)

        # case: image_name is not None:
        call_args2 = {"image_id": image_id,
                      "name": image_name2,
                      "min_disk": min_disk,
                      "min_ram": min_ram,
                      "remove_props": remove_props}
        image2 = self.service.update_image(image_id=image_id,
                                           image_name=image_name2,
                                           min_disk=min_disk,
                                           min_ram=min_ram,
                                           remove_props=remove_props)
        self.assertEqual(self.gc.images.update.return_value, image2)
        self.gc.images.update.assert_called_with(**call_args2)

    def test_list_images(self):
        status = "active"
        kwargs = {"status": status}
        filters = {"filters": kwargs}
        self.gc.images.list.return_value = iter([1, 2, 3])

        self.assertEqual([1, 2, 3], self.service.list_images())
        self.gc.images.list.assert_called_once_with(**filters)

    def test_list_images_with_filters(self):
        self.gc.images.list.return_value = iter([1, 2, 3])

        self.assertEqual(
            [1, 2, 3],
            self.service.list_images(visibility="public", owner="tenant_id"))
        self.gc.images.list.assert_called_once_with(filters={
            "status": "active",
            "visibility": "public",
            "owner": "tenant_id",
        })

    def test_set_visibility(self):
        image_id = "image_id"
        visibility = "shared"
        self.service.set_visibility(image_id=image_id)
        self.gc.images.update.assert_called_once_with(
            image_id,
            visibility=visibility)

    def test_deactivate_image(self):
        image_id = "image_id"
        self.service.deactivate_image(image_id)
        self.gc.images.deactivate.assert_called_once_with(image_id)

    def test_reactivate_image(self):
        image_id = "image_id"
        self.service.reactivate_image(image_id)
        self.gc.images.reactivate.assert_called_once_with(image_id)

    def test_create_image_for_import(self):
        image_name = "image_name"
        container_format = "container_format"
        disk_format = "disk_format"
        visibility = "public"
        properties = {"fakeprop": "fake"}

        image = self.service.create_image_for_import(
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format,
            visibility=visibility,
            properties=properties)

        call_args = {"container_format": container_format,
                     "disk_format": disk_format,
                     "name": image_name,
                     "visibility": visibility,
                     "min_disk": 0,
                     "min_ram": 0,
                     "fakeprop": "fake"}
        self.gc.images.create.assert_called_once_with(**call_args)
        self.assertEqual(image, self.mock_wait_for_status.mock.return_value)
        # Verify wait_for_status was called with 'queued' status (not 'active')
        self.mock_wait_for_status.mock.assert_called_once_with(
            mock.ANY, ["queued"],
            update_resource=mock.ANY,
            timeout=mock.ANY,
            check_interval=mock.ANY)

    def test_create_image_for_import_random_name(self):
        # Test that random name is generated when image_name is None
        container_format = "container_format"
        disk_format = "disk_format"

        self.service.create_image_for_import(
            container_format=container_format,
            disk_format=disk_format)
        call_args = self.gc.images.create.call_args[1]
        self.assertEqual(call_args["name"], self.name_generator.return_value)

    @mock.patch("requests.get")
    def test_stage_image_data_from_url(self, mock_requests_get):
        image_id = "foo"
        location = "http://example.com/image.qcow2"

        self.service.stage_image_data(image_id, image_location=location)

        mock_requests_get.assert_called_once_with(location, stream=True,
                                                  verify=False)
        self.gc.images.stage.assert_called_once_with(
            image_id, mock_requests_get.return_value.raw)

    @mock.patch("requests.get")
    def test_stage_image_data_from_file(self, mock_requests_get):
        image_id = "foo"
        # Create an actual file so os.path.isfile() returns True
        location = self._get_temp_file_name()
        with open(location, "wb") as f:
            f.write(b"fake image data")

        self.service.stage_image_data(image_id, image_location=location)

        # requests.get must not be called when image_location is a file
        self.assertFalse(mock_requests_get.called)
        self.gc.images.stage.assert_called_once_with(
            image_id, mock.ANY)

    @ddt.data(
        {"stores": None, "all_stores": True},
        {"stores": ["store1", "store2"], "all_stores": False},
    )
    @ddt.unpack
    def test_import_image_glance_direct(self, stores, all_stores):
        image_id = "image_id"

        result = self.service.import_image(
            image_id=image_id,
            import_method="glance-direct",
            stores=stores,
            all_stores=all_stores)

        if stores:
            self.gc.images.image_import.assert_called_once_with(
                image_id,
                method="glance-direct",
                stores=stores)
        else:
            self.gc.images.image_import.assert_called_once_with(
                image_id,
                method="glance-direct",
                all_stores=True)

        self.mock_wait_for_status.mock.assert_called_once_with(
            image_id,
            ready_statuses=["active"],
            failure_statuses=["killed", "deleted", "pending_delete", "error"],
            update_resource=mock.ANY,
            timeout=mock.ANY,
            check_interval=mock.ANY)

        self.assertEqual(result, self.mock_wait_for_status.mock.return_value)

    def test_import_image_web_download(self):
        image_id = "image_id"
        import_uri = "http://example.com/image.qcow2"

        result = self.service.import_image(
            image_id=image_id,
            import_method="web-download",
            import_uri=import_uri)

        self.gc.images.image_import.assert_called_once_with(
            image_id,
            method="web-download",
            uri=import_uri,
            all_stores=True)

        self.assertEqual(result, self.mock_wait_for_status.mock.return_value)

    def test_import_image_web_download_missing_uri(self):
        image_id = "image_id"

        self.assertRaises(ValueError,
                          self.service.import_image,
                          image_id=image_id,
                          import_method="web-download")

    def test_import_image_glance_download(self):
        image_id = "image_id"
        import_uri = "glance://remote-glance/source-image-id"

        result = self.service.import_image(
            image_id=image_id,
            import_method="glance-download",
            import_uri=import_uri)

        self.gc.images.image_import.assert_called_once_with(
            image_id,
            method="glance-download",
            uri=import_uri,
            all_stores=True)

        self.assertEqual(result, self.mock_wait_for_status.mock.return_value)

    def test_import_image_copy_image(self):
        image_id = "image_id"
        stores = ["store1", "store2"]

        result = self.service.import_image(
            image_id=image_id,
            import_method="copy-image",
            stores=stores,
            all_stores=False)

        # Verify image_import was called with stores parameter
        self.gc.images.image_import.assert_called_once_with(
            image_id,
            method="copy-image",
            stores=stores)

        self.assertEqual(result, self.mock_wait_for_status.mock.return_value)

    def test_import_image_old_glanceclient(self):
        image_id = "image_id"

        del self.gc.images.image_import

        exc = self.assertRaises(NotImplementedError,
                                self.service.import_image,
                                image_id=image_id)
        self.assertIn("python-glanceclient >= 2.9.0", str(exc))

    @mock.patch("%s.glance_v2.GlanceV2Service.stage_image_data" % PATH)
    @mock.patch("%s.glance_v2.GlanceV2Service.import_image" % PATH)
    def test_stage_and_import_image_success(self, mock_import_image,
                                            mock_stage_image_data):
        image_id = "image_id"
        location = "/path/to/image.qcow2"
        stores = ["store1"]

        result = self.service.stage_and_import_image(
            image_id=image_id,
            image_location=location,
            import_method="glance-direct",
            stores=stores,
            all_stores=False)

        mock_stage_image_data.assert_called_once_with(image_id, location)
        mock_import_image.assert_called_once_with(
            image_id,
            import_method="glance-direct",
            stores=stores,
            all_stores=False)

        self.assertEqual(result, mock_import_image.return_value)

    def test_stage_and_import_image_wrong_method(self):
        image_id = "image_id"
        location = "/path/to/image.qcow2"

        exc = self.assertRaises(ValueError,
                                self.service.stage_and_import_image,
                                image_id=image_id,
                                image_location=location,
                                import_method="web-download")
        self.assertIn("only supports", str(exc))
        self.assertIn("glance-direct", str(exc))


@ddt.ddt
class UnifiedGlanceV2ServiceTestCase(test.TestCase):
    def setUp(self):
        super(UnifiedGlanceV2ServiceTestCase, self).setUp()
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
