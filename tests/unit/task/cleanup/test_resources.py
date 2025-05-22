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

import copy
from unittest import mock

import ddt
from neutronclient.common import exceptions as neutron_exceptions
from novaclient import exceptions as nova_exc
from watcherclient.common.apiclient import exceptions as watcher_exceptions

from rally_openstack.task.cleanup import resources
from tests.unit import test

BASE = "rally_openstack.task.cleanup.resources"
GLANCE_V2_PATH = ("rally_openstack.common.services.image.glance_v2."
                  "GlanceV2Service")


class SynchronizedDeletionTestCase(test.TestCase):

    def test_is_deleted(self):
        self.assertTrue(resources.SynchronizedDeletion().is_deleted())


class QuotaMixinTestCase(test.TestCase):

    @mock.patch("%s.identity.Identity" % BASE)
    def test_list(self, mock_identity):
        quota = resources.QuotaMixin()
        quota.tenant_uuid = None
        quota.user = mock.MagicMock()
        self.assertEqual([], quota.list())
        self.assertFalse(mock_identity.called)

        quota.tenant_uuid = mock.MagicMock()
        self.assertEqual([mock_identity.return_value.get_project.return_value],
                         quota.list())
        mock_identity.assert_called_once_with(quota.user)


class MagnumMixinTestCase(test.TestCase):

    def test_id(self):
        magnum = resources.MagnumMixin()
        magnum._service = "magnum"
        magnum.raw_resource = mock.MagicMock()
        self.assertEqual(magnum.raw_resource.uuid, magnum.id())

    def test_list(self):
        magnum = resources.MagnumMixin()
        magnum._service = "magnum"
        some_resources = [mock.MagicMock(), mock.MagicMock(),
                          mock.MagicMock(), mock.MagicMock()]
        magnum._manager = mock.MagicMock()
        magnum._manager.return_value.list.side_effect = (
            some_resources[:2], some_resources[2:4], [])
        self.assertEqual(some_resources, magnum.list())
        self.assertEqual(
            [mock.call(marker=None), mock.call(marker=some_resources[1].uuid),
             mock.call(marker=some_resources[3].uuid)],
            magnum._manager.return_value.list.call_args_list)


class NovaServerTestCase(test.TestCase):

    @mock.patch(BASE + ".nova_utils.list_servers")
    def test_list(self, mock_list_servers):

        user_clients = mock.Mock()
        admin_clients = mock.Mock()

        servers_res = resources.NovaServer(
            admin=admin_clients, user=user_clients
        )

        self.assertEqual(
            mock_list_servers.return_value,
            servers_res.list()
        )
        mock_list_servers.assert_called_once_with(user_clients.nova(),
                                                  detailed=True)

    def test_delete(self):
        server = resources.NovaServer()
        server.raw_resource = mock.Mock()
        server._manager = mock.Mock()
        server.delete()

        server._manager.return_value.delete.assert_called_once_with(
            server.raw_resource.id)

    def test_delete_locked(self):
        server = resources.NovaServer()
        server.raw_resource = mock.Mock()
        setattr(server.raw_resource, "OS-EXT-STS:locked", True)
        server._manager = mock.Mock()
        server.delete()

        server.raw_resource.unlock.assert_called_once_with()
        server._manager.return_value.delete.assert_called_once_with(
            server.raw_resource.id)


class NovaFlavorsTestCase(test.TestCase):

    @mock.patch("%s.base.ResourceManager._manager" % BASE)
    def test_is_deleted(self, mock_resource_manager__manager):
        exc = nova_exc.NotFound(404)
        mock_resource_manager__manager().get.side_effect = exc
        flavor = resources.NovaFlavors()
        flavor.raw_resource = mock.MagicMock()
        self.assertTrue(flavor.is_deleted())

    @mock.patch("%s.base.ResourceManager._manager" % BASE)
    def test_is_deleted_fail(self, mock_resource_manager__manager):
        mock_resource_manager__manager().get.side_effect = TypeError()
        flavor = resources.NovaFlavors()
        flavor.raw_resource = mock.MagicMock()
        self.assertRaises(TypeError, flavor.is_deleted)


class NovaServerGroupsTestCase(test.TestCase):

    @mock.patch("%s.base.ResourceManager._manager" % BASE)
    @mock.patch("rally.common.utils.name_matches_object")
    def test_list(self, mock_name_matches_object,
                  mock_resource_manager__manager):
        server_groups = [mock.MagicMock(name="rally_foo1"),
                         mock.MagicMock(name="rally_foo2"),
                         mock.MagicMock(name="foo3")]
        mock_name_matches_object.side_effect = [False, True, True]
        mock_resource_manager__manager().list.return_value = server_groups
        self.assertEqual(server_groups, resources.NovaServerGroups().list())


