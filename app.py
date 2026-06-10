from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import requests
from flask import Flask, jsonify, redirect, request, send_from_directory


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULT_DIR = DATA_DIR / "results"
STATE_DIR = DATA_DIR / "states"

GRAPH_VERSION = os.getenv("IG_GRAPH_VERSION", "v24.0")
GRAPH_BASE = os.getenv("IG_GRAPH_BASE", f"https://graph.instagram.com/{GRAPH_VERSION}")
GRAPH_BASE_NO_VERSION = "https://graph.instagram.com"
AUTH_BASE = os.getenv("IG_AUTH_BASE", "https://www.instagram.com/oauth/authorize")
TOKEN_URL = os.getenv("IG_TOKEN_URL", "https://api.instagram.com/oauth/access_token")
DEFAULT_SCOPES = "instagram_business_basic,instagram_business_manage_comments,instagram_business_manage_insights"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def ensure_dirs() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv()
ensure_dirs()

app = Flask(__name__, static_folder=str(ROOT), static_url_path="")


class InstagramApiError(RuntimeError):
    pass


def app_configured() -> bool:
    return bool(env("IG_APP_ID") and env("IG_APP_SECRET") and env("IG_REDIRECT_URI"))


def public_config() -> dict[str, Any]:
    return {
        "configured": app_configured(),
        "redirectUri": env("IG_REDIRECT_URI"),
        "scopes": env("IG_SCOPES", DEFAULT_SCOPES),
        "graphVersion": GRAPH_VERSION,
        "requiresProfessionalAccount": True,
    }


def save_state(payload: dict[str, Any]) -> str:
    state = secrets.token_urlsafe(32)
    state_payload = {
        "createdAt": int(time.time()),
        "payload": payload,
    }
    (STATE_DIR / f"{state}.json").write_text(json.dumps(state_payload, ensure_ascii=False), encoding="utf-8")
    return state


def pop_state(state: str) -> dict[str, Any]:
    if not re.fullmatch(r"[-_a-zA-Z0-9]{20,120}", state or ""):
        raise InstagramApiError("잘못된 인증 상태값입니다.")
    path = STATE_DIR / f"{state}.json"
    if not path.exists():
        raise InstagramApiError("인증 세션이 만료되었거나 존재하지 않습니다.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.unlink(missing_ok=True)
    if int(time.time()) - int(payload.get("createdAt", 0)) > 900:
        raise InstagramApiError("인증 세션이 만료되었습니다. 다시 시작해 주세요.")
    return payload.get("payload", {})


def appsecret_proof(access_token: str) -> str:
    return hmac.new(env("IG_APP_SECRET").encode(), access_token.encode(), hashlib.sha256).hexdigest()


def graph_get(path: str, access_token: str, params: dict[str, Any] | None = None, *, fallback_no_version: bool = True) -> dict[str, Any]:
    query = dict(params or {})
    query["access_token"] = access_token
    if env("IG_APP_SECRET"):
        query["appsecret_proof"] = appsecret_proof(access_token)

    path = path if path.startswith("/") else f"/{path}"
    urls = [f"{GRAPH_BASE}{path}"]
    if fallback_no_version:
        urls.append(f"{GRAPH_BASE_NO_VERSION}{path}")

    last_error = None
    for url in urls:
        response = requests.get(url, params=query, timeout=25)
        if response.ok:
            return response.json()
        last_error = response.text
    raise InstagramApiError(last_error or f"Instagram API 호출 실패: {path}")


def exchange_code_for_token(code: str) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": env("IG_APP_ID"),
            "client_secret": env("IG_APP_SECRET"),
            "grant_type": "authorization_code",
            "redirect_uri": env("IG_REDIRECT_URI"),
            "code": code,
        },
        timeout=25,
    )
    if not response.ok:
        raise InstagramApiError(response.text)
    short_token = response.json()

    access_token = short_token.get("access_token")
    if not access_token:
        raise InstagramApiError("Instagram access token을 받지 못했습니다.")

    long_response = requests.get(
        f"{GRAPH_BASE_NO_VERSION}/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": env("IG_APP_SECRET"),
            "access_token": access_token,
        },
        timeout=25,
    )
    if long_response.ok and long_response.json().get("access_token"):
        long_token = long_response.json()
        return {
            "access_token": long_token["access_token"],
            "expires_in": long_token.get("expires_in"),
            "token_type": long_token.get("token_type", "bearer"),
            "user_id": short_token.get("user_id"),
        }

    return short_token


