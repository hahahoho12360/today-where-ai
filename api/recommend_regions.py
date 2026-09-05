from lib.backend import JsonHandler, recommend_regions


class handler(JsonHandler):
    def do_POST(self):  # noqa: N802
        def work():
            payload = self.read_json()
            return {"regions": recommend_regions(payload)}

        self.run(work)

