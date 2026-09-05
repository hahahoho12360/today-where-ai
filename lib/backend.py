"""외부 API 호출, 입력 검증, JSON 응답을 한곳에서 관리한다."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable, Literal
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

KAKAO_BASE_URL = "https://dapi.kakao.com/v2/local"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TOUR_API_URL = "https://apis.data.go.kr/B551011/KorService2/searchFestival2"
HTTP_TIMEOUT = (3.05, 9)


def today_in_korea() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


class ServiceError(Exception):
    """사용자에게 안전하게 보여 줄 수 있는 오류."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class RegionIdea(BaseModel):
    full_address: str = Field(min_length=4, max_length=80)
    dong_type: Literal["법정동", "행정동"]
    reason: str = Field(min_length=8, max_length=160)


class RegionIdeas(BaseModel):
    candidates: list[RegionIdea] = Field(min_length=3, max_length=5)


class PlacePick(BaseModel):
    restaurant_id: str
    restaurant_reason: str = Field(max_length=140)
    cafe_id: str
    cafe_reason: str = Field(max_length=140)
    parking_id: str
    parking_reason: str = Field(max_length=140)


class ScheduleItem(BaseModel):
    time: str = Field(min_length=4, max_length=12)
    place_id: str
    activity: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=4, max_length=140)


class AiTripPlan(BaseModel):
    title: str = Field(min_length=4, max_length=80)
    summary: str = Field(min_length=10, max_length=280)
    schedule: list[ScheduleItem] = Field(min_length=1, max_length=6)
    picks: PlacePick
    weather_tip: str = Field(max_length=180)
    checklist: list[str] = Field(min_length=2, max_length=7)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ServiceError(
            503,
            "CONFIG_MISSING",
            f"서버에 {name} 환경 변수가 등록되지 않았습니다. 관리자에게 알려 주세요.",
        )
    return value


def validate_coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ServiceError(400, "INVALID_COORDINATES", "위도와 경도 값이 올바르지 않습니다.") from exc

    if not 33.0 <= lat <= 39.6 or not 124.0 <= lng <= 132.2:
        raise ServiceError(
            422,
            "OUTSIDE_KOREA",
            "현재 위치가 대한민국 범위 밖으로 확인되었습니다. 지역을 직접 입력해 주세요.",
        )
    return lat, lng


def validate_trip_date(value: Any) -> str:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ServiceError(400, "INVALID_DATE", "여행 날짜를 YYYY-MM-DD 형식으로 선택해 주세요.") from exc
    if parsed < today_in_korea():
        raise ServiceError(422, "PAST_DATE", "지난 날짜가 아닌 오늘 이후의 날짜를 선택해 주세요.")
    return parsed.isoformat()


def validate_time(value: Any, fallback: str) -> str:
    clean = str(value or fallback)
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clean):
        raise ServiceError(400, "INVALID_TIME", "시간을 00:00부터 23:59 사이로 선택해 주세요.")
    return clean


