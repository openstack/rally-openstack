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

import contextlib
import enum
import functools
import hashlib
import io
import pathlib
import re
import sys
import time
import typing as t

import typing_extensions as te

from rally import exceptions
from rally.common import cfg
from rally.task import atomic

from rally_openstack.common.clients import base


if t.TYPE_CHECKING:
    import requests
    from openstack.image.v1 import _proxy as v1_proxy
    from openstack.image.v2 import _proxy as v2_proxy
    from openstack.image.v2 import image as v2_image

    # v1 metadata is converted to a v2 image on the way in, so callers see a
    # single type whichever version the cloud speaks
    Image = v2_image.Image
    # anything the openstacksdk accepts where an image is expected
    ImageRef = str | Image
    # where the bytes of an image come from: an open stream, a local file, or
    # a string that is either a path or an http(s) URL
    ImageData = t.IO[bytes] | pathlib.Path | str

    F = t.TypeVar("F", bound=t.Callable[..., t.Any])


CONF = cfg.CONF


if sys.version_info >= (3, 11):
    StrEnum = enum.StrEnum
else:
    class StrEnum(str, enum.Enum):  # type: ignore[no-redef]
        """Backport of :class:`enum.StrEnum` for Python 3.10."""

        def __str__(self) -> str:
            return str(self.value)


class ImageStatus(StrEnum):
    """Lifecycle state of an image."""

    QUEUED = "queued"
    SAVING = "saving"
    UPLOADING = "uploading"
    IMPORTING = "importing"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    KILLED = "killed"
    DELETED = "deleted"
    PENDING_DELETE = "pending_delete"


# How many ids one "id=in:..." query may carry before it is split in two.
#   Glance sets no limit; the ids go in the query string, so the bound is the
#   request line a web server accepts (commonly 8 KB).
ID_FILTER_BATCH = 100

FAILURE_STATUSES = (
    ImageStatus.KILLED,
    ImageStatus.DELETED,
    ImageStatus.PENDING_DELETE
)


class ContainerFormat(StrEnum):
    """Container format of an image."""

    AMI = "ami"
    ARI = "ari"
    AKI = "aki"
    BARE = "bare"
    OVF = "ovf"


class DiskFormat(StrEnum):
    """Disk format of an image."""

    AMI = "ami"
    ARI = "ari"
    AKI = "aki"
    VHD = "vhd"
    VMDK = "vmdk"
    RAW = "raw"
    QCOW2 = "qcow2"
    VDI = "vdi"
    ISO = "iso"


class ImportMethod(StrEnum):
    """Way the image data reaches Glance on an interoperable import."""

    GLANCE_DIRECT = "glance-direct"
    WEB_DOWNLOAD = "web-download"


class Visibility(StrEnum):
    """Who can see an image.

    Glance v1 knows only ``public`` and ``private``; ``shared`` and
    ``community`` were introduced by v2.
    """

    PUBLIC = "public"
    PRIVATE = "private"
    SHARED = "shared"
    COMMUNITY = "community"

    @property
    def is_everyone(self) -> bool:
        """Whether any project of the cloud can use an image like this.

        ``private`` reaches only the owner and ``shared`` only the projects
        added to it one by one, so neither can be handed to an arbitrary
        tenant as an id.
        """
        return self in (Visibility.PUBLIC, Visibility.COMMUNITY)


# mypy is still bad on TypedDict support, it does not recognize extra_items yet
class ImageProperties(  # type: ignore[call-arg]
    te.TypedDict, total=False, extra_items=str
):
    """Custom image properties.

    The purpose of this entity is to define a list of properties restricted
    to be passed by end-users as they either conflict with Glance API or
    Rally internal logic
    """

    container_format: te.Never
    disk_format: te.Never
    id: te.Never
    is_public: te.Never
    location: te.Never
    locations: te.Never
    min_disk: te.Never
    min_ram: te.Never
    name: te.Never
    os_hidden: te.Never
    owner: te.Never
    properties: te.Never
    protected: te.Never
    size: te.Never
    status: te.Never
    tags: te.Never
    visibility: te.Never


def _id_of(image: ImageRef) -> str:
    """Return the id of an image object, or the argument if it is one."""
    if isinstance(image, str):
        return image
    return image.id


_V1_META_PREFIX = "x-image-meta-"
_V1_PROP_PREFIX = "x-image-meta-property-"

# What glance v1 accepts as ``x-image-meta-*``. It answers anything else with
# "Bad header", so custom properties travel under _V1_PROP_PREFIX instead.
_V1_META_FIELDS = frozenset((
    "checksum", "container_format", "copy_from", "created_at", "deleted",
    "deleted_at", "disk_format", "id", "is_public", "location", "min_disk",
    "min_ram", "name", "owner", "protected", "size", "status", "store",
    "updated_at", "uri", "virtual_size"
))