def fetch_all_pages(path: str, access_token: str, params: dict[str, Any], limit_pages: int = 4) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    data = graph_get(path, access_token, params, fallback_no_version=True)
    pages = 0
    while pages < limit_pages:
        records.extend(data.get("data", []))
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        response = requests.get(next_url, timeout=25)
        if not response.ok:
            break
        data = response.json()
        pages += 1
    return records


def safe_graph_get(path: str, access_token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return graph_get(path, access_token, params)
    except Exception as exc:
        return {"error": str(exc)}


def fetch_instagram_dataset(access_token: str) -> dict[str, Any]:
    profile_fields = ",".join(
        [
            "id",
            "user_id",
            "username",
            "name",
            "account_type",
            "profile_picture_url",
            "followers_count",
            "follows_count",
            "media_count",
        ]
    )
    profile = graph_get("me", access_token, {"fields": profile_fields})

    media_fields = ",".join(
        [
            "id",
            "caption",
            "media_type",
            "media_product_type",
            "permalink",
            "timestamp",
            "comments_count",
            "like_count",
            "thumbnail_url",
            "media_url",
        ]
    )
    media = fetch_all_pages("me/media", access_token, {"fields": media_fields, "limit": env("IG_MEDIA_LIMIT", "24")}, limit_pages=2)

    enriched_media: list[dict[str, Any]] = []
    comment_limit = int(env("IG_COMMENT_LIMIT", "25"))
    for item in media[: int(env("IG_ENRICH_MEDIA_LIMIT", "12"))]:
        media_id = item.get("id")
        comments: list[dict[str, Any]] = []
        insights: dict[str, Any] = {}
        if media_id:
            comments_data = safe_graph_get(
                f"{media_id}/comments",
                access_token,
                {"fields": "id,text,timestamp,username,like_count", "limit": comment_limit},
            )
            comments = comments_data.get("data", []) if isinstance(comments_data.get("data"), list) else []

            insights = safe_graph_get(
                f"{media_id}/insights",
                access_token,
                {"metric": "reach,views,likes,comments,saved,shares,total_interactions"},
            )
        enriched_media.append({**item, "comments": comments, "insights": insights})

    profile_insights = safe_graph_get(
        f"{profile.get('id')}/insights",
        access_token,
        {"metric": "reach,profile_views,accounts_engaged,follower_count,profile_links_taps", "period": "day"},
    )

    return {
        "profile": profile,
        "media": enriched_media,
        "profileInsights": profile_insights,
        "fetchedAt": int(time.time()),
    }


EMOTION_WORDS = [
    "좋아",
    "사랑",
    "행복",
    "외로",
    "힘들",
    "슬프",
    "고마",
    "미안",
    "불안",
    "무서",
    "기쁘",
    "설레",
    "그립",
]
SELF_WORDS = ["나", "내", "저", "제가", "나는", "내가", "나를", "스스로"]
RELATION_WORDS = ["우리", "너", "사람", "친구", "사랑", "관계", "마음", "함께", "혼자"]


def text_score(text: str, words: list[str]) -> int:
    return sum(text.count(word) for word in words)


def clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


def analyze_dataset(dataset: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    profile = dataset.get("profile", {})
    media = dataset.get("media", [])
    captions = [item.get("caption") or "" for item in media]
    comments = [comment for item in media for comment in item.get("comments", [])]
    comment_text = "\n".join(comment.get("text") or "" for comment in comments)
    caption_text = "\n".join(captions)
    full_text = f"{caption_text}\n{comment_text}".strip()

    media_count = len(media)
    comment_count = len(comments)
    unique_commenters = len({comment.get("username") for comment in comments if comment.get("username")})
    avg_caption_len = sum(len(caption) for caption in captions) / max(1, len(captions))
    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", full_text))
    question_count = full_text.count("?") + full_text.count("？")
    emotion_count = text_score(full_text, EMOTION_WORDS)
    self_count = text_score(caption_text, SELF_WORDS)
    relation_count = text_score(full_text, RELATION_WORDS)
    total_likes = sum(int(item.get("like_count") or 0) for item in media)
    total_comments_declared = sum(int(item.get("comments_count") or 0) for item in media)

    media_types = Counter(item.get("media_type", "UNKNOWN") for item in media)
    recent_density = media_count / max(1, int(profile.get("media_count") or media_count or 1))
    engagement_signal = (total_likes + total_comments_declared * 3 + comment_count * 4) / max(1, media_count)

    scores = {
        "selfDisplay": clamp(42 + self_count * 4 + avg_caption_len / 6),
        "relationSensitivity": clamp(36 + relation_count * 3 + unique_commenters * 2 + question_count * 4),
        "emotionalDepth": clamp(34 + emotion_count * 5 + avg_caption_len / 7),
        "approvalNeed": clamp(28 + engagement_signal / 4 + emoji_count * 1.8),
        "distanceControl": clamp(50 + (media_types.get("IMAGE", 0) * 3) - (comment_count / max(1, media_count))),
        "shadowIndex": clamp(30 + emotion_count * 3 + question_count * 8 + (avg_caption_len / 12)),
    }

    archetypes = [
        {
            "name": "가면 뒤에 숨은 광대",
            "condition": scores["relationSensitivity"] + scores["distanceControl"],
            "subtitle": "웃으며 거리를 조절하는 사람",
            "summary": "사람들에게 편하게 보이지만, 속마음을 전부 드러내기보다 분위기를 먼저 맞추는 패턴이 보입니다.",
        },
        {
            "name": "왕좌 위의 고독한 왕",
            "condition": scores["selfDisplay"] + scores["approvalNeed"],
            "subtitle": "인정받고 싶지만 쉽게 기대지 않는 사람",
            "summary": "자신의 이미지와 기준을 강하게 세우는 동시에, 반응이 줄어드는 순간에는 민감하게 흔들릴 수 있습니다.",
        },
        {
            "name": "자기 무덤을 파는 유령",
            "condition": scores["shadowIndex"] + scores["emotionalDepth"],
            "subtitle": "말하지 않은 감정이 오래 남는 사람",
            "summary": "직접 말하지 않은 감정이 캡션과 반응 패턴 사이에 남아 있습니다. 피하려던 감정일수록 반복해서 등장합니다.",
        },
        {
            "name": "등대의 감시자",
            "condition": scores["relationSensitivity"] + scores["emotionalDepth"] - scores["selfDisplay"] / 2,
            "subtitle": "주변을 오래 보고 해석하는 사람",
            "summary": "중심에 서기보다 관계의 흐름을 먼저 읽습니다. 타인의 반응을 세밀하게 관찰하는 힘이 강합니다.",
        },
    ]
    selected = max(archetypes, key=lambda item: item["condition"])

    top_commenters = Counter(comment.get("username") for comment in comments if comment.get("username")).most_common(5)
    top_words = Counter(re.findall(r"[가-힣a-zA-Z]{2,}", full_text.lower())).most_common(12)

    chapters = [
        {
            "title": "겉으로 보이는 얼굴",
            "body": f"최근 {media_count}개의 게시물은 {media_types.most_common(1)[0][0] if media_types else '콘텐츠'} 중심으로 구성되어 있습니다. 평균 캡션 길이는 {avg_caption_len:.0f}자로, 자신을 설명하는 밀도가 {'높은' if avg_caption_len > 80 else '절제된'} 편입니다.",
        },
        {
            "title": "관계 속 반복 패턴",
            "body": f"분석 가능한 댓글 작성자는 {unique_commenters}명입니다. 질문형 문장과 관계 단어의 비율을 보면, 관계를 단순 반응보다 의미 있는 신호로 해석하려는 경향이 보입니다.",
        },
        {
            "title": "숨겨진 결핍 버튼",
            "body": "반응이 몰리는 콘텐츠와 감정어가 포함된 문장 사이의 간격을 보면, 인정 자체보다 '내가 제대로 읽히는가'에 더 예민하게 반응하는 구조가 나타납니다.",
        },
        {
            "title": "스페셜 질문 해석",
            "body": f"선택한 질문은 '{payload.get('question') or '나를 무장해제 시키는 칭찬 세가지는?'}'입니다. 이 질문은 당신이 가장 직접적으로 확인받고 싶은 관계의 장면을 드러내는 단서로 처리했습니다.",
        },
    ]

    return {
        "id": str(uuid.uuid4()),
        "generatedAt": int(time.time()),
        "payload": {key: value for key, value in payload.items() if key != "state"},
        "profile": {
            "id": profile.get("id"),
            "username": profile.get("username"),
            "name": profile.get("name"),
            "accountType": profile.get("account_type"),
            "profilePictureUrl": profile.get("profile_picture_url"),
            "followersCount": profile.get("followers_count"),
            "followsCount": profile.get("follows_count"),
            "mediaCount": profile.get("media_count"),
        },
        "evidence": {
            "mediaAnalyzed": media_count,
            "commentsAnalyzed": comment_count,
            "uniqueCommenters": unique_commenters,
            "totalLikes": total_likes,
            "declaredComments": total_comments_declared,
            "mediaTypes": dict(media_types),
            "topCommenters": top_commenters,
            "topWords": top_words,
            "recentDensity": recent_density,
        },
        "scores": scores,
        "archetype": selected,
        "chapters": chapters,
        "disclaimer": "이 결과는 사용자가 동의해 제공한 Instagram Professional 계정 데이터 기반의 자기이해/엔터테인먼트 리포트이며, 의학적 또는 심리상담 진단이 아닙니다.",
    }


def save_result(result: dict[str, Any]) -> str:
    result_id = result["id"]
    (RESULT_DIR / f"{result_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_id


@app.get("/")
def index() -> Any:
    return send_from_directory(ROOT, "index.html")


@app.get("/api/config")
def config() -> Any:
    return jsonify(public_config())


@app.post("/api/analysis/start")
def analysis_start() -> Any:
    payload = request.get_json(silent=True) or {}
    handle = str(payload.get("handle") or "").strip().lstrip("@")
    if len(handle) < 2:
        return jsonify({"error": "Instagram ID를 입력해 주세요."}), 400
    if not app_configured():
        return jsonify(
            {
                "mode": "setup_required",
                "error": "instagram_app_not_configured",
                "message": "실제 분석을 시작하려면 IG_APP_ID, IG_APP_SECRET, IG_REDIRECT_URI 환경변수가 필요합니다.",
                "config": public_config(),
            }
        )

    state = save_state({**payload, "handle": handle})
    query = {
        "client_id": env("IG_APP_ID"),
        "redirect_uri": env("IG_REDIRECT_URI"),
        "scope": env("IG_SCOPES", DEFAULT_SCOPES),
        "response_type": "code",
        "state": state,
        "enable_fb_login": "0",
        "force_authentication": "1",
    }
    return jsonify({"mode": "oauth", "authUrl": f"{AUTH_BASE}?{urlencode(query)}"})


@app.get("/auth/instagram/callback")
def instagram_callback() -> Any:
    error = request.args.get("error") or request.args.get("error_reason")
    if error:
        message = request.args.get("error_description") or error
        return redirect(f"/result.html?error={quote(message)}")

    code = request.args.get("code")
    state_value = request.args.get("state")
    if not code or not state_value:
        return redirect("/result.html?error=missing_code")

    try:
        payload = pop_state(state_value)
        token = exchange_code_for_token(code)
        dataset = fetch_instagram_dataset(token["access_token"])
        result = analyze_dataset(dataset, payload)
        result_id = save_result(result)
        return redirect(f"/result.html?id={result_id}")
    except Exception as exc:
        return redirect(f"/result.html?error={quote(str(exc)[:600])}")


@app.get("/api/result/<result_id>")
def result_api(result_id: str) -> Any:
    if not re.fullmatch(r"[a-f0-9-]{36}", result_id):
        return jsonify({"error": "invalid_result_id"}), 400
    path = RESULT_DIR / f"{result_id}.json"
    if not path.exists():
        return jsonify({"error": "result_not_found"}), 404
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.get("/health")
def health() -> Any:
    return jsonify({"ok": True, "configured": app_configured()})


if __name__ == "__main__":
    app.run(host=env("HOST", "127.0.0.1"), port=int(env("PORT", "5000")), debug=env("FLASK_DEBUG") == "1")
