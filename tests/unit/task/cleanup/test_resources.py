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

from unittest import mock

import ddt
from novaclient import exceptions as nova_exc
from openstack.network.v2 import extension as sdk_extension
from openstack.network.v2 import port as sdk_port
from openstack.network.v2 import router as sdk_router
from openstack.network.v2 import tap_flow
from openstack.network.v2 import tap_service
from watcherclient.common.apiclient import exceptions as watcher_exceptions

from rally_openstack.common.clients import glance
from rally_openstack.task.cleanup import resources
from tests.unit import test


BASE = "rally_openstack.task.cleanup.resources"


def _dict(resource):
    return resource.to_dict(
        computed=False, original_names=True, headers=False, ignore_none=True)


def _set_extensions(user, extensions):
    """Stub the openstacksdk network proxy extensions() for supports_ext."""
    user._conn.network.extensions.return_value = iter(
        [sdk_extension.Extension(**{"alias": ext}) for ext in extensions])


class SynchronizedDeletionTestCase(test.TestCase):

    def test_is_deleted(self):
        self.assertTrue(resources.SynchronizedDeletion().is_deleted())


class QuotaMixinTestCase(test.TestCase):

    def test_list(self):
        quota = resources.QuotaMixin()
        quota.tenant_uuid = None
        quota.user = mock.MagicMock()
        self.assertEqual([], quota.list())
        self.assertFalse(quota.user.keystone.get_project.called)

        quota.tenant_uuid = mock.MagicMock()
        self.assertEqual(
            [quota.user.keystone.get_project.return_value],
            quota.list())
        quota.user.keystone.get_project.assert_called_once_with(
            quota.tenant_uuid)


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
        _set_extensions(user, extensions)
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
        _set_extensions(user, extensions)
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
        _set_extensions(admin, extensions)
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


def _set_client_extensions(clients, extensions):
    clients.neutron.supports_extension.side_effect = (
        lambda alias: alias in extensions)


class NeutronFirewallRuleTestCase(test.TestCase):

    def get_firewall_rule_resource(self, extensions=()):
        user = mock.MagicMock()
        neut = resources.NeutronFirewallRule(user=user)
        neut.tenant_uuid = "user_tenant"
        _set_client_extensions(user, extensions)
        return neut

    def test_list_fwaas_available(self):
        neut = self.get_firewall_rule_resource(extensions=["fwaas_v2"])
        rules = [mock.Mock(id="rule-1"), mock.Mock(id="rule-2")]
        neut.user.neutron.list_firewall_rules.return_value = rules

        self.assertEqual("firewall_rule", neut._resource)
        self.assertEqual(rules, neut.list())
        neut.user.neutron.supports_extension.assert_called_once_with(
            "fwaas_v2")
        neut.user.neutron.list_firewall_rules.assert_called_once_with(
            project_id="user_tenant")

    def test_list_fwaas_unavailable(self):
        neut = self.get_firewall_rule_resource()

        self.assertEqual([], neut.list())
        self.assertFalse(neut.user.neutron.list_firewall_rules.called)

    def test_delete(self):
        neut = self.get_firewall_rule_resource(extensions=["fwaas_v2"])
        neut.raw_resource = mock.Mock(id="rule-id")

        neut.delete()

        neut.user.neutron.delete_firewall_rule.assert_called_once_with(
            "rule-id")


class NeutronFirewallPolicyTestCase(test.TestCase):

    def get_firewall_policy_resource(self, extensions=()):
        user = mock.MagicMock()
        neut = resources.NeutronFirewallPolicy(user=user)
        neut.tenant_uuid = "user_tenant"
        _set_client_extensions(user, extensions)
        return neut

    def test_list_fwaas_available(self):
        neut = self.get_firewall_policy_resource(extensions=["fwaas_v2"])
        policies = [mock.Mock(id="policy-1"), mock.Mock(id="policy-2")]
        neut.user.neutron.list_firewall_policies.return_value = policies

        self.assertEqual("firewall_policy", neut._resource)
        self.assertEqual(policies, neut.list())
        neut.user.neutron.list_firewall_policies.assert_called_once_with(
            project_id="user_tenant")

    def test_list_fwaas_unavailable(self):
        neut = self.get_firewall_policy_resource()

        self.assertEqual([], neut.list())
        self.assertFalse(neut.user.neutron.list_firewall_policies.called)

    def test_delete(self):
        neut = self.get_firewall_policy_resource(extensions=["fwaas_v2"])
        neut.raw_resource = mock.Mock(id="policy-id")

        neut.delete()

        neut.user.neutron.delete_firewall_policy.assert_called_once_with(
            "policy-id")


