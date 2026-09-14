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

import hashlib
import io
import pathlib
from unittest import mock

import fixtures
from openstack import exceptions as sdk_exc

from rally import exceptions

from rally_openstack.common import credential as oscredential
from rally_openstack.common.clients import glance
from tests.unit import test


PATH = "rally_openstack.common.clients.glance"
BASE_PATH = "rally_openstack.common.clients.base"
V2_IMAGE = "openstack.image.v2.image.Image"


class _ClientTestCase(test.TestCase):
    """A glance client whose openstacksdk proxy is the only thing mocked."""

    version = "2"

    def setUp(self):
        super().setUp()
        self.credential = oscredential.OpenStackCredential(
            "http://auth_url/v3", "user", "pass", "tenant")
        self._sleeps = 0
        self.gl = self._make_glance(self.version)

    def _make_glance(self, version="2", cache=None, name_generator=True):
        client = glance.Glance(
            self.credential, {} if cache is None else cache)
        client._clients = mock.Mock()
        if name_generator:
            client._name_generator = mock.Mock(return_value="random_name")
        client._sleeper = mock.Mock(side_effect=self._bounded_sleep)
        client.version = version
        return client

    def _bounded_sleep(self, seconds):
        self._sleeps += 1
        if self._sleeps > 10:
            raise AssertionError(
                "the waiter polled more than 10 times; the mocked image never "
                "reached a terminal status.")

    @property
    def proxy(self):
        return self.gl._clients._conn.image


