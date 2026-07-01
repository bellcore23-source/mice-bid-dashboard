# 나라장터 MICE 입찰공고 검색 시스템

조달청 나라장터 OpenAPI를 연동하여 **MICE(포럼·국제회의·심포지엄·컨퍼런스·세미나)** 관련 실공고 입찰 데이터를 수집·필터링·시각화하는 Streamlit 대시보드입니다.

---

## 📁 프로젝트 디렉토리 구조

```
mice-bid-dashboard/
│
├── app.py              # Streamlit 메인 대시보드 (진입점)
├── collector.py        # 나라장터 OpenAPI 데이터 수집·정제 엔진
├── config.py           # 전역 설정 (API URL, 키워드, 금액구간 등)
├── requirements.txt    # Python 의존성 패키지
├── .env.example        # 환경변수 예시 (.env 파일 작성 참고용)
└── README.md           # 프로젝트 문서
```

---

## ⚙️ 설치 및 실행

### 1. 환경 준비

```bash
# 가상환경 생성 (선택)
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# 패키지 설치
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
# .env.example 을 .env 로 복사 후 편집
copy .env.example .env
```

`.env` 파일에 발급받은 인증키 입력:
```
NARA_API_KEY=발급받은_인증키_입력
```

> **API 키 발급**: [공공데이터포털](https://www.data.go.kr) → "나라장터 서비스" 검색 → 활용신청

### 3. 앱 실행

```bash
streamlit run app.py
```

---

## 🔑 API 연동 정보

| 항목 | 내용 |
|------|------|
| API 명 | 나라장터 입찰공고정보서비스(용역) |
| 엔드포인트 | `getBidPblancListInfoServcPPSSrch02` |
| 출처 | 공공데이터포털 (data.go.kr) |
| 인증 방식 | ServiceKey (URL 파라미터) |
| 응답 포맷 | JSON |

---

## 🔍 검색 필터 조건

### Positive 키워드 (공고명 포함 필수)
`포럼`, `국제회의`, `심포지엄`, `컨퍼런스`, `콘퍼런스`, `세미나`

### Negative 키워드 (자동 제외)
`공사`, `구축`, `리모델링`, `인테리어`, `환경개선`, `물품`, `구매`, `제조`, `시스템`, `유지보수`

### 배정예산 구간
5,000만 원 단위로 최대 5억 원까지 세분화

---

## 🗺️ 아키텍처 흐름

```
┌──────────────┐      ┌──────────────────┐      ┌──────────────┐
│   config.py  │─────▶│   collector.py   │─────▶│    app.py    │
│  (상수/설정) │      │ (API 호출·정제)  │      │  (Streamlit) │
└──────────────┘      └──────────────────┘      └──────────────┘
                              │
                              ▼
                   조달청 나라장터 OpenAPI
                   (data.go.kr)
```

---

## 📌 주요 기능

| 기능 | 설명 |
|------|------|
| 실시간 수집 | 사이드바 버튼 클릭 → API 호출 → 결과 즉시 반영 |
| 키워드 필터 | Positive/Negative 자동 적용 |
| 금액 구간 필터 | 5천만 원 단위 selectbox |
| 마감 상태 판별 | `bidClsDt` 없으면 `opengDt` 폴백 |
| 상세 보기 | 테이블 행 클릭 → 우측 패널 상세 카드 |
| 데모 모드 | API 키 없어도 샘플 데이터로 동작 |

---

## 🛠️ GitHub 배포 (선택)

```bash
git init
git add .
git commit -m "feat: 나라장터 MICE 입찰공고 대시보드 초기 구축"
git remote add origin https://github.com/<YOUR_USERNAME>/mice-bid-dashboard.git
git push -u origin main
```

> ⚠️ `.env` 파일은 반드시 `.gitignore`에 추가하여 API 키 노출을 방지하세요.

---

## 📜 라이선스
MIT
