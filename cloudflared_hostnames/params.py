class Params:
    def __init__(self, zone_id: str):
        self._zone_id = zone_id

    @property
    def zone_id(self):
        return self._zone_id

    def add_to_zone(self, zone):
        raise NotImplementedError()

    def remove_from_zone(self, zone):
        raise NotImplementedError()
