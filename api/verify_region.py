from lib.backend import JsonHandler, verify_region_query


class handler(JsonHandler):
    def do_POST(self):  # noqa: N802
        def work():
            payload = self.read_json()
            return {"region": verify_region_query(payload.get("query"))}

        self.run(work)

