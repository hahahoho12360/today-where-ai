from lib.backend import JsonHandler, region_from_coordinates


class handler(JsonHandler):
    def do_POST(self):  # noqa: N802
        def work():
            payload = self.read_json()
            return {"region": region_from_coordinates(payload.get("latitude"), payload.get("longitude"))}

        self.run(work)

