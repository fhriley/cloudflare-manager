from enum import Enum
import logging
from typing import Optional

import CloudFlare

LOGGER = logging.getLogger('cfd-hostnames.api')


class DnsRecordType(Enum):
    A = 1
    CNAME = 2


class CloudflareApi:
    def __init__(self, token: str, debug=False):
        self._cf = CloudFlare.CloudFlare(token=token, debug=debug)

    def get_zone_id(self, zone_name: str) -> Optional[str]:
        try:
            zones = self._cf.zones.get(params={'name': zone_name, 'per_page': 1})
            if not zones:
                return None
            return zones[0]['id']
        except CloudFlare.exceptions.CloudFlareAPIError as exc:
            LOGGER.error('/zones.get %d %s - cloudflare api call failed', exc, exc)
        except Exception as exc:
            LOGGER.error('/zones.get - %s - cloudflare api call failed', exc)
        return None

    def get_tunnel_configs(self, account_id: str, tunnel_id: str) -> Optional[dict]:
        try:
            return self._cf.accounts.cfd_tunnel.configurations.get(account_id, tunnel_id)
        except CloudFlare.exceptions.CloudFlareAPIError as exc:
            LOGGER.error('/accounts/cfd_tunnels/configurations.get %d %s - cloudflare api call failed', exc, exc)
        except Exception as exc:
            LOGGER.error('/accounts/cfd_tunnels/configurations.get - %s - cloudflare api call failed', exc)
        return None

    def get_dns_records(self, zone_id: str) -> Optional[list[dict]]:
        try:
            records = self._cf.zones.dns_records.get(zone_id)
            return [record for record in records if record['type'] in ['A', 'CNAME']]
        except CloudFlare.exceptions.CloudFlareAPIError as exc:
            LOGGER.error('/zones/dns_records.get %d %s - cloudflare api call failed', exc, exc)
        except Exception as exc:
            LOGGER.error('/zones/dns_records.get - %s - cloudflare api call failed', exc)
        return None

    def get_dns_record_id(self, zone_id: str, name: str) -> Optional[str]:
        try:
            records = self._cf.zones.dns_records.get(zone_id, params={'name': name, 'per_page': 1})
            if not records:
                return None
            return records[0]['id']
        except CloudFlare.exceptions.CloudFlareAPIError as exc:
            LOGGER.error('/zones.get %d %s - cloudflare api call failed', exc, exc)
        except Exception as exc:
            LOGGER.error('/zones.get - %s - cloudflare api call failed', exc)
        return None

    def create_dns_record(self, typ: DnsRecordType, zone_id: str, hostname: str, value: str, proxied: bool) -> bool:
        try:
            self._cf.zones.dns_records.post(zone_id, data={
                'type': typ.name,
                'proxied': proxied,
                'name': hostname,
                'content': value,
            })
        except CloudFlare.exceptions.CloudFlareAPIError as exc:
            LOGGER.error('/zones/dns_records.post %d %s - cloudflare api call failed', exc, exc)
            return False
        except Exception as exc:
            LOGGER.error('/zones/dns_records.post - %s - cloudflare api call failed', exc)
            return False
        return True

    def delete_dns_record(self, zone_id: str, dns_record_id: str) -> bool:
        try:
            self._cf.zones.dns_records.delete(zone_id, dns_record_id)
        except CloudFlare.exceptions.CloudFlareAPIError as exc:
            LOGGER.error('/zones/dns_records.delete %d %s - cloudflare api call failed', exc, exc)
            return False
        except Exception as exc:
            LOGGER.error('/zones/dns_records.delete - %s - cloudflare api call failed', exc)
            return False
        return True

    def update_tunnel_configs(self, account_id: str, tunnel_id: str, data: dict) -> bool:
        try:
            self._cf.accounts.cfd_tunnel.configurations.put(account_id, tunnel_id, data=data)
        except CloudFlare.exceptions.CloudFlareAPIError as exc:
            LOGGER.error('/accounts/cfd_tunnels/configurations.put %d %s - cloudflare api call failed', exc, exc)
            return False
        except Exception as exc:
            LOGGER.error('/accounts/cfd_tunnels/configurations.put - %s - cloudflare api call failed', exc)
            return False
        return True