class NeutronMixinTestCase(test.TestCase):

    def get_neutron_mixin(self):
        neut = resources.NeutronMixin()
        neut._service = "neutron"
        return neut

    def test_manager(self):
        neut = self.get_neutron_mixin()
        neut.user = mock.MagicMock()
        self.assertEqual(neut.user.neutron.return_value, neut._manager())

    def test_id(self):
        neut = self.get_neutron_mixin()
        neut.raw_resource = {"id": "test"}
        self.assertEqual("test", neut.id())

    def test_name(self):
        neutron = self.get_neutron_mixin()
        neutron.raw_resource = {"id": "test_id", "name": "test_name"}
        self.assertEqual("test_name", neutron.name())

    def test_delete(self):
        neut = self.get_neutron_mixin()
        neut.user = mock.MagicMock()
        neut._resource = "some_resource"
        neut.raw_resource = {"id": "42"}

        neut.delete()
        neut.user.neutron().delete_some_resource.assert_called_once_with("42")

    def test_list(self):
        neut = self.get_neutron_mixin()
        neut.user = mock.MagicMock()
        neut._resource = "some_resource"
        neut.tenant_uuid = "user_tenant"

        some_resources = [{"tenant_id": neut.tenant_uuid}, {"tenant_id": "a"}]
        neut.user.neutron().list_some_resources.return_value = {
            "some_resources": some_resources
        }

        self.assertEqual([some_resources[0]], list(neut.list()))

        neut.user.neutron().list_some_resources.assert_called_once_with(
            tenant_id=neut.tenant_uuid)


class NeutronLbaasV1MixinTestCase(test.TestCase):

    def get_neutron_lbaasv1_mixin(self, extensions=None):
        if extensions is None:
            extensions = []
        user = mock.MagicMock()
        neut = resources.NeutronLbaasV1Mixin(user=user)
        neut._service = "neutron"
        neut._resource = "some_resource"
        neut._manager = mock.Mock()
        user.neutron.return_value.list_extensions.return_value = {
            "extensions": [{"alias": ext} for ext in extensions]
        }
        return neut

    def test_list_lbaas_available(self):
        neut = self.get_neutron_lbaasv1_mixin(extensions=["lbaas"])
        neut.tenant_uuid = "user_tenant"

        some_resources = [{"tenant_id": neut.tenant_uuid}, {"tenant_id": "a"}]
        neut._manager().list_some_resources.return_value = {
            "some_resources": some_resources
        }

        self.assertEqual([some_resources[0]], list(neut.list()))
        neut._manager().list_some_resources.assert_called_once_with(
            tenant_id=neut.tenant_uuid)

    def test_list_lbaas_unavailable(self):
        neut = self.get_neutron_lbaasv1_mixin()

        self.assertEqual([], list(neut.list()))
        self.assertFalse(neut._manager().list_some_resources.called)


class NeutronLbaasV2MixinTestCase(test.TestCase):

    def get_neutron_lbaasv2_mixin(self, extensions=None):
        if extensions is None:
            extensions = []

        user = mock.MagicMock()
        neut = resources.NeutronLbaasV2Mixin(user=user)
        neut._service = "neutron"
        neut._resource = "some_resource"
        neut._manager = mock.Mock()
        user.neutron.return_value.list_extensions.return_value = {
            "extensions": [{"alias": ext} for ext in extensions]
        }
        return neut

    def test_list_lbaasv2_available(self):
        neut = self.get_neutron_lbaasv2_mixin(extensions=["lbaasv2"])
        neut.tenant_uuid = "user_tenant"

        some_resources = [{"tenant_id": neut.tenant_uuid}, {"tenant_id": "a"}]
        neut._manager().list_some_resources.return_value = {
            "some_resources": some_resources
        }

        self.assertEqual([some_resources[0]], list(neut.list()))
        neut._manager().list_some_resources.assert_called_once_with(
            tenant_id=neut.tenant_uuid)

    def test_list_lbaasv2_unavailable(self):
        neut = self.get_neutron_lbaasv2_mixin()

        self.assertEqual([], list(neut.list()))
        self.assertFalse(neut._manager().list_some_resources.called)


class NeutronV2LoadbalancerTestCase(test.TestCase):

    def get_neutron_lbaasv2_lb(self):
        neutron_lb = resources.NeutronV2Loadbalancer()
        neutron_lb.raw_resource = {"id": "1", "name": "s_rally"}
        neutron_lb._manager = mock.Mock()
        return neutron_lb

    def test_is_deleted_true(self):
        from neutronclient.common import exceptions as n_exceptions
        neutron_lb = self.get_neutron_lbaasv2_lb()
        neutron_lb._manager().show_loadbalancer.side_effect = (
            n_exceptions.NotFound)

        self.assertTrue(neutron_lb.is_deleted())

        neutron_lb._manager().show_loadbalancer.assert_called_once_with(
            neutron_lb.id())

    def test_is_deleted_false(self):
        from neutronclient.common import exceptions as n_exceptions
        neutron_lb = self.get_neutron_lbaasv2_lb()
        neutron_lb._manager().show_loadbalancer.return_value = (
            neutron_lb.raw_resource)

        self.assertFalse(neutron_lb.is_deleted())
        neutron_lb._manager().show_loadbalancer.assert_called_once_with(
            neutron_lb.id())

        neutron_lb._manager().show_loadbalancer.reset_mock()

        neutron_lb._manager().show_loadbalancer.side_effect = (
            n_exceptions.Forbidden)

        self.assertFalse(neutron_lb.is_deleted())
        neutron_lb._manager().show_loadbalancer.assert_called_once_with(
            neutron_lb.id())