_V1_INT_FIELDS = ("size", "min_disk", "min_ram", "virtual_size")

# v1 truncates a listing to ``limit_param_default`` (25) and advertises no
# next link, so pages are walked by marker. glance refuses more than
# ``api_limit_max``, 1000 by default.
V1_PAGE_SIZE = 200


def _v1_bool(value: t.Any) -> bool:
    """Read a v1 boolean, which arrives as a string when it comes in a header.

    Mirrors the ``strutils.bool_from_string`` glance itself applies to
    ``is_public``, ``protected`` and ``deleted``.
    """
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on", "y", "t")


def _v1_meta_to_headers(attrs: t.Mapping[str, t.Any]) -> dict[str, str]:
    """Turn image attributes into the headers glance v1 reads them from.

    Encoding the values is left to requests. python-glanceclient
    percent-encoded them first, but glance never unquotes, so that stored an
    image named ``my image`` as ``my%20image``.
    """
    headers: dict[str, str] = {}
    for key, value in attrs.items():
        if value is None:
            continue
        if key == "properties":
            for prop, prop_value in value.items():
                headers[f"{_V1_PROP_PREFIX}{prop}"] = str(prop_value)
        elif key in _V1_META_FIELDS:
            headers[f"{_V1_META_PREFIX}{key}"] = str(value)
        else:
            raise exceptions.RallyException(
                f"'{key}' is not an image attribute the Image API v1 knows.")
    return headers


def _v1_meta_from_headers(headers: t.Mapping[str, str]) -> dict[str, t.Any]:
    """Read image metadata back out of the headers of a v1 response."""
    meta: dict[str, t.Any] = {"properties": {}}
    for key, value in headers.items():
        key = key.lower()
        if key.startswith(_V1_PROP_PREFIX):
            meta["properties"][key[len(_V1_PROP_PREFIX):]] = value
        elif key.startswith(_V1_META_PREFIX):
            meta[key[len(_V1_META_PREFIX):].replace("-", "_")] = value
    return meta


def _v1_image(meta: t.Mapping[str, t.Any]) -> Image:
    """Build a v2 image out of v1 metadata.

    The two versions describe the same thing in different words, so the
    difference is settled here and everything above this line handles a v2
    image only. Accepts both the strings a HEAD returns and the typed values
    of a ``/images/detail`` listing. Fields v2 has no room for (``deleted``,
    ``location``) are dropped rather than smuggled in as custom properties,
    which is where unknown keys would otherwise land.
    """
    from openstack.image.v2 import image as v2_image

    attrs: dict[str, t.Any] = {
        "properties": dict(meta.get("properties") or {})}
    for key in ("id", "name", "status", "checksum", "container_format",
                "disk_format", "owner", "created_at", "updated_at"):
        if meta.get(key) is not None:
            attrs[key] = meta[key]
    for key in _V1_INT_FIELDS:
        value = meta.get(key)
        if value is not None and value != "":
            attrs[key] = int(value)
    if meta.get("is_public") is not None:
        attrs["visibility"] = (Visibility.PUBLIC if _v1_bool(meta["is_public"])
                               else Visibility.PRIVATE).value
    if meta.get("protected") is not None:
        attrs["is_protected"] = _v1_bool(meta["protected"])
    return v2_image.Image.existing(**attrs)


