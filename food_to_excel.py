import requests
import pandas as pd
import time

# ── 설정 ──────────────────────────────────────────────
SERVICE_KEY = "9boDl9wgN+W558JNizAC59FOwXJnQfLO3HX9UhRb7DgpLeHcwPfN+DDEOb6jp37BTXx8Fo8Clfa7WQf8wDAMOw=="
URL = "https://apis.data.go.kr/1741000/food_manufacturing_processors/info"
NUM_OF_ROWS = 100          # 한 번에 받을 건수 (최대 100)
OUTPUT_FILE = "식품제조가공업.xlsx"

# 영문 컬럼명 → 한글 컬럼명 매핑 (원하는 항목만 골라 둠)
COLUMN_NAMES = {
    "BPLC_NM": "사업장명",
    "BZSTAT_SE_NM": "업종구분",
    "SALS_STTS_NM": "영업상태",
    "DTL_SALS_STTS_NM": "상세영업상태",
    "LCPMT_VMD": "인허가일자",
    "ROAD_NM_ADDR": "도로명주소",
    "ROAD_NM_ZIP": "우편번호",
    "LOTNO_ADDR": "지번주소",
    "TELNO": "전화번호",
    "OPN_ATMY_GRP_CD": "개방자치단체코드",
    "DAT_UPDT_PNT": "데이터갱신시점",
}
# ─────────────────────────────────────────────────────

all_rows = []
page = 1

while True:
    try:
        resp = requests.get(URL, params={
            "serviceKey": SERVICE_KEY,
            "pageNo": page,
            "numOfRows": NUM_OF_ROWS,
            "returnType": "json",
        }, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"{page}페이지 요청 실패: {e} — 3초 후 재시도")
        time.sleep(3)
        continue

    body = resp.json()["response"]["body"]
    items = body.get("items", {}).get("item", [])
    if not items:
        break

    all_rows.extend(items)
    total = body.get("totalCount", 0)
    print(f"{page}페이지 수집 중... 누적 {len(all_rows)} / {total}건")

    if len(all_rows) >= total:
        break
    page += 1
    time.sleep(0.1)   # 서버 부담 방지

# 데이터프레임으로 변환
df = pd.DataFrame(all_rows)

# 한글 컬럼명 적용 (매핑에 있는 컬럼만 골라 순서대로)
cols = [c for c in COLUMN_NAMES if c in df.columns]
df = df[cols].rename(columns=COLUMN_NAMES)

# 엑셀로 저장
df.to_excel(OUTPUT_FILE, index=False)
print(f"\n완료! 총 {len(df)}건을 '{OUTPUT_FILE}' 로 저장했습니다.")