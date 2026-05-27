"""
미트피플 구매게시판 모니터링 + 시세 매칭 알림
- 10분마다 미트피플 구매게시판 크롤링
- 내 시세 데이터와 품목 매칭
- 매칭되면 소리 알림 + latest_posts.csv 저장
"""

import requests
import pandas as pd
import time
import os
import re
import json
import winsound
from datetime import datetime

# =============================================
# 설정
# =============================================

# 구글 시트 시세 데이터 URL (meat_search.py와 동일한 URL)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

# 미트피플 구매게시판 URL (iframe 내부 URL)
MEETPEOPLE_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoTs"

# CSV 저장 경로 (Streamlit 앱과 같은 폴더)
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_posts.csv")
MATCHED_CSV_PATH = CSV_PATH.replace(".csv", "_matched.csv")

# 확인 주기 (초)
CHECK_INTERVAL = 10 * 60  # 10분

# 이미 알림을 보낸 글번호 기록
notified_ids = set()

# =============================================
# 다음 카페 쿠키 설정
# =============================================
# 크롬 → 미트피플 로그인 → F12 → Application → Cookies → cafe.daum.net
# 각 쿠키 이름 클릭 → 하단에서 전체 값 복사
DAUM_COOKIES = {
    "HTS": "XUwrpyOXxWx9TFx_NPqLqw00",
    "JSESSIONID": "FABAC0B35048CDFFA8426677DAE9BA60",
    "PROF": "0603012032024064024192UiQPJk7X-6w0mlxoempuua9QsdGeNIag3O1dpXj_gbkQKuZP3z7wEl2bxriNh5SdkQ00LYYSA9A1_cGNLCyhCzrwOgj61xkRhz7hDHbz3NH3TPhotxsi_HxV.ZeBXdFBFd3ofIauQlo8OTLLnHHY.bHDTw00vcQtS7zilQDLGZ8G3iSvt1Okkw1SdF7si3NZE2RfySxeElXDnNK2.GGi-FMJ1bLfiXZFiEe7R2buqNP6DuNTyApBuUCkhis3ZM7CbYtTS4v_Cn81JJotyokPqTzBHRDQjyBXmYEKGlxBdC1p1XiyLXO3CYrQvN1gPN.ltqjW8uhEX7nLHx4ANm125NdGii-7",
    "ALID": "KN6XC2KuL5bGq0vzhLQhPSZvFgslAvu4jPIHdBwWDl5Hn4fnDEnIN5oszMeiixP2w999UI",
    "HM_CU": "562UzJ5yPrq",
}

# =============================================
# 시세 데이터 로드
# =============================================

def load_my_prices():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df = df.dropna(how="all")
        if "단가(원/kg)" in df.columns:
            df = df[df["단가(원/kg)"].notna() & (df["단가(원/kg)"] != "")]
        print(f"[시세] {len(df)}개 품목 로드 완료")
        return df
    except Exception as e:
        print(f"[시세] 로드 실패: {e}")
        return pd.DataFrame()


# =============================================
# 미트피플 크롤링 (JavaScript에서 데이터 추출)
# =============================================

def fetch_posts():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://cafe.daum.net/meetpeople",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    try:
        resp = requests.get(MEETPEOPLE_URL, headers=headers, cookies=DAUM_COOKIES, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text

        # JavaScript articles 배열에서 dataid, title, author, created 추출
        pattern = re.compile(
            r"articles\.push\(\{.*?dataid:\s*'([^']+)'.*?title:\s*'([^']+)'.*?author:\s*'([^']+)'.*?created:\s*'([^']+)'",
            re.DOTALL
        )
        matches = pattern.findall(html)

        posts = []
        for dataid, title_raw, author_raw, created in matches:
            # 유니코드 이스케이프 디코딩 (\uC2A4 → 스)
            title = title_raw.encode('raw_unicode_escape').decode('unicode_escape')
            author = author_raw.encode('raw_unicode_escape').decode('unicode_escape')

            posts.append({
                "글번호": dataid,
                "제목": title,
                "글쓴이": author,
                "작성일": created,
                "링크": f"https://cafe.daum.net/meetpeople/HoTs/{dataid}",
            })

        print(f"[크롤링] {len(posts)}개 글 수집")
        return posts

    except Exception as e:
        print(f"[크롤링] 실패: {e}")
        return []


# =============================================
# 품목 매칭
# =============================================

def match_posts_with_prices(posts, price_df):
    if price_df.empty or not posts:
        return []

    my_items = []
    if "품목" in price_df.columns:
        my_items = price_df["품목"].dropna().unique().tolist()

    matched = []
    for post in posts:
        title = post.get("제목", "")
        for item in my_items:
            if str(item) in title:
                item_prices = price_df[price_df["품목"] == item]
                price_info = ""
                if not item_prices.empty and "단가(원/kg)" in item_prices.columns:
                    prices = item_prices["단가(원/kg)"].tolist()
                    price_info = f"{min(prices)}~{max(prices)}원" if len(prices) > 1 else f"{prices[0]}원"

                matched.append({
                    **post,
                    "매칭품목": item,
                    "내시세": price_info,
                })
                break

    return matched


# =============================================
# 소리 알림
# =============================================

def play_alert(count):
    print(f"\n🔔 매칭 {count}건 발견!")
    for _ in range(3):
        winsound.Beep(1000, 300)
        time.sleep(0.2)


# =============================================
# 메인 루프
# =============================================

def main():
    print("=" * 50)
    print("미트피플 모니터링 시작")
    print(f"확인 주기: {CHECK_INTERVAL // 60}분")
    print("=" * 50)

    price_df = load_my_prices()

    while True:
        # 운영 시간 체크 (09:00 ~ 17:30)
        now_time = datetime.now().time()
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("17:30", "%H:%M").time()

        if not (start_time <= now_time <= end_time):
            print(f"  운영 시간 외 ({now_time.strftime('%H:%M')}) - 대기 중...")
            time.sleep(3600)  # 60분마다 체크
            continue
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] 게시판 확인 중...")

        posts = fetch_posts()

        if posts:
            # CSV 저장
            df = pd.DataFrame(posts)
            df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
            print(f"[저장] {CSV_PATH}")

            # 새 글만 필터
            new_posts = [p for p in posts if p.get("글번호") not in notified_ids]

            if new_posts:
                matched = match_posts_with_prices(new_posts, price_df)

                if matched:
                    play_alert(len(matched))
                    for m in matched:
                        print(f"  ✅ [{m['매칭품목']}] {m['제목']}")
                        print(f"     내 시세: {m['내시세']}")
                        print(f"     링크: {m['링크']}")

                    pd.DataFrame(matched).to_csv(MATCHED_CSV_PATH, index=False, encoding="utf-8-sig")
                else:
                    print("  매칭 품목 없음")

                for p in new_posts:
                    notified_ids.add(p.get("글번호"))

        else:
            print("  게시글 수집 실패 (쿠키 확인 필요)")

        print(f"  다음 확인: {CHECK_INTERVAL // 60}분 후")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()