"""
config.py
─────────
프로젝트 전역 설정값 및 검색 필터 기준값 정의 모듈.
API 엔드포인트, 키워드 목록, 금액 구간 등 모든 상수를 중앙 관리한다.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API 및 데이터베이스 설정 ──────────────────────────────────────────────────
API_KEY: str = os.getenv("NARA_API_KEY", "")
BASE_URL: str = (
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
    "/getBidPblancListInfoServcPPSSrch"
)
PAGE_SIZE: int = 100          # 1회 호출 당 최대 수신 건수
MAX_PAGES: int = 30           # 무한 루프 방지를 위한 최대 페이지 수
REQUEST_TIMEOUT: int = 20     # 초 단위

# Supabase 설정
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# ── 검색 기간 기본값 ─────────────────────────────────────────────────────────
DEFAULT_PERIOD_DAYS: int = 90  # 기본 90일(3개월)

# ── 키워드 필터 ───────────────────────────────────────────────────────────────
POSITIVE_KEYWORDS: list[str] = [
    "포럼", "국제회의", "심포지엄", "컨퍼런스", "콘퍼런스", "세미나",
]

NEGATIVE_KEYWORDS: list[str] = [
    "공사", "구축", "리모델링", "인테리어", "환경개선",
    "물품", "구매", "제조", "시스템", "유지보수",
]

# ── 금액 구간 정의 ────────────────────────────────────────────────────────────
# (label, 하한 원, 상한 원)  *상한 None → '이상' 의미
BUDGET_RANGES: list[tuple[str, int | None, int | None]] = [
    ("전체",                   None,         None        ),
    ("5천만 원 미만",           0,            50_000_000  ),
    ("5천만 ~ 1억 원 미만",     50_000_000,   100_000_000 ),
    ("1억 ~ 1.5억 원 미만",     100_000_000,  150_000_000 ),
    ("1.5억 ~ 2억 원 미만",     150_000_000,  200_000_000 ),
    ("2억 ~ 2.5억 원 미만",     200_000_000,  250_000_000 ),
    ("2.5억 ~ 3억 원 미만",     250_000_000,  300_000_000 ),
    ("3억 ~ 3.5억 원 미만",     300_000_000,  350_000_000 ),
    ("3.5억 ~ 4억 원 미만",     350_000_000,  400_000_000 ),
    ("4억 ~ 4.5억 원 미만",     400_000_000,  450_000_000 ),
    ("4.5억 ~ 5억 원 미만",     450_000_000,  500_000_000 ),
    ("5억 원 이상",             500_000_000,  None        ),
]

BUDGET_RANGE_LABELS: list[str] = [r[0] for r in BUDGET_RANGES]

# ── 컬럼 표시 이름 매핑 ───────────────────────────────────────────────────────
COLUMN_DISPLAY_NAMES: dict[str, str] = {
    "bidNtceNo":       "공고번호",
    "bidNtceNm":       "공고명",
    "ntceInsttNm":     "공고기관",
    "bidNtceDt":       "게시일자",
    "bidClsDt":        "마감일자",
    "asignBdgtAmt":    "배정예산(원)",
    "bidMethdNm":      "입찰방법",
    "status":          "진행상태",
}

# ── 나라장터 공고 상세 URL 패턴 ───────────────────────────────────────────────
BID_DETAIL_URL_TEMPLATE: str = (
    "https://www.g2b.go.kr:8101/ep/invitation/publish/bidInfoDtl.do"
    "?bidno={bidNtceNo}&bidseq={bidNtceOrd}"
)
