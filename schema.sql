-- Supabase PostgreSQL Table Schema
-- Execute this script in your Supabase project's SQL Editor to set up the database table.

CREATE TABLE IF NOT EXISTS tenders (
    id TEXT PRIMARY KEY,                       -- Unique identifier: bid_ntce_no + '-' + bid_ntce_ord
    bid_ntce_no TEXT NOT NULL,                 -- 공고번호
    bid_ntce_ord TEXT NOT NULL,                -- 공고차수
    bid_ntce_nm TEXT NOT NULL,                 -- 공고명
    ntce_instt_nm TEXT,                        -- 공고기관
    bid_ntce_dt TEXT,                          -- 게시일자 (YYYY-MM-DD)
    bid_cls_dt TEXT,                           -- 마감일시 (YYYY-MM-DD HH:MM)
    asign_bdgt_amt NUMERIC,                    -- 배정예산 (원)
    bid_methd_nm TEXT,                         -- 입찰방법
    openg_dt TEXT,                             -- 개찰일시 (폴백 판별용)
    status TEXT,                               -- 진행상태
    budget_range TEXT,                         -- 금액구간 레이블
    detail_url TEXT,                           -- 공고 상세 링크 URL
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Indexing for performance
CREATE INDEX IF NOT EXISTS idx_tenders_bid_ntce_dt ON tenders(bid_ntce_dt DESC);
CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders(status);