class NeutronBgpvpnTestCase(test.TestCase):

    def get_neutron_bgpvpn_mixin(self, extensions=None):
        if extensions is None:
            extensions = []
        admin = mock.Mock()
        neut = resources.NeutronBgpvpn(admin=admin)
        neut._manager = mock.Mock()
        nc = admin.neutron.return_value
        nc.list_extensions.return_value = {
            "extensions": [{"alias": ext} for ext in extensions]
        }
        return neut

    def test_list_user(self):
        neut = self.get_neutron_bgpvpn_mixin(extensions=["bgpvpn"])
        user_bgpvpns = {"bgpvpns": [{"tenant_id": "foo", "id": "bgpvpn_id"}]}
        neut._manager().list_bgpvpns.return_value = user_bgpvpns

        bgpvpns_list = neut.list()
        self.assertEqual("bgpvpn", neut._resource)
        neut._manager().list_bgpvpns.assert_called_once_with()
        self.assertEqual(bgpvpns_list, user_bgpvpns["bgpvpns"])

    def test_list_admin(self):
        neut = self.get_neutron_bgpvpn_mixin(extensions=["bgpvpn"])
        admin_bgpvpns = {"bgpvpns": [{"tenant_id": "foo", "id": "bgpvpn_id"}]}
        neut._manager().list_bgpvpns.return_value = admin_bgpvpns

        self.assertEqual("bgpvpn", neut._resource)
        self.assertEqual(neut.list(), admin_bgpvpns["bgpvpns"])


class NeutronFloatingIPTestCase(test.TestCase):

    def test_name(self):
        fips = resources.NeutronFloatingIP({"name": "foo",
                                            "description": "OoO"})
        self.assertEqual(fips.name(), "OoO")

    def test_list(self):
        fips = {"floatingips": [{"tenant_id": "foo", "id": "foo"}]}

        user = mock.MagicMock()
        user.neutron.return_value.list_floatingips.return_value = fips

        self.assertEqual(fips["floatingips"], list(
            resources.NeutronFloatingIP(user=user, tenant_uuid="foo").list()))
        user.neutron.return_value.list_floatingips.assert_called_once_with(
            tenant_id="foo")


class NeutronTrunkTestcase(test.TestCase):

    def test_list(self):
        user = mock.MagicMock()
        trunk = resources.NeutronTrunk(user=user)
        user.neutron().list_trunks.return_value = {
            "trunks": ["trunk"]}
        self.assertEqual(["trunk"], trunk.list())
        user.neutron().list_trunks.assert_called_once_with(
            tenant_id=None)

    def test_list_with_not_found(self):

        class NotFound(Exception):
            status_code = 404

        user = mock.MagicMock()
        trunk = resources.NeutronTrunk(user=user)
        user.neutron().list_trunks.side_effect = NotFound()

        self.assertEqual([], trunk.list())
        user.neutron().list_trunks.assert_called_once_with(
            tenant_id=None)


class NeutronPortTestCase(test.TestCase):

    def test_delete(self):
        raw_res = {"device_owner": "abbabaab", "id": "some_id"}
        user = mock.MagicMock()

        resources.NeutronPort(resource=raw_res, user=user).delete()

        user.neutron().delete_port.assert_called_once_with(raw_res["id"])

    def test_delete_port_raise_exception(self):
        raw_res = {"device_owner": "abbabaab", "id": "some_id"}
        user = mock.MagicMock()
        user.neutron().delete_port.side_effect = (
            neutron_exceptions.PortNotFoundClient)

        resources.NeutronPort(resource=raw_res, user=user).delete()

        user.neutron().delete_port.assert_called_once_with(raw_res["id"])

    def test_delete_port_device_owner(self):
        raw_res = {
            "device_owner": "network:router_interface",
            "id": "some_id",
            "device_id": "dev_id"
        }
        user = mock.MagicMock()

        resources.NeutronPort(resource=raw_res, user=user).delete()

        user.neutron().remove_interface_router.assert_called_once_with(
            raw_res["device_id"], {"port_id": raw_res["id"]})

    def test_name(self):
        raw_res = {
            "id": "some_id",
            "device_id": "dev_id",
        }

        # automatically created or manually created port. No name field
        self.assertEqual(
            resources.NeutronPort(resource=raw_res,
                                  user=mock.MagicMock()).name(),
            "")

        raw_res["name"] = "foo"
        self.assertEqual("foo", resources.NeutronPort(
            resource=raw_res, user=mock.MagicMock()).name())

        raw_res["parent_name"] = "bar"
        self.assertEqual("bar", resources.NeutronPort(
            resource=raw_res, user=mock.MagicMock()).name())

        del raw_res["name"]
        self.assertEqual("bar", resources.NeutronPort(
            resource=raw_res, user=mock.MagicMock()).name())

    def test_list(self):

        tenant_uuid = "uuuu-uuuu-iiii-dddd"

        ports = [
            # the case when 'name' is present, so 'device_owner' field is not
            #   required
            {"tenant_id": tenant_uuid, "id": "id1", "name": "foo"},
            # 3 different cases when router_interface is an owner
            {"tenant_id": tenant_uuid, "id": "id2",
             "device_owner": "network:router_interface",
             "device_id": "router-1"},
            {"tenant_id": tenant_uuid, "id": "id3",
             "device_owner": "network:router_interface_distributed",
             "device_id": "router-1"},
            {"tenant_id": tenant_uuid, "id": "id4",
             "device_owner": "network:ha_router_replicated_interface",
             "device_id": "router-2"},
            # the case when gateway router is an owner
            {"tenant_id": tenant_uuid, "id": "id5",
             "device_owner": "network:router_gateway",
             "device_id": "router-3"},
            # the case when gateway router is an owner, but device_id is
            #   invalid
            {"tenant_id": tenant_uuid, "id": "id6",
             "device_owner": "network:router_gateway",
             "device_id": "aaaa"},
            # the case when port was auto-created with floating-ip
            {"tenant_id": tenant_uuid, "id": "id7",
             "device_owner": "network:dhcp",
             "device_id": "asdasdasd"},
            # the case when port is from another tenant. it should not be
            #   here as we are filtering by tenant id, but anyway.
            {"tenant_id": "wrong tenant", "id": "id8", "name": "foo"},
            # WTF port without any parent and name
            {"tenant_id": tenant_uuid, "id": "id9", "device_owner": ""},
        ]

        routers = [
            {"id": "router-1", "name": "Router-1", "tenant_id": tenant_uuid},
            {"id": "router-2", "name": "Router-2", "tenant_id": tenant_uuid},
            {"id": "router-3", "name": "Router-3", "tenant_id": tenant_uuid},
            {"id": "router-4", "name": "Router-4", "tenant_id": tenant_uuid},
            {"id": "router-5", "name": "Router-5", "tenant_id": tenant_uuid},
        ]

        expected_ports = []
        for port in ports:
            if port["tenant_id"] == tenant_uuid:
                expected_ports.append(copy.deepcopy(port))
                if ("device_id" in port
                        and port["device_id"].startswith("router")):
                    expected_ports[-1]["parent_name"] = [
                        r for r in routers
                        if r["id"] == port["device_id"]][0]["name"]

        class FakeNeutronClient(object):

            list_ports = mock.Mock()
            list_routers = mock.Mock()

        neutron = FakeNeutronClient
        neutron.list_ports.return_value = {"ports": ports}
        neutron.list_routers.return_value = {"routers": routers}

        user = mock.Mock(neutron=neutron)
        self.assertEqual(expected_ports, resources.NeutronPort(
            user=user, tenant_uuid=tenant_uuid).list())
        neutron.list_ports.assert_called_once_with(tenant_id=tenant_uuid)
        neutron.list_routers.assert_called_once_with(tenant_id=tenant_uuid)


