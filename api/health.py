import os

from lib.backend import JsonHandler


class handler(JsonHandler):
    def do_GET(self):  # noqa: N802
        self.run(
            lambda: {
                "status": "healthy",
                "configured": {
                    "openai": bool(os.getenv("OPENAI_API_KEY")),
                    "kakao": bool(os.getenv("KAKAO_REST_API_KEY")),
                    "tour": bool(os.getenv("TOUR_API_KEY")),
                },
            }
        )

