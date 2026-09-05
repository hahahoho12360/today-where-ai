from lib.backend import JsonHandler, generate_trip


class handler(JsonHandler):
    def do_POST(self):  # noqa: N802
        def work():
            payload = self.read_json()
            return {"result": generate_trip(payload)}

        self.run(work)

