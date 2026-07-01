"""
collector.py
────────────
나라장터 OpenAPI에서 MICE 관련 입찰공고를 수집·정제하고 Supabase(PostgreSQL)에 적재하는 엔진.

주요 흐름:
  1. API 호출 → 페이지네이션 처리로 전체 데이터 수집 (데모 데이터 폴백 지원)
  2. 2단계 필터링 적용 (Positive 검색 후 Negative 키워드 차단)
  3. 마감 상태 판별 (bidClsDt 누락 시 opengDt 기준 폴백)
  4. 금액 구간화 컬럼 추가
  5. Supabase(PostgreSQL)에 Upsert (중복 방지)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests
from supabase import create_client, Client

import config

# 로깅 기본 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# 한국 표준시 (UTC+9)
KST = timezone(timedelta(hours=9))

# 기본 DataFrame 컬럼 정의 (KeyError 방지용)
COLUMNS = [
    "bidNtceNo", "bidNtceOrd", "bidNtceNm", "ntceInsttNm", "bidNtceDt",
    "bidClsDt", "asignBdgtAmt", "bidMethdNm", "opengDt", "status",
    "budgetRange", "detailUrl"
]


# ─────────────────────────────────────────────────────────────────────────────
# 내부 유틸 함수
# ─────────────────────────────────────────────────────────────────────────────

def _now_kst() -> datetime:
    """현재 KST 시각 반환."""
    return datetime.now(tz=KST)


def _parse_dt(raw: str | None) -> datetime | None:
    """
    나라장터 API의 다양한 날짜 포맷을 파싱하여 KST datetime 반환.
    지원 포맷: 'YYYYMMDDHHMMSS', 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DD HH:MM', 'YYYYMMDD'
    파싱 실패 시 None 반환.
    """
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=KST)
        except ValueError:
            continue
    logger.debug("날짜 파싱 실패: %s", raw)
    return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    """text 안에 keywords 중 하나라도 포함되면 True."""
    return any(kw in text for kw in keywords)


def _build_budget_label(amount: float | None) -> str:
    """금액(원)을 구간 레이블로 변환."""
    if amount is None or amount < 0:
        return "미확인"
    for label, lo, hi in config.BUDGET_RANGES:
        if label == "전체":
            continue
        if lo is not None and hi is not None:
            if lo <= amount < hi:
                return label
        elif lo is not None and hi is None:
            if amount >= lo:
                return label
        elif lo is None and hi is not None:
            if amount < hi:
                return label
    return "미확인"


# ─────────────────────────────────────────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_page(
    service_key: str,
    page_no: int,
    start_date: str,
    end_date: str,
    keyword: str,
) -> dict[str, Any]:
    """
    나라장터 OpenAPI 단일 페이지 호출.
    """
    params = {
        "serviceKey":  service_key,
        "pageNo":      str(page_no),
        "numOfRows":   str(config.PAGE_SIZE),
        "type":        "json",
        "inqryDiv":    "1",       # 1 = 입찰공고
        "inqryBgnDt":  start_date,
        "inqryEndDt":  end_date,
        "bidNtceNm":   keyword,
        "ntceKindCd":  "00",      # 00 = 실공고
    }
    try:
        resp = requests.get(
            config.BASE_URL,
            params=params,
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error("API 요청 타임아웃 (page=%d, keyword=%s)", page_no, keyword)
        return {}
    except requests.exceptions.RequestException as exc:
        logger.error("API 요청 오류: %s", exc)
        return {}
    except ValueError:
        logger.error("JSON 파싱 실패 (page=%d)", page_no)
        return {}


def _extract_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """API 응답 body에서 items 리스트 추출."""
    try:
        return body["response"]["body"]["items"] or []
    except (KeyError, TypeError):
        return []


def _get_total_count(body: dict[str, Any]) -> int:
    """API 응답에서 전체 결과 수 추출."""
    try:
        return int(body["response"]["body"]["totalCount"])
    except (KeyError, TypeError, ValueError):
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# 데이터 정제
# ─────────────────────────────────────────────────────────────────────────────

def _determine_status(row: dict[str, Any]) -> str:
    """
    마감 상태 판별 로직.

    - bidClsDt(입찰마감일시) 존재 → 해당 시각 기준 마감 여부 판별
    - bidClsDt 누락 → opengDt(개찰일시) 기준 폴백 판별
    - 기준 시각을 알 수 없는 경우 → '정보없음'
    """
    now = _now_kst()

    close_dt = _parse_dt(row.get("bidClsDt"))
    if close_dt is not None:
        return "마감" if now > close_dt else "진행중"

    open_dt = _parse_dt(row.get("opengDt"))
    if open_dt is not None:
        return "마감(개찰기준)" if now > open_dt else "진행중"

    return "정보없음"


def _clean_amount(raw: Any) -> float | None:
    """예산 금액 문자열/숫자를 float으로 변환. 실패 시 None."""
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _build_detail_url(row: dict[str, Any]) -> str:
    """공고 상세 페이지 URL 생성."""
    return config.BID_DETAIL_URL_TEMPLATE.format(
        bidNtceNo=row.get("bidNtceNo", ""),
        bidNtceOrd=row.get("bidNtceOrd", "00"),
    )


def _clean_item(raw: dict[str, Any]) -> dict[str, Any]:
    """
    API 원문 item 하나를 정제된 레코드로 변환.
    """
    amount = _clean_amount(raw.get("asignBdgtAmt"))
    status = _determine_status(raw)

    ntce_dt = _parse_dt(raw.get("bidNtceDt"))
    cls_dt  = _parse_dt(raw.get("bidClsDt"))

    return {
        "bidNtceNo":    raw.get("bidNtceNo", ""),
        "bidNtceOrd":   raw.get("bidNtceOrd", "00"),
        "bidNtceNm":    raw.get("bidNtceNm", "").strip(),
        "ntceInsttNm":  raw.get("ntceInsttNm", "").strip(),
        "bidNtceDt":    ntce_dt.strftime("%Y-%m-%d") if ntce_dt else "",
        "bidClsDt":     cls_dt.strftime("%Y-%m-%d %H:%M") if cls_dt else "",
        "asignBdgtAmt": amount,
        "bidMethdNm":   raw.get("bidMethdNm", ""),
        "opengDt":      raw.get("opengDt", ""),
        "status":       status,
        "budgetRange":  _build_budget_label(amount),
        "detailUrl":    _build_detail_url(raw),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 퍼블릭 API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_mice_bids(
    api_key: str | None = None,
    period_days: int = config.DEFAULT_PERIOD_DAYS,
) -> pd.DataFrame:
    """
    나라장터 OpenAPI에서 MICE 관련 입찰공고를 수집하여 DataFrame으로 반환.
    """
    service_key = api_key or config.API_KEY
    if not service_key or service_key == "your_api_key_here":
        logger.warning("API 키가 설정되지 않았거나 기본값입니다. 데모 데이터를 반환합니다.")
        return _load_demo_data()

    now      = _now_kst()
    end_dt   = now.strftime("%Y%m%d%H%M%S")
    start_dt = (now - timedelta(days=period_days)).strftime("%Y%m%d%H%M%S")

    all_items: list[dict[str, Any]] = []

    for keyword in config.POSITIVE_KEYWORDS:
        logger.info("키워드 '%s' 수집 시작 (기간: %s ~ %s)", keyword, start_dt[:8], end_dt[:8])
        page = 1
        while page <= config.MAX_PAGES:
            body = _fetch_page(service_key, page, start_dt, end_dt, keyword)
            items = _extract_items(body)
            if not items:
                break

            all_items.extend(items)
            total = _get_total_count(body)
            fetched = (page - 1) * config.PAGE_SIZE + len(items)
            logger.info("  page %d: %d건 수신 (누적 %d / 전체 %d)", page, len(items), fetched, total)

            if fetched >= total:
                break
            page += 1

    if not all_items:
        logger.warning("수집된 공고가 없습니다.")
        return pd.DataFrame(columns=COLUMNS)

    # 1단계: 공고번호 + 공고차수 기준 중복 제거
    seen: set[str] = set()
    unique_items: list[dict[str, Any]] = []
    for item in all_items:
        key = item.get("bidNtceNo", "") + item.get("bidNtceOrd", "")
        if key and key not in seen:
            seen.add(key)
            unique_items.append(item)

    # 2단계: 공고명 Positive 재검증 + Negative 필터링 (공사, 구축, 리모델링 등 제외)
    filtered: list[dict[str, Any]] = []
    for item in unique_items:
        nm = item.get("bidNtceNm", "")
        # Positive 키워드가 공고명에 매칭되는지 확인
        if not _contains_any(nm, config.POSITIVE_KEYWORDS):
            continue
        # Negative 키워드가 들어있는 경우 차단
        if _contains_any(nm, config.NEGATIVE_KEYWORDS):
            logger.info("Negative 필터 제외: %s", nm)
            continue
        filtered.append(item)

    logger.info("필터링 완료: %d건 → %d건", len(unique_items), len(filtered))

    records = [_clean_item(item) for item in filtered]
    df = pd.DataFrame(records, columns=COLUMNS)

    if df.empty:
        return df

    # 게시일자 최신순 정렬
    df.sort_values("bidNtceDt", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 데모 데이터 (API 키 미설정 시 동작 확인용)
# ─────────────────────────────────────────────────────────────────────────────

def _load_demo_data() -> pd.DataFrame:
    """
    API 키 없이도 동작 확인이 가능하도록 데모 데이터 반환.
    """
    from datetime import date

    today = date.today()

    sample = [
        {
            "bidNtceNo":    "20240001",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "2024년 국제 스마트시티 컨퍼런스 운영 용역",
            "ntceInsttNm":  "국토교통부",
            "bidNtceDt":    str(today - timedelta(days=5)),
            "bidClsDt":     str(today + timedelta(days=10)) + " 18:00",
            "asignBdgtAmt": 180_000_000,
            "bidMethdNm":   "일반경쟁",
            "opengDt":      "",
            "status":       "진행중",
            "budgetRange":  "1.5억 ~ 2억 원 미만",
            "detailUrl":    "https://www.g2b.go.kr",
        },
        {
            "bidNtceNo":    "20240002",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "제15회 글로벌 포럼 기획 및 운영 대행",
            "ntceInsttNm":  "한국관광공사",
            "bidNtceDt":    str(today - timedelta(days=12)),
            "bidClsDt":     str(today + timedelta(days=3)) + " 17:00",
            "asignBdgtAmt": 320_000_000,
            "bidMethdNm":   "제한경쟁",
            "opengDt":      "",
            "status":       "진행중",
            "budgetRange":  "3억 ~ 3.5억 원 미만",
            "detailUrl":    "https://www.g2b.go.kr",
        },
        {
            "bidNtceNo":    "20240003",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "2024 국제회의 통·번역 및 운영 지원 용역",
            "ntceInsttNm":  "외교부",
            "bidNtceDt":    str(today - timedelta(days=20)),
            "bidClsDt":     str(today - timedelta(days=2)) + " 18:00",
            "asignBdgtAmt": 75_000_000,
            "bidMethdNm":   "일반경쟁",
            "opengDt":      "",
            "status":       "마감",
            "budgetRange":  "5천만 ~ 1억 원 미만",
            "detailUrl":    "https://www.g2b.go.kr",
        },
        {
            "bidNtceNo":    "20240004",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "2024 바이오 심포지엄 운영 대행 용역",
            "ntceInsttNm":  "보건복지부",
            "bidNtceDt":    str(today - timedelta(days=3)),
            "bidClsDt":     str(today + timedelta(days=15)) + " 18:00",
            "asignBdgtAmt": 55_000_000,
            "bidMethdNm":   "일반경쟁",
            "opengDt":      "",
            "status":       "진행중",
            "budgetRange":  "5천만 ~ 1억 원 미만",
            "detailUrl":    "https://www.g2b.go.kr",
        },
        {
            "bidNtceNo":    "20240005",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "AI·디지털 혁신 세미나 운영 위탁 용역",
            "ntceInsttNm":  "과학기술정보통신부",
            "bidNtceDt":    str(today - timedelta(days=7)),
            "bidClsDt":     str(today + timedelta(days=8)) + " 17:00",
            "asignBdgtAmt": 120_000_000,
            "bidMethdNm":   "일반경쟁",
            "opengDt":      "",
            "status":       "진행중",
            "budgetRange":  "1억 ~ 1.5억 원 미만",
            "detailUrl":    "https://www.g2b.go.kr",
        },
        {
            "bidNtceNo":    "20240006",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "한-ASEAN 콘퍼런스 통역·운영 서비스 용역",
            "ntceInsttNm":  "외교부 ASEAN협력과",
            "bidNtceDt":    str(today - timedelta(days=30)),
            "bidClsDt":     str(today - timedelta(days=10)) + " 18:00",
            "asignBdgtAmt": 245_000_000,
            "bidMethdNm":   "제한경쟁",
            "opengDt":      "",
            "status":       "마감",
            "budgetRange":  "2억 ~ 2.5억 원 미만",
            "detailUrl":    "https://www.g2b.go.kr",
        },
        {
            "bidNtceNo":    "20240007",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "2024 탄소중립 국제 컨퍼런스 운영 대행",
            "ntceInsttNm":  "환경부",
            "bidNtceDt":    str(today - timedelta(days=1)),
            "bidClsDt":     str(today + timedelta(days=20)) + " 18:00",
            "asignBdgtAmt": 510_000_000,
            "bidMethdNm":   "일반경쟁",
            "opengDt":      "",
            "status":       "진행중",
            "budgetRange":  "5억 원 이상",
            "detailUrl":    "https://www.g2b.go.kr",
        },
        {
            "bidNtceNo":    "20240008",
            "bidNtceOrd":   "00",
            "bidNtceNm":    "2024 글로벌 헬스케어 포럼 개최 운영 용역",
            "ntceInsttNm":  "한국보건산업진흥원",
            "bidNtceDt":    str(today - timedelta(days=4)),
            "bidClsDt":     str(today + timedelta(days=12)) + " 17:00",
            "asignBdgtAmt": 380_000_000,
            "bidMethdNm":   "일반경쟁",
            "opengDt":      "",
            "status":       "진행중",
            "budgetRange":  "3.5억 ~ 4억 원 미만",
            "detailUrl":    "https://www.g2b.go.kr",
        },
    ]
    df = pd.DataFrame(sample)
    df.sort_values("bidNtceDt", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 메인 실행 블록
# ─────────────────────────────────────────────────────────────────────────────

def run_collector():
    """수집 및 Supabase 적재 메인 함수."""
    logger.info("========================================")
    logger.info("MICE Bidding Collector 실행 시작")
    logger.info("========================================")

    # 1. API 데이터 수집
    df = fetch_mice_bids()
    if df.empty:
        logger.warning("수집 또는 정제된 공고 데이터가 없습니다.")
        return

    logger.info(f"총 {len(df)}건의 정제된 공고 수집 완료.")

    # 2. Supabase 설정 확인
    if not config.SUPABASE_URL or not config.SUPABASE_KEY or \
            config.SUPABASE_URL == "your_supabase_url_here" or \
            config.SUPABASE_KEY == "your_supabase_anon_key_here":
        logger.error("Supabase 연결 정보가 누락되었거나 placeholder 상태입니다.")
        logger.error(".env 파일에 올바른 SUPABASE_URL 및 SUPABASE_KEY를 작성해 주세요.")
        return

    # 3. Supabase 적재 데이터 매핑
    records = df.to_dict(orient="records")
    db_items = []
    for item in records:
        db_items.append({
            "id": f"{item['bidNtceNo']}-{item['bidNtceOrd']}",
            "bid_ntce_no": str(item["bidNtceNo"]),
            "bid_ntce_ord": str(item["bidNtceOrd"]),
            "bid_ntce_nm": str(item["bidNtceNm"]),
            "ntce_instt_nm": str(item["ntceInsttNm"]) if item.get("ntceInsttNm") else None,
            "bid_ntce_dt": str(item["bidNtceDt"]) if item.get("bidNtceDt") else None,
            "bid_cls_dt": str(item["bidClsDt"]) if item.get("bidClsDt") else None,
            "asign_bdgt_amt": item["asignBdgtAmt"],
            "bid_methd_nm": str(item["bidMethdNm"]) if item.get("bidMethdNm") else None,
            "openg_dt": str(item["opengDt"]) if item.get("opengDt") else None,
            "status": str(item["status"]),
            "budget_range": str(item["budgetRange"]),
            "detail_url": str(item["detailUrl"]),
        })

    # 4. Supabase Upsert 수행
    try:
        supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        logger.info(f"Supabase 연결 성공. 적재 진행 중... (총 {len(db_items)}건)")

        # 100건씩 배치 처리
        batch_size = 100
        for i in range(0, len(db_items), batch_size):
            batch = db_items[i:i + batch_size]
            supabase.table("tenders").upsert(batch).execute()
            logger.info(f"  배치 적재 완료: {i + len(batch)} / {len(db_items)}")

        logger.info("========================================")
        logger.info("MICE Bidding Collector 적재 성공!")
        logger.info("========================================")
    except Exception as e:
        logger.error(f"Supabase Upsert 작업 중 치명적 오류 발생: {e}")


if __name__ == "__main__":
    run_collector()
