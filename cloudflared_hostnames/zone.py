import argparse
from collections import OrderedDict
import logging
from .api import Api
from .dns import DnsParams
from .zerotrust import ZeroTrustParams

LOGGER = logging.getLogger('cfd-hostnames.zone')


def ingress_exists(params: ZeroTrustParams, tunnel_ingress: list) -> bool:
    hostname_lower = params.hostname.lower()
    for item in tunnel_ingress:
        if item.get('hostname', '').lower() == hostname_lower:
            return True
    return False


def params_to_tunnel_ingress_entry(params: ZeroTrustParams) -> dict[str, str]:
    origin_request = {}
    if params.notlsverify is not None:
        origin_request['noTLSVerify'] = params.notlsverify
    return {
        'service': params.service,
        'hostname': params.hostname,
        'originRequest': origin_request,
    }


class Zone:
    def __init__(self, api: Api, account_id: str, zone_id: str):
        self._api = api
        self._account_id = account_id
        self._zone_id = zone_id
        self._records = api.get_dns_records(zone_id)
        self._new_records: OrderedDict[DnsParams] = OrderedDict()
        self._ingress_by_tunnel_id: dict[str, list] = {}
        self._ingress_changed = False
        self._dns_removals = set()

    def add_dns_record(self, params: DnsParams):
        if params.name in self._records:
            LOGGER.info('DNS record for "%s" already exists', params.name)
        elif params in self._new_records:
            LOGGER.error('duplicate DNS record for "%s" "%s"', params.name, params.zone_id)
        else:
            self._new_records[params] = None

    def remove_dns_record(self, params: DnsParams):
        LOGGER.info(f'Removing %s DNS record "%s"', params.dns_type.name, params.name)
        record_id = self._api.get_dns_record_id(params.zone_id, params.name)
        if record_id:
            self._dns_removals.add(record_id)
        else:
            LOGGER.warning('No %s DNS record "%s"', params.dns_type.name, params.name)

    def _get_ingress(self, params: ZeroTrustParams):
        tunnel_ingress = self._ingress_by_tunnel_id.get(params.tunnel_id)
        if tunnel_ingress is None:
            tunnel_ingress = self._api.get_tunnel_ingress(self._account_id, params.tunnel_id)
            self._ingress_by_tunnel_id[params.tunnel_id] = tunnel_ingress
        return tunnel_ingress

    def add_ingress(self, params: ZeroTrustParams):
        tunnel_ingress = self._get_ingress(params)
        if ingress_exists(params, tunnel_ingress):
            LOGGER.info('Public hostname "%s" for tunnel "%s" already exists', params.hostname, params.tunnel_id)
        else:
            tunnel_ingress.insert(-1, params_to_tunnel_ingress_entry(params))
            LOGGER.info(f'Adding public hostname "%s" -> "%s" for tunnel "%s"', params.hostname, params.service,
                        params.tunnel_id)
            self._ingress_changed = True

    def remove_ingress(self, params: ZeroTrustParams):
        LOGGER.info(f'Removing public hostname "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
        tunnel_ingress = self._get_ingress(params)
        before_len = len(tunnel_ingress)
        hostname_lower = params.hostname.lower()
        tunnel_ingress = [ii for ii in tunnel_ingress if ii.get('hostname', '').lower() != hostname_lower]
        if before_len == len(tunnel_ingress):
            LOGGER.warning('No public hostname "%s" for tunnel "%s"', params.hostname, params.tunnel_id)
        else:
            self._ingress_by_tunnel_id[params.tunnel_id] = tunnel_ingress
            self._ingress_changed = True

    def update_cloudflare(self, args: argparse.Namespace):
        for record_id in self._dns_removals:
            if not args.dry_run:
                if not self._api.cf.delete_dns_record(self._zone_id, record_id):
                    LOGGER.error('Failed to remove DNS record ID %s', record_id)
        self._dns_removals.clear()

        for params in self._new_records.keys():
            LOGGER.info(f'Adding %s DNS record "%s" -> "%s"', params.dns_type.name, params.name, params.value)
            if not args.dry_run:
                if not self._api.cf.create_dns_record(params.dns_type, params.zone_id, params.name,
                                                      params.value):
                    LOGGER.error('Failed to add %s DNS record "%s"', params.dns_type.name, params.name)
        self._new_records.clear()

        if self._ingress_changed:
            for tunnel_id, tunnel_ingress in self._ingress_by_tunnel_id.items():
                if not args.dry_run:
                    if not self._api.cf.update_tunnel_configs(self._account_id, tunnel_id,
                                                              {'config': {'ingress': tunnel_ingress}}):
                        LOGGER.error(f'Failed to update tunnel ingress for tunnel "{tunnel_id}" failed')
            self._ingress_changed = False