@ddt.ddt
class NeutronSecurityGroupTestCase(test.TestCase):

    @ddt.data(
        {"admin": mock.Mock(), "admin_required": True},
        {"admin": None, "admin_required": False})
    @ddt.unpack
    def test_list(self, admin, admin_required):
        sg_list = [{"tenant_id": "user_tenant", "name": "default"},
                   {"tenant_id": "user_tenant", "name": "foo_sg"}]

        neut = resources.NeutronSecurityGroup()
        neut.user = mock.MagicMock()
        neut._resource = "security_group"
        neut.tenant_uuid = "user_tenant"

        neut.user.neutron().list_security_groups.return_value = {
            "security_groups": sg_list
        }

        expected_result = [sg_list[1]]
        self.assertEqual(expected_result, list(neut.list()))

        neut.user.neutron().list_security_groups.assert_called_once_with(
            tenant_id=neut.tenant_uuid)

    def test_list_with_not_found(self):

        class NotFound(Exception):
            status_code = 404

        neut = resources.NeutronSecurityGroup()
        neut.user = mock.MagicMock()
        neut._resource = "security_group"
        neut.tenant_uuid = "user_tenant"

        neut.user.neutron().list_security_groups.side_effect = NotFound()

        expected_result = []
        self.assertEqual(expected_result, list(neut.list()))

        neut.user.neutron().list_security_groups.assert_called_once_with(
            tenant_id=neut.tenant_uuid)


class NeutronQuotaTestCase(test.TestCase):

    def test_delete(self):
        admin = mock.MagicMock()
        resources.NeutronQuota(admin=admin, tenant_uuid="fake").delete()
        admin.neutron.return_value.delete_quota.assert_called_once_with("fake")


@ddt.ddt
class GlanceImageTestCase(test.TestCase):

    @mock.patch("rally_openstack.common.services.image.image.Image")
    def test__client_admin(self, mock_image):
        admin = mock.Mock()
        glance = resources.GlanceImage(admin=admin)
        client = glance._client()

        mock_image.assert_called_once_with(admin)
        self.assertEqual(client, mock_image.return_value)

    @mock.patch("rally_openstack.common.services.image.image.Image")
    def test__client_user(self, mock_image):
        user = mock.Mock()
        glance = resources.GlanceImage(user=user)
        wrapper = glance._client()

        mock_image.assert_called_once_with(user)
        self.assertEqual(wrapper, mock_image.return_value)

    @mock.patch("rally_openstack.common.services.image.image.Image")
    def test__client_admin_preferred(self, mock_image):
        admin = mock.Mock()
        user = mock.Mock()
        glance = resources.GlanceImage(admin=admin, user=user)
        client = glance._client()

        mock_image.assert_called_once_with(admin)
        self.assertEqual(client, mock_image.return_value)

    def test_list(self):
        glance = resources.GlanceImage()
        glance._client = mock.Mock()
        list_images = glance._client.return_value.list_images
        list_images.side_effect = (
            ["active-image1", "active-image2"],
            ["deactivated-image1"])
        glance.tenant_uuid = mock.Mock()

        self.assertEqual(
            glance.list(),
            ["active-image1", "active-image2", "deactivated-image1"])
        list_images.assert_has_calls([
            mock.call(owner=glance.tenant_uuid),
            mock.call(status="deactivated", owner=glance.tenant_uuid)])

    def test_delete(self):
        glance = resources.GlanceImage()
        glance._client = mock.Mock()
        glance._wrapper = mock.Mock()
        glance.raw_resource = mock.Mock()

        client = glance._client.return_value

        deleted_image = mock.Mock(status="DELETED")
        client.get_image.side_effect = [glance.raw_resource, deleted_image]

        glance.delete()
        client.delete_image.assert_called_once_with(glance.raw_resource.id)
        self.assertFalse(client.reactivate_image.called)

    @mock.patch("%s.reactivate_image" % GLANCE_V2_PATH)
    def test_delete_deactivated_image(self, mock_reactivate_image):
        glance = resources.GlanceImage()
        glance._client = mock.Mock()
        glance._wrapper = mock.Mock()
        glance.raw_resource = mock.Mock(status="deactivated")

        client = glance._client.return_value

        deleted_image = mock.Mock(status="DELETED")
        client.get_image.side_effect = [glance.raw_resource, deleted_image]

        glance.delete()

        mock_reactivate_image.assert_called_once_with(glance.raw_resource.id)
        client.delete_image.assert_called_once_with(glance.raw_resource.id)


