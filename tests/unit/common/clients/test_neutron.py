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

from rally_openstack.common import credential as oscredential
from rally_openstack.common.clients import neutron
from tests.unit import test


PATH = "rally_openstack.common.clients.neutron"


class NeutronTestMixin(test.TestCase):

    def setUp(self):
        super().setUp()
        self.credential = oscredential.OpenStackCredential(
            "http://auth_url/v3", "user", "pass", "tenant")

    def _make_neutron(self, cache=None, name_generator=True):
        client = neutron.Neutron(
            self.credential, {} if cache is None else cache)
        client._clients = mock.Mock()
        if name_generator:
            client._name_generator = mock.Mock(return_value="random_name")
        return client

    @property
    def network(self):
        return self.neutron._clients._conn.network


class NeutronLegacyClientTestCase(NeutronTestMixin):

    @mock.patch("%s.Neutron.keystone" % PATH, new_callable=mock.PropertyMock)
    def test_create_client(self, mock_neutron_keystone):
        self.neutron = self._make_neutron(name_generator=False)
        session = mock.Mock()
        mock_neutron_keystone.return_value.get_session.return_value = (
            session, mock.Mock())
        self.neutron._get_endpoint = mock.Mock(return_value="http://neutron")

        with mock.patch(
            "neutronclient.neutron.client.Client",
        ) as neutron_client:
            result = self.neutron.create_client()

        neutron_client.assert_called_once_with(
            "2.0",
            session=session,
            endpoint_override="http://neutron",
        )
        self.assertEqual(neutron_client.return_value, result)

    def test_call_returns_legacy_client_by_default(self):
        self.neutron = self._make_neutron(name_generator=False)
        legacy = mock.Mock()
        self.neutron.create_client = mock.Mock(return_value=legacy)

        self.assertEqual(legacy, self.neutron())
        self.neutron.create_client.assert_called_once_with(None)

    def test_call_legacy_false_returns_sdk_client(self):
        self.neutron = self._make_neutron(name_generator=False)

        self.assertIs(self.neutron, self.neutron(legacy=False))