class NeutronFirewallGroupTestCase(test.TestCase):

    def get_firewall_group_resource(self, extensions=()):
        user = mock.MagicMock()
        neut = resources.NeutronFirewallGroup(user=user)
        neut.tenant_uuid = "user_tenant"
        _set_client_extensions(user, extensions)
        return neut

    def test_id_and_name(self):
        neut = self.get_firewall_group_resource()
        neut.raw_resource = mock.Mock(id="group-id")
        neut.raw_resource.name = "group-name"

        self.assertEqual("group-id", neut.id())
        self.assertEqual("group-name", neut.name())

    def test_list_fwaas_available(self):
        neut = self.get_firewall_group_resource(extensions=["fwaas_v2"])
        groups = [mock.Mock(id="group-1"), mock.Mock(id="group-2")]
        neut.user.neutron.list_firewall_groups.return_value = groups

        self.assertEqual("firewall_group", neut._resource)
        self.assertEqual(groups, neut.list())
        neut.user.neutron.list_firewall_groups.assert_called_once_with(
            project_id="user_tenant")

    def test_list_fwaas_unavailable(self):
        neut = self.get_firewall_group_resource()

        self.assertEqual([], neut.list())
        self.assertFalse(neut.user.neutron.list_firewall_groups.called)

    def test_delete(self):
        neut = self.get_firewall_group_resource(extensions=["fwaas_v2"])
        neut.raw_resource = mock.Mock(id="group-id", ports=[])

        neut.delete()

        neut.user.neutron.delete_firewall_group.assert_called_once_with(
            "group-id")
        self.assertFalse(
            neut.user.neutron.disassociate_firewall_group_ports.called)

    def test_delete_with_ports(self):
        neut = self.get_firewall_group_resource(extensions=["fwaas_v2"])
        neut.raw_resource = mock.Mock(id="group-id", ports=["port-1"])

        client = neut.user.neutron

        neut.delete()

        client.disassociate_firewall_group_ports.assert_called_once_with(
            "group-id")
        neut.user.neutron.delete_firewall_group.assert_called_once_with(
            "group-id")


class NeutronTapMirrorTestCase(test.TestCase):

    def get_tap_mirror_resource(self, extensions=()):
        user = mock.MagicMock()
        neut = resources.NeutronTapMirror(user=user)
        neut.tenant_uuid = "user_tenant"
        _set_client_extensions(user, extensions)
        return neut

    def test_id_and_name(self):
        neut = self.get_tap_mirror_resource()
        neut.raw_resource = mock.Mock()
        neut.raw_resource.id = "mirror-id"
        neut.raw_resource.name = "mirror-name"

        self.assertEqual("mirror-id", neut.id())
        self.assertEqual("mirror-name", neut.name())

    def test_list_tap_mirror_available(self):
        neut = self.get_tap_mirror_resource(extensions=["tap-mirror"])
        mirror1 = mock.Mock(project_id="user_tenant", id="mirror-1")
        mirror3 = mock.Mock(project_id="user_tenant", id="mirror-3")
        neut.user.neutron.list_tap_mirrors.return_value = [
            mirror1, mirror3]

        self.assertEqual("tap_mirror", neut._resource)
        self.assertEqual([mirror1, mirror3], neut.list())
        neut.user.neutron.list_tap_mirrors.assert_called_once_with(
            project_id="user_tenant")

    def test_list_tap_mirror_unavailable(self):
        neut = self.get_tap_mirror_resource()

        self.assertEqual([], neut.list())
        self.assertFalse(neut.user.neutron.list_tap_mirrors.called)

    def test_delete(self):
        neut = self.get_tap_mirror_resource(extensions=["tap-mirror"])
        neut.raw_resource = mock.Mock(id="mirror-id", name="mirror-name")
        neut.delete()
        neut.user.neutron.delete_tap_mirror.assert_called_once_with(
            "mirror-id")


