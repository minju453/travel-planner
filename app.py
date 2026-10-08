import os
import json
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai

# .env 파일에서 환경변수 로드
load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")


def search_serper(query: str) -> str:
    """
    Serper.dev API를 호출하여 구글 최신 검색 결과를 가져옵니다.
    """
    if not SERPER_API_KEY:
        return "최신 검색 결과 없음 (SERPER_API_KEY 미설정)"

    url = "https://google.serper.dev/search"
    payload = json.dumps({
        "q": query,
        "gl": "kr",
        "hl": "ko",
        "num": 5
    })
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            snippets = []
            if "organic" in data:
                for item in data["organic"][:5]:
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    snippets.append(f"- {title}: {snippet}")
            return "\n".join(snippets) if snippets else "검색 결과 없음"
        else:
            return f"검색 요청 실패 (상태 코드: {response.status_code})"
    except Exception as e:
        return f"검색 중 오류 발생: {str(e)}"


def search_serper_images(query: str, limit: int = 4) -> list:
    """
    Serper.dev 이미지 검색 API를 호출하여 여행지 대표 사진 URL들을 가져옵니다.
    """
    if not SERPER_API_KEY:
        return []

    url = "https://google.serper.dev/images"
    payload = json.dumps({
        "q": f"{query} 여행 명소 풍경",
        "gl": "kr",
        "hl": "ko",
        "num": limit
    })
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            images = []
            if "images" in data:
                for item in data["images"][:limit]:
                    image_url = item.get("imageUrl")
                    title = item.get("title", query)
                    if image_url:
                        images.append({"url": image_url, "title": title})
            return images
        return []
    except Exception:
        return []


@app.route("/")
def index():
    """메인 페이지를 렌더링합니다."""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """
    7가지 사용자 입력을 받아 Serper 검색 + 이미지 검색 후 Gemini 모델로
    6가지 항목이 포함된 여행 일정을 생성합니다.
    (429 Quota 에러 방지를 위한 멀티 모델 Fallback 지원)
    """
    # 1. API 키 확인
    if not GEMINI_API_KEY:
        return jsonify({
            "success": False,
            "error": "GEMINI_API_KEY가 .env 파일에 설정되어 있지 않습니다."
        }), 500

    # 2. 클라이언트 요청 데이터 추출
    data = request.get_json() or {}
    destination = data.get("destination", "").strip()
    duration = data.get("duration", "").strip()
    budget = data.get("budget", "").strip()
    interests = data.get("interests", "").strip()
    companions = data.get("companions", "").strip()
    transportation = data.get("transportation", "").strip()
    accommodation = data.get("accommodation", "").strip()

    # 3. 백엔드 필수 입력 검증 (7가지 항목 모두 검증)
    missing_fields = []
    if not destination: missing_fields.append("여행지")
    if not duration: missing_fields.append("여행 기간")
    if not budget: missing_fields.append("예산")
    if not interests: missing_fields.append("관심사")
    if not companions: missing_fields.append("동행자")
    if not transportation: missing_fields.append("이동수단")
    if not accommodation: missing_fields.append("숙소 선호")

    if missing_fields:
        return jsonify({
            "success": False,
            "error": f"다음 필수 입력 항목이 누락되었습니다: {', '.join(missing_fields)}"
        }), 400

    # 4. Serper.dev API로 최신 여행지 정보 및 이미지 검색
    search_query = f"{destination} 여행 추천 코스 명소 맛집 최신 정보"
    search_results = search_serper(search_query)
    images = search_serper_images(destination, limit=4)

    # 5. Gemini 프롬프트 구성
    system_instruction = (
        "당신은 전 세계 여행을 깊이 이해하고 있는 전문 수석 여행 플래너입니다.\n"
        "사용자가 제공한 여행 조건과 검색된 최신 현지 정보를 기반으로 실용적이고 완벽한 여행 일정을 한국어로 작성해야 합니다.\n\n"
        "★ 핵심 제약사항 (반드시 준수할 것):\n"
        "1. 실시간 변동 가능성이 높은 정보(정확한 숙소/식당 가격, 관광지 입장료, 운영시간, 정기 휴무일, 교통비 등)는 절대 확정된 사실처럼 단정하지 마십시오.\n"
        "2. 이러한 정보에는 반드시 명칭이나 숫자 옆에 **`[확인 필요]`** 레이블을 명시해야 합니다.\n"
        "   예시: '루브르 박물관 (입장료: 약 22유로 [확인 필요], 매주 화요일 휴무 [확인 필요])'\n"
        "   예시: '점심 식사 (예상 식비: 인당 약 15,000원 [확인 필요])'\n"
        "3. 출력 형식은 반드시 가독성이 뛰어난 Markdown(마크다운) 규격으로 작성하세요.\n"
        "4. 아래 6가지 섹션을 반드시 빠짐없이 포함하여 목차를 구성하세요:\n"
        "   - ## 1. 전체 일정 요약 (핵심 테마, 주요 동선 요약)\n"
        "   - ## 2. 날짜별 상세 일정 (Day 1, Day 2 ... 시간대별 오전/오후/저녁 추천 활동, 식당 및 명소)\n"
        "   - ## 3. 예상 비용 안내 (카테고리별 예상 지출 내역 및 [확인 필요] 표기)\n"
        "   - ## 4. 이동 계획 및 동선 팁 (추천 이동수단, 동선 최적화 조언)\n"
        "   - ## 5. 필수 준비물 체크리스트 (계절/현지 맞춤 준비물)\n"
        "   - ## 6. 여행 주의사항 및 안전 팁 (현지 에티켓, 사기 예방, 비상 연락망 등)"
    )

    user_prompt = f"""
[여행자 요청 정보]
- 여행지: {destination}
- 여행 기간: {duration}
- 예산: {budget}
- 관심사 / 여행 스타일: {interests}
- 동행자: {companions}
- 선호 이동수단: {transportation}
- 숙소 선호 스타일: {accommodation}

[Serper.dev 실시간 웹 검색 정보]
{search_results}

위 정보를 종합하여, 6가지 필수 항목을 포함하고 변동 가능 정보에 `[확인 필요]` 레이블이 충실히 적용된 최적의 여행 계획서를 완성해 주세요.
"""

    # 429 한도 초과 방지용 모델 우선순위 목록 (무료 한도가 넉넉한 모델 순차 시도)
    candidate_models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-3.5-flash"
    ]

    client = genai.Client(api_key=GEMINI_API_KEY)
    last_error = ""

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config={
                    "system_instruction": system_instruction,
                    "temperature": 0.7,
                }
            )

            plan_content = response.text or "일정을 생성하지 못했습니다."

            return jsonify({
                "success": True,
                "plan": plan_content,
                "images": images,
                "used_model": model_name
            })
        except Exception as e:
            error_str = str(e)
            last_error = error_str
            # 만약 429(할당량 초과) 또는 특정 모델을 찾을 수 없는 경우 다음 모델로 자동 시도
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "404" in error_str:
                continue
            else:
                # 429가 아닌 다른 치명적인 오류는 즉시 반환
                break

    return jsonify({
        "success": False,
        "error": f"일정 생성 중 할당량 초과 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. (세부 내용: {last_error})"
    }), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
