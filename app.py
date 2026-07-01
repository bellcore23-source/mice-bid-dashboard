"""
app.py
──────
나라장터 MICE 입찰공고 검색 대시보드 — Streamlit 메인 진입점.

실행 방법:
    streamlit run app.py
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd
import streamlit as st

import config
from collector import fetch_mice_bids

# ─────────────────────────────────────────────────────────────────────────────
# 로깅 기본 설정
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ─────────────────────────────────────────────────────────────────────────────
# 페이지 전체 설정
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="나라장터 MICE 입찰공고 검색",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# 글로벌 CSS 스타일
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Inter:wght@300;400;600;700&display=swap');

    /* ── 전체 기본 폰트 ── */
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', 'Inter', sans-serif;
    }

    /* ── 헤더 영역 ── */
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f4c81 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(15, 76, 129, 0.35);
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(56,189,248,0.12) 0%, transparent 70%);
        border-radius: 50%;
    }
    .main-header h1 {
        color: #f8fafc;
        font-size: 1.85rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: #94a3b8;
        font-size: 0.9rem;
        margin: 0.4rem 0 0 0;
    }
    .header-badge {
        display: inline-block;
        background: rgba(56,189,248,0.18);
        color: #38bdf8;
        border: 1px solid rgba(56,189,248,0.35);
        border-radius: 20px;
        padding: 2px 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 0.6rem;
        letter-spacing: 0.5px;
    }

    /* ── 지표 카드 ── */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .metric-card::after {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
    }
    .metric-card.total::after   { background: linear-gradient(90deg, #3b82f6, #6366f1); }
    .metric-card.active::after  { background: linear-gradient(90deg, #10b981, #06b6d4); }
    .metric-card.budget::after  { background: linear-gradient(90deg, #f59e0b, #ef4444); }

    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    }
    .metric-label {
        font-size: 0.78rem;
        color: #64748b;
        font-weight: 600;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #f1f5f9;
        line-height: 1.1;
    }
    .metric-value.budget-val {
        font-size: 1.5rem;
    }
    .metric-sub {
        font-size: 0.72rem;
        color: #475569;
        margin-top: 0.3rem;
    }

    /* ── 섹션 구분선 ── */
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #334155, transparent);
        margin: 1.5rem 0;
    }

    /* ── 상태 배지 ── */
    .badge-active {
        background: rgba(16,185,129,0.15);
        color: #34d399;
        border: 1px solid rgba(16,185,129,0.3);
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .badge-closed {
        background: rgba(239,68,68,0.12);
        color: #f87171;
        border: 1px solid rgba(239,68,68,0.25);
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .badge-unknown {
        background: rgba(100,116,139,0.15);
        color: #94a3b8;
        border: 1px solid rgba(100,116,139,0.3);
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }

    /* ── 상세 카드 ── */
    .detail-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 1.6rem;
        margin-top: 1rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .detail-title {
        color: #e2e8f0;
        font-size: 1.05rem;
        font-weight: 700;
        line-height: 1.5;
        word-break: keep-all;
        overflow-wrap: break-word;
        margin-bottom: 1rem;
        border-bottom: 1px solid #334155;
        padding-bottom: 0.8rem;
    }
    .detail-row {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
        align-items: flex-start;
    }
    .detail-key {
        color: #64748b;
        font-size: 0.82rem;
        font-weight: 600;
        min-width: 90px;
    }
    .detail-val {
        color: #cbd5e1;
        font-size: 0.85rem;
        word-break: break-all;
    }
    .detail-url-btn {
        display: inline-block;
        margin-top: 1rem;
        background: linear-gradient(135deg, #3b82f6, #6366f1);
        color: white !important;
        text-decoration: none;
        padding: 0.5rem 1.2rem;
        border-radius: 8px;
        font-size: 0.82rem;
        font-weight: 600;
        transition: opacity 0.2s;
    }
    .detail-url-btn:hover { opacity: 0.85; }

    /* ── 사이드바 ── */
    section[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stSlider label,
    section[data-testid="stSidebar"] .stNumberInput label {
        color: #94a3b8 !important;
        font-size: 0.82rem !important;
        font-weight: 600;
        letter-spacing: 0.3px;
    }

    /* ── 데이터 테이블 오버라이드 ── */
    .dataframe-container {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #334155;
    }

    /* ── 새 공고 강조 태그 ── */
    .tag-new {
        background: linear-gradient(135deg, #f59e0b, #ef4444);
        color: white;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 4px;
        margin-left: 5px;
        vertical-align: middle;
        letter-spacing: 0.5px;
    }

    /* ── 정보 박스 ── */
    .info-box {
        background: rgba(59,130,246,0.08);
        border: 1px solid rgba(59,130,246,0.25);
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        color: #93c5fd;
        font-size: 0.82rem;
        line-height: 1.6;
    }

    /* ── 빈 상태 메시지 ── */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: #475569;
    }
    .empty-state .icon { font-size: 3rem; margin-bottom: 0.5rem; }
    .empty-state p { font-size: 0.95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────────────────────────────────────
if "raw_df" not in st.session_state:
    st.session_state.raw_df = None
if "selected_idx" not in st.session_state:
    st.session_state.selected_idx = None


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_budget(amount: float | None) -> str:
    """예산 금액을 '억/천만 원' 단위 문자열로 포맷."""
    if amount is None or amount < 0:
        return "미확인"
    if amount == 0:
        return "0원"
    if amount >= 1_0000_0000:
        val = amount / 1_0000_0000
        return f"{val:,.1f}억 원"
    if amount >= 1_000_0000:
        val = amount / 1_000_0000
        return f"{val:,.0f}천만 원"
    return f"{int(amount):,}원"


def _fmt_budget_pool(total: float) -> str:
    """예산 풀 합계를 간결하게 포맷."""
    if total >= 1_0000_0000:
        return f"₩ {total / 1_0000_0000:,.1f}억"
    if total >= 1_000_0000:
        return f"₩ {total / 1_000_0000:,.0f}천만"
    return f"₩ {total:,.0f}"


def _status_badge(status: str) -> str:
    """상태 문자열을 HTML 배지로 변환."""
    if "진행중" in status:
        return f'<span class="badge-active">● 진행중</span>'
    if "마감" in status:
        return f'<span class="badge-closed">✕ 마감</span>'
    return f'<span class="badge-unknown">? {status}</span>'


def _apply_filters(
    df: pd.DataFrame,
    budget_label: str,
    keyword: str,
    period_days: int,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    result = df.copy()

    # 기간 필터 (게시일자 기준)
    from datetime import date
    cutoff = date.today() - timedelta(days=period_days)
    result = result[result["bidNtceDt"] >= str(cutoff)]

    # 금액 구간 필터
    if budget_label != "전체":
        result = result[result["budgetRange"] == budget_label]

    # 공고명 키워드 검색
    if keyword.strip():
        result = result[
            result["bidNtceNm"].str.contains(keyword.strip(), na=False, case=False)
        ]

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 사이드바 UI
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        '<div style="padding:1rem 0 0.5rem;"><span style="color:#38bdf8;font-size:1.1rem;font-weight:700;">🔍 검색 필터</span></div>',
        unsafe_allow_html=True,
    )

    # API 키 입력
    with st.expander("⚙️ API 설정", expanded=not bool(config.API_KEY)):
        api_key_input = st.text_input(
            "나라장터 API 키",
            value=config.API_KEY,
            type="password",
            placeholder="공공데이터포털 인증키 입력",
            help="https://www.data.go.kr 에서 발급",
            key="api_key_widget",
        )

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    # 조회 기간
    period_days = st.slider(
        "📅 게시 기간 (일)",
        min_value=7,
        max_value=180,
        value=config.DEFAULT_PERIOD_DAYS,
        step=7,
        help="현재일 기준 과거 몇 일의 공고를 조회할지 설정합니다.",
        key="period_slider",
    )

    st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

    # 금액 구간
    budget_label = st.selectbox(
        "💰 배정예산 구간",
        options=config.BUDGET_RANGE_LABELS,
        index=0,
        key="budget_select",
    )

    # 공고명 키워드 검색
    keyword = st.text_input(
        "🔎 공고명 키워드",
        placeholder="예: 글로벌, 환경, 헬스케어...",
        key="keyword_input",
    )

    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

    # 데이터 수집 버튼
    fetch_btn = st.button(
        "🚀 공고 데이터 수집",
        use_container_width=True,
        type="primary",
        key="fetch_btn",
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 도움말
    st.markdown(
        """
        <div class="info-box">
        <b>📌 사용 안내</b><br>
        ① API 키 설정 후 <b>공고 데이터 수집</b> 클릭<br>
        ② 사이드바 필터로 원하는 공고 탐색<br>
        ③ 테이블에서 행 선택 시 상세 내역 확인<br><br>
        <b>⚠️ API 키 미설정 시</b> 데모 데이터로 동작합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="main-header">
        <span class="header-badge">🏛️ PUBLIC PROCUREMENT SERVICE</span>
        <h1>나라장터 MICE 입찰공고 검색 시스템</h1>
        <p>조달청 OpenAPI 연동 · 포럼·국제회의·심포지엄·컨퍼런스·세미나 실공고 실시간 모니터링</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# 데이터 수집