class NeutronTapServiceTestCase(test.TestCase):

    def get_tap_service_resource(self, extensions=()):
        user = mock.MagicMock()
        resource = resources.NeutronTapService(user=user)
        resource.tenant_uuid = "user_tenant"
        _set_client_extensions(user, extensions)
        return resource

    def test_id_and_name(self):
        resource = self.get_tap_service_resource()
        resource.raw_resource = mock.Mock(id="service-id")
        resource.raw_resource.name = "service-name"

        self.assertEqual("service-id", resource.id())
        self.assertEqual("service-name", resource.name())

    def test_list_tap_service_available(self):
        resource = self.get_tap_service_resource(extensions=["taas"])
        services = [
            tap_service.TapService(id="service-1", project_id="user_tenant"),
            tap_service.TapService(id="service-2", project_id="other-project"),
        ]
        resource.user.neutron.list_tap_services.return_value = services

        self.assertEqual([services[0]], resource.list())
        resource.user.neutron.list_tap_services.assert_called_once_with()

    def test_list_tap_service_with_legacy_project_attribute(self):
        resource = self.get_tap_service_resource(extensions=["taas"])
        service = tap_service.TapService(
            id="service-1", tenant_id="user_tenant")
        resource.user.neutron.list_tap_services.return_value = [service]

        self.assertEqual([service], resource.list())
        resource.user.neutron.list_tap_services.assert_called_once_with()

    def test_list_tap_service_without_project(self):
        resource = self.get_tap_service_resource(extensions=["taas"])
        resource.tenant_uuid = None
        services = [
            tap_service.TapService(id="service-1", project_id="project-1"),
            tap_service.TapService(id="service-2", project_id="project-2"),
        ]
        resource.user.neutron.list_tap_services.return_value = services

        self.assertEqual(services, resource.list())
        resource.user.neutron.list_tap_services.assert_called_once_with()

    def test_list_tap_service_unavailable(self):
        resource = self.get_tap_service_resource()

        self.assertEqual([], resource.list())
        resource.user.neutron.list_tap_services.assert_not_called()

    def test_list_tap_service_as_admin(self):
        resource = self.get_tap_service_resource(extensions=["taas"])
        resource._admin_required = True
        resource.admin = mock.MagicMock()
        _set_client_extensions(resource.admin, ["taas"])
        services = [
            tap_service.TapService(id="service-1", project_id="user_tenant"),
            tap_service.TapService(id="service-2", project_id="other-project"),
        ]
        resource.admin.neutron.list_tap_services.return_value = services

        self.assertEqual([services[0]], resource.list())
        resource.admin.neutron.list_tap_services.assert_called_once_with()
        resource.user.neutron.list_tap_services.assert_not_called()

    def test_delete(self):
        resource = self.get_tap_service_resource()
        resource.raw_resource = mock.Mock(id="service-id")

        resource.delete()

        resource.user.neutron.delete_tap_service.assert_called_once_with(
            "service-id")