class CeilometerTestCase(test.TestCase):

    def test_id(self):
        ceil = resources.CeilometerAlarms()
        ceil.raw_resource = mock.MagicMock()
        self.assertEqual(ceil.raw_resource.alarm_id, ceil.id())

    @mock.patch("%s.CeilometerAlarms._manager" % BASE)
    def test_list(self, mock_ceilometer_alarms__manager):

        ceil = resources.CeilometerAlarms()
        ceil.tenant_uuid = mock.MagicMock()
        mock_ceilometer_alarms__manager().list.return_value = ["a", "b", "c"]
        mock_ceilometer_alarms__manager.reset_mock()

        self.assertEqual(["a", "b", "c"], ceil.list())
        mock_ceilometer_alarms__manager().list.assert_called_once_with(
            q=[{"field": "project_id", "op": "eq", "value": ceil.tenant_uuid}])


class ZaqarQueuesTestCase(test.TestCase):

    def test_list(self):
        user = mock.Mock()
        zaqar = resources.ZaqarQueues(user=user)
        zaqar.list()
        user.zaqar().queues.assert_called_once_with()


class KeystoneMixinTestCase(test.TestCase):

    def test_is_deleted(self):
        self.assertTrue(resources.KeystoneMixin().is_deleted())

    def get_keystone_mixin(self):
        kmixin = resources.KeystoneMixin()
        kmixin._service = "keystone"
        return kmixin

    @mock.patch("%s.identity" % BASE)
    def test_manager(self, mock_identity):
        keystone_mixin = self.get_keystone_mixin()
        keystone_mixin.admin = mock.MagicMock()
        self.assertEqual(mock_identity.Identity.return_value,
                         keystone_mixin._manager())
        mock_identity.Identity.assert_called_once_with(
            keystone_mixin.admin)

    @mock.patch("%s.identity" % BASE)
    def test_delete(self, mock_identity):
        keystone_mixin = self.get_keystone_mixin()
        keystone_mixin._resource = "some_resource"
        keystone_mixin.id = lambda: "id_a"
        keystone_mixin.admin = mock.MagicMock()

        keystone_mixin.delete()
        mock_identity.Identity.assert_called_once_with(keystone_mixin.admin)
        identity_service = mock_identity.Identity.return_value
        identity_service.delete_some_resource.assert_called_once_with("id_a")

    @mock.patch("%s.identity" % BASE)
    def test_list(self, mock_identity):
        keystone_mixin = self.get_keystone_mixin()
        keystone_mixin._resource = "some_resource2"
        keystone_mixin.admin = mock.MagicMock()
        identity = mock_identity.Identity

        self.assertSequenceEqual(
            identity.return_value.list_some_resource2s.return_value,
            keystone_mixin.list())
        identity.assert_called_once_with(keystone_mixin.admin)
        identity.return_value.list_some_resource2s.assert_called_once_with()


class KeystoneEc2TestCase(test.TestCase):
    def test_user_id_property(self):
        user_client = mock.Mock()
        admin_client = mock.Mock()

        manager = resources.KeystoneEc2(user=user_client, admin=admin_client)

        self.assertEqual(user_client.keystone.auth_ref.user_id,
                         manager.user_id)

    def test_list(self):
        user_client = mock.Mock()
        admin_client = mock.Mock()

        with mock.patch("%s.identity.Identity" % BASE, autospec=True) as p:
            identity = p.return_value
            manager = resources.KeystoneEc2(user=user_client,
                                            admin=admin_client)
            self.assertEqual(identity.list_ec2credentials.return_value,
                             manager.list())
            p.assert_called_once_with(user_client)
            identity.list_ec2credentials.assert_called_once_with(
                manager.user_id)

    def test_delete(self):
        user_client = mock.Mock()
        admin_client = mock.Mock()
        raw_resource = mock.Mock()

        with mock.patch("%s.identity.Identity" % BASE, autospec=True) as p:
            manager = resources.KeystoneEc2(user=user_client,
                                            admin=admin_client,
                                            resource=raw_resource)
            manager.delete()

            p.assert_called_once_with(user_client)
            p.return_value.delete_ec2credential.assert_called_once_with(
                manager.user_id, access=raw_resource.access)