class NeutronTestCase(NeutronTestMixin):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_create_network(self):
        mock_network = mock.Mock(id="net-id")
        self.network.create_network.return_value = mock_network

        result = self.neutron.create_network()

        self.assertEqual(mock_network, result)
        self.network.create_network.assert_called_once_with(
            name="random_name",
        )

    def test_create_network_with_name(self):
        self.network.create_network.return_value = mock.Mock(id="net-id")

        self.neutron.create_network(name="my-network")

        self.network.create_network.assert_called_once_with(name="my-network")

    def test_list_networks(self):
        networks = [mock.Mock(id="net-1"), mock.Mock(id="net-2")]
        self.network.networks.return_value = networks

        result = self.neutron.list_networks()

        self.assertEqual(networks, result)
        self.network.networks.assert_called_once_with()

    def test_get_network(self):
        mock_network = mock.Mock(id="net-id")
        self.network.get_network.return_value = mock_network

        result = self.neutron.get_network("net-id")

        self.assertEqual(mock_network, result)
        self.network.get_network.assert_called_once_with("net-id")

    def test_delete_network(self):
        self.neutron.delete_network("net-id")

        self.network.delete_network.assert_called_once_with(
            "net-id", ignore_missing=False)

    def test_create_port(self):
        mock_port = mock.Mock(id="port-id")
        self.network.create_port.return_value = mock_port

        result = self.neutron.create_port(network_id="net-id")

        self.assertEqual(mock_port, result)
        self.network.create_port.assert_called_once_with(
            network_id="net-id",
            name="random_name",
        )

    def test_create_port_with_name(self):
        self.network.create_port.return_value = mock.Mock(id="port-id")

        self.neutron.create_port(network_id="net-id", name="my-port")

        self.network.create_port.assert_called_once_with(
            network_id="net-id",
            name="my-port",
        )

    def test_create_port_does_not_mutate_kwargs(self):
        self.network.create_port.return_value = mock.Mock(id="port-id")
        kwargs = {"device_owner": "compute:nova"}

        self.neutron.create_port(network_id="net-id", **kwargs)

        self.assertNotIn("name", kwargs)

    def test_list_ports(self):
        ports = [mock.Mock(id="port-1"), mock.Mock(id="port-2")]
        self.network.ports.return_value = ports

        result = self.neutron.list_ports()

        self.assertEqual(ports, result)
        self.network.ports.assert_called_once_with()

    def test_get_port(self):
        mock_port = mock.Mock(id="port-id")
        self.network.get_port.return_value = mock_port

        result = self.neutron.get_port("port-id")

        self.assertEqual(mock_port, result)
        self.network.get_port.assert_called_once_with("port-id")

    def test_delete_port(self):
        self.neutron.delete_port("port-id")

        self.network.delete_port.assert_called_once_with(
            "port-id", ignore_missing=False)

    def test_list_security_groups(self):
        self.neutron._atomic_actions = []
        groups = [mock.Mock(id="sg-1")]
        self.network.security_groups.return_value = iter(groups)

        self.assertEqual(groups, self.neutron.list_security_groups())
        self.network.security_groups.assert_called_once_with()
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(), "neutron.list_security_groups")

    def test_list_security_groups_with_filters(self):
        self.network.security_groups.return_value = iter([])

        self.neutron.list_security_groups(
            project_id="project-id", name="default")

        self.network.security_groups.assert_called_once_with(
            project_id="project-id", name="default")

    def test_delete_security_group(self):
        self.neutron.delete_security_group("sg-id")

        self.network.delete_security_group.assert_called_once_with(
            "sg-id", ignore_missing=False)

    def test_list_extensions_is_cached(self):
        extensions = [mock.Mock(alias="ext-1"), mock.Mock(alias="ext-2")]
        self.network.extensions.return_value = iter(extensions)

        self.assertEqual(extensions, self.neutron.list_extensions())
        self.assertEqual(extensions, self.neutron.list_extensions())

        self.network.extensions.assert_called_once_with()

    def test_list_extensions_shares_cache(self):
        cache = {}
        extensions = [mock.Mock(alias="ext-1")]
        first = self._make_neutron(cache=cache)
        first._clients._conn.network.extensions.return_value = extensions
        second = self._make_neutron(cache=cache)

        first.list_extensions()

        self.assertEqual(extensions, second.list_extensions())
        self.assertFalse(second._clients._conn.network.extensions.called)

    def test_supports_extension(self):
        self.network.extensions.return_value = [mock.Mock(alias="fwaas_v2")]

        self.assertTrue(self.neutron.supports_extension("fwaas_v2"))
        self.assertFalse(self.neutron.supports_extension("taas"))