class NeutronTapFlowTestCase(test.TestCase):

    def get_tap_flow_resource(self, extensions=None):
        user = mock.MagicMock()
        resource = resources.NeutronTapFlow(user=user)
        resource.tenant_uuid = "user_tenant"
        _set_extensions(user, extensions or [])
        return resource

    def test_id_and_name(self):
        resource = self.get_tap_flow_resource()
        resource.raw_resource = mock.Mock(id="flow-id")
        resource.raw_resource.name = "flow-name"

        self.assertEqual("flow-id", resource.id())
        self.assertEqual("flow-name", resource.name())

    def test_list_tap_flow_available(self):
        resource = self.get_tap_flow_resource(extensions=["taas"])
        flows = [
            tap_flow.TapFlow(id="flow-1", project_id="user_tenant"),
            tap_flow.TapFlow(id="flow-2", project_id="other-project"),
        ]
        resource.user.neutron.list_tap_flows.return_value = flows

        self.assertEqual("tap_flow", resource._resource)
        self.assertEqual([flows[0]], resource.list())
        resource.user.neutron.list_tap_flows.assert_called_once_with()

    def test_list_tap_flow_unavailable(self):
        resource = self.get_tap_flow_resource()

        self.assertEqual([], resource.list())
        resource.user.neutron.list_tap_flows.assert_not_called()

    def test_list_tap_flow_as_admin(self):
        resource = self.get_tap_flow_resource(extensions=["taas"])
        resource._admin_required = True
        resource.admin = mock.MagicMock()
        _set_extensions(resource.admin, ["taas"])
        flows = [tap_flow.TapFlow(id="flow-1", project_id="user_tenant")]
        resource.admin.neutron.list_tap_flows.return_value = flows

        self.assertEqual(flows, resource.list())
        resource.admin.neutron.list_tap_flows.assert_called_once_with()
        resource.user.neutron.list_tap_flows.assert_not_called()

    def test_delete(self):
        resource = self.get_tap_flow_resource()
        resource.raw_resource = mock.Mock(id="flow-id")

        resource.delete()

        resource.user.neutron.delete_tap_flow.assert_called_once_with(
            "flow-id")


class NeutronFloatingIPTestCase(test.TestCase):

    def test_name(self):
        fips = resources.NeutronFloatingIP({"name": "foo",
                                            "description": "OoO"})
        self.assertEqual(fips.name(), "OoO")

    def test_list(self):
        from openstack.network.v2 import floating_ip as sdk_fip

        fip_objs = [sdk_fip.FloatingIP(id="foo", tenant_id="foo")]
        user = mock.MagicMock()
        user._conn.network.ips.return_value = iter(fip_objs)

        result = list(
            resources.NeutronFloatingIP(user=user, tenant_uuid="foo").list())
        self.assertEqual(
            [fip_objs[0].to_dict(computed=False, original_names=True,
                                 headers=False, ignore_none=True)],
            result)
        # list_floatingips translates tenant_id to project_id for the sdk
        user._conn.network.ips.assert_called_once_with(project_id="foo")


class NeutronTrunkTestcase(test.TestCase):

    def test_list(self):
        from openstack.network.v2 import trunk as sdk_trunk

        trunk_objs = [sdk_trunk.Trunk(id="trunk-1", name="t1")]
        user = mock.MagicMock()
        user.neutron.list_trunks.return_value = trunk_objs
        trunk = resources.NeutronTrunk(user=user)
        self.assertEqual(trunk_objs, trunk.list())
        user.neutron.list_trunks.assert_called_once_with(project_id=None)

    def test_list_with_not_found(self):

        class NotFound(Exception):  # noqa: N818
            status_code = 404

        user = mock.MagicMock()
        user.neutron.list_trunks.side_effect = NotFound()
        trunk = resources.NeutronTrunk(user=user)

        self.assertEqual([], trunk.list())
        user.neutron.list_trunks.assert_called_once_with(project_id=None)

    def test_delete(self):
        from openstack.network.v2 import trunk as sdk_trunk

        user = mock.MagicMock()
        trunk = resources.NeutronTrunk(
            resource=sdk_trunk.Trunk(id="trunk-1"), user=user)
        trunk.delete()
        user.neutron.delete_trunk.assert_called_once_with("trunk-1")


