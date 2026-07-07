import requests
import pandas as pd
import time

KEY = "9boDl9wgN+W558JNizAC59FOwXJnQfLO3HX9UhRb7DgpLeHcwPfN+DDEOb6jp37BTXx8Fo8Clfa7WQf8wDAMOw=="
URL = "https://apis.data.go.kr/1741000/livestock_processing/info"
OUTPUT = "축산가공업.xlsx"

rows = []
page = 1
retry = 0
while True:
    try:
        r = requests.get(URL, params={
            "serviceKey": KEY, "pageNo": page,
            "numOfRows": 100, "returnType": "json",
        }, timeout=15)
    except requests.RequestException as e:
        print(f"{page}페이지 네트워크 오류: {e} — 5초 후 재시도"); time.sleep(5); continue

    if r.status_code != 200:
        retry += 1
        if retry <= 10:
            print(f"{page}페이지 {r.status_code} 응답 — {retry}번째 재시도 (5초 대기)")
            time.sleep(5); continue
        else:
            print(f"{page}페이지에서 재시도 10회 모두 실패. 여기까지 저장합니다."); break

    retry = 0
    body = r.json()["response"]["body"]
    items = body.get("items", {})
    items = items.get("item", []) if isinstance(items, dict) else items
    if isinstance(items, dict):
        items = [items]
    if not items:
        break
    rows.extend(items)
    total = int(body.get("totalCount", 0))
    print(f"{page}페이지 수집... 누적 {len(rows)} / {total}건")
    if len(rows) >= total:
        break
    page += 1
    time.sleep(0.5)   # 호출 간격을 0.5초로 늘림

if rows:
    pd.DataFrame(rows).to_excel(OUTPUT, index=False)
    print(f"\n완료! 총 {len(rows)}건을 '{OUTPUT}'(D:\\digitalmeat 폴더)로 저장했습니다.")
else:
    print("\n수집된 데이터가 없습니다.")