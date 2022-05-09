import argparse
from collections import OrderedDict
import logging
import unittest
from unittest.mock import Mock, call

from cloudflare_manager.cloudflare_api import CloudflareApi, DnsRecordType
from cloudflare_manager.api import CachedApi
from cloudflare_manager.main import handle_start_event, handle_die_event, update_cloudflare
from cloudflare_manager.zerotrust import ZeroTrustParams

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s|%(name)s|%(levelname)s|%(message)s')

args = argparse.Namespace(dry_run=False)


class TestEvents(unittest.TestCase):
    def test_start(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = []
        cf_mock.get_tunnel_configs.return_value = {'tunnel_id': 'tunnel_id', 'config': None}

        params = ZeroTrustParams(CachedApi(cf_mock), 'account_id', 'host.example.com', 'http://service:80',
                                 'example.com', 'example_zone_id', 'tunnel_id',
                                 None)
        zones = {}
        tunnels = {}
        handle_start_event(zones, tunnels, params)
        update_cloudflare(args, zones, tunnels)

        cf_mock.create_dns_record.assert_called_once_with(DnsRecordType.CNAME, 'example_zone_id', 'host.example.com',
                                                          'tunnel_id.cfargotunnel.com', True)
        value = {
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_called_once_with('account_id', 'tunnel_id', value)

    def test_start_cname_already_exists(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = [{'name': 'host.example.com'}]
        cf_mock.get_tunnel_configs.return_value = {'tunnel_id': 'tunnel_id', 'config': None}

        params = ZeroTrustParams(CachedApi(cf_mock), 'account_id', 'host.example.com', 'http://service:80',
                                 'example.com', 'example_zone_id', 'tunnel_id',
                                 None)
        zones = {}
        tunnels = {}
        handle_start_event(zones, tunnels, params)
        update_cloudflare(args, zones, tunnels)

        cf_mock.create_dns_record.assert_not_called()

    def test_start_ingress_already_exists(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = [{'name': 'host.example.com'}]
        cf_mock.get_tunnel_configs.return_value = {
            'tunnel_id': 'tunnel_id',
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ],
            },
        }

        params = ZeroTrustParams(CachedApi(cf_mock), 'account_id', 'host.example.com', 'http://service:80',
                                 'example.com', 'example_zone_id', 'tunnel_id',
                                 None)
        zones = {}
        tunnels = {}
        handle_start_event(zones, tunnels, params)
        update_cloudflare(args, zones, tunnels)

        cf_mock.update_tunnel_configs.assert_not_called()

    def test_die(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_dns_record_id.return_value = 'dns_record_id'
        cf_mock.get_dns_records.return_value = [{'name': 'host.example.com'}]
        cf_mock.get_tunnel_configs.return_value = {
            'tunnel_id': 'tunnel_id',
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ],
            },
        }

        params = ZeroTrustParams(CachedApi(cf_mock), 'account_id', 'host.example.com', 'http://service:80',
                                 'example.com', 'example_zone_id', 'tunnel_id',
                                 None)
        zones = {}
        tunnels = {}
        handle_die_event(zones, tunnels, params)
        update_cloudflare(args, zones, tunnels)

        cf_mock.delete_dns_record.assert_called_once_with('example_zone_id', 'dns_record_id')
        value = {
            'config': {
                'ingress': [
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_called_once_with('account_id', 'tunnel_id', value)

    def test_die_multiple(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_dns_record_id.side_effect = ['dns_record_id3', 'dns_record_id']
        cf_mock.get_dns_records.return_value = []
        cf_mock.get_tunnel_configs.return_value = {
            'tunnel_id': 'tunnel_id',
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http://service:80', 'hostname': 'host.example2.com', 'originRequest': {}},
                    {'service': 'http://service:80', 'hostname': 'host.example3.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ],
            },
        }

        api = CachedApi(cf_mock)

        params = [
            ZeroTrustParams(api, 'account_id', 'host.example3.com', 'http://service:80', 'example3.com',
                            'example3_zone_id', 'tunnel_id',
                            None),
            ZeroTrustParams(api, 'account_id', 'host.example.com', 'http://service:80', 'example.com',
                            'example_zone_id', 'tunnel_id',
                            None),
        ]

        zones = OrderedDict()
        tunnels = OrderedDict()
        for pp in params:
            handle_die_event(zones, tunnels, pp)
        update_cloudflare(args, zones, tunnels)

        # for pp in params:
        #     zone = zones.get(pp.zone_id) or Zone(api, 'account_id', pp.zone_id)
        #     zones[pp.zone_id] = zone
        #     pp.remove_from_zone(zone)
        #
        # for zone in zones.values():
        #     zone.update_cloudflare(args)

        cf_mock.delete_dns_record.assert_has_calls([
            call('example3_zone_id', 'dns_record_id3'),
            call('example_zone_id', 'dns_record_id'),
        ])

        value = {
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example2.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_has_calls([
            call('account_id', 'tunnel_id', value),
        ])

    def test_die_cname_doesnt_exist(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_dns_record_id.return_value = None
        cf_mock.get_dns_records.return_value = []
        cf_mock.get_tunnel_configs.return_value = {
            'tunnel_id': 'tunnel_id',
            'config': {
                'ingress': [
                    {'service': 'http://service:80', 'hostname': 'host.example.com', 'originRequest': {}},
                    {'service': 'http_status:404'},
                ],
            },
        }

        params = ZeroTrustParams(CachedApi(cf_mock), 'account_id', 'host.example.com', 'http://service:80',
                                 'example.com', 'example_zone_id', 'tunnel_id',
                                 None)
        zones = {}
        tunnels = {}
        handle_die_event(zones, tunnels, params)
        update_cloudflare(args, zones, tunnels)

        cf_mock.delete_dns_record.assert_not_called()
        value = {
            'config': {
                'ingress': [
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_called_once_with('account_id', 'tunnel_id', value)

    def test_die_ingress_doesnt_exist(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_dns_record_id.return_value = 'dns_record_id'
        cf_mock.get_dns_records.return_value = [{'name': 'host.example.com'}]
        cf_mock.get_tunnel_configs.return_value = {
            'tunnel_id': 'tunnel_id',
            'config': {
                'ingress': [
                    {'service': 'http_status:404'},
                ],
            },
        }

        params = ZeroTrustParams(CachedApi(cf_mock), 'account_id', 'host.example.com', 'http://service:80',
                                 'example.com', 'example_zone_id', 'tunnel_id',
                                 None)
        zones = {}
        tunnels = {}
        handle_die_event(zones, tunnels, params)
        update_cloudflare(args, zones, tunnels)

        cf_mock.delete_dns_record.assert_called_once_with('example_zone_id', 'dns_record_id')
        cf_mock.update_tunnel_configs.assert_not_called()