class NeutronPortTestCase(test.TestCase):

    def test_delete(self):
        raw_res = {"device_owner": "abbabaab", "id": "some_id"}
        user = mock.MagicMock()

        resources.NeutronPort(resource=raw_res, user=user).delete()

        # delete_port now drives the openstacksdk network proxy.
        user._conn.network.delete_port.assert_called_once_with(
            raw_res["id"], ignore_missing=False)

    def test_delete_port_raise_exception(self):
        from openstack import exceptions as sdk_exceptions

        raw_res = {"device_owner": "abbabaab", "id": "some_id"}
        user = mock.MagicMock()
        user._conn.network.delete_port.side_effect = (
            sdk_exceptions.NotFoundException)

        resources.NeutronPort(resource=raw_res, user=user).delete()

        user._conn.network.delete_port.assert_called_once_with(
            raw_res["id"], ignore_missing=False)

    def test_delete_port_device_owner(self):
        raw_res = {
            "device_owner": "network:router_interface",
            "id": "some_id",
            "device_id": "dev_id"
        }
        user = mock.MagicMock()

        resources.NeutronPort(resource=raw_res, user=user).delete()

        # router interface removal is delegated to the sdk proxy with the
        # port_id keyword.
        user._conn.network.remove_interface_from_router.\
            assert_called_once_with(
                raw_res["device_id"], port_id=raw_res["id"])

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

        port_objs = [sdk_port.Port(**p) for p in ports]
        router_objs = [sdk_router.Router(**r) for r in routers]

        expected_ports = []
        for port in ports:
            if port["tenant_id"] == tenant_uuid:
                expected_port = _dict(sdk_port.Port(**port))
                if ("device_id" in port
                        and port["device_id"].startswith("router")):
                    expected_port["parent_name"] = [
                        r for r in routers
                        if r["id"] == port["device_id"]][0]["name"]
                expected_ports.append(expected_port)

        neutron_proxy = mock.Mock()
        neutron_proxy.ports.return_value = iter(port_objs)
        neutron_proxy.routers.return_value = iter(router_objs)

        user = mock.Mock()
        user._conn.network = neutron_proxy
        self.assertEqual(expected_ports, resources.NeutronPort(
            user=user, tenant_uuid=tenant_uuid).list())
        # list_* translates the legacy tenant_id filter to project_id before
        # calling the openstacksdk proxy.
        neutron_proxy.ports.assert_called_once_with(project_id=tenant_uuid)
        neutron_proxy.routers.assert_called_once_with(project_id=tenant_uuid)


@ddt.ddt
class NeutronSecurityGroupTestCase(test.TestCase):

    @ddt.data(
        {"admin": mock.Mock(), "admin_required": True},
        {"admin": None, "admin_required": False})
    @ddt.unpack
    def test_list(self, admin, admin_required):
        from openstack.network.v2 import security_group as sdk_sg

        sg_objs = [
            sdk_sg.SecurityGroup(tenant_id="user_tenant", name="default"),
            sdk_sg.SecurityGroup(tenant_id="user_tenant", name="foo_sg"),
        ]

        neut = resources.NeutronSecurityGroup()
        neut.user = mock.MagicMock()
        neut._resource = "security_group"
        neut.tenant_uuid = "user_tenant"

        neut.user._conn.network.security_groups.return_value = iter(sg_objs)

        expected_result = [
            sg_objs[1].to_dict(computed=False, original_names=True,
                               headers=False, ignore_none=True)]
        self.assertEqual(expected_result, list(neut.list()))

        # list_security_groups translates tenant_id to project_id
        neut.user._conn.network.security_groups.assert_called_once_with(
            project_id=neut.tenant_uuid)

    def test_list_with_not_found(self):

        class NotFound(Exception):  # noqa: N818
            status_code = 404

        neut = resources.NeutronSecurityGroup()
        neut.user = mock.MagicMock()
        neut._resource = "security_group"
        neut.tenant_uuid = "user_tenant"

        neut.user._conn.network.security_groups.side_effect = NotFound()

        expected_result = []
        self.assertEqual(expected_result, list(neut.list()))

        neut.user._conn.network.security_groups.assert_called_once_with(
            project_id=neut.tenant_uuid)


class NeutronQuotaTestCase(test.TestCase):

    def test_delete(self):
        admin = mock.MagicMock()
        resources.NeutronQuota(admin=admin, tenant_uuid="fake").delete()
        admin._conn.network.delete_quota.assert_called_once_with("fake")


