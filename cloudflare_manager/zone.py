import argparse
from collections import OrderedDict
import logging
from .api import Api
from .dns import DnsParams

LOGGER = logging.getLogger('cf-mgr.zone')


class Zone:
    def __init__(self, api: Api, account_id: str, zone_id: str):
        self._api = api
        self._account_id = account_id
        self._zone_id = zone_id
        self._records = api.get_dns_records(zone_id)
        self._new_records: OrderedDict[DnsParams] = OrderedDict()
        self._dns_removals: OrderedDict[str] = OrderedDict()

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
            self._dns_removals[record_id] = None
        else:
            LOGGER.warning('No %s DNS record "%s"', params.dns_type.name, params.name)

    def update_cloudflare(self, args: argparse.Namespace):
        for record_id in self._dns_removals.keys():
            if not args.dry_run:
                if not self._api.cf.delete_dns_record(self._zone_id, record_id):
                    LOGGER.error('Failed to remove DNS record ID %s', record_id)
        self._dns_removals.clear()

        for params in self._new_records.keys():
            LOGGER.info('Adding %s DNS record "%s" -> "%s"', params.dns_type.name, params.name, params.value)
            if not args.dry_run:
                if not self._api.cf.create_dns_record(params.dns_type, params.zone_id, params.name,
                                                      params.value, params.proxied):
                    LOGGER.error('Failed to add %s DNS record "%s"', params.dns_type.name, params.name)
        self._new_records.clear()
