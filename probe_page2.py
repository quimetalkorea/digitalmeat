"""
다음 카페 페이지네이션 구조 분석 스크립트 (2차)
- 1페이지 HTML 안에서 실제 '다음 페이지 링크'와 글 데이터 구조를 찾아냄

사용법: python probe_page2.py
"""

import html as htmllib
import re

import requests

from monitor import DAUM_COOKIES

BASE = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cafe.daum.net/meetpeople",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def main():
    resp = requests.get(BASE, headers=HEADERS, cookies=DAUM_COOKIES, timeout=15)
    resp.encoding = "utf-8"
    text = resp.text
    print(f"응답 크기: {len(text)}자\n")

    # 1) articles.push 원본 블록 하나 출력 (어떤 필드가 있는지 확인)
    mt = re.search(r"articles\.push\(\{(.*?)\}\)", text, re.DOTALL)
    if mt:
        print("── articles.push 필드 구조 (첫 번째 글) ──")
        print(mt.group(1)[:600])
        print()

    # 2) HTML 안의 bbs_list 링크 전부 추출 (페이지네이션 링크 포함)
    links = re.findall(r"bbs_list[?][^\"'<>\s\\]+", text)
    uniq = []
    for l in links:
        d = htmllib.unescape(l).replace("\\/", "/").replace("\\u0026", "&")
        if d not in uniq:
            uniq.append(d)
    print(f"── HTML 내 bbs_list 링크 {len(uniq)}종 ──")
    for l in uniq[:15]:
        print(" ", l[:160])
    print()

    # 3) 페이지 이동 관련 키워드 주변 문맥
    for kw in ["prev_page", "lastbbsdepth", "firstbbsdepth", "nextPage", "pagingBlock", "page="]:
        for mm in re.finditer(re.escape(kw), text):
            s = max(0, mm.start() - 60)
            snippet = text[s:mm.start() + 120].replace("\n", " ")
            print(f"[{kw}] ...{snippet}...")
            break  # 키워드당 첫 번째만

    print("\n위 출력 전체를 Claude에게 붙여넣어 주세요.")


if __name__ == "__main__":
    main()