import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IdAndLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.local_links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a" and str(values.get("href", "")).startswith("#"):
            self.local_links.append(values["href"][1:])


class ProjectContractTests(unittest.TestCase):
    def test_five_required_sections_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for section_id in ("setup", "plan", "places", "local-info", "summary"):
            self.assertIn(f'id="{section_id}"', html)

    def test_ids_are_unique_and_menu_targets_exist(self):
        parser = IdAndLinkParser()
        parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for target in parser.local_links:
            self.assertIn(target, parser.ids)

    def test_frontend_uses_required_api_routes(self):
        js = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        for route in ("/api/verify_region", "/api/current_region", "/api/recommend_regions", "/api/generate"):
            self.assertIn(route, js)
        self.assertIn("navigator.geolocation", js)
        self.assertIn("AbortController", js)

    def test_secret_files_are_ignored(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".env", ignored)
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("sk-", example)

    def test_python_api_files_exist(self):
        for name in ("current_region.py", "verify_region.py", "recommend_regions.py", "generate.py", "health.py"):
            self.assertTrue((ROOT / "api" / name).exists())

    def test_responsive_breakpoints_exist(self):
        css = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")
        for breakpoint in ("900px", "720px", "460px"):
            self.assertIn(f"max-width: {breakpoint}", css)
        self.assertIn("prefers-reduced-motion", css)


if __name__ == "__main__":
    unittest.main()