class NeutronTapMirrorTestCase(NeutronTestMixin):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_create_tap_mirror(self):
        mock_mirror = mock.MagicMock()
        self.network.create_tap_mirror.return_value = mock_mirror

        result = self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
        )

        self.assertEqual(mock_mirror, result)
        self.network.create_tap_mirror.assert_called_once_with(
            name="random_name",
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type="gre",
        )

    def test_create_tap_mirror_erspanv1(self):
        self.network.create_tap_mirror.return_value = mock.MagicMock()

        self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type=neutron.MirrorType.ERSPANV1,
        )

        self.network.create_tap_mirror.assert_called_once_with(
            name="random_name",
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type="erspanv1",
        )

    def test_create_tap_mirror_with_description(self):
        mock_mirror = mock.MagicMock()
        self.network.create_tap_mirror.return_value = mock_mirror

        result = self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            description="mirror desc",
        )

        self.assertEqual(mock_mirror, result)
        self.network.create_tap_mirror.assert_called_once_with(
            name="random_name",
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
            mirror_type="gre",
            description="mirror desc",
        )

    def test_create_tap_mirror_always_generates_name(self):
        self.network.create_tap_mirror.return_value = mock.MagicMock()

        self.neutron.create_tap_mirror(
            port_id="port-id",
            directions={"IN": 101},
            remote_ip="10.0.0.50",
        )

        call_kwargs = self.network.create_tap_mirror.call_args.kwargs
        self.assertEqual("random_name", call_kwargs["name"])

    def test_list_tap_mirrors(self):
        mirrors = [mock.MagicMock(), mock.MagicMock()]
        self.network.tap_mirrors.return_value = iter(mirrors)

        result = self.neutron.list_tap_mirrors()

        self.assertEqual(mirrors, result)
        self.network.tap_mirrors.assert_called_once_with()

    def test_list_tap_mirrors_with_filter(self):
        mirrors = [mock.MagicMock()]
        self.network.tap_mirrors.return_value = iter(mirrors)

        result = self.neutron.list_tap_mirrors(project_id="proj-123")

        self.assertEqual(mirrors, result)
        self.network.tap_mirrors.assert_called_once_with(project_id="proj-123")

    def test_get_tap_mirror(self):
        mock_mirror = mock.MagicMock()
        self.network.get_tap_mirror.return_value = mock_mirror

        result = self.neutron.get_tap_mirror("mirror-id")

        self.assertEqual(mock_mirror, result)
        self.network.get_tap_mirror.assert_called_once_with("mirror-id")

    def test_update_tap_mirror_with_name(self):
        mock_mirror = mock.MagicMock()
        self.network.update_tap_mirror.return_value = mock_mirror

        result = self.neutron.update_tap_mirror(
            "mirror-id", name="new-name")

        self.assertEqual(mock_mirror, result)
        self.network.update_tap_mirror.assert_called_once_with(
            "mirror-id", name="new-name")

    def test_update_tap_mirror_with_description(self):
        mock_mirror = mock.MagicMock()
        self.network.update_tap_mirror.return_value = mock_mirror

        result = self.neutron.update_tap_mirror(
            "mirror-id", description="updated")

        self.assertEqual(mock_mirror, result)
        self.network.update_tap_mirror.assert_called_once_with(
            "mirror-id", description="updated")

    def test_update_tap_mirror_with_name_and_description(self):
        mock_mirror = mock.MagicMock()
        self.network.update_tap_mirror.return_value = mock_mirror

        result = self.neutron.update_tap_mirror(
            "mirror-id", name="new-name", description="new-desc")

        self.assertEqual(mock_mirror, result)
        self.network.update_tap_mirror.assert_called_once_with(
            "mirror-id", name="new-name", description="new-desc")

    def test_update_tap_mirror_raises_without_args(self):
        self.assertRaises(
            ValueError,
            self.neutron.update_tap_mirror, "mirror-id")

    def test_delete_tap_mirror(self):
        self.neutron.delete_tap_mirror("mirror-id")

        self.network.delete_tap_mirror.assert_called_once_with(
            "mirror-id", ignore_missing=False)