@ddt.ddt
class GlanceImageTestCase(test.TestCase):

    def test_list(self):
        for with_admin in (True, False):
            with self.subTest(with_admin=with_admin):
                admin = mock.Mock() if with_admin else None
                user = mock.Mock()
                client = (admin or user).glance
                glance_image = resources.GlanceImage(
                    admin=admin, user=user, tenant_uuid="tenant-id")

                self.assertEqual(client.list_images.return_value,
                                 glance_image.list())
                client.list_images.assert_called_once_with(
                    status=None, owner="tenant-id")
                if with_admin:
                    self.assertFalse(user.glance.list_images.called)

    def test_delete(self):
        admin = mock.Mock()
        glance_image = resources.GlanceImage(resource=mock.Mock(), admin=admin)

        glance_image.delete()

        client = admin.glance
        client.delete_image.assert_called_once_with(
            glance_image.raw_resource.id)
        client.wait_for_image_deleted.assert_called_once_with(
            glance_image.raw_resource.id, timeout=mock.ANY,
            check_interval=mock.ANY)
        self.assertFalse(client.reactivate_image.called)

    def test_delete_deactivated_image(self):
        admin = mock.Mock()
        glance_image = resources.GlanceImage(
            resource=mock.Mock(status=glance.ImageStatus.DEACTIVATED),
            admin=admin)

        glance_image.delete()

        client = admin.glance
        client.reactivate_image.assert_called_once_with(
            glance_image.raw_resource.id)
        client.delete_image.assert_called_once_with(
            glance_image.raw_resource.id)


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


class KeystoneResourcesTestCase(test.TestCase):

    _resources = ((resources.KeystoneUser, "user"),
                  (resources.KeystoneProject, "project"),
                  (resources.KeystoneService, "service"),
                  (resources.KeystoneRole, "role"))

    def test_manager(self):
        for cls, _resource in self._resources:
            mgr = cls(admin=mock.MagicMock())
            self.assertEqual(mgr.admin.keystone, mgr._manager())

    def test_delete(self):
        for cls, resource in self._resources:
            mgr = cls(admin=mock.MagicMock())
            mgr.id = lambda: "id_a"
            mgr.delete()
            getattr(mgr.admin.keystone,
                    f"delete_{resource}").assert_called_once_with("id_a")

    def test_list(self):
        for cls, resource in self._resources:
            mgr = cls(admin=mock.MagicMock())
            list_method = getattr(mgr.admin.keystone, f"list_{resource}s")
            self.assertEqual(list_method.return_value, mgr.list())
            list_method.assert_called_once_with()


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

        manager = resources.KeystoneEc2(user=user_client, admin=admin_client)
        self.assertEqual(
            user_client.keystone.list_credentials.return_value,
            manager.list())
        user_client.keystone.list_credentials.assert_called_once_with(
            user_id=manager.user_id, cred_type="ec2")

    def test_delete(self):
        user_client = mock.Mock()
        admin_client = mock.Mock()
        raw_resource = mock.Mock()

        manager = resources.KeystoneEc2(user=user_client,
                                        admin=admin_client,
                                        resource=raw_resource)
        manager.delete()

        user_client.keystone.delete_credential.assert_called_once_with(
            raw_resource.id)


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

    class Resource:
        def __init__(self, id=None, name=None):  # noqa: A002
            self.id = id
            self.name = name

    def test_list(self):
        admin = mock.Mock()

        glance_client = admin.glance
        cinder = admin.cinder.return_value

        image_1 = self.Resource("foo", name="foo-name")
        glance_client.list_images.return_value = [image_1]
        volume_1 = self.Resource(name="v1")
        volume_2 = self.Resource(name="image-foo")
        volume_3 = self.Resource(name="foo")
        volume_4 = self.Resource(name="image-gone")
        cinder.volumes.list.return_value = [volume_1, volume_2, volume_3,
                                            volume_4]

        manager = resources.CinderImageVolumeCache(admin=admin)

        self.assertEqual([{"volume": volume_2, "image": image_1}],
                         manager.list())

        glance_client.list_images.assert_called_once_with(
            ids=["foo", "gone"])
        cinder.volumes.list.assert_called_once_with(
            search_opts={"all_tenants": 1})

    def test_list_without_cached_volumes(self):
        admin = mock.Mock()
        admin.cinder.return_value.volumes.list.return_value = [
            self.Resource(name="v1"), self.Resource(name=None)]
        admin.glance.list_images.return_value = []

        manager = resources.CinderImageVolumeCache(admin=admin)

        self.assertEqual([], manager.list())
        admin.glance.list_images.assert_called_once_with(ids=[])

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
