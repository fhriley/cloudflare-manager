from typing import List, Dict, Optional
from .cloudflare_api import CloudflareApi


class Api:
    def __init__(self, cf: CloudflareApi):
        self._cf = cf

    @property
    def cf(self):
        return self._cf

    def get_zone_id(self, name: str) -> str:
        zone_id = self._cf.get_zone_id(name)
        if not zone_id:
            raise Exception(f'Could not find zone name "{name}"')
        return zone_id

    def get_dns_record_id(self, zone_id: str, name: str) -> Optional[str]:
        return self._cf.get_dns_record_id(zone_id, name)

    def get_dns_records(self, zone_id: str) -> Dict:
        records = self._cf.get_dns_records(zone_id)
        if records is None:
            raise Exception(f'Could not find zone id "{zone_id}"')
        return {ii['name']: ii for ii in records}

    def get_tunnel_ingress(self, account_id: str, tunnel_id: str) -> List:
        tunnel_ingress = self._cf.get_tunnel_configs(account_id, tunnel_id)
        if tunnel_ingress is None:
            raise Exception(f'Could not find tunnel ingress for account "{account_id}" and tunnel "{tunnel_id}"')
        return (tunnel_ingress.get('config') or {}).get('ingress') or [{'service': 'http_status:404'}]


class CachedApi(Api):
    def __init__(self, cf: CloudflareApi):
        super().__init__(cf)
        self._zone_name_to_id: Dict[str, str] = {}
        self._dns_records_by_zone_id: Dict = {}
        self._tunnel_config_cache: Dict = {}
        self._dns_record_id_cache: Dict = {}

    def get_zone_id(self, name: str) -> str:
        return self._get_from_cache(self._zone_name_to_id, super().get_zone_id, name)

    def get_dns_record_id(self, zone_id: str, name: str) -> str:
        return self._get_from_cache(self._dns_record_id_cache, super().get_dns_record_id, zone_id, name)

    def get_dns_records(self, zone_id: str) -> Dict:
        return self._get_from_cache(self._dns_records_by_zone_id, super().get_dns_records, zone_id)

    def get_tunnel_ingress(self, account_id: str, tunnel_id: str) -> List:
        return self._get_from_cache(self._tunnel_config_cache, super().get_tunnel_ingress, account_id, tunnel_id)

    @staticmethod
    def _get_from_cache(cache, func, *keys):
        if keys in cache:
            val = cache[keys]
        else:
            val = func(*keys)
            cache[keys] = val
        return val