class NeutronTapServiceTestCase(NeutronTestMixin):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_create_tap_service(self):
        self.neutron._atomic_actions = []
        service = self.network.create_tap_service.return_value

        result = self.neutron.create_tap_service("port-id")

        self.assertIs(service, result)
        self.network.create_tap_service.assert_called_once_with(
            name="random_name", port_id="port-id")
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(), "neutron.create_tap_service")

    def test_create_tap_service_with_description(self):
        self.neutron.create_tap_service("port-id", description="desc")

        self.network.create_tap_service.assert_called_once_with(
            name="random_name", port_id="port-id", description="desc")

    def test_create_tap_service_rejects_custom_name(self):
        self.assertRaises(
            TypeError, self.neutron.create_tap_service,
            "port-id", name="custom-name")

        self.network.create_tap_service.assert_not_called()

    def test_list_tap_services(self):
        services = [mock.Mock(id="service-1"), mock.Mock(id="service-2")]
        self.network.tap_services.return_value = iter(services)

        self.assertEqual(services, self.neutron.list_tap_services())
        self.network.tap_services.assert_called_once_with()

    def test_get_tap_service(self):
        service = self.network.get_tap_service.return_value

        self.assertIs(service, self.neutron.get_tap_service("service-id"))
        self.network.get_tap_service.assert_called_once_with("service-id")

    def test_update_tap_service(self):
        service = self.network.update_tap_service.return_value

        result = self.neutron.update_tap_service(
            "service-id", description="updated")

        self.assertIs(service, result)
        self.network.update_tap_service.assert_called_once_with(
            "service-id", description="updated")
        self.neutron._name_generator.assert_not_called()

    def test_update_tap_service_with_name(self):
        self.neutron.update_tap_service("service-id", name="new-name")

        self.network.update_tap_service.assert_called_once_with(
            "service-id", name="new-name")

    def test_update_tap_service_with_name_and_description(self):
        self.neutron.update_tap_service(
            "service-id", name="new-name", description="updated")

        self.network.update_tap_service.assert_called_once_with(
            "service-id", name="new-name", description="updated")

    def test_update_tap_service_clears_description(self):
        self.neutron.update_tap_service("service-id", description="")

        self.network.update_tap_service.assert_called_once_with(
            "service-id", description="")

    def test_update_tap_service_requires_changes(self):
        self.assertRaises(
            ValueError, self.neutron.update_tap_service, "service-id")

        self.network.update_tap_service.assert_not_called()

    def test_update_tap_service_rejects_port_changes(self):
        self.assertRaises(
            TypeError, self.neutron.update_tap_service,
            "service-id", port_id="another-port")

        self.network.update_tap_service.assert_not_called()

    def test_delete_tap_service(self):
        self.neutron.delete_tap_service("service-id")

        self.network.delete_tap_service.assert_called_once_with(
            "service-id", ignore_missing=False)