class GlanceTestCase(_ClientTestCase):

    def setUp(self):
        super().setUp()
        # The v2 resource class is stubbed because the client builds its v2
        # requests through it, and what it is handed is what these tests
        # assert on. Everything else is the real openstacksdk.
        self.image_cls = self.useFixture(fixtures.MockPatch(V2_IMAGE)).mock
        self.created = self.image_cls.new.return_value.create.return_value
        self.created.id = "img-id"

    def some_images(self):
        """Four images, two of them sharing a name."""
        images = []
        for id_, name in (("100", "cirros-uec"),
                          ("101", "cirros-uec-ramdisk"),
                          ("102", "cirros-uec-ramdisk-copy"),
                          ("103", "cirros-uec-ramdisk-copy")):
            image = mock.Mock(id=id_)
            image.name = name
            images.append(image)
        return images

    def image_is(self, status):
        """Answer the waiter with an image in this status."""
        self.proxy.get_image.return_value = mock.Mock(
            id="img-id", status=status)
        return self.proxy.get_image.return_value

    def write_through(self, chunks):
        """Make the mocked sdk write ``chunks`` into the sink it is given."""
        def download_image(image, *, stream, output, chunk_size):
            for chunk in chunks:
                output.write(chunk)
        self.proxy.download_image.side_effect = download_image

    def test_version(self):
        for major, expected in (((2, 16), "2"), ((1, 1), "1"), (None, None)):
            with self.subTest(major=major):
                gl = self._make_glance()
                del gl.version
                gl._clients._conn.image.get_api_major_version.return_value = (
                    major)
                if expected is None:
                    self.assertRaises(exceptions.RallyException,
                                      lambda: gl.version)
                else:
                    self.assertEqual(expected, gl.version)

    def test_v1_v2_guards(self):
        self.gl.version = "2"
        self.assertIs(self.proxy, self.gl._v2)
        self.assertRaises(exceptions.RallyException, lambda: self.gl._v1)

        self.gl.version = "1"
        self.assertIs(self.proxy, self.gl._v1)
        self.assertRaises(exceptions.RallyException, lambda: self.gl._v2)

    def test_v2_only_operations(self):
        self.gl.version = "1"
        for name, kwargs in (("stage_image", {"data": b"payload"}),
                             ("import_image", {}),
                             ("deactivate_image", {}),
                             ("reactivate_image", {})):
            with self.subTest(name):
                self.assertRaises(exceptions.RallyException,
                                  getattr(self.gl, name), "img", **kwargs)

    def test_v1_rejects_v2_only_arguments(self):
        self.gl.version = "1"
        for name, args, kwargs in (
            ("list_images", (), {"visibility": glance.Visibility.SHARED}),
            ("create_image_record", ("name",),
             {"visibility": glance.Visibility.SHARED}),
            ("update_image", ("img",),
             {"visibility": glance.Visibility.COMMUNITY}),
            ("update_image", ("img",), {"remove_properties": ["foo"]}),
        ):
            with self.subTest(f"{name}{kwargs}"):
                self.assertRaises(exceptions.RallyException,
                                  getattr(self.gl, name), *args, **kwargs)

    def test_call(self):
        self.assertIs(self.gl, self.gl(legacy=False))
        self.assertIs(self.gl, self.gl(2, legacy=False))

        pinned = self.gl(1, legacy=False)
        self.gl._clients.override.assert_called_once_with(glance="1")
        self.assertIs(self.gl._clients.override.return_value.glance, pinned)

        # legacy
        self.gl.create_client = mock.Mock()
        self.assertIs(self.gl.create_client.return_value, self.gl())
        self.gl()
        self.gl.create_client.assert_called_once_with(None)

    def test_call_non_legacy_unattached(self):
        self.gl._clients = None
        self.assertRaises(exceptions.RallyException,
                          self.gl, 1, legacy=False)

    @mock.patch(f"{BASE_PATH}.LOG.warning")
    def test_create_client_warns_once(self, mock_log_warning):
        glance.base._reported_legacy_clients.discard("glance")
        self.addCleanup(
            glance.base._reported_legacy_clients.discard, "glance")
        fake_glanceclient = mock.MagicMock()
        self.gl._get_endpoint = mock.Mock(return_value="http://image")
        with (
            mock.patch.dict("sys.modules",
                            {"glanceclient": fake_glanceclient}),
            mock.patch.object(glance.base.LegacyClientCompat, "keystone",
                              new_callable=mock.PropertyMock),
        ):
            self.gl.create_client()
            self.gl.create_client()
        self.assertEqual(1, mock_log_warning.call_count)
        self.assertEqual(2, fake_glanceclient.Client.call_count)

    def test_wait_for_status_ready(self):
        self.proxy.get_image.side_effect = [
            mock.Mock(status="queued"), mock.Mock(status="active")]
        result = self.gl._wait_for_status(
            "img", ready_statuses=["active"], timeout=10, check_interval=0.5)
        self.assertEqual("active", result.status)
        self.gl._sleeper.assert_called_once_with(0.5)

    def test_wait_for_status_is_case_insensitive(self):
        self.image_is("active")
        self.assertIsNotNone(self.gl._wait_for_status(
            "img", ready_statuses=["ACTIVE"], timeout=10, check_interval=1))

    def test_wait_for_status_failures(self):
        for label, seed, timeout, expected in (
            ("failure status", {"return_value": mock.Mock(status="killed")},
             10, exceptions.GetResourceErrorStatus),
            ("never becomes ready",
             {"return_value": mock.Mock(status="queued")},
             0, exceptions.TimeoutException),
            ("image is gone", {"side_effect": sdk_exc.NotFoundException},
             10, exceptions.GetResourceNotFound),
        ):
            with self.subTest(label):
                self.proxy.get_image.reset_mock(
                    return_value=True, side_effect=True)
                self.proxy.get_image.configure_mock(**seed)
                self.assertRaises(expected, self.gl._wait_for_status, "img",
                                  ready_statuses=["active"],
                                  timeout=timeout, check_interval=1)

    def test_wait_for_status_deleted(self):
        self.proxy.get_image.side_effect = sdk_exc.NotFoundException
        self.assertIsNone(self.gl._wait_for_status(
            "img", ready_statuses=["deleted"], timeout=10, check_interval=1,
            check_deletion=True))

    def test_wait_for_image(self):
        image = mock.Mock(status="active")
        self.proxy.get_image.return_value = image
        self.assertIs(image, self.gl.wait_for_image("img", timeout=10,
                                                    check_interval=1))

    def test_wait_for_image_deleted(self):
        self.proxy.get_image.side_effect = sdk_exc.NotFoundException
        self.assertIsNone(self.gl.wait_for_image_deleted(
            "img", timeout=10, check_interval=1))

    def test__data_stream_a_stream_is_yielded_as_is(self):
        with self.gl._data_stream(b"payload") as stream:
            self.assertEqual(b"payload", stream)

    @mock.patch("pathlib.Path.is_file")
    @mock.patch("pathlib.Path.open")
    def test__data_stream_a_path_is_never_sniffed(self, mock_path_open,
                                                  mock_path_is_file):
        opened = mock_path_open.return_value.__enter__.return_value
        with self.gl._data_stream(pathlib.Path("~/an-image")) as stream:
            self.assertIs(opened, stream)
        self.assertFalse(mock_path_is_file.called)
        mock_path_open.assert_called_once_with("rb")

    @mock.patch("pathlib.Path.open")
    @mock.patch("pathlib.Path.is_file", return_value=True)
    def test__data_stream_a_string_that_is_a_file(self, mock_path_is_file,
                                                  mock_path_open):
        opened = mock_path_open.return_value.__enter__.return_value
        with self.gl._data_stream("~/an-image") as stream:
            self.assertIs(opened, stream)
        mock_path_open.assert_called_once_with("rb")

    @mock.patch("requests.get")
    @mock.patch("pathlib.Path.is_file", return_value=False)
    def test__data_stream_a_string_that_is_a_url(self, mock_path_is_file,
                                                 mock_get):
        with self.gl._data_stream("http://example.com/img") as stream:
            self.assertIs(mock_get.return_value.raw, stream)
        mock_get.assert_called_once_with(
            "http://example.com/img", stream=True, verify=True)
        mock_get.return_value.close.assert_called_once_with()

    def test_get_image(self):
        # the sdk takes an id or an image, so both go straight through
        for reference in ("img", mock.Mock(id="img")):
            with self.subTest(type(reference).__name__):
                self.proxy.get_image.reset_mock()
                self.assertIs(self.proxy.get_image.return_value,
                              self.gl.get_image(reference))
                self.proxy.get_image.assert_called_once_with(reference)

    def test_get_image_not_found(self):
        self.proxy.get_image.side_effect = sdk_exc.NotFoundException
        self.assertRaises(exceptions.GetResourceNotFound,
                          self.gl.get_image, "img")

    def test_delete_image(self):
        self.gl.delete_image("img")
        self.proxy.delete_image.assert_called_once_with(
            "img", ignore_missing=False)

    def test_list_images_v2(self):
        for kwargs, query in (
            ({}, {"status": "active"}),
            ({"status": None, "visibility": glance.Visibility.PUBLIC,
              "owner": "tenant-id", "name": "img", "ids": ["id1", "id2"]},
             {"visibility": glance.Visibility.PUBLIC, "owner": "tenant-id",
              "name": "img", "id": "in:id1,id2"}),
        ):
            with self.subTest(str(kwargs)):
                self.proxy.images.reset_mock()
                self.proxy.images.return_value = iter([1, 2, 3])
                self.assertEqual([1, 2, 3], self.gl.list_images(**kwargs))
                self.proxy.images.assert_called_once_with(**query)

    def test_list_images_v2_by_ids_in_batches(self):
        ids = [f"id{i}" for i in range(glance.ID_FILTER_BATCH + 1)]
        self.proxy.images.side_effect = [iter(ids[:-1]), iter(ids[-1:])]
        self.assertEqual(ids, self.gl.list_images(status=None, ids=ids))
        self.assertEqual(
            [mock.call(id=f"in:{','.join(ids[:-1])}"),
             mock.call(id=f"in:{ids[-1]}")],
            self.proxy.images.call_args_list)

    def test_list_images_by_no_ids_at_all(self):
        for version in ("1", "2"):
            with self.subTest(version=version):
                self.gl.version = version
                self.assertEqual([], self.gl.list_images(ids=[]))
                self.assertFalse(self.proxy.images.called)

    def test_visibility_is_everyone(self):
        for visibility in (glance.Visibility.PUBLIC,
                           glance.Visibility.COMMUNITY):
            with self.subTest(visibility.value):
                self.assertTrue(visibility.is_everyone)

        for visibility in (glance.Visibility.PRIVATE,
                           glance.Visibility.SHARED):
            with self.subTest(visibility.value):
                self.assertFalse(visibility.is_everyone)

    def test_deactivate_and_reactivate_image(self):
        for name in ("deactivate_image", "reactivate_image"):
            with self.subTest(name):
                getattr(self.gl, name)("img")
                getattr(self.proxy, name).assert_called_once_with("img")

    def test_find_image_by_name(self):
        uec = self.some_images()[0]
        self.proxy.images.side_effect = [[uec]]
        self.assertIs(uec, self.gl.find_image("cirros-uec"))
        self.proxy.images.assert_called_once_with(
            status=glance.ImageStatus.ACTIVE, name="cirros-uec")

    def test_find_image_by_name_ambiguous(self):
        copy, twin = self.some_images()[2:]
        self.proxy.images.side_effect = [[copy, twin]]
        e = self.assertRaises(exceptions.GetResourceFailure,
                              self.gl.find_image, "cirros-uec-ramdisk-copy")
        self.assertIn("several images bear that name: 102, 103",
                      e.format_message())

    def test_find_image_by_name_falls_back_to_a_pattern(self):
        images = self.some_images()
        self.proxy.images.side_effect = [[], images]
        self.assertIs(images[0], self.gl.find_image("^cirros-uec$"))
        self.assertEqual(
            [mock.call(status=glance.ImageStatus.ACTIVE, name="^cirros-uec$"),
             mock.call(status=glance.ImageStatus.ACTIVE)],
            self.proxy.images.call_args_list)

    def test_find_image_by_name_accurate_does_not_fall_back(self):
        self.proxy.images.side_effect = [[]]
        e = self.assertRaises(exceptions.GetResourceNotFound,
                              self.gl.find_image, "cirros-uec",
                              accurate=True)
        self.assertIn("image named 'cirros-uec' is not found",
                      e.format_message())
        self.proxy.images.assert_called_once_with(
            status=glance.ImageStatus.ACTIVE, name="cirros-uec")

    def test_find_image_by_regex(self):
        images = self.some_images()
        self.proxy.images.side_effect = [images]
        self.assertIs(images[1], self.gl.find_image(regex="ramdisk$"))

    def test_find_image_by_regex_takes_the_latest_of_several(self):
        images = self.some_images()
        self.proxy.images.side_effect = [images]
        self.assertIn(self.gl.find_image(regex="^cirros"), images[2:])

    def test_find_image_by_regex_accurate_refuses_several(self):
        self.proxy.images.side_effect = [self.some_images()]
        e = self.assertRaises(exceptions.GetResourceFailure,
                              self.gl.find_image, regex="^cirros",
                              accurate=True)
        self.assertIn("several images match it: 100, 101, 102, 103",
                      e.format_message())

    def test_find_image_no_match(self):
        for listing in (self.some_images(), []):
            with self.subTest(f"{len(listing)} images listed"):
                self.proxy.images.side_effect = [listing]
                e = self.assertRaises(exceptions.GetResourceNotFound,
                                      self.gl.find_image, regex="-boot$")
                self.assertIn("image matching '-boot$' is not found",
                              e.format_message())

    def test_find_image_multiple(self):
        images = self.some_images()
        self.proxy.images.side_effect = [images[2:], images]
        self.assertEqual(
            images[2:],
            self.gl.find_image("cirros-uec-ramdisk-copy", multiple=True))
        self.assertEqual(images[2:],
                         self.gl.find_image(regex="copy$", multiple=True))

    def test_find_image_filters_reach_the_listing(self):
        self.proxy.images.side_effect = [self.some_images()]
        self.gl.find_image(regex="^cirros", status=None,
                           visibility=glance.Visibility.PUBLIC,
                           owner="tenant-id")
        self.proxy.images.assert_called_once_with(
            visibility=glance.Visibility.PUBLIC, owner="tenant-id")

    def test_find_image_without_a_name_or_a_regex(self):
        self.assertRaises(exceptions.InvalidArgumentsException,
                          self.gl.find_image)
        self.assertFalse(self.proxy.images.called)

    def test_create_image_record(self):
        self.image_is("queued")

        image = self.gl.create_image_record(
            "name",
            container_format=glance.ContainerFormat.BARE,
            disk_format=glance.DiskFormat.QCOW2,
            visibility=glance.Visibility.PRIVATE,
            min_disk=1, min_ram=2, properties={"fakeprop": "fake"})

        self.image_cls.new.assert_called_once_with(
            name="name", min_disk=1, min_ram=2,
            container_format=glance.ContainerFormat.BARE,
            disk_format=glance.DiskFormat.QCOW2,
            visibility=glance.Visibility.PRIVATE, fakeprop="fake")
        self.assertEqual("queued", image.status)

    def test_create_image_record_generates_a_name(self):
        self.image_is("queued")
        self.gl.create_image_record()
        self.assertEqual("random_name",
                         self.image_cls.new.call_args[1]["name"])

    def test_create_image_record_v1_rejects_v2_visibility(self):
        self.gl.version = "1"
        self.assertRaises(exceptions.RallyException,
                          self.gl.create_image_record,
                          "name", visibility=glance.Visibility.SHARED)

    def test_create_image(self):
        self.gl.create_image_record = mock.Mock()
        self.gl.upload_image = mock.Mock()
        created = self.gl.create_image_record.return_value

        result = self.gl.create_image(
            "name", location="loc",
            disk_format=glance.DiskFormat.QCOW2, min_ram=2)

        self.gl.create_image_record.assert_called_once_with(
            "name", container_format=None,
            disk_format=glance.DiskFormat.QCOW2, visibility=None,
            min_disk=0, min_ram=2, properties=None)
        self.gl.upload_image.assert_called_once_with(created.id, data="loc")
        self.assertEqual(self.gl.upload_image.return_value, result)

    def test_upload_image(self):
        self.image_is("active")
        with mock.patch("pathlib.Path.open") as mock_open:
            opened = mock_open.return_value.__enter__.return_value
            image = self.gl.upload_image(
                "img", data=pathlib.Path("/an-image"))
        self.image_cls.existing.assert_called_once_with(id="img")
        self.image_cls.existing.return_value.upload.assert_called_once_with(
            self.proxy, data=opened)
        self.assertEqual("active", image.status)

    def test_stage_image(self):
        self.gl.stage_image("img", data=b"payload")
        self.image_cls.existing.return_value.stage.assert_called_once_with(
            self.proxy, data=b"payload")

    def test_import_image_stages_only_the_data_it_is_given(self):
        self.image_is("active")
        image = self.image_cls.existing.return_value
        for label, kwargs in (("already staged", {}),
                              ("data to stage", {"data": b"payload"})):
            with self.subTest(label):
                image.reset_mock()
                self.gl.import_image("img", **kwargs)
                image.import_image.assert_called_once_with(
                    self.proxy, method=glance.ImportMethod.GLANCE_DIRECT)
                if kwargs:
                    image.stage.assert_called_once_with(
                        self.proxy, data=b"payload")
                else:
                    self.assertFalse(image.stage.called)

    def test_import_image_web_download(self):
        self.image_is("active")
        self.gl.import_image(
            "img", data="http://example.com/img",
            method=glance.ImportMethod.WEB_DOWNLOAD)
        image = self.image_cls.existing.return_value
        _, kwargs = image.import_image.call_args
        self.assertEqual(glance.ImportMethod.WEB_DOWNLOAD, kwargs["method"])
        self.assertEqual("http://example.com/img", kwargs["uri"])
        self.assertFalse(image.stage.called)

    def test_import_image_rejects_an_unknown_method(self):
        # glance would only reject it after the data has been staged
        self.assertRaises(exceptions.RallyException, self.gl.import_image,
                          "img", data="http://example.com/img",
                          method="glance-download")
        self.assertFalse(self.image_cls.existing.return_value.stage.called)

    def test_import_image_web_download_needs_a_url(self):
        for data in (None, b"payload", pathlib.Path("/an-image")):
            with self.subTest(type(data).__name__):
                self.assertRaises(
                    exceptions.RallyException, self.gl.import_image, "img",
                    data=data, method=glance.ImportMethod.WEB_DOWNLOAD)

    def test_import_image_with_stores(self):
        self.image_is("active")
        self.gl.import_image("img", stores=["store1"], all_stores=True)
        image = self.image_cls.existing.return_value
        _, kwargs = image.import_image.call_args
        # stores wins, and glance is left to its own default otherwise
        self.assertNotIn("all_stores", kwargs)
        self.assertEqual(["store1"], [s.id for s in kwargs["stores"]])

        image.import_image.reset_mock()
        self.gl.import_image("img")
        _, kwargs = image.import_image.call_args
        self.assertNotIn("all_stores", kwargs)
        self.assertNotIn("stores", kwargs)

    def test_import_image_fails_on_error_status(self):
        self.image_is("killed")
        self.assertRaises(exceptions.GetResourceErrorStatus,
                          self.gl.import_image, "img")

    def test_update_image(self):
        # only what is given reaches glance: nothing is invented for the rest
        for kwargs in ({"name": "new", "min_ram": 512},
                       {"min_ram": 512},
                       {"visibility": glance.Visibility.SHARED}):
            with self.subTest(str(kwargs)):
                self.proxy.update_image.reset_mock()
                self.assertIs(self.proxy.update_image.return_value,
                              self.gl.update_image("img", **kwargs))
                self.proxy.update_image.assert_called_once_with(
                    "img", **kwargs)

    def test_update_image_without_anything_to_change(self):
        self.assertRaises(exceptions.InvalidArgumentsException,
                          self.gl.update_image, "img")
        self.assertFalse(self.proxy.update_image.called)

    def test_update_image_remove_properties(self):
        self.proxy.get_image.return_value = mock.Mock(
            properties={"foo": 1, "bar": 2})

        result = self.gl.update_image(
            "img", remove_properties=["foo", "bar", "absent"],
            properties={"bar": "kept"})

        patched = self.image_cls.existing.return_value
        patched.patch.assert_called_once_with(
            self.proxy, patch=[{"op": "remove", "path": "/foo"}])
        self.assertEqual(patched.patch.return_value, result)

    def test_update_image_remove_properties_noop(self):
        current = mock.Mock(properties={})
        self.proxy.get_image.return_value = current
        self.assertIs(current, self.gl.update_image(
            "img", remove_properties=["absent"]))

    def test_download_image_counts_the_bytes(self):
        self.write_through([b"1234", b"56"])

        self.assertEqual(6, self.gl.download_image("img"))

        _, kwargs = self.proxy.download_image.call_args
        self.assertTrue(kwargs["stream"])
        self.assertIsInstance(kwargs["output"], glance._CountingSink)

    def test_download_image_to_an_output(self):
        stream = io.BytesIO()
        path = pathlib.Path(
            self.useFixture(fixtures.TempDir()).path) / "img.raw"

        for label, output, read_back in (("file object", stream,
                                          stream.getvalue),
                                         ("path", path, path.read_bytes)):
            with self.subTest(label):
                self.write_through([b"1234", b"56"])
                self.assertEqual(
                    6, self.gl.download_image("img", output=output))
                self.assertEqual(b"123456", read_back())


