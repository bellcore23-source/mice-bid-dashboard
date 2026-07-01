"""
main.py
───────
FastAPI 기반 백엔드 API 서버.
Supabase(PostgreSQL)에 적재된 MICE 입찰 공고 데이터를 조회 및 필터링하여 프론트엔드로 전달한다.

실행 방법:
    uvicorn main:app --reload
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

import config

# 로거 설정
logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

# FastAPI 앱 생성
app = FastAPI(
    title="MICE Bidding Collector API",
    description="조달청 및 Supabase 기반 MICE 입찰 공고 수집 엔진 API",
    version="1.0.0",
)

# CORS 미들웨어 등록 (로컬 개발 및 프론트엔드 연동 지원)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase 클라이언트 초기화 (레이지 로딩 방식을 사용하여 설정 확인)
supabase_client: Optional[Client] = None

def get_supabase() -> Client:
    global supabase_client
    if supabase_client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY or \
                config.SUPABASE_URL == "your_supabase_url_here" or \
                config.SUPABASE_KEY == "your_supabase_anon_key_here":
            raise HTTPException(
                status_code=500,
                detail="Supabase URL 또는 Key 환경변수가 구성되지 않았습니다. .env 파일을 작성해 주세요."
            )
        try:
            supabase_client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Supabase 클라이언트 생성 중 오류가 발생했습니다: {e}"
            )
    return supabase_client


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────────────────────────────────────

def _determine_status_dynamic(bid_cls_dt_str: Optional[str], openg_dt_str: Optional[str]) -> str:
    """
    현재 시각 기준으로 마감 상태를 동적으로 판별하는 로직.
    """
    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst)

    def parse_date(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        raw = raw.strip()
        # 공백이나 특수문자 제거 후 파싱 가능한 형식 시도
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d%H%M%S", "%Y%m%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.replace(tzinfo=kst)
            except ValueError:
                continue
        return None

    close_dt = parse_date(bid_cls_dt_str)
    if close_dt is not None:
        return "마감" if now > close_dt else "진행중"

    open_dt = parse_date(openg_dt_str)
    if open_dt is not None:
        return "마감(개찰기준)" if now > open_dt else "진행중"

    return "정보없음"


# ─────────────────────────────────────────────────────────────────────────────
# API 엔드포인트
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "MICE Bidding Collector API 가상 가동 중",
        "endpoints": {
            "get_tenders": "/api/tenders"
        }
    }


@app.get("/api/tenders")
def get_tenders(
    search: Optional[str] = Query(None, description="공고명 키워드 검색"),
    status: Optional[str] = Query(None, description="진행 상태 필터 (진행중 / 마감 / 마감(개찰기준) / 정보없음)"),
    budget_range: Optional[str] = Query(None, description="배정 예산 구간 필터"),
    limit: int = Query(100, ge=1, le=1000, description="최대 조회 개수"),
):
    """
    Supabase에 누적된 MICE 입찰 공고 정보를 조회하는 엔드포인트.
    """
    client = get_supabase()

    try:
        # Supabase 쿼리 빌드
        # 기본적으로 게시일자 최신순 정렬
        query = client.table("tenders").select("*").order("bid_ntce_dt", descending=True).limit(limit)

        # 1. 텍스트 검색 조건 (공고명 부분 일치)
        # SQL의 ILIKE(%keyword%)와 동일하게 동작
        if search and search.strip():
            query = query.ilike("bid_ntce_nm", f"%{search.strip()}%")

        # 2. 금액 구간 필터
        if budget_range and budget_range != "전체":
            query = query.eq("budget_range", budget_range)

        # Supabase 호출 실행
        response = query.execute()
        raw_tenders = response.data or []

        # 3. 실시간 마감일시 기준 동적 상태(Status) 계산 및 필터링
        processed_tenders = []
        for item in raw_tenders:
            # DB에 저장된 마감일시/개찰일시를 기반으로 현재 시각 기준의 상태 재조정
            dyn_status = _determine_status_dynamic(item.get("bid_cls_dt"), item.get("openg_dt"))
            item["status"] = dyn_status

            # 상태 필터 적용 (파라미터 입력 시)
            if status:
                if status in dyn_status:
                    processed_tenders.append(item)
            else:
                processed_tenders.append(item)

        return {
            "success": True,
            "count": len(processed_tenders),
            "data": processed_tenders
        }

    except Exception as e:
        logger.error(f"API 데이터 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"데이터베이스 조회 도중 오류가 발생했습니다: {e}"
        )