# ─────────────────────────────────────────────────────────────────────────────
if fetch_btn:
    with st.spinner("📡 나라장터 OpenAPI에서 데이터를 수집 중입니다..."):
        df_raw = fetch_mice_bids(
            api_key=api_key_input or None,
            period_days=period_days,
        )
    st.session_state.raw_df = df_raw
    st.session_state.selected_idx = None

    if df_raw.empty:
        st.warning("수집된 공고가 없습니다. API 키와 네트워크를 확인하세요.", icon="⚠️")
    else:
        st.success(f"✅ 총 {len(df_raw)}건의 MICE 공고를 수집했습니다.", icon="✅")

# 최초 진입 시 데모 데이터 자동 로드
if st.session_state.raw_df is None:
    st.session_state.raw_df = fetch_mice_bids(api_key=None, period_days=period_days)

raw_df: pd.DataFrame = st.session_state.raw_df

# 필터 적용
filtered_df = _apply_filters(raw_df, budget_label, keyword, period_days)


# ─────────────────────────────────────────────────────────────────────────────
# 지표 카드 (Key Metrics)
# ─────────────────────────────────────────────────────────────────────────────
total_count  = len(filtered_df)
active_df    = filtered_df[filtered_df["status"].str.contains("진행중", na=False)]
active_count = len(active_df)
budget_pool  = active_df["asignBdgtAmt"].dropna().sum()