class V1MetadataTestCase(test.TestCase):
    """Translation between v1's x-image-meta-* headers and a v2 image."""

    def test_meta_to_headers(self):
        headers = glance._v1_meta_to_headers({
            "name": "cirros",
            "min_disk": 0,
            "is_public": True,
            "container_format": glance.ContainerFormat.BARE,
            "checksum": None,
            "properties": {"hw_rng_model": "virtio"},
        })

        self.assertEqual(
            {"x-image-meta-name": "cirros",
             "x-image-meta-min_disk": "0",
             "x-image-meta-is_public": "True",
             "x-image-meta-container_format": "bare",
             "x-image-meta-property-hw_rng_model": "virtio"},
            headers)

    def test_meta_to_headers_rejects_an_unknown_field(self):
        # glance answers an x-image-meta-* header it does not know with
        # "Bad header", so the field is refused before it reaches the wire
        self.assertRaises(exceptions.RallyException,
                          glance._v1_meta_to_headers, {"visibility": "public"})

    def test_meta_from_headers(self):
        meta = glance._v1_meta_from_headers({
            "X-Image-Meta-Name": "cirros",
            "x-image-meta-min_ram": "512",
            "x-image-meta-property-hw_rng_model": "virtio",
            "Content-Length": "0",
        })

        self.assertEqual({"name": "cirros",
                          "min_ram": "512",
                          "properties": {"hw_rng_model": "virtio"}}, meta)

    def test_bool(self):
        for value, expected in (("True", True), ("true", True), ("1", True),
                                ("False", False), ("0", False), ("", False),
                                (True, True), (False, False)):
            with self.subTest(value=value):
                self.assertIs(expected, glance._v1_bool(value))

    def test_image_is_converted_to_v2(self):
        image = glance._v1_image({
            "id": "img", "name": "cirros", "status": "active",
            "size": "13287936", "min_disk": "0", "min_ram": "64",
            "is_public": "True", "protected": "False",
            "properties": {"hw_rng_model": "virtio"},
        })

        self.assertEqual("img", image.id)
        self.assertEqual("cirros", image.name)
        self.assertEqual(13287936, image.size)
        self.assertEqual(64, image.min_ram)
        self.assertEqual("public", image.visibility)
        self.assertIs(False, image.is_protected)
        self.assertEqual({"hw_rng_model": "virtio"}, image.properties)

    def test_image_drops_what_v2_has_no_room_for(self):
        # unknown keys would otherwise be stored as custom properties
        image = glance._v1_image({
            "id": "img", "deleted": "False", "deleted_at": None,
            "location": "file:///x", "properties": {},
        })

        self.assertEqual({}, image.properties)

    def test_enums_render_as_their_value(self):
        # a plain (str, Enum) renders as "ClassName.MEMBER"; the value is what
        # has to reach glance, in a header as much as in a message
        for member in (glance.ImageStatus.ACTIVE, glance.Visibility.PUBLIC,
                       glance.ContainerFormat.BARE, glance.DiskFormat.QCOW2,
                       glance.ImportMethod.WEB_DOWNLOAD):
            with self.subTest(repr(member)):
                self.assertEqual(member.value, str(member))
                self.assertEqual(member.value, f"{member}")


