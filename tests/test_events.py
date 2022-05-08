import argparse
import logging
import unittest
from unittest.mock import Mock

from cloudflared_hostnames.cloudflare_api import CloudflareApi, DnsRecordType
from cloudflared_hostnames.api import CachedApi
from cloudflared_hostnames.zerotrust import ZeroTrustParams
from cloudflared_hostnames.zone import Zone

args = argparse.Namespace(dry_run=False)


class TestEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger().setLevel(logging.CRITICAL)

    def test_start(self):
        cf_mock = Mock(CloudflareApi)
        cf_mock.get_zone_id.return_value = 'example_zone_id'
        cf_mock.get_dns_records.return_value = []
        cf_mock.get_tunnel_configs.return_value = {'tunnel_id': 'tunnel_id', 'config': None}

        params = ZeroTrustParams('host.example.com', 'http://service:80', 'example.com', 'example_zone_id', 'tunnel_id', None)
        zone = Zone(CachedApi(cf_mock), 'account_id', params.zone_id)
        params.add_to_zone(zone)
        zone.update_cloudflare(args)

        cf_mock.create_dns_record.assert_called_once_with(DnsRecordType.CNAME, 'example_zone_id', 'host.example.com',
                                                          'tunnel_id.cfargotunnel.com')
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

        params = ZeroTrustParams('host.example.com', 'http://service:80', 'example.com', 'example_zone_id', 'tunnel_id', None)
        zone = Zone(CachedApi(cf_mock), 'account_id', params.zone_id)
        params.add_to_zone(zone)
        zone.update_cloudflare(args)

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

        params = ZeroTrustParams('host.example.com', 'http://service:80', 'example.com', 'example_zone_id', 'tunnel_id', None)
        zone = Zone(CachedApi(cf_mock), 'account_id', params.zone_id)
        params.add_to_zone(zone)
        zone.update_cloudflare(args)

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

        params = ZeroTrustParams('host.example.com', 'http://service:80', 'example.com', 'example_zone_id', 'tunnel_id', None)
        zone = Zone(CachedApi(cf_mock), 'account_id', params.zone_id)
        params.remove_from_zone(zone)
        zone.update_cloudflare(args)

        cf_mock.delete_dns_record.assert_called_once_with('example_zone_id', 'dns_record_id')
        value = {
            'config': {
                'ingress': [
                    {'service': 'http_status:404'},
                ]
            }
        }
        cf_mock.update_tunnel_configs.assert_called_once_with('account_id', 'tunnel_id', value)

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

        params = ZeroTrustParams('host.example.com', 'http://service:80', 'example.com', 'example_zone_id', 'tunnel_id', None)
        zone = Zone(CachedApi(cf_mock), 'account_id', params.zone_id)
        params.remove_from_zone(zone)
        zone.update_cloudflare(args)

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

        params = ZeroTrustParams('host.example.com', 'http://service:80', 'example.com', 'example_zone_id', 'tunnel_id', None)
        zone = Zone(CachedApi(cf_mock), 'account_id', params.zone_id)
        params.remove_from_zone(zone)
        zone.update_cloudflare(args)

        cf_mock.delete_dns_record.assert_called_once_with('example_zone_id', 'dns_record_id')
        cf_mock.update_tunnel_configs.assert_not_called()