def validate_interests(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ServiceError(400, "INTEREST_REQUIRED", "관심사를 한 개 이상 선택해 주세요.")
    cleaned = [str(item).strip()[:30] for item in value[:6] if str(item).strip()]
    if not cleaned:
        raise ServiceError(400, "INTEREST_REQUIRED", "관심사를 한 개 이상 선택해 주세요.")
    return cleaned


def kakao_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    key = required_env("KAKAO_REST_API_KEY")
    try:
        response = requests.get(
            f"{KAKAO_BASE_URL}{path}",
            headers={"Authorization": f"KakaoAK {key}"},
            params=params,
            timeout=HTTP_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ServiceError(504, "KAKAO_TIMEOUT", "지역 정보 응답이 늦어지고 있습니다. 잠시 후 다시 시도해 주세요.") from exc
    except requests.RequestException as exc:
        raise ServiceError(502, "KAKAO_NETWORK", "지역 정보 서버에 연결하지 못했습니다.") from exc

    if response.status_code in (401, 403):
        raise ServiceError(503, "KAKAO_AUTH", "카카오 API 키 또는 권한 설정을 확인해 주세요.")
    if not response.ok:
        raise ServiceError(502, "KAKAO_ERROR", "카카오 지역 정보를 불러오지 못했습니다.")
    try:
        return response.json()
    except ValueError as exc:
        raise ServiceError(502, "KAKAO_BAD_JSON", "지역 정보의 응답 형식이 올바르지 않습니다.") from exc


def region_from_coordinates(latitude: Any, longitude: Any) -> dict[str, Any]:
    lat, lng = validate_coordinates(latitude, longitude)
    data = kakao_get(
        "/geo/coord2regioncode.json",
        {"x": lng, "y": lat, "input_coord": "WGS84", "output_coord": "WGS84"},
    )
    documents = data.get("documents", [])
    legal = next((item for item in documents if item.get("region_type") == "B"), None)
    admin = next((item for item in documents if item.get("region_type") == "H"), None)
    if not legal and not admin:
        raise ServiceError(404, "REGION_NOT_FOUND", "이 좌표에서 행정구역을 찾지 못했습니다.")

    basis = legal or admin
    return {
        "display_name": (admin or legal).get("address_name", ""),
        "legal_dong": legal.get("region_3depth_name", "") if legal else "",
        "administrative_dong": admin.get("region_3depth_name", "") if admin else "",
        "province": basis.get("region_1depth_name", ""),
        "district": basis.get("region_2depth_name", ""),
        "legal_code": legal.get("code", "") if legal else "",
        "administrative_code": admin.get("code", "") if admin else "",
        "latitude": lat,
        "longitude": lng,
        "verified": True,
    }


def verify_region_query(query: Any) -> dict[str, Any]:
    clean_query = " ".join(str(query or "").split())
    if len(clean_query) < 4 or len(clean_query) > 80:
        raise ServiceError(400, "INVALID_REGION", "시·도, 시·군·구, 동을 포함한 지역명을 입력해 주세요.")
    if len(clean_query.split()) < 2:
        raise ServiceError(
            422,
            "AMBIGUOUS_REGION",
            "같은 이름의 동이 여러 곳에 있습니다. 예: ‘서울특별시 종로구 청운효자동’처럼 입력해 주세요.",
        )

    data = kakao_get("/search/address.json", {"query": clean_query, "size": 10})
    documents = data.get("documents", [])
    if documents:
        first = documents[0]
        return region_from_coordinates(first.get("y"), first.get("x"))

    # 행정동 이름은 주소 검색에서 누락될 수 있어 주민센터 검색으로 한 번 보완한다.
    keyword = kakao_get(
        "/search/keyword.json",
        {"query": f"{clean_query} 주민센터", "size": 10, "sort": "accuracy"},
    )
    places = keyword.get("documents", [])
    if not places:
        raise ServiceError(
            404,
            "REGION_NOT_FOUND",
            "지역을 확인하지 못했습니다. 시·도부터 동까지 전체 이름을 다시 입력해 주세요.",
        )
    return region_from_coordinates(places[0].get("y"), places[0].get("x"))


def normalize_place(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id", "")),
        "name": item.get("place_name", "이름 미상"),
        "category": item.get("category_group_name") or item.get("category_name", ""),
        "address": item.get("road_address_name") or item.get("address_name", "주소 미상"),
        "phone": item.get("phone") or "전화번호 미제공",
        "distance_m": int(item.get("distance") or 0),
        "url": item.get("place_url", ""),
        "latitude": float(item.get("y") or 0),
        "longitude": float(item.get("x") or 0),
    }


def search_category(
    latitude: float,
    longitude: float,
    category: str,
    radius: int,
    excluded_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded_ids = excluded_ids or set()
    allowed = {"FD6", "CE7", "PK6", "AT4", "CT1"}
    if category not in allowed:
        raise ServiceError(400, "INVALID_CATEGORY", "지원하지 않는 장소 종류입니다.")

    def fetch(search_radius: int) -> list[dict[str, Any]]:
        result = kakao_get(
            "/search/category.json",
            {
                "category_group_code": category,
                "x": longitude,
                "y": latitude,
                "radius": search_radius,
                "size": 15,
                "sort": "distance",
            },
        )
        return [
            normalize_place(item)
            for item in result.get("documents", [])
            if str(item.get("id", "")) not in excluded_ids
        ]

    places = fetch(radius)
    if not places and radius < 20000:
        places = fetch(min(radius * 2, 20000))
    return places


def fetch_place_pools(
    region: dict[str, Any], radius: int, excluded_ids: set[str]
) -> dict[str, list[dict[str, Any]]]:
    lat, lng = validate_coordinates(region.get("latitude"), region.get("longitude"))
    safe_radius = max(500, min(int(radius or 3000), 20000))
    return {
        "restaurant": search_category(lat, lng, "FD6", safe_radius, excluded_ids),
        "cafe": search_category(lat, lng, "CE7", safe_radius, excluded_ids),
        "parking": search_category(lat, lng, "PK6", safe_radius, excluded_ids),
        "attraction": (
            search_category(lat, lng, "AT4", safe_radius, excluded_ids)
            + search_category(lat, lng, "CT1", safe_radius, excluded_ids)
        )[:15],
    }


WEATHER_CODES = {
    0: "맑음",
    1: "대체로 맑음",
    2: "부분적으로 흐림",
    3: "흐림",
    45: "안개",
    48: "서리 안개",
    51: "약한 이슬비",
    53: "이슬비",
    55: "강한 이슬비",
    61: "약한 비",
    63: "비",
    65: "강한 비",
    71: "약한 눈",
    73: "눈",
    75: "강한 눈",
    80: "소나기",
    81: "강한 소나기",
    82: "매우 강한 소나기",
    95: "뇌우",
}


def fetch_weather(latitude: float, longitude: float, trip_date: str) -> dict[str, Any]:
    target = datetime.strptime(trip_date, "%Y-%m-%d").date()
    today = today_in_korea()
    if target < today or target > today + timedelta(days=15):
        return {
            "available": False,
            "message": "날씨 예보 제공 범위(오늘부터 15일 이내) 밖입니다. 여행일이 가까워지면 다시 확인해 주세요.",
        }
    try:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "Asia/Seoul",
                "start_date": trip_date,
                "end_date": trip_date,
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        daily = response.json().get("daily", {})
        if not daily.get("time"):
            raise ValueError("empty daily weather")
        code = int(daily.get("weather_code", [3])[0])
        return {
            "available": True,
            "date": daily["time"][0],
            "condition": WEATHER_CODES.get(code, f"기상 코드 {code}"),
            "temperature_max": daily.get("temperature_2m_max", [None])[0],
            "temperature_min": daily.get("temperature_2m_min", [None])[0],
            "precipitation_probability": daily.get("precipitation_probability_max", [None])[0],
            "source": "Open-Meteo",
        }
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return {"available": False, "message": "날씨 정보를 잠시 불러오지 못했습니다."}


AREA_CODES = {
    "서울": "1", "서울특별시": "1", "인천": "2", "인천광역시": "2",
    "대전": "3", "대전광역시": "3", "대구": "4", "대구광역시": "4",
    "광주": "5", "광주광역시": "5", "부산": "6", "부산광역시": "6",
    "울산": "7", "울산광역시": "7", "세종": "8", "세종특별자치시": "8",
    "경기": "31", "경기도": "31", "강원": "32", "강원특별자치도": "32",
    "충북": "33", "충청북도": "33", "충남": "34", "충청남도": "34",
    "경북": "35", "경상북도": "35", "경남": "36", "경상남도": "36",
    "전북": "37", "전북특별자치도": "37", "전남": "38", "전라남도": "38",
    "제주": "39", "제주특별자치도": "39",
}


def fetch_events(province: str, trip_date: str) -> dict[str, Any]:
    key = os.getenv("TOUR_API_KEY", "").strip()
    if not key:
        return {
            "available": False,
            "message": "선택 환경 변수 TOUR_API_KEY를 등록하면 실제 지역 축제를 보여 줍니다.",
        }
    area_code = AREA_CODES.get(province)
    if not area_code:
        return {"available": False, "message": "이 지역의 행사 코드 정보를 찾지 못했습니다."}
    try:
        response = requests.get(
            TOUR_API_URL,
            params={
                "serviceKey": key,
                "MobileOS": "ETC",
                "MobileApp": "TodayWhereAI",
                "_type": "json",
                "eventStartDate": trip_date.replace("-", ""),
                "eventEndDate": trip_date.replace("-", ""),
                "areaCode": area_code,
                "arrange": "A",
                "numOfRows": 6,
                "pageNo": 1,
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json().get("response", {}).get("body", {})
        raw_items = body.get("items", {}).get("item", []) if body else []
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        events = [
            {
                "title": item.get("title", "이름 미상"),
                "address": item.get("addr1", "주소 미제공"),
                "start_date": item.get("eventstartdate", ""),
                "end_date": item.get("eventenddate", ""),
                "image": item.get("firstimage", ""),
                "content_id": str(item.get("contentid", "")),
            }
            for item in raw_items[:3]
        ]
        if not events:
            return {"available": True, "events": [], "message": "선택한 날짜에 확인된 축제가 없습니다."}
        return {"available": True, "events": events, "source": "한국관광공사 TourAPI"}
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return {"available": False, "message": "행사 정보를 잠시 불러오지 못했습니다."}


def ai_client() -> OpenAI:
    return OpenAI(api_key=required_env("OPENAI_API_KEY"), timeout=22.0, max_retries=1)


def parse_with_ai(model_class: type[BaseModel], system: str, user: str) -> BaseModel:
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    try:
        response = ai_client().responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=model_class,
            max_output_tokens=2500,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ServiceError(502, "AI_EMPTY", "AI가 결과를 만들지 못했습니다. 표현을 바꿔 다시 시도해 주세요.")
        return parsed
    except AuthenticationError as exc:
        raise ServiceError(503, "AI_AUTH", "OpenAI API 키 또는 프로젝트 권한을 확인해 주세요.") from exc
    except RateLimitError as exc:
        raise ServiceError(429, "AI_RATE_LIMIT", "AI 사용량이 잠시 많습니다. 잠시 후 다시 시도해 주세요.") from exc
    except APITimeoutError as exc:
        raise ServiceError(504, "AI_TIMEOUT", "AI 응답이 늦어지고 있습니다. 잠시 후 다시 시도해 주세요.") from exc
    except APIConnectionError as exc:
        raise ServiceError(502, "AI_NETWORK", "AI 서버에 연결하지 못했습니다.") from exc
    except APIStatusError as exc:
        raise ServiceError(502, "AI_ERROR", f"AI 요청에 실패했습니다(상태 {exc.status_code}).") from exc
    except ValidationError as exc:
        raise ServiceError(502, "AI_BAD_OUTPUT", "AI 결과 형식이 예상과 달라 다시 만들 수 없습니다.") from exc


def recommend_regions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    trip_date = validate_trip_date(payload.get("date"))
    preferences = {
        "date": trip_date,
        "departure": str(payload.get("departure") or "미입력")[:80],
        "companion": str(payload.get("companion") or "혼자")[:30],
        "transport": str(payload.get("transport") or "대중교통")[:30],
        "interests": validate_interests(payload.get("interests")),
        "budget": str(payload.get("budget") or "보통")[:30],
    }
    result = parse_with_ai(
        RegionIdeas,
        (
            "당신은 대한민국 국내 여행 지역 추천가입니다. 사용자의 조건에 맞는 서로 다른 후보 5곳을 제안하세요. "
            "각 full_address는 반드시 실제 대한민국의 ‘시도 + 시군구 + 법정동 또는 행정동’ 전체 이름이어야 합니다. "
            "확실하지 않은 지명은 쓰지 말고, 같은 이름의 동을 구분할 수 있게 전체 주소를 적으세요."
        ),
        json.dumps(preferences, ensure_ascii=False),
    )

    verified: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for idea in result.candidates:
        try:
            region = verify_region_query(idea.full_address)
        except ServiceError:
            continue
        unique_code = region.get("administrative_code") or region.get("legal_code")
        if unique_code in seen_codes:
            continue
        seen_codes.add(unique_code)
        region["reason"] = idea.reason
        region["suggested_type"] = idea.dong_type
        verified.append(region)
        if len(verified) == 3:
            break
    if len(verified) < 2:
        raise ServiceError(
            422,
            "TOO_FEW_VERIFIED_REGIONS",
            "AI 후보 중 실제 주소로 확인된 지역이 부족합니다. 조건을 조금 바꾸거나 지역을 직접 입력해 주세요.",
        )
    return verified


def _compact_places(pools: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for kind, places in pools.items():
        for place in places[:8]:
            compact.append(
                {
                    "kind": kind,
                    "id": place["id"],
                    "name": place["name"],
                    "address": place["address"],
                    "distance_m": place["distance_m"],
                }
            )
    return compact


def _pick_place(
    pool: list[dict[str, Any]], requested_id: str, reason: str
) -> dict[str, Any] | None:
    if not pool:
        return None
    place = next((item for item in pool if item["id"] == requested_id), pool[0]).copy()
    place["reason"] = reason if place["id"] == requested_id else "실제 검색 결과 중 가까운 장소로 안전하게 대체했습니다."
    return place


def generate_trip(payload: dict[str, Any]) -> dict[str, Any]:
    trip_date = validate_trip_date(payload.get("date"))
    region = payload.get("region")
    if not isinstance(region, dict) or not region.get("verified"):
        raise ServiceError(400, "REGION_REQUIRED", "먼저 현재 위치 또는 직접 입력으로 지역을 확인해 주세요.")
    lat, lng = validate_coordinates(region.get("latitude"), region.get("longitude"))
    radius = max(500, min(int(payload.get("radius") or 3000), 20000))
    raw_excluded = payload.get("excluded_place_ids", [])
    if not isinstance(raw_excluded, list):
        raise ServiceError(400, "INVALID_EXCLUDES", "재추천 제외 목록 형식이 올바르지 않습니다.")
    excluded_ids = {str(x) for x in raw_excluded if str(x)}
    interests = validate_interests(payload.get("interests"))
    start_time = validate_time(payload.get("start_time"), "10:00")
    end_time = validate_time(payload.get("end_time"), "19:00")
    if start_time >= end_time:
        raise ServiceError(422, "INVALID_TIME_RANGE", "마침 시간은 시작 시간보다 뒤여야 합니다.")
    pools = fetch_place_pools(region, radius, excluded_ids)

    if not any(pools.values()):
        raise ServiceError(404, "NO_PLACES", "선택 지역 반경에서 확인된 장소가 없습니다. 검색 반경을 넓혀 주세요.")

    weather = fetch_weather(lat, lng, trip_date)
    events = fetch_events(str(region.get("province", "")), trip_date)
    conditions = {
        "date": trip_date,
        "region": region.get("display_name"),
        "legal_dong": region.get("legal_dong"),
        "administrative_dong": region.get("administrative_dong"),
        "companion": str(payload.get("companion") or "혼자")[:30],
        "transport": str(payload.get("transport") or "대중교통")[:30],
        "interests": interests,
        "budget": str(payload.get("budget") or "보통")[:30],
        "start_time": start_time,
        "end_time": end_time,
        "weather": weather,
        "events": events,
        "verified_places": _compact_places(pools),
    }
    plan = parse_with_ai(
        AiTripPlan,
        (
            "당신은 검증된 데이터만 쓰는 국내 당일 여행 플래너입니다. verified_places 목록의 id와 이름만 사용하세요. "
            "목록에 없는 장소·영업시간·평점·가격·주차 가능 여부를 만들지 마세요. schedule.place_id와 picks의 id는 반드시 "
            "verified_places에 있는 id여야 합니다. restaurant/cafe/parking 후보가 비어 있으면 해당 id는 빈 문자열로 쓰세요. "
            "이동 시간을 여유 있게 두고 한국어로 간결하게 작성하세요. weather.available이 false이면 날씨를 단정하지 마세요."
        ),
        json.dumps(conditions, ensure_ascii=False),
    )

    picked_places = {
        "restaurant": _pick_place(pools["restaurant"], plan.picks.restaurant_id, plan.picks.restaurant_reason),
        "cafe": _pick_place(pools["cafe"], plan.picks.cafe_id, plan.picks.cafe_reason),
        "parking": _pick_place(pools["parking"], plan.picks.parking_id, plan.picks.parking_reason),
    }
    all_places = {place["id"]: place for places in pools.values() for place in places}
    safe_schedule: list[dict[str, Any]] = []
    for item in plan.schedule:
        place = all_places.get(item.place_id)
        if not place:
            continue
        safe_schedule.append(
            {
                "time": item.time,
                "place_id": item.place_id,
                "place_name": place["name"],
                "address": place["address"],
                "url": place["url"],
                "activity": item.activity,
                "reason": item.reason,
            }
        )
    if not safe_schedule:
        fallback = next((items[0] for items in pools.values() if items), None)
        if fallback:
            safe_schedule.append(
                {
                    "time": conditions["start_time"],
                    "place_id": fallback["id"],
                    "place_name": fallback["name"],
                    "address": fallback["address"],
                    "url": fallback["url"],
                    "activity": "선택 지역 둘러보기",
                    "reason": "실제 검색 결과로 확인된 장소입니다.",
                }
            )

    return {
        "title": plan.title,
        "summary": plan.summary,
        "schedule": safe_schedule,
        "places": picked_places,
        "candidate_pools": {key: value[:10] for key, value in pools.items() if key != "attraction"},
        "weather": weather,
        "events": events,
        "weather_tip": plan.weather_tip,
        "checklist": plan.checklist,
        "region": {
            "display_name": region.get("display_name"),
            "legal_dong": region.get("legal_dong"),
            "administrative_dong": region.get("administrative_dong"),
        },
        "date": trip_date,
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
    }


class JsonHandler(BaseHTTPRequestHandler):
    """Vercel의 파일 기반 Python 함수가 공통으로 사용하는 핸들러."""

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Allow", "POST, GET, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def read_json(self, max_bytes: int = 24_000) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ServiceError(400, "BAD_LENGTH", "요청 크기 정보가 올바르지 않습니다.") from exc
        if length <= 0:
            raise ServiceError(400, "EMPTY_BODY", "입력 내용이 비어 있습니다.")
        if length > max_bytes:
            raise ServiceError(413, "BODY_TOO_LARGE", "입력 내용이 너무 깁니다.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ServiceError(400, "BAD_JSON", "요청 형식이 올바른 JSON이 아닙니다.") from exc
        if not isinstance(data, dict):
            raise ServiceError(400, "BAD_JSON", "JSON 객체 형식으로 입력해 주세요.")
        return data

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def run(self, callback: Callable[[], dict[str, Any]], success_status: int = 200) -> None:
        try:
            result = callback()
            self.send_json(success_status, {"ok": True, **result})
        except ServiceError as exc:
            self.send_json(exc.status, {"ok": False, "error": {"code": exc.code, "message": exc.message}})
        except (TypeError, ValueError):
            self.send_json(400, {"ok": False, "error": {"code": "INVALID_INPUT", "message": "입력값을 다시 확인해 주세요."}})
        except Exception:
            # 키, 좌표, 원문 응답 등 민감하거나 긴 정보는 외부로 내보내지 않는다.
            self.send_json(500, {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "서버에서 예상하지 못한 오류가 발생했습니다."}})