class NeutronFWaaSTestCase(NeutronTestMixin):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_create_firewall_rule(self):
        self.neutron._atomic_actions = []
        rule = self.network.create_firewall_rule.return_value

        result = self.neutron.create_firewall_rule()

        self.assertIs(rule, result)
        self.network.create_firewall_rule.assert_called_once_with(
            name="random_name", protocol=None)
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(), "neutron.create_firewall_rule")

    def test_create_firewall_rule_with_all_args(self):
        self.neutron.create_firewall_rule(
            protocol=neutron.FirewallProtocol.TCP,
            action=neutron.FirewallAction.ALLOW,
            ip_version=6,
            source_ip_address="::1",
            destination_ip_address="::2",
            source_port="1000:2000",
            destination_port=22,
            enabled=False,
            shared=True,
            description="desc")

        self.network.create_firewall_rule.assert_called_once_with(
            name="random_name", protocol="tcp", action="allow", ip_version=6,
            source_ip_address="::1", destination_ip_address="::2",
            source_port="1000:2000", destination_port=22, enabled=False,
            shared=True, description="desc")

    def test_create_firewall_rule_rejects_custom_name(self):
        self.assertRaises(
            TypeError, self.neutron.create_firewall_rule, name="custom")

        self.assertFalse(self.network.create_firewall_rule.called)

    def test_list_firewall_rules(self):
        rules = [mock.Mock(id="rule-1")]
        self.network.firewall_rules.return_value = iter(rules)

        self.assertEqual(rules, self.neutron.list_firewall_rules())
        self.network.firewall_rules.assert_called_once_with()

    def test_list_firewall_rules_by_project(self):
        self.network.firewall_rules.return_value = iter([])

        self.neutron.list_firewall_rules(project_id="project-id")

        self.network.firewall_rules.assert_called_once_with(
            project_id="project-id")

    def test_update_firewall_rule(self):
        rule = self.network.update_firewall_rule.return_value

        result = self.neutron.update_firewall_rule(
            "rule-id", name="new-name",
            action=neutron.FirewallAction.REJECT, enabled=False)

        self.assertIs(rule, result)
        self.network.update_firewall_rule.assert_called_once_with(
            "rule-id", name="new-name", action="reject", enabled=False)
        self.assertFalse(self.neutron._name_generator.called)

    def test_update_firewall_rule_to_any_protocol(self):
        self.neutron.update_firewall_rule(
            "rule-id", protocol=neutron.FirewallProtocol.ANY)

        self.network.update_firewall_rule.assert_called_once_with(
            "rule-id", protocol=None)

    def test_update_firewall_rule_requires_changes(self):
        self.assertRaises(
            ValueError, self.neutron.update_firewall_rule, "rule-id")

        self.assertFalse(self.network.update_firewall_rule.called)

    def test_delete_firewall_rule(self):
        self.neutron.delete_firewall_rule("rule-id")

        self.network.delete_firewall_rule.assert_called_once_with(
            "rule-id", ignore_missing=False)

    def test_create_firewall_policy(self):
        self.neutron._atomic_actions = []
        policy = self.network.create_firewall_policy.return_value

        result = self.neutron.create_firewall_policy()

        self.assertIs(policy, result)
        self.network.create_firewall_policy.assert_called_once_with(
            name="random_name")
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(), "neutron.create_firewall_policy")

    def test_create_firewall_policy_with_all_args(self):
        self.neutron.create_firewall_policy(
            firewall_rules=["rule-1", "rule-2"], audited=True, shared=False,
            description="desc")

        self.network.create_firewall_policy.assert_called_once_with(
            name="random_name", firewall_rules=["rule-1", "rule-2"],
            audited=True, shared=False, description="desc")

    def test_list_firewall_policies(self):
        policies = [mock.Mock(id="policy-1")]
        self.network.firewall_policies.return_value = iter(policies)

        self.assertEqual(policies, self.neutron.list_firewall_policies())
        self.network.firewall_policies.assert_called_once_with()

    def test_list_firewall_policies_by_project(self):
        self.network.firewall_policies.return_value = iter([])

        self.neutron.list_firewall_policies(project_id="project-id")

        self.network.firewall_policies.assert_called_once_with(
            project_id="project-id")

    def test_get_firewall_policy(self):
        policy = self.network.get_firewall_policy.return_value

        self.assertIs(policy, self.neutron.get_firewall_policy("policy-id"))
        self.network.get_firewall_policy.assert_called_once_with("policy-id")

    def test_update_firewall_policy(self):
        policy = self.network.update_firewall_policy.return_value

        result = self.neutron.update_firewall_policy(
            "policy-id", name="new-name", firewall_rules=[])

        self.assertIs(policy, result)
        self.network.update_firewall_policy.assert_called_once_with(
            "policy-id", name="new-name", firewall_rules=[])

    def test_update_firewall_policy_requires_changes(self):
        self.assertRaises(
            ValueError, self.neutron.update_firewall_policy, "policy-id")

        self.assertFalse(self.network.update_firewall_policy.called)

    def test_delete_firewall_policy(self):
        self.neutron.delete_firewall_policy("policy-id")

        self.network.delete_firewall_policy.assert_called_once_with(
            "policy-id", ignore_missing=False)

    def test_insert_firewall_rule_in_policy(self):
        self.neutron._atomic_actions = []
        policy = self.network.insert_rule_into_policy.return_value

        result = self.neutron.insert_firewall_rule_in_policy(
            "policy-id", "rule-id", insert_before="rule-0")

        self.assertIs(policy, result)
        self.network.insert_rule_into_policy.assert_called_once_with(
            "policy-id", "rule-id", insert_after=None, insert_before="rule-0")
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(),
            "neutron.insert_firewall_rule_in_policy")

    def test_remove_firewall_rule_from_policy(self):
        policy = self.network.remove_rule_from_policy.return_value

        result = self.neutron.remove_firewall_rule_from_policy(
            "policy-id", "rule-id")

        self.assertIs(policy, result)
        self.network.remove_rule_from_policy.assert_called_once_with(
            "policy-id", "rule-id")

    def test_create_firewall_group(self):
        self.neutron._atomic_actions = []
        group = self.network.create_firewall_group.return_value

        result = self.neutron.create_firewall_group()

        self.assertIs(group, result)
        self.network.create_firewall_group.assert_called_once_with(
            name="random_name")
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(), "neutron.create_firewall_group")

    def test_create_firewall_group_with_all_args(self):
        self.neutron.create_firewall_group(
            ingress_firewall_policy_id="in-id",
            egress_firewall_policy_id="eg-id",
            ports=["port-1"],
            admin_state_up=False,
            shared=True,
            description="desc")

        self.network.create_firewall_group.assert_called_once_with(
            name="random_name", ingress_firewall_policy_id="in-id",
            egress_firewall_policy_id="eg-id", ports=["port-1"],
            admin_state_up=False, shared=True, description="desc")

    def test_list_firewall_groups(self):
        groups = [mock.Mock(id="group-1")]
        self.network.firewall_groups.return_value = iter(groups)

        self.assertEqual(groups, self.neutron.list_firewall_groups())
        self.network.firewall_groups.assert_called_once_with()

    def test_list_firewall_groups_with_filters(self):
        self.network.firewall_groups.return_value = iter([])

        self.neutron.list_firewall_groups(
            project_id="project-id", name="default")

        self.network.firewall_groups.assert_called_once_with(
            project_id="project-id", name="default")

    def test_update_firewall_group(self):
        group = self.network.update_firewall_group.return_value

        result = self.neutron.update_firewall_group(
            "group-id", name="new-name", ingress_firewall_policy_id="in-id")

        self.assertIs(group, result)
        self.network.update_firewall_group.assert_called_once_with(
            "group-id", name="new-name", ingress_firewall_policy_id="in-id")

    def test_update_firewall_group_requires_changes(self):
        self.assertRaises(
            ValueError, self.neutron.update_firewall_group, "group-id")

        self.assertFalse(self.network.update_firewall_group.called)

    def test_associate_firewall_group_ports(self):
        self.neutron._atomic_actions = []
        group = self.network.update_firewall_group.return_value

        result = self.neutron.associate_firewall_group_ports(
            "group-id", ["port-1", "port-2"])

        self.assertIs(group, result)
        self.network.update_firewall_group.assert_called_once_with(
            "group-id", ports=["port-1", "port-2"])
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(),
            "neutron.associate_firewall_group_port")

    def test_disassociate_firewall_group_ports(self):
        self.neutron._atomic_actions = []
        group = self.network.update_firewall_group.return_value

        result = self.neutron.disassociate_firewall_group_ports("group-id")

        self.assertIs(group, result)
        self.network.update_firewall_group.assert_called_once_with(
            "group-id", ports=[])
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(),
            "neutron.disassociate_firewall_group_port")

    def test_delete_firewall_group(self):
        self.neutron.delete_firewall_group("group-id")

        self.network.delete_firewall_group.assert_called_once_with(
            "group-id", ignore_missing=False)