class GlanceV1TestCase(_ClientTestCase):
    """The Image API v1 paths, which speak raw HTTP through the proxy.

    v1 keeps image metadata in headers, so the openstacksdk v1 resource -- it
    models glance's registry API instead -- is unused and nothing beyond the
    proxy is stubbed here: the images the client returns are real resources.
    """

    version = "1"

    def responds(self, method, *, headers=None, json=None):
        """Point one raw v1 verb at a mocked response."""
        response = self.a_response(headers=headers, json=json)
        getattr(self.proxy, method).return_value = response
        return response

    @staticmethod
    def a_response(*, headers=None, json=None):
        response = mock.Mock(status_code=200, headers=headers or {})
        response.json.return_value = json
        return response

    def test_create_image_record(self):
        self.responds("post", json={"image": {"id": "img"}})

        image = self.gl.create_image_record(
            "cirros",
            container_format=glance.ContainerFormat.BARE,
            disk_format=glance.DiskFormat.QCOW2,
            visibility=glance.Visibility.PUBLIC,
            properties={"hw_rng_model": "virtio"})

        # the metadata rides in the headers and the body stays empty: v1
        # would read a body as the image data
        self.proxy.post.assert_called_once_with(
            "/images",
            headers={"x-image-meta-name": "cirros",
                     "x-image-meta-min_disk": "0",
                     "x-image-meta-min_ram": "0",
                     "x-image-meta-container_format": "bare",
                     "x-image-meta-disk_format": "qcow2",
                     "x-image-meta-is_public": "True",
                     "x-image-meta-property-hw_rng_model": "virtio"})
        self.assertEqual("img", image.id)

    def test_create_image_record_leaves_visibility_to_glance(self):
        self.responds("post", json={"image": {"id": "img"}})
        self.gl.create_image_record("cirros")
        self.assertNotIn("x-image-meta-is_public",
                         self.proxy.post.call_args[1]["headers"])

    def test_get_image_reads_the_headers_of_a_head(self):
        # a GET would answer with the image data instead of its metadata
        self.responds("head", headers={"x-image-meta-id": "img",
                                       "x-image-meta-name": "cirros",
                                       "x-image-meta-is_public": "False"})

        image = self.gl.get_image("img")

        self.proxy.head.assert_called_once_with("/images/img")
        self.assertEqual("img", image.id)
        self.assertEqual("cirros", image.name)
        self.assertEqual("private", image.visibility)

    def test_upload_image_puts_the_data_back_on_the_image(self):
        self.responds("put")
        self.responds("head", headers={"x-image-meta-status": "active"})
        self.gl.upload_image("img", data=b"payload")
        self.proxy.put.assert_called_once_with(
            "/images/img",
            headers={"Content-Type": "application/octet-stream",
                     "x-glance-registry-purge-props": "false"},
            data=b"payload")

    def test_update_image(self):
        self.responds("put", json={"image": {"id": "img"}})

        self.gl.update_image("img", name="new", min_ram=64,
                             properties={"hw_rng_model": "virtio"})

        self.proxy.put.assert_called_once_with(
            "/images/img",
            headers={"x-image-meta-name": "new",
                     "x-image-meta-min_ram": "64",
                     "x-image-meta-property-hw_rng_model": "virtio",
                     "x-glance-registry-purge-props": "false"})

    def test_update_image_visibility(self):
        self.responds("put", json={"image": {"id": "img"}})
        for visibility, is_public in ((glance.Visibility.PUBLIC, "True"),
                                      (glance.Visibility.PRIVATE, "False")):
            with self.subTest(visibility.value):
                self.proxy.put.reset_mock()
                self.gl.update_image("img", visibility=visibility)
                self.assertEqual(
                    is_public,
                    self.proxy.put.call_args[1]["headers"][
                        "x-image-meta-is_public"])

    def test_list_images(self):
        self.responds("get", json={"images": [
            {"id": "id1", "owner": "me"},
            {"id": "id2", "owner": "them"},
            {"id": "id3", "owner": "me"},
        ]})

        images = self.gl.list_images(owner="me",
                                     visibility=glance.Visibility.PUBLIC,
                                     ids=["id1", "id2"])

        # the visibility is a v1 filter, the owner is not
        self.assertEqual(["id1"], [i.id for i in images])
        self.proxy.get.assert_called_once_with(
            "/images/detail",
            params={"status": glance.ImageStatus.ACTIVE,
                    "is_public": "True",
                    "limit": glance.V1_PAGE_SIZE})

    def test_list_images_by_owner_asks_for_every_visibility(self):
        # v1 hides other projects' private images unless is_public is pinned
        # to this, which is exactly what an admin cleaning up needs to see
        self.responds("get", json={"images": []})
        self.gl.list_images(owner="them")
        self.assertEqual("None",
                         self.proxy.get.call_args[1]["params"]["is_public"])

    def test_list_images_pages_by_marker(self):
        # v1 truncates a listing and offers no next link to follow
        full_page = [{"id": f"id{i}"} for i in range(glance.V1_PAGE_SIZE)]
        self.proxy.get.side_effect = [
            self.a_response(json={"images": full_page}),
            self.a_response(json={"images": [{"id": "last"}]}),
        ]

        images = self.gl.list_images(status=None)

        self.assertEqual(glance.V1_PAGE_SIZE + 1, len(images))
        self.assertEqual("last", images[-1].id)
        self.assertEqual(
            [mock.call("/images/detail",
                       params={"limit": glance.V1_PAGE_SIZE}),
             mock.call("/images/detail",
                       params={"limit": glance.V1_PAGE_SIZE,
                               "marker": f"id{glance.V1_PAGE_SIZE - 1}"})],
            self.proxy.get.call_args_list)

    def test_download_image(self):
        payload = b"123456"
        response = self.responds("get", headers={
            "x-image-meta-checksum": hashlib.md5(payload).hexdigest()})
        response.iter_content.return_value = [b"1234", b"56"]

        self.assertEqual(6, self.gl.download_image("img"))
        self.proxy.get.assert_called_once_with("/images/img", stream=True)

    def test_download_image_checksum_mismatch(self):
        response = self.responds(
            "get", headers={"x-image-meta-checksum": "not-the-hash"})
        response.iter_content.return_value = [b"123456"]

        self.assertRaises(sdk_exc.InvalidResponse,
                          self.gl.download_image, "img")

    def test_a_failing_request_is_raised(self):
        # the proxy defaults to raise_exc=False, so a 4xx would otherwise
        # arrive as an ordinary response and read as success
        self.proxy.head.return_value = mock.Mock(
            status_code=404, headers={}, content=b"", reason="Not Found")
        self.assertRaises(exceptions.GetResourceNotFound,
                          self.gl.get_image, "img")