class SwiftMixinTestCase(test.TestCase):

    def get_swift_mixin(self):
        swift_mixin = resources.SwiftMixin()
        swift_mixin._service = "swift"
        return swift_mixin

    def test_manager(self):
        swift_mixin = self.get_swift_mixin()
        swift_mixin.user = mock.MagicMock()
        self.assertEqual(swift_mixin.user.swift.return_value,
                         swift_mixin._manager())

    def test_id(self):
        swift_mixin = self.get_swift_mixin()
        swift_mixin.raw_resource = mock.MagicMock()
        self.assertEqual(swift_mixin.raw_resource, swift_mixin.id())

    def test_name(self):
        swift = self.get_swift_mixin()
        swift.raw_resource = ["name1", "name2"]
        self.assertEqual("name2", swift.name())

    def test_delete(self):
        swift_mixin = self.get_swift_mixin()
        swift_mixin.user = mock.MagicMock()
        swift_mixin._resource = "some_resource"
        swift_mixin.raw_resource = mock.MagicMock()
        swift_mixin.delete()
        swift_mixin.user.swift().delete_some_resource.assert_called_once_with(
            *swift_mixin.raw_resource)


class SwiftObjectTestCase(test.TestCase):

    @mock.patch("%s.SwiftMixin._manager" % BASE)
    def test_list(self, mock_swift_mixin__manager):
        containers = [mock.MagicMock(), mock.MagicMock()]
        objects = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]
        mock_swift_mixin__manager().get_account.return_value = (
            "header", containers)
        mock_swift_mixin__manager().get_container.return_value = (
            "header", objects)
        self.assertEqual(len(containers),
                         len(resources.SwiftContainer().list()))
        self.assertEqual(len(containers) * len(objects),
                         len(resources.SwiftObject().list()))


class SwiftContainerTestCase(test.TestCase):

    @mock.patch("%s.SwiftMixin._manager" % BASE)
    def test_list(self, mock_swift_mixin__manager):
        containers = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock()]
        mock_swift_mixin__manager().get_account.return_value = (
            "header", containers)
        self.assertEqual(len(containers),
                         len(resources.SwiftContainer().list()))


class ManilaShareTestCase(test.TestCase):

    def test_list(self):
        share_resource = resources.ManilaShare()
        share_resource._manager = mock.MagicMock()

        share_resource.list()

        self.assertEqual("shares", share_resource._resource)
        share_resource._manager.return_value.list.assert_called_once_with()

    def test_delete(self):
        share_resource = resources.ManilaShare()
        share_resource._manager = mock.MagicMock()
        share_resource.id = lambda: "fake_id"

        share_resource.delete()

        self.assertEqual("shares", share_resource._resource)
        share_resource._manager.return_value.delete.assert_called_once_with(
            "fake_id")


class ManilaShareNetworkTestCase(test.TestCase):

    def test_list(self):
        sn_resource = resources.ManilaShareNetwork()
        sn_resource._manager = mock.MagicMock()

        sn_resource.list()

        self.assertEqual("share_networks", sn_resource._resource)
        sn_resource._manager.return_value.list.assert_called_once_with()

    def test_delete(self):
        sn_resource = resources.ManilaShareNetwork()
        sn_resource._manager = mock.MagicMock()
        sn_resource.id = lambda: "fake_id"

        sn_resource.delete()

        self.assertEqual("share_networks", sn_resource._resource)
        sn_resource._manager.return_value.delete.assert_called_once_with(
            "fake_id")


class ManilaSecurityServiceTestCase(test.TestCase):

    def test_list(self):
        ss_resource = resources.ManilaSecurityService()
        ss_resource._manager = mock.MagicMock()

        ss_resource.list()

        self.assertEqual("security_services", ss_resource._resource)
        ss_resource._manager.return_value.list.assert_called_once_with()

    def test_delete(self):
        ss_resource = resources.ManilaSecurityService()
        ss_resource._manager = mock.MagicMock()
        ss_resource.id = lambda: "fake_id"

        ss_resource.delete()

        self.assertEqual("security_services", ss_resource._resource)
        ss_resource._manager.return_value.delete.assert_called_once_with(
            "fake_id")


class MistralWorkbookTestCase(test.TestCase):

    def test_delete(self):
        clients = mock.MagicMock()
        resource = mock.Mock()
        resource.name = "TEST_NAME"

        mistral = resources.MistralWorkbooks(
            user=clients,
            resource=resource)

        mistral.delete()

        clients.mistral().workbooks.delete.assert_called_once_with(
            "TEST_NAME")


class MistralExecutionsTestCase(test.TestCase):

    def test_name(self):
        execution = mock.MagicMock(workflow_name="bar")
        execution.name = "foo"
        self.assertEqual("bar", resources.MistralExecutions(execution).name())


class WatcherTemplateTestCase(test.TestCase):

    def test_id(self):
        watcher = resources.WatcherTemplate()
        watcher.raw_resource = mock.MagicMock(uuid=100)
        self.assertEqual(100, watcher.id())

    @mock.patch("%s.WatcherTemplate._manager" % BASE)
    def test_is_deleted(self, mock__manager):
        mock__manager.return_value.get.return_value = None
        watcher = resources.WatcherTemplate()
        watcher.id = mock.Mock()
        self.assertFalse(watcher.is_deleted())
        mock__manager.side_effect = [watcher_exceptions.NotFound()]
        self.assertTrue(watcher.is_deleted())

    def test_list(self):
        watcher = resources.WatcherTemplate()
        watcher._manager = mock.MagicMock()

        watcher.list()

        self.assertEqual("audit_template", watcher._resource)
        watcher._manager().list.assert_called_once_with(limit=0)