class NeutronTrunkClientTestCase(NeutronTestMixin):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_list_trunks(self):
        trunks = [mock.MagicMock(), mock.MagicMock()]
        self.network.trunks.return_value = iter(trunks)

        result = self.neutron.list_trunks()

        self.assertEqual(trunks, result)
        self.network.trunks.assert_called_once_with()

    def test_list_trunks_with_filter(self):
        trunks = [mock.MagicMock()]
        self.network.trunks.return_value = iter(trunks)

        result = self.neutron.list_trunks(project_id="proj-123")

        self.assertEqual(trunks, result)
        self.network.trunks.assert_called_once_with(project_id="proj-123")

    def test_delete_trunk(self):
        self.neutron.delete_trunk("trunk-id")

        self.network.delete_trunk.assert_called_once_with("trunk-id")


@ddt.ddt
class NeutronTapFlowTestCase(NeutronTestMixin, test.TestCase):

    def setUp(self):
        super().setUp()
        self.neutron = self._make_neutron()

    def test_create_tap_flow(self):
        self.neutron._atomic_actions = []
        flow = self.network.create_tap_flow.return_value

        result = self.neutron.create_tap_flow("service-id", "port-id")

        self.assertIs(flow, result)
        self.network.create_tap_flow.assert_called_once_with(
            name="random_name", tap_service_id="service-id",
            source_port="port-id", direction="IN")
        self._test_atomic_action_timer(
            self.neutron.atomic_actions(), "neutron.create_tap_flow")

    def test_create_tap_flow_direction(self):
        self.neutron.create_tap_flow(
            "service-id", "port-id", direction="BOTH")

        self.network.create_tap_flow.assert_called_once_with(
            name="random_name", tap_service_id="service-id",
            source_port="port-id", direction="BOTH")

    def test_create_tap_flow_with_description(self):
        self.neutron.create_tap_flow(
            "service-id", "port-id", description="desc")

        self.network.create_tap_flow.assert_called_once_with(
            name="random_name", tap_service_id="service-id",
            source_port="port-id", direction="IN", description="desc")

    def test_create_tap_flow_rejects_custom_name(self):
        self.assertRaises(
            TypeError, self.neutron.create_tap_flow,
            "service-id", "port-id", name="custom-name")

        self.network.create_tap_flow.assert_not_called()

    def test_list_tap_flows(self):
        flows = [mock.Mock(id="flow-1"), mock.Mock(id="flow-2")]
        self.network.tap_flows.return_value = iter(flows)

        self.assertEqual(flows, self.neutron.list_tap_flows())
        self.network.tap_flows.assert_called_once_with()

    @ddt.data({"project_id": "proj-123"}, {"name": "flow-name"},
              {"project_id": "proj-123", "name": "flow-name"})
    def test_list_tap_flows_with_filter(self, filters):
        flows = [mock.Mock(id="flow-1")]
        self.network.tap_flows.return_value = iter(flows)

        result = self.neutron.list_tap_flows(**filters)

        self.assertEqual(flows, result)
        self.network.tap_flows.assert_called_once_with(**filters)

    def test_get_tap_flow(self):
        flow = self.network.get_tap_flow.return_value

        self.assertIs(flow, self.neutron.get_tap_flow("flow-id"))
        self.network.get_tap_flow.assert_called_once_with("flow-id")

    def test_update_tap_flow_with_name(self):
        self.neutron.update_tap_flow("flow-id", name="new-name")

        self.network.update_tap_flow.assert_called_once_with(
            "flow-id", name="new-name")

    def test_update_tap_flow_with_name_and_description(self):
        self.neutron.update_tap_flow(
            "flow-id", name="new-name", description="updated")

        self.network.update_tap_flow.assert_called_once_with(
            "flow-id", name="new-name", description="updated")

    def test_update_tap_flow_clears_description(self):
        self.neutron.update_tap_flow("flow-id", description="")

        self.network.update_tap_flow.assert_called_once_with(
            "flow-id", description="")

    def test_update_tap_flow_requires_changes(self):
        self.assertRaises(
            ValueError, self.neutron.update_tap_flow, "flow-id")

        self.network.update_tap_flow.assert_not_called()

    def test_update_tap_flow_rejects_source_changes(self):
        self.assertRaises(
            TypeError, self.neutron.update_tap_flow,
            "flow-id", source_port="another-port")

        self.network.update_tap_flow.assert_not_called()

    def test_delete_tap_flow(self):
        self.neutron.delete_tap_flow("flow-id")

        self.network.delete_tap_flow.assert_called_once_with(
            "flow-id", ignore_missing=False)