col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    st.markdown(
        f"""
        <div class="metric-card total">
            <div class="metric-label">🗂️ 전체 검색 공고 수</div>
            <div class="metric-value">{total_count:,}</div>
            <div class="metric-sub">건 (필터 적용 결과)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_m2:
    st.markdown(
        f"""
        <div class="metric-card active">
            <div class="metric-label">✅ 진행 중인 활성 공고</div>
            <div class="metric-value">{active_count:,}</div>
            <div class="metric-sub">건 (마감 공고 제외)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_m3:
    st.markdown(
        f"""
        <div class="metric-card budget">
            <div class="metric-label">💰 활성 입찰 예산 Pool</div>
            <div class="metric-value budget-val">{_fmt_budget_pool(budget_pool)}</div>
            <div class="metric-sub">마감 공고 예산 제외 합산</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 메인 영역: 리스트 테이블 + 상세 보기
# ─────────────────────────────────────────────────────────────────────────────
if filtered_df.empty:
    st.markdown(
        """
        <div class="empty-state">
            <div class="icon">🔍</div>
            <p>조건에 맞는 공고가 없습니다.<br>필터 조건을 완화하거나 데이터를 새로 수집해 보세요.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    list_col, detail_col = st.columns([3, 2], gap="large")

    with list_col:
        st.markdown(
            f'<div style="color:#94a3b8;font-size:0.82rem;margin-bottom:0.6rem;">'
            f'총 <b style="color:#f1f5f9">{total_count}</b>건 검색됨 '
            f'· 활성 <b style="color:#34d399">{active_count}</b>건 '
            f'· 최신순 정렬</div>',
            unsafe_allow_html=True,
        )

        # 표시용 DataFrame 생성
        display_rows = []
        for _, row in filtered_df.iterrows():
            budget_str = _fmt_budget(row.get("asignBdgtAmt"))
            display_rows.append({
                "게시일자":   row.get("bidNtceDt", ""),
                "공고명":     row.get("bidNtceNm", ""),
                "공고기관":   row.get("ntceInsttNm", ""),
                "마감일자":   row.get("bidClsDt", "") or "미확인",
                "배정예산":   budget_str,
                "예산구간":   row.get("budgetRange", ""),
                "진행상태":   row.get("status", ""),
            })

        display_df = pd.DataFrame(display_rows)

        # 행 선택을 위한 라디오 인덱스
        if len(display_df) > 0:
            # st.dataframe with selection
            event = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=False,
                height=480,
                column_config={
                    "게시일자": st.column_config.TextColumn("📅 게시일자", width="small"),
                    "공고명":   st.column_config.TextColumn("📋 공고명",   width="large"),
                    "공고기관": st.column_config.TextColumn("🏢 공고기관", width="medium"),
                    "마감일자": st.column_config.TextColumn("⏰ 마감일자", width="medium"),
                    "배정예산": st.column_config.TextColumn("💰 배정예산", width="small"),
                    "예산구간": st.column_config.TextColumn("📊 예산구간", width="medium"),
                    "진행상태": st.column_config.TextColumn("🚦 진행상태", width="small"),
                },
                on_select="rerun",
                selection_mode="single-row",
                key="bid_table",
            )

            # 선택된 행 추출
            selected_rows = event.selection.rows if event.selection else []
            if selected_rows:
                st.session_state.selected_idx = selected_rows[0]

    with detail_col:
        st.markdown(
            '<div style="color:#94a3b8;font-size:0.82rem;margin-bottom:0.6rem;">'
            '📂 <b style="color:#f1f5f9">공고 상세 보기</b> — 좌측 테이블에서 행을 클릭하세요</div>',
            unsafe_allow_html=True,
        )

        sel_idx = st.session_state.get("selected_idx")

        if sel_idx is None:
            st.markdown(
                """
                <div style="background:#1e293b;border:1px dashed #334155;border-radius:14px;
                            padding:3rem 1.5rem;text-align:center;color:#475569;">
                    <div style="font-size:2.5rem;margin-bottom:0.8rem;">🖱️</div>
                    <p style="font-size:0.9rem;">왼쪽 테이블에서<br>공고를 선택하면<br>상세 내용이 표시됩니다.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            try:
                row = filtered_df.iloc[sel_idx]
            except IndexError:
                st.warning("선택한 행이 유효하지 않습니다.")
                row = None

            if row is not None:
                status      = row.get("status", "")
                badge_html  = _status_badge(status)
                budget_disp = _fmt_budget(row.get("asignBdgtAmt"))
                detail_url  = row.get("detailUrl", "https://www.g2b.go.kr")
                bid_no      = row.get("bidNtceNo", "")
                method      = row.get("bidMethdNm", "")

                st.markdown(
                    f"""
                    <div class="detail-card">
                        <div style="margin-bottom:0.6rem;">{badge_html}</div>
                        <div class="detail-title">{row.get("bidNtceNm", "")}</div>
                        <div class="detail-row">
                            <span class="detail-key">공고번호</span>
                            <span class="detail-val">{bid_no}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">공고기관</span>
                            <span class="detail-val">{row.get("ntceInsttNm", "")}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">게시일자</span>
                            <span class="detail-val">{row.get("bidNtceDt", "")}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">마감일자</span>
                            <span class="detail-val">{row.get("bidClsDt", "") or "미확인"}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">배정예산</span>
                            <span class="detail-val" style="color:#fbbf24;font-weight:600;">{budget_disp}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">예산구간</span>
                            <span class="detail-val">{row.get("budgetRange", "")}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">입찰방법</span>
                            <span class="detail-val">{method or "미확인"}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-key">진행상태</span>
                            <span class="detail-val">{status}</span>
                        </div>
                        <a class="detail-url-btn" href="{detail_url}" target="_blank">
                            🔗 나라장터 원문 공고 보기 →
                        </a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# ─────────────────────────────────────────────────────────────────────────────
# 푸터
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-divider" style="margin-top:2rem;"></div>', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#334155;font-size:0.75rem;">'
    '🏛️ 나라장터 MICE 입찰공고 검색 시스템 · 조달청 OpenAPI 연동 · 데이터 출처: 공공데이터포털'
    '</div>',
    unsafe_allow_html=True,
)