class WatcherAuditTestCase(test.TestCase):

    def test_id(self):
        watcher = resources.WatcherAudit()
        watcher.raw_resource = mock.MagicMock(uuid=100)
        self.assertEqual(100, watcher.id())

    def test_name(self):
        watcher = resources.WatcherAudit()
        watcher.raw_resource = mock.MagicMock(uuid="name")
        self.assertEqual("name", watcher.name())

    @mock.patch("%s.WatcherAudit._manager" % BASE)
    def test_is_deleted(self, mock__manager):
        mock__manager.return_value.get.return_value = None
        watcher = resources.WatcherAudit()
        watcher.id = mock.Mock()
        self.assertFalse(watcher.is_deleted())
        mock__manager.side_effect = [watcher_exceptions.NotFound()]
        self.assertTrue(watcher.is_deleted())

    def test_list(self):
        watcher = resources.WatcherAudit()
        watcher._manager = mock.MagicMock()

        watcher.list()

        self.assertEqual("audit", watcher._resource)
        watcher._manager().list.assert_called_once_with(limit=0)


class WatcherActionPlanTestCase(test.TestCase):

    def test_id(self):
        watcher = resources.WatcherActionPlan()
        watcher.raw_resource = mock.MagicMock(uuid=100)
        self.assertEqual(100, watcher.id())

    def test_name(self):
        watcher = resources.WatcherActionPlan()
        self.assertIsInstance(watcher.name(), resources.base.NoName)

    @mock.patch("%s.WatcherActionPlan._manager" % BASE)
    def test_is_deleted(self, mock__manager):
        mock__manager.return_value.get.return_value = None
        watcher = resources.WatcherActionPlan()
        watcher.id = mock.Mock()
        self.assertFalse(watcher.is_deleted())
        mock__manager.side_effect = [watcher_exceptions.NotFound()]
        self.assertTrue(watcher.is_deleted())

    def test_list(self):
        watcher = resources.WatcherActionPlan()
        watcher._manager = mock.MagicMock()

        watcher.list()

        self.assertEqual("action_plan", watcher._resource)
        watcher._manager().list.assert_called_once_with(limit=0)


class CinderImageVolumeCacheTestCase(test.TestCase):

    class Resource(object):
        def __init__(self, id=None, name=None):
            self.id = id
            self.name = name

    @mock.patch("rally_openstack.common.services.image.image.Image")
    def test_list(self, mock_image):
        admin = mock.Mock()

        glance = mock_image.return_value
        cinder = admin.cinder.return_value

        image_1 = self.Resource("foo", name="foo-name")
        image_2 = self.Resource("bar", name="bar-name")
        glance.list_images.return_value = [image_1, image_2]
        volume_1 = self.Resource(name="v1")
        volume_2 = self.Resource(name="image-foo")
        volume_3 = self.Resource(name="foo")
        volume_4 = self.Resource(name="bar")
        cinder.volumes.list.return_value = [volume_1, volume_2, volume_3,
                                            volume_4]

        manager = resources.CinderImageVolumeCache(admin=admin)

        self.assertEqual([{"volume": volume_2, "image": image_1}],
                         manager.list())

        mock_image.assert_called_once_with(admin)
        glance.list_images.assert_called_once_with()
        cinder.volumes.list.assert_called_once_with(
            search_opts={"all_tenants": 1})

    def test_id_and_name(self):

        res = resources.CinderImageVolumeCache(
            {"volume": self.Resource("volume-id", "volume-name"),
             "image": self.Resource("image-id", "image-name")})

        self.assertEqual("volume-id", res.id())
        self.assertEqual("image-name", res.name())


class GnocchiMixinTestCase(test.TestCase):

    def get_gnocchi(self):
        gnocchi = resources.GnocchiMixin()
        gnocchi._service = "gnocchi"
        return gnocchi

    def test_id(self):
        gnocchi = self.get_gnocchi()
        gnocchi.raw_resource = {"name": "test_name"}
        self.assertEqual("test_name", gnocchi.id())

    def test_name(self):
        gnocchi = self.get_gnocchi()
        gnocchi.raw_resource = {"name": "test_name"}
        self.assertEqual("test_name", gnocchi.name())


class GnocchiMetricTestCase(test.TestCase):

    def get_gnocchi(self):
        gnocchi = resources.GnocchiMetric()
        gnocchi._service = "gnocchi"
        return gnocchi

    def test_id(self):
        gnocchi = self.get_gnocchi()
        gnocchi.raw_resource = {"id": "test_id"}
        self.assertEqual("test_id", gnocchi.id())

    def test_list(self):
        gnocchi = self.get_gnocchi()
        gnocchi._manager = mock.MagicMock()
        metrics = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock(),
                   mock.MagicMock()]
        gnocchi._manager.return_value.list.side_effect = (
            metrics[:2], metrics[2:4], [])
        self.assertEqual(metrics, gnocchi.list())
        self.assertEqual(
            [mock.call(marker=None), mock.call(marker=metrics[1]["id"]),
             mock.call(marker=metrics[3]["id"])],
            gnocchi._manager.return_value.list.call_args_list)


class GnocchiResourceTestCase(test.TestCase):

    def get_gnocchi(self):
        gnocchi = resources.GnocchiResource()
        gnocchi._service = "gnocchi"
        return gnocchi

    def test_id(self):
        gnocchi = self.get_gnocchi()
        gnocchi.raw_resource = {"id": "test_id"}
        self.assertEqual("test_id", gnocchi.id())

    def test_list(self):
        gnocchi = self.get_gnocchi()
        gnocchi._manager = mock.MagicMock()
        res = [mock.MagicMock(), mock.MagicMock(), mock.MagicMock(),
               mock.MagicMock()]
        gnocchi._manager.return_value.list.side_effect = (
            res[:2], res[2:4], [])
        self.assertEqual(res, gnocchi.list())
        self.assertEqual(
            [mock.call(marker=None), mock.call(marker=res[1]["id"]),
             mock.call(marker=res[3]["id"])],
            gnocchi._manager.return_value.list.call_args_list)


