"""
다음 카페 페이지 이동 파라미터 탐색 스크립트
- 여러 후보 파라미터로 2페이지를 요청해보고, 1페이지와 다른 글이 나오는 방식을 찾음

사용법: python probe_page.py
"""

import re
import time

import requests

from monitor import DAUM_COOKIES

BASE = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cafe.daum.net/meetpeople",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

PATTERN = re.compile(r"articles\.push\(\{.*?dataid:\s*'([^']+)'", re.DOTALL)

CANDIDATES = [
    "&page=2",
    "&pagenum=2",
    "&curpage=2",
    "&pageNum=2",
    "&p=2",
    "&page=2&listnum=10",
    "&page=2&listnum=20",
    "&page=2&firstbbsdepth=&lastbbsdepth=&contentval=",
    "&prev_page=1&page=2",
    "&pageIndex=2",
]


def first_ids(url):
    try:
        resp = requests.get(url, headers=HEADERS, cookies=DAUM_COOKIES, timeout=15)
        resp.encoding = "utf-8"
        ids = PATTERN.findall(resp.text)
        return ids
    except Exception as e:
        return [f"오류: {e}"]


def main():
    print("기준(1페이지) 요청 중...")
    base_ids = first_ids(BASE)
    if not base_ids:
        print("1페이지 수집 실패 — 쿠키 확인 필요")
        return
    print(f"1페이지 글번호: {base_ids[:3]} ... 총 {len(base_ids)}건\n")

    found = []
    for cand in CANDIDATES:
        time.sleep(2.5)
        ids = first_ids(BASE + cand)
        same = (ids[:3] == base_ids[:3])
        status = "❌ 1페이지와 동일" if same else f"✅ 다른 글 반환! 첫 글번호: {ids[0] if ids else '없음'}"
        print(f"  {cand:50s} → {status} ({len(ids)}건)")
        if not same and ids:
            found.append(cand)

    print()
    if found:
        print(f"🎯 작동하는 파라미터: {found[0]}")
        print("이 결과를 Claude에게 붙여넣으면 backfill_sell.py를 맞춰줍니다.")
    else:
        print("모든 후보가 실패했어요. 이 경우 브라우저에서 실제 요청을 캡처해야 합니다:")
        print("  1. 크롬에서 판매게시판 열기 → F12 → Network 탭")
        print("  2. 게시판 하단에서 '2' 페이지 클릭")
        print("  3. Network 목록에서 새로 생긴 요청(bbs_list 등) 우클릭 → Copy → Copy URL")
        print("  4. 그 URL을 Claude에게 붙여넣기")


if __name__ == "__main__":
    main()