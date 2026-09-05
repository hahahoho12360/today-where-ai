import sys
import types
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from pydantic import ValidationError

# 이 실행 환경에 배포 의존성이 아직 설치되지 않아도 순수 검증 로직은 검사한다.
# 실제 배포 환경에서는 requirements.txt의 진짜 패키지가 사용된다.
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Timeout = type("Timeout", (Exception,), {})
    requests_stub.RequestException = type("RequestException", (Exception,), {})
    requests_stub.get = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

try:
    import dotenv  # noqa: F401
except ModuleNotFoundError:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda: None
    sys.modules["dotenv"] = dotenv_stub

try:
    import openai  # noqa: F401
except ModuleNotFoundError:
    openai_stub = types.ModuleType("openai")
    for name in (
        "APIConnectionError", "APIStatusError", "APITimeoutError",
        "AuthenticationError", "RateLimitError",
    ):
        setattr(openai_stub, name, type(name, (Exception,), {}))
    openai_stub.OpenAI = type("OpenAI", (), {})
    sys.modules["openai"] = openai_stub

from lib.backend import (
    AiTripPlan,
    ServiceError,
    generate_trip,
    normalize_place,
    region_from_coordinates,
    validate_coordinates,
    validate_interests,
    validate_time,
    validate_trip_date,
    today_in_korea,
)


class ValidationTests(unittest.TestCase):
    def test_valid_korean_coordinates(self):
        self.assertEqual(validate_coordinates("37.5665", "126.9780"), (37.5665, 126.978))

    def test_outside_korea_is_rejected(self):
        with self.assertRaises(ServiceError) as context:
            validate_coordinates(40.8, -73.9)
        self.assertEqual(context.exception.code, "OUTSIDE_KOREA")

    def test_trip_date_accepts_today(self):
        self.assertEqual(validate_trip_date(today_in_korea().isoformat()), today_in_korea().isoformat())

    def test_old_trip_date_is_rejected(self):
        old = (today_in_korea() - timedelta(days=7)).isoformat()
        with self.assertRaises(ServiceError) as context:
            validate_trip_date(old)
        self.assertEqual(context.exception.code, "PAST_DATE")

    def test_bad_time_is_rejected(self):
        with self.assertRaises(ServiceError):
            validate_time("25:80", "10:00")

    def test_interest_is_required(self):
        with self.assertRaises(ServiceError):
            validate_interests([])


class RegionTests(unittest.TestCase):
    @patch("lib.backend.kakao_get")
    def test_coordinate_result_contains_legal_and_admin_dong(self, kakao_get):
        kakao_get.return_value = {
            "documents": [
                {
                    "region_type": "B", "address_name": "서울특별시 종로구 청운동",
                    "region_1depth_name": "서울특별시", "region_2depth_name": "종로구",
                    "region_3depth_name": "청운동", "code": "1111010100",
                },
                {
                    "region_type": "H", "address_name": "서울특별시 종로구 청운효자동",
                    "region_1depth_name": "서울특별시", "region_2depth_name": "종로구",
                    "region_3depth_name": "청운효자동", "code": "1111051500",
                },
            ]
        }
        result = region_from_coordinates(37.58, 126.97)
        self.assertTrue(result["verified"])
        self.assertEqual(result["legal_dong"], "청운동")
        self.assertEqual(result["administrative_dong"], "청운효자동")


class PlaceTests(unittest.TestCase):
    def test_normalize_place_never_invents_missing_fields(self):
        result = normalize_place({"id": "1", "place_name": "테스트 식당", "x": "127", "y": "37"})
        self.assertEqual(result["phone"], "전화번호 미제공")
        self.assertEqual(result["address"], "주소 미상")
        self.assertNotIn("rating", result)
        self.assertNotIn("opening_hours", result)


class StructuredOutputTests(unittest.TestCase):
    def test_ai_plan_schema_rejects_empty_schedule(self):
        payload = {
            "title": "동네 하루 여행",
            "summary": "검증된 장소를 이용하는 안전한 하루 여행입니다.",
            "schedule": [],
            "picks": {
                "restaurant_id": "1", "restaurant_reason": "가까움",
                "cafe_id": "2", "cafe_reason": "동선",
                "parking_id": "3", "parking_reason": "거리",
            },
            "weather_tip": "우산을 확인하세요.",
            "checklist": ["물", "편한 신발"],
        }
        with self.assertRaises(ValidationError):
            AiTripPlan.model_validate(payload)

    @patch("lib.backend.parse_with_ai")
    @patch("lib.backend.fetch_events")
    @patch("lib.backend.fetch_weather")
    @patch("lib.backend.fetch_place_pools")
    def test_unverified_ai_place_ids_are_replaced(
        self, fetch_pools, fetch_weather, fetch_events, parse_ai
    ):
        verified = {
            "id": "verified-1", "name": "검증 장소", "address": "서울 종로구",
            "url": "https://place.map.kakao.com/1", "distance_m": 100,
            "phone": "전화번호 미제공", "category": "음식점",
            "latitude": 37.5, "longitude": 126.9,
        }
        fetch_pools.return_value = {
            "restaurant": [verified], "cafe": [], "parking": [], "attraction": []
        }
        fetch_weather.return_value = {"available": False, "message": "없음"}
        fetch_events.return_value = {"available": False, "message": "없음"}
        parse_ai.return_value = AiTripPlan.model_validate({
            "title": "검증된 동네 하루 여행",
            "summary": "검증 후보만 사용하도록 서버가 한 번 더 확인하는 일정입니다.",
            "schedule": [{
                "time": "10:00", "place_id": "invented-id",
                "activity": "가짜 장소 방문", "reason": "AI가 잘못 만든 ID",
            }],
            "picks": {
                "restaurant_id": "invented-id", "restaurant_reason": "AI 선택",
                "cafe_id": "", "cafe_reason": "후보 없음",
                "parking_id": "", "parking_reason": "후보 없음",
            },
            "weather_tip": "예보를 확인하세요.",
            "checklist": ["물", "편한 신발"],
        })
        payload = {
            "date": today_in_korea().isoformat(),
            "region": {
                "verified": True, "latitude": 37.5, "longitude": 126.9,
                "display_name": "서울특별시 종로구 청운효자동",
                "legal_dong": "청운동", "administrative_dong": "청운효자동",
                "province": "서울특별시",
            },
            "radius": 3000, "interests": ["맛집"],
            "start_time": "10:00", "end_time": "19:00",
        }
        result = generate_trip(payload)
        self.assertEqual(result["places"]["restaurant"]["id"], "verified-1")
        self.assertEqual(result["schedule"][0]["place_id"], "verified-1")
        self.assertNotIn("invented-id", str(result["schedule"]))


if __name__ == "__main__":
    unittest.main()