def _v2_only(method: F) -> F:
    """Refuse an operation the Image API v1 does not have."""
    @functools.wraps(method)
    def wrapper(self: Glance, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if self.version != "2":
            raise exceptions.RallyException(
                f"'{method.__name__}' is not supported by the Image API "
                f"v{self.version}.")
        return method(self, *args, **kwargs)
    return t.cast("F", wrapper)


class _CountingSink(io.RawIOBase):
    """A writable file that counts the bytes passing through it.

    Lets one code path serve both "save the image" and "just measure the
    download": the openstacksdk verifies the checksum only when it has
    somewhere to write to, so discarding the data still has to look like a
    file.
    """

    def __init__(self, target: t.IO[bytes] | None = None) -> None:
        super().__init__()
        self._target = target
        self.count = 0

    def writable(self) -> bool:
        return True

    def write(self, b: t.Any) -> int:
        if self._target is not None:
            self._target.write(b)
        self.count += len(b)
        return len(b)


@base.configure(
    "glance", default_version="2", default_service_type="image",
    supported_versions=("1", "2")
)
class Glance(base.LegacyClientCompat):
    """Image (glance) client backed by openstacksdk.

    Provides version-agnostic image operations that work against both Glance
    v1 and v2. Each operation records a ``glance.<op>`` atomic action wrapping
    the version-specific ``glance_v{1,2}.<op>`` one.
    """

    def create_client(
        self, version: str | int | None = None, service_type: str | None = None
    ) -> t.Any:
        """Return a raw python-glanceclient."""
        base.warn_legacy_client("glance")

        import glanceclient as glance

        return glance.Client(
            version=self.spec.choose_version(self.credential, version),
            endpoint_override=self._get_endpoint(service_type),
            session=self.keystone.get_session()[0])

    @t.overload
    def __call__(
        self, version: str | int | None = ..., *, legacy: t.Literal[False]
    ) -> te.Self: ...

    @t.overload
    def __call__(
        self, version: str | int | None = ..., *, legacy: t.Literal[True] = ...
    ) -> t.Any: ...

    def __call__(
        self, version: str | int | None = None, *, legacy: bool = True
    ) -> t.Any:
        """Return an image client.

        :param version: API major version to pin to.
        :param legacy: when true (the default, for backward compatibility),
            return the raw ``python-glanceclient``. This is deprecated and
            emits a warning. Pass ``legacy=False`` to get this client instead,
            pinned to ``version`` when given.
        """
        if legacy:
            key = f"glance_legacy_client_{version}"
            if key not in self._cache:
                self._cache[key] = self.create_client(version)
            return self._cache[key]
        if version is None or str(version) == self.version:
            return self
        if self._clients is None:
            raise exceptions.RallyException(
                "Cannot pin a version on a client that is not attached to a "
                "Clients container.")
        return self._clients.override(glance=str(version)).glance

    @functools.cached_property
    def version(self) -> str:
        major = self._image.get_api_major_version()
        if not major:
            raise exceptions.RallyException(
                "Unable to determine the image API version.")
        return str(major[0])

    @property
    def _image(self) -> v1_proxy.Proxy | v2_proxy.Proxy:
        return self._conn.image

    @property
    def _v1(self) -> v1_proxy.Proxy:
        if self.version != "1":
            raise exceptions.RallyException(
                f"image v1 proxy requested while running v{self.version}.")
        return t.cast("v1_proxy.Proxy", self._conn.image)

    @property
    def _v2(self) -> v2_proxy.Proxy:
        if self.version != "2":
            raise exceptions.RallyException(
                f"image v2 proxy requested while running v{self.version}.")
        return t.cast("v2_proxy.Proxy", self._conn.image)

    def _v1_request(
        self, method: str, url: str, **kwargs: t.Any
    ) -> requests.Response:
        """Issue a raw v1 request, raising on anything but success.

        The proxy defaults to ``raise_exc=False``, so without this a 4xx
        comes back as an ordinary response and reads as success.
        """
        from openstack import exceptions as sdk_exc

        response = getattr(self._v1, method)(url, **kwargs)
        sdk_exc.raise_from_response(response)
        return response

    def _v1_list_images(self, query: dict[str, t.Any]) -> list[Image]:
        """Page through ``GET /images/detail``.

        v1 truncates a listing to ``limit_param_default`` (25 images) and
        offers no next link, so the pages are walked by marker.
        """
        images: list[Image] = []
        marker: str | None = None
        while True:
            params = {**query, "limit": V1_PAGE_SIZE}
            if marker is not None:
                params["marker"] = marker
            page = self._v1_request(
                "get", "/images/detail", params=params).json()["images"]
            images.extend(_v1_image(meta) for meta in page)
            if len(page) < V1_PAGE_SIZE:
                return images
            marker = page[-1]["id"]

    def _v1_download(
        self, image_id: str, sink: _CountingSink, chunk_size: int
    ) -> None:
        """Stream the data of a v1 image into ``sink``, checking its hash."""
        from openstack import exceptions as sdk_exc

        response = self._v1_request("get", f"/images/{image_id}", stream=True)
        expected = response.headers.get("x-image-meta-checksum")
        hasher = hashlib.md5(usedforsecurity=False) if expected else None
        try:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if hasher is not None:
                    hasher.update(chunk)
                sink.write(chunk)
        finally:
            response.close()
        if hasher is not None and hasher.hexdigest() != expected:
            raise sdk_exc.InvalidResponse(
                f"checksum mismatch (md5): {expected} != {hasher.hexdigest()}")

    @contextlib.contextmanager
    def _data_stream(self, data: ImageData) -> t.Iterator[t.Any]:
        """Yield a readable stream for image data.

        A :class:`pathlib.Path` is a local file and a stream is passed
        through; only a plain string is guessed at, and then only because a
        task hands its image location over as one.
        """
        if isinstance(data, pathlib.Path):
            with data.expanduser().open("rb") as stream:
                yield stream
            return
        if not isinstance(data, str):
            yield data
            return

        path = pathlib.Path(data).expanduser()
        if path.is_file():
            with path.open("rb") as stream:
                yield stream
            return
        import requests

        response = requests.get(
            data,
            stream=True,
            verify=(self.credential.https_cacert
                    or not self.credential.https_insecure)
        )
        try:
            yield response.raw
        finally:
            response.close()

    @t.overload
    def _wait_for_status(
        self,
        image: ImageRef,
        *,
        ready_statuses: t.Sequence[str],
        timeout: float,
        check_interval: float,
        failure_statuses: t.Sequence[str] = ...,
        check_deletion: t.Literal[False] = ...,
    ) -> Image: ...

    @t.overload
    def _wait_for_status(
        self,
        image: ImageRef,
        *,
        ready_statuses: t.Sequence[str],
        timeout: float,
        check_interval: float,
        failure_statuses: t.Sequence[str] = ...,
        check_deletion: t.Literal[True],
    ) -> Image | None: ...

    def _wait_for_status(
        self,
        image: ImageRef,
        *,
        ready_statuses: t.Sequence[str],
        timeout: float,
        check_interval: float,
        failure_statuses: t.Sequence[str] = FAILURE_STATUSES,
        check_deletion: bool = False,
    ) -> Image | None:
        """Poll an image until it reaches one of ``ready_statuses``.

        Mirrors ``rally.task.utils.wait_for_status`` but sleeps through
        ``self._sleeper``, so the delay is abort-aware and counts toward the
        owning scenario's idle duration. Worth lifting into
        ``rally_openstack.common.clients.base.BaseClient`` once a second
        client needs to wait for something.

        Returns ``None`` only when ``check_deletion`` is set and the image is
        already gone.
        """
        image_id = _id_of(image)
        ready = {s.upper() for s in ready_statuses}
        failure = {s.upper() for s in failure_statuses} - ready
        start = time.time()
        while True:
            try:
                resource = self.get_image(image_id)
            except exceptions.GetResourceNotFound:
                if check_deletion:
                    return None
                raise
            status = (resource.status or "").upper()
            if status in ready:
                return resource
            if status in failure:
                raise exceptions.GetResourceErrorStatus(
                    resource=resource, status=status,
                    fault=f"Status in failure list {sorted(failure)}")
            self._sleeper(check_interval)
            if time.time() - start > timeout:
                raise exceptions.TimeoutException(
                    desired_status="('%s')" % "', '".join(sorted(ready)),
                    resource_name=getattr(resource, "name", None) or image_id,
                    resource_type=type(resource).__name__,
                    resource_id=image_id,
                    resource_status=status,
                    timeout=timeout)

    @staticmethod
    def _check_v1_visibility(visibility: Visibility | None) -> None:
        if visibility is None:
            return
        if visibility not in (Visibility.PUBLIC, Visibility.PRIVATE):
            raise exceptions.RallyException(
                f"'{visibility.value}' visibility is not supported by "
                f"the Image API v1. "
                f"Use '{Visibility.PUBLIC.value}' or "
                f"'{Visibility.PRIVATE.value}'.")

    @atomic.action_timer("glance.create_image_record")
    def create_image_record(
        self,
        name: str | None = None,
        *,
        container_format: ContainerFormat | None = None,
        disk_format: DiskFormat | None = None,
        visibility: Visibility | None = None,
        min_disk: int = 0,
        min_ram: int = 0,
        properties: ImageProperties | None = None,
    ) -> Image:
        """Create the image record, without any data.

        The image is left in ``queued`` state. Use ``create_image`` to get
        a complete, ``active`` image in one call.

        :param name: name of the image; a random one is generated when omitted
        :param container_format: container format of the image
        :param disk_format: disk format of the image
        :param visibility: who the image is visible to
        :param min_disk: minimum disk size, in GB, required to boot the image
        :param min_ram: minimum RAM, in MB, required to boot the image
        :param properties: custom image properties
        """
        # Both branches go through the resource rather than the proxy's own
        # create_image: that one is the shade-era one-shot, which dedupes by
        # name, adds owner_specified.* properties of its own, may route the
        # data through swift.
        attrs: dict[str, t.Any] = {
            "name": name or self.generate_random_name(),
            "min_disk": min_disk,
            "min_ram": min_ram
        }
        if container_format is not None:
            attrs["container_format"] = container_format
        if disk_format is not None:
            attrs["disk_format"] = disk_format

        if self.version == "1":
            self._check_v1_visibility(visibility)
            if visibility is not None:
                attrs["is_public"] = visibility == Visibility.PUBLIC
            if properties:
                attrs["properties"] = properties
            response = self._v1_request(
                "post", "/images", headers=_v1_meta_to_headers(attrs))
            return _v1_image(response.json()["image"])

        from openstack.image.v2 import image as v2_image

        if visibility is not None:
            attrs["visibility"] = visibility
        if properties:
            attrs = {**properties, **attrs}
        with self._atomic_action("glance.create_image_record_request"):
            image = v2_image.Image.new(**attrs).create(self._v2)

        self._sleeper(CONF.openstack.glance_image_create_prepoll_delay)
        return self.wait_for_image(
            image, ready_statuses=[ImageStatus.QUEUED],
            timeout=CONF.openstack.glance_image_create_timeout,
            check_interval=(
                CONF.openstack.glance_image_create_poll_interval))

    @atomic.action_timer("glance.upload_image")
    def upload_image(self, image: ImageRef, *, data: ImageData) -> Image:
        """Upload the data of an existing image and wait for it to go active.

        This is the plain ``PUT /file`` path; see ``import_image`` for the
        interoperable import.

        :param image: image or its id to upload the data to
        :param data: an open stream, a local file, or a string that is either
            a path or an http(s) URL
        """
        # The proxy's upload_image does not do this: on both versions it
        # creates a new image instead of feeding an existing one, and the sdk
        # has it deprecated for removal in 5.0.
        image_id = _id_of(image)
        with (
            self._atomic_action("glance.upload_image_request"),
            self._data_stream(data) as stream,
        ):
            if self.version == "1":
                # v1 has no upload endpoint: the data is PUT back onto the
                # image itself. The content type is what tells v1 the body
                # is image data rather than metadata, and it rejects the
                # upload without it; the purge-props header keeps glance
                # from dropping the properties set at create time.
                self._v1_request(
                    "put", f"/images/{image_id}",
                    headers={
                        "Content-Type": "application/octet-stream",
                        "x-glance-registry-purge-props": "false"
                    },
                    data=stream)
            else:

                from openstack.image.v2 import image as v2_image

                v2_image.Image.existing(id=image_id).upload(
                    self._v2, data=stream
                )
        return self.wait_for_image(image_id)

    @atomic.action_timer("glance.stage_image")
    @_v2_only
    def stage_image(self, image: ImageRef, *, data: ImageData) -> None:
        """Put the data in glance's staging area, ready to be imported.

        ``import_image`` calls this itself, so a caller only needs it to stage
        now and import later. Glance accepts it only while the image is
        ``queued``.

        :param image: image or its id to stage the data for
        :param data: an open stream, a local file, or a string that is either
            a path or an http(s) URL
        """
        from openstack.image.v2 import image as v2_image

        with self._data_stream(data) as stream:
            v2_image.Image.existing(id=_id_of(image)).stage(
                self._v2, data=stream)

    @atomic.action_timer("glance.import_image")
    @_v2_only
    def import_image(
        self,
        image: ImageRef,
        *,
        data: ImageData | None = None,
        method: ImportMethod = ImportMethod.GLANCE_DIRECT,
        stores: list[str] | None = None,
        all_stores: bool | None = None,
    ) -> Image:
        """Run an interoperable image import and wait for it to finish.

        How ``data`` reaches glance is what the import method selects, and
        this call does whichever the method needs: ``glance-direct`` stages
        the data first and then imports it from the staging area, while
        ``web-download`` just hands glance the URL to fetch. Staging is
        reported as its own action either way, so the two phases stay
        measurable.

        Pass no ``data`` with ``glance-direct`` to import what an earlier
        ``stage_image`` already put in the staging area.

        :param image: image or its id to import the data for
        :param data: an open stream, a local file, or a string that is either
            a path or an http(s) URL. ``web-download`` needs a URL, since it
            is glance that fetches it.
        :param method: the import method to ask glance for
        :param stores: stores to import into; mutually exclusive with
            ``all_stores``
        :param all_stores: import into every available store; left to glance's
            own default (a single store) when unset
        """
        from openstack.image.v2 import image as v2_image
        from openstack.image.v2 import service_info as v2_service_info

        try:
            method = ImportMethod(method)
        except ValueError:
            # left to glance, an unknown method is only rejected after the
            # data has been staged, which can mean transferring the whole
            # image for nothing
            raise exceptions.RallyException(
                f"'{method}' is not an import method rally knows. Use one of: "
                f"{', '.join(m.value for m in ImportMethod)}.") from None

        params: dict[str, t.Any] = {}
        if method == ImportMethod.WEB_DOWNLOAD:
            if not isinstance(data, str):
                raise exceptions.RallyException(
                    f"'{ImportMethod.WEB_DOWNLOAD.value}' needs a URL to "
                    f"fetch, since glance downloads the data itself.")
            params["uri"] = data
            data = None
        if stores:
            params["stores"] = [v2_service_info.Store(id=s) for s in stores]
        elif all_stores is not None:
            params["all_stores"] = all_stores

        image_id = _id_of(image)
        if data is not None:
            self.stage_image(image_id, data=data)
        with self._atomic_action("glance.import_image_request"):
            # The proxy helper refuses an image it has not fetched (it
            # asserts container_format/disk_format), so the request is
            # issued from the resource itself, off a bare id.
            v2_image.Image.existing(id=image_id).import_image(
                self._v2, method=method, **params)
        return self.wait_for_image(
            image_id, ready_statuses=[ImageStatus.ACTIVE],
            timeout=CONF.openstack.glance_image_import_timeout,
            check_interval=(
                CONF.openstack.glance_image_import_poll_interval))

    @atomic.action_timer("glance.create_image")
    def create_image(
        self,
        name: str | None = None,
        *,
        location: ImageData,
        container_format: ContainerFormat | None = None,
        disk_format: DiskFormat | None = None,
        visibility: Visibility | None = None,
        min_disk: int = 0,
        min_ram: int = 0,
        properties: ImageProperties | None = None,
    ) -> Image:
        """Create an image and get its data in, in one call.

        Composes ``create_image_record`` and ``upload_image``, both of which
        keep recording their own actions. The returned image is ``active``.

        :param location: where the image data is.  a string that is either a
            path or an http(s) URL, or a local file or open stream when the
            caller has one
        """
        image = self.create_image_record(
            name, container_format=container_format, disk_format=disk_format,
            visibility=visibility, min_disk=min_disk, min_ram=min_ram,
            properties=properties)
        return self.upload_image(image.id, data=location)

    @atomic.action_timer("glance.update_image")
    def update_image(
        self,
        image: ImageRef,
        *,
        name: str | None = None,
        visibility: Visibility | None = None,
        min_disk: int | None = None,
        min_ram: int | None = None,
        properties: ImageProperties | None = None,
        remove_properties: list[str] | None = None,
    ) -> Image:
        """Update an image.

        Only the arguments that are given are changed.

        :param image: image or its id to update
        :param name: new image name
        :param visibility: who the image should be visible to
        :param min_disk: new minimum disk size, in GB
        :param min_ram: new minimum RAM, in MB
        :param properties: custom image properties to set
        :param remove_properties: names of custom image properties to drop
        :raises InvalidArgumentsException: when nothing to change is given
        """
        if (name is None and visibility is None and min_disk is None
                and min_ram is None and not properties
                and not remove_properties):
            raise exceptions.InvalidArgumentsException(
                "Nothing to update: none of 'name', 'visibility', 'min_disk', "
                "'min_ram', 'properties' or 'remove_properties' is given.")

        attrs: dict[str, t.Any] = {}
        if name is not None:
            attrs["name"] = name
        if min_disk is not None:
            attrs["min_disk"] = min_disk
        if min_ram is not None:
            attrs["min_ram"] = min_ram

        if self.version == "1":
            if remove_properties:
                raise exceptions.RallyException(
                    f"Removing properties ({remove_properties}) is not "
                    f"supported by the Image API v1.")
            if visibility is not None:
                self._check_v1_visibility(visibility)
                attrs["is_public"] = visibility == Visibility.PUBLIC
            if properties:
                attrs["properties"] = properties
            with self._atomic_action("glance.update_image_request"):
                response = self._v1_request(
                    "put", f"/images/{_id_of(image)}",
                    headers={
                        **_v1_meta_to_headers(attrs),
                        # without this v1 drops every property the call does
                        # not restate
                        "x-glance-registry-purge-props": "false"
                    })
            return _v1_image(response.json()["image"])

        if visibility is not None:
            attrs["visibility"] = visibility
        if properties:
            attrs = {**properties, **attrs}
        if not remove_properties:
            with self._atomic_action("glance.update_image_request"):
                return self._v2.update_image(image, **attrs)

        from openstack.image.v2 import image as v2_image

        # Glance rejects a "remove" operation for a property the image does
        # not carry, so the list is intersected with what is actually set; a
        # property being written by the same call is never removed. An id is
        # all we have to go on, whereas an image object is taken at its word.
        current = self.get_image(image) if isinstance(image, str) else image
        removable = ((set(current.properties or {}) & set(remove_properties))
                     - set(attrs))
        patch = [{"op": "remove", "path": f"/{prop}"}
                 for prop in sorted(removable)]
        if not patch and not attrs:
            return current
        patched = v2_image.Image.existing(id=current.id)
        for key, value in attrs.items():
            setattr(patched, key, value)
        with self._atomic_action("glance.update_image_request"):
            return patched.patch(self._v2, patch=patch)

    def list_images(
        self,
        *,
        status: ImageStatus | None = ImageStatus.ACTIVE,
        visibility: Visibility | None = None,
        owner: str | None = None,
        name: str | None = None,
        ids: list[str] | None = None,
    ) -> list[Image]:
        """List images.

        :param status: only images in this status; ``None`` for any
        :param visibility: only images with this visibility
        :param owner: only images owned by this project id
        :param name: only images with this exact name
        :param ids: only images with one of these ids; an empty sequence
            matches nothing and no request is made. Long lists are asked for
            in batches, so the caller does not have to care how many ids it
            has. Each batch is a request of its own and is timed as one.
        """
        if ids is not None and not ids:
            return []

        filters: dict[str, t.Any] = {}
        if status:
            filters["status"] = status
        if name:
            filters["name"] = name

        if self.version == "1":
            self._check_v1_visibility(visibility)
            if visibility:
                filters["is_public"] = str(visibility == Visibility.PUBLIC)
            elif owner:
                # v1 shows public and own images unless is_public is pinned
                # to this, which an admin needs to reach another project's
                # private ones
                filters["is_public"] = "None"
            with self._atomic_action("glance.list_images"):
                images = self._v1_list_images(filters)
            # owner is not among v1's filters, so it is matched here
            if owner:
                images = [i for i in images if i.owner == owner]
            if ids:
                wanted = set(ids)
                images = [i for i in images if i.id in wanted]
            return images

        if visibility:
            filters["visibility"] = visibility
        if owner:
            filters["owner"] = owner
        if not ids:
            with self._atomic_action("glance.list_images"):
                return list(self._v2.images(**filters))
        images = []
        for i in range(0, len(ids), ID_FILTER_BATCH):
            batch = ids[i:i + ID_FILTER_BATCH]
            with self._atomic_action("glance.list_images"):
                images.extend(
                    self._v2.images(id=f"in:{','.join(batch)}", **filters))
        return images

    @t.overload
    def find_image(
        self,
        name: str | None = ...,
        *,
        regex: str | None = ...,
        accurate: bool = ...,
        multiple: t.Literal[False] = ...,
        status: ImageStatus | None = ...,
        visibility: Visibility | None = ...,
        owner: str | None = ...,
    ) -> Image: ...

    @t.overload
    def find_image(
        self,
        name: str | None = ...,
        *,
        regex: str | None = ...,
        accurate: bool = ...,
        multiple: t.Literal[True],
        status: ImageStatus | None = ...,
        visibility: Visibility | None = ...,
        owner: str | None = ...,
    ) -> list[Image]: ...

    @atomic.action_timer("glance.find_image")
    def find_image(
        self,
        name: str | None = None,
        *,
        regex: str | None = None,
        accurate: bool = False,
        multiple: bool = False,
        status: ImageStatus | None = ImageStatus.ACTIVE,
        visibility: Visibility | None = None,
        owner: str | None = None,
    ) -> Image | list[Image]:
        """Find the image, or the images, matching a name or a pattern.

        An exact ``name`` is asked of glance itself. When it matches nothing
        and ``accurate`` is not set, the name is retried as a regular
        expression over the images the filters leave, which is also how
        ``regex`` is always matched: glance compares names for equality and
        for membership of a list, never against a pattern.

        :param name: the exact name of the image, tried as a regular
            expression when nothing bears it
        :param regex: a regular expression to match image names against
        :param accurate: fail instead of falling back to the pattern match, or
            instead of picking the latest of several matches
        :param multiple: return every match instead of a single image
        :param status: only consider images in this status; ``None`` for any
        :param visibility: only consider images with this visibility
        :param owner: only consider images owned by this project id
        :raises InvalidArgumentsException: when the arguments describe no
            image at all
        :raises GetResourceNotFound: when nothing matches
        :raises GetResourceFailure: when several images match and only one
            was asked for
        """
        if not name and not regex:
            raise exceptions.InvalidArgumentsException(
                "Neither 'name' nor 'regex' is given, so there is nothing to "
                "look an image up by.")

        filters: dict[str, t.Any] = {
            "status": status, "visibility": visibility, "owner": owner}
        if name:
            named = self.list_images(name=name, **filters)
            if named:
                if multiple:
                    return named
                if len(named) > 1:
                    raise exceptions.GetResourceFailure(
                        resource=f"image named '{name}'",
                        err=(
                            "several images bear that name: "
                            + ", ".join(image.id for image in named))
                    )
                return named[0]
            if accurate:
                raise exceptions.GetResourceNotFound(
                    resource=f"image named '{name}'")

        pattern = re.compile(t.cast("str", regex or name))
        matching = [image for image in self.list_images(**filters)
                    if pattern.search(image.name or "")]
        if not matching:
            raise exceptions.GetResourceNotFound(
                resource=f"image matching '{pattern.pattern}'")
        if multiple:
            return matching
        if len(matching) > 1:
            if accurate:
                raise exceptions.GetResourceFailure(
                    resource=f"image matching '{pattern.pattern}'",
                    err=("several images match it: "
                         + ", ".join(image.id for image in matching))
                )
            return sorted(matching, key=lambda i: i.name or "")[-1]
        return matching[0]

    @atomic.action_timer("glance.get_image")
    def get_image(self, image: ImageRef) -> Image:
        """Return an image by id.

        :raises GetResourceNotFound: when the image does not exist
        """
        from openstack import exceptions as sdk_exc

        image_id = _id_of(image)
        try:
            if self.version == "1":
                # a GET here would answer with the image data instead
                response = self._v1_request("head", f"/images/{image_id}")
                return _v1_image(_v1_meta_from_headers(response.headers))
            return self._image.get_image(image)
        except sdk_exc.NotFoundException:
            raise exceptions.GetResourceNotFound(resource=image_id) from None

    @atomic.action_timer("glance.delete_image")
    def delete_image(self, image: ImageRef) -> None:
        """Delete an image."""
        self._image.delete_image(image, ignore_missing=False)

    @atomic.action_timer("glance.download_image")
    def download_image(
        self,
        image: ImageRef,
        *,
        output: str | pathlib.Path | t.IO[bytes] | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> int:
        """Download the data of an image.

        The data is always transferred: with ``output`` it is written there,
        otherwise it is read and discarded. Either way the action measures the
        real transfer, not just the request setup, and the openstacksdk
        verifies the checksum on the way past.

        :param image: image or its id to download
        :param output: a path or a file object to write the data into
        :param chunk_size: how much to read from the wire at a time
        :returns: number of bytes transferred
        """
        with contextlib.ExitStack() as stack:
            target: t.IO[bytes] | None = None
            if isinstance(output, (str, pathlib.Path)):
                target = stack.enter_context(
                    pathlib.Path(output).expanduser().open("wb"))
            elif output is not None:
                target = output
            sink = _CountingSink(target)
            if self.version == "1":
                self._v1_download(_id_of(image), sink, chunk_size)
            else:
                self._image.download_image(
                    image, stream=True, output=sink, chunk_size=chunk_size)
            return sink.count

    @atomic.action_timer("glance.deactivate_image")
    @_v2_only
    def deactivate_image(self, image: ImageRef) -> None:
        """Deactivate an image, making its data unavailable."""
        self._v2.deactivate_image(image)

    @atomic.action_timer("glance.reactivate_image")
    @_v2_only
    def reactivate_image(self, image: ImageRef) -> None:
        """Reactivate a deactivated image."""
        self._v2.reactivate_image(image)

    def wait_for_image(
        self,
        image: ImageRef,
        *,
        ready_statuses: t.Sequence[str] = (ImageStatus.ACTIVE,),
        timeout: float | None = None,
        check_interval: float | None = None,
    ) -> Image:
        """Poll an image until it reaches one of ``ready_statuses``.

        The statuses waited for are part of the atomic action name, since
        waiting for an image to be ``queued`` and waiting for it to be
        ``active`` are not the same thing to compare.
        """

        aa_suffix = "_or_".join(sorted(ready_statuses))

        with self._atomic_action(f"glance.wait_for_image_{aa_suffix}"):
            return self._wait_for_status(
                image,
                ready_statuses=ready_statuses,
                timeout=(timeout
                         if timeout is not None
                         else CONF.openstack.glance_image_create_timeout),
                check_interval=(
                    check_interval if check_interval is not None
                    else CONF.openstack.glance_image_create_poll_interval)
            )

    @atomic.action_timer("glance.wait_for_image_deleted")
    def wait_for_image_deleted(
        self,
        image: ImageRef,
        *,
        timeout: float | None = None,
        check_interval: float | None = None,
    ) -> None:
        """Poll an image until it is gone."""
        self._wait_for_status(
            image,
            ready_statuses=[ImageStatus.DELETED, ImageStatus.PENDING_DELETE],
            failure_statuses=(),
            check_deletion=True,
            timeout=(timeout
                     if timeout is not None
                     else CONF.openstack.glance_image_delete_timeout),
            check_interval=(
                check_interval if check_interval is not None
                else CONF.openstack.glance_image_delete_poll_interval)
        )
