from .api import Api


class Params:
    def __init__(self, api: Api, account_id: str, zone_id: str):
        self._api = api
        self._account_id = account_id
        self._zone_id = zone_id

    @property
    def api(self):
        return self._api

    @property
    def account_id(self):
        return self._account_id

    @property
    def zone_id(self):
        return self._zone_id

    def add_to_zone(self, zone):
        raise NotImplementedError()

    def remove_from_zone(self, zone):
        raise NotImplementedError()

    def add_to_tunnel(self, tunnels: dict):
        pass

    def remove_from_tunnel(self, tunnels: dict):
        pass