class BarbicanSecretsTestCase(test.TestCase):

    def test_id(self):
        barbican = resources.BarbicanSecrets()
        barbican.raw_resource = mock.MagicMock(secret_ref="fake_uuid")
        self.assertEqual("fake_uuid", barbican.id())

    def test_list(self):
        barbican = resources.BarbicanSecrets()
        barbican._manager = mock.MagicMock()

        barbican.list()
        barbican._manager.assert_called_once_with()

    def test_delete(self):
        barbican = resources.BarbicanSecrets()
        barbican._manager = mock.MagicMock()
        barbican.raw_resource = mock.MagicMock(uuid="fake_uuid")

        barbican.delete()
        barbican._manager.assert_called_once_with()

    def test_is_deleted(self):
        barbican = resources.BarbicanSecrets()
        barbican._manager = mock.MagicMock()
        barbican.raw_resource = mock.MagicMock(uuid="fake_uuid")
        self.assertFalse(barbican.is_deleted())


@resources.base.resource("octavia", "some", order=3)
class OctaviaSimpleResource(resources.OctaviaMixIn):
    pass


class OctaviaResourceTestCase(test.TestCase):

    def test_name(self):
        resource = OctaviaSimpleResource({"name": "test_name"})
        self.assertEqual("test_name", resource.name())

    def test_id(self):
        resource = OctaviaSimpleResource({"id": "test_id"})
        self.assertEqual("test_id", resource.id())

    def test_delete(self):
        clients = mock.MagicMock()
        octavia_client = clients.octavia.return_value
        resource = OctaviaSimpleResource(
            user=clients, resource={"id": "test_id"})

        resource.delete()

        octavia_client.some_delete.assert_called_once_with("test_id")

    def test_delete_load_balancers(self):
        clients = mock.MagicMock()
        octavia_client = clients.octavia.return_value
        resource = resources.OctaviaLoadBalancers(
            user=clients, resource={"id": "test_id"})

        resource.delete()

        octavia_client.load_balancer_delete.assert_called_once_with(
            "test_id", cascade=True)

    def test_delete_with_exception(self):
        clients = mock.MagicMock()
        octavia_client = clients.octavia.return_value
        resource = OctaviaSimpleResource(
            user=clients, resource={"id": "test_id"})

        # case #1: random exception is raised
        octavia_client.some_delete.side_effect = ValueError("asd")

        self.assertRaises(ValueError, resource.delete)

        # case #2: octaviaclient inner exception with random message
        from octaviaclient.api.v2 import octavia as octavia_exc

        e = octavia_exc.OctaviaClientException(409, "bla bla bla")
        octavia_client.some_delete.side_effect = e

        self.assertRaises(octavia_exc.OctaviaClientException, resource.delete)

        # case #3: octaviaclient inner exception with specific message
        e = octavia_exc.OctaviaClientException(
            409, "Invalid state PENDING_DELETE bla bla")
        octavia_client.some_delete.side_effect = e

        resource.delete()

    def test_delete_load_balancer_with_exception(self):
        clients = mock.MagicMock()
        octavia_client = clients.octavia.return_value
        resource = resources.OctaviaLoadBalancers(
            user=clients, resource={"id": "test_id"})

        # case #1: random exception is raised
        octavia_client.load_balancer_delete.side_effect = ValueError("asd")

        self.assertRaises(ValueError, resource.delete)

        # case #2: octaviaclient inner exception with random message
        from octaviaclient.api.v2 import octavia as octavia_exc

        e = octavia_exc.OctaviaClientException(409, "bla bla bla")
        octavia_client.load_balancer_delete.side_effect = e

        self.assertRaises(octavia_exc.OctaviaClientException, resource.delete)

        # case #3: octaviaclient inner exception with specific message
        e = octavia_exc.OctaviaClientException(
            409, "Invalid state PENDING_DELETE bla bla")
        octavia_client.load_balancer_delete.side_effect = e

        resource.delete()

    def test_is_deleted_false(self):
        clients = mock.MagicMock()
        octavia_client = clients.octavia.return_value
        resource = OctaviaSimpleResource(
            user=clients, resource={"id": "test_id"})
        self.assertFalse(resource.is_deleted())
        octavia_client.some_show.assert_called_once_with("test_id")

    def test_is_deleted_true(self):
        from osc_lib import exceptions as osc_exc

        clients = mock.MagicMock()
        octavia_client = clients.octavia.return_value
        octavia_client.some_show.side_effect = osc_exc.NotFound(404, "foo")
        resource = OctaviaSimpleResource(
            user=clients, resource={"id": "test_id"})

        self.assertTrue(resource.is_deleted())

        octavia_client.some_show.assert_called_once_with("test_id")

    def test_list(self):
        clients = mock.MagicMock()
        octavia_client = clients.octavia.return_value
        octavia_client.some_list.return_value = {"somes": [1, 2]}
        manager = OctaviaSimpleResource(user=clients)

        self.assertEqual([1, 2], manager.list())

        octavia_client.some_list.assert_called_once_with()

        octavia_client.l7policy_list.return_value = {"l7policies": [3, 4]}
        manager = resources.OctaviaL7Policies(user=clients)

        self.assertEqual([3, 4], manager.list())

        octavia_client.l7policy_list.assert_called_once_with()
