"""
미트피플 판매게시판(HoUW) 백필 스크립트 (커서 방식)
- 다음 카페는 firstbbsdepth/lastbbsdepth 커서를 넘겨야 다음 페이지를 줌
- 1페이지부터 순서대로 수집하며, 진행 상태를 저장해 다음 실행 때 이어받음

사용법:
    python backfill_sell.py 50        ← 50페이지 수집 (이전 실행이 있으면 이어서)
    python backfill_sell.py 50 new   ← 처음부터 다시 시작

수집 후:
    python merge_sell.py              ← sell_posts.csv 에 병합
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime

import pandas as pd
import requests

from monitor import DAUM_COOKIES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(BASE_DIR, "sell_backfill_auto.csv")
STATE_PATH = os.path.join(BASE_DIR, "backfill_state.json")
BOARD_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"

DELAY_MIN, DELAY_MAX = 3.0, 6.0
SAVE_EVERY = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cafe.daum.net/meetpeople",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

ARTICLE_RE = re.compile(
    r"articles\.push\(\{.*?dataid:\s*'([^']+)'.*?title:\s*'([^']+)'.*?created:\s*'([^']*)'",
    re.DOTALL,
)
AUTHOR_RE = re.compile(r"author:\s*'([^']*)'")
FIRST_DEPTH_RE = re.compile(r'name="firstbbsdepth"\s+value="([^"]*)"')
LAST_DEPTH_RE = re.compile(r'name="lastbbsdepth"\s+value="([^"]*)"')
BLOCK_RE = re.compile(r"articles\.push\(\{(.*?)\}\)", re.DOTALL)


def decode_js(s):
    return s.replace("\\/", "/").encode("raw_unicode_escape").decode("unicode_escape")


def fetch_page(page, first_depth=None, last_depth=None):
    """반환: (posts, (first_depth, last_depth), 오류메시지)"""
    url = BOARD_URL
    if page > 1:
        if not last_depth:
            return None, (None, None), "커서(lastbbsdepth)가 없어 다음 페이지 요청 불가"
        url += (
            f"&page={page}&prev_page={page-1}"
            f"&firstbbsdepth={first_depth or ''}&lastbbsdepth={last_depth}&listnum=20"
        )
    resp = requests.get(url, headers=HEADERS, cookies=DAUM_COOKIES, timeout=15)
    resp.encoding = "utf-8"
    html = resp.text

    posts = []
    for block in BLOCK_RE.findall(html):
        did = re.search(r"dataid:\s*'([^']+)'", block)
        tit = re.search(r"title:\s*'([^']*)'", block)
        aut = AUTHOR_RE.search(block)
        crt = re.search(r"created:\s*'([^']*)'", block)
        if not did or not tit:
            continue
        posts.append({
            "글번호": did.group(1),
            "제목": decode_js(tit.group(1)),
            "글쓴이": decode_js(aut.group(1)) if aut else "",
            "작성일": crt.group(1) if crt else "",
            "링크": f"https://cafe.daum.net/meetpeople/HoUW/{did.group(1)}",
            "수집일": datetime.now().strftime("%Y-%m-%d"),
        })

    fd = FIRST_DEPTH_RE.search(html)
    ld = LAST_DEPTH_RE.search(html)
    depths = (fd.group(1) if fd else None, ld.group(1) if ld else None)

    if posts:
        return posts, depths, None
    if "logins.daum.net" in html or "로그인이 필요" in html:
        return None, depths, "로그인 페이지로 이동됨 (쿠키 만료 또는 접근 권한 부족)"
    if "articles.push" not in html:
        return None, depths, f"목록 구조 없음 (응답 {len(html)}자)"
    return [], depths, None  # 마지막 페이지


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_state(next_page, first_depth, last_depth):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "next_page": next_page,
                "first_depth": first_depth,
                "last_depth": last_depth,
                "저장시각": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save(rows):
    if not rows:
        return
    df = pd.DataFrame(rows)
    if os.path.exists(OUT_PATH):
        old = pd.read_csv(OUT_PATH, encoding="utf-8-sig", dtype=str)
        df = pd.concat([old, df], ignore_index=True)
    df = df.drop_duplicates(subset="글번호", keep="first")
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"  💾 저장: 누적 {len(df)}건 → {os.path.basename(OUT_PATH)}")


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    fresh = len(sys.argv) > 2 and sys.argv[2] == "new"

    state = None if fresh else load_state()
    if state:
        page = state["next_page"]
        first_depth = state.get("first_depth")
        last_depth = state.get("last_depth")
        print(f"[이어받기] {page}페이지부터 계속 (마지막 저장: {state.get('저장시각','?')})")
    else:
        page, first_depth, last_depth = 1, None, None
        if fresh and os.path.exists(STATE_PATH):
            os.remove(STATE_PATH)

    end_page = page + count - 1
    print("=" * 55)
    print(f"판매게시판 백필: {page} ~ {end_page} 페이지 (커서 방식)")
    print(f"요청 간 {DELAY_MIN}~{DELAY_MAX}초 대기 (예상 소요: 약 {int(count*(DELAY_MIN+DELAY_MAX)/2/60)+1}분)")
    print("=" * 55)

    collected = []
    prev_first_id = None
    done = 0

    while page <= end_page:
        posts, depths, err = fetch_page(page, first_depth, last_depth)

        if err:
            print(f"\n⛔ {page}페이지에서 중단: {err}")
            print("→ 상태가 저장돼 있으니 문제 해결 후 같은 명령으로 이어서 실행하면 됩니다.")
            break

        if posts == []:
            print(f"\n✅ {page}페이지: 글 없음 → 게시판 끝 도달, 종료")
            break

        if posts[0]["글번호"] == prev_first_id:
            print(f"\n✅ {page}페이지: 이전과 동일 → 게시판 끝 도달, 종료")
            break
        prev_first_id = posts[0]["글번호"]

        collected.extend(posts)
        done += 1
        oldest = posts[-1]["작성일"]
        print(f"  [{page}p] {len(posts)}건 (가장 오래된 글: {oldest}) / 이번 실행 누적 {done*20}건 내외")

        first_depth, last_depth = depths
        save_state(page + 1, first_depth, last_depth)

        if done % SAVE_EVERY == 0:
            save(collected)
            collected = []

        page += 1
        if page <= end_page:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    save(collected)
    print(f"\n이번 실행 완료 ({done}페이지 수집). 다음 단계:")
    print(f"  · 더 수집: python backfill_sell.py {count}   ← 자동으로 이어받음")
    print(f"  · 병합:   python merge_sell.py")


if __name__ == "__main__":
    main()