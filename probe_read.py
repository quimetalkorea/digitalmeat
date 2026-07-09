# -*- coding: utf-8 -*-
"""
본문 주소 진단 스크립트
- 최신 판매글 1건에 대해 여러 본문 주소를 시험하고 결과를 보고
- 목록 페이지의 espam(보안 토큰)을 이용한 방식도 시험

사용법: python probe_read.py  →  출력 전체를 Claude에게 붙여넣기
"""

import html as htmllib
import re
import time

import requests

from monitor import DAUM_COOKIES, normalize_text

LIST_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cafe.daum.net/meetpeople",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
MOBILE_HEADERS = {**HEADERS, "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"}


def html_to_text(src):
    src = re.sub(r"<script.*?</script>", " ", src, flags=re.DOTALL | re.IGNORECASE)
    src = re.sub(r"<style.*?</style>", " ", src, flags=re.DOTALL | re.IGNORECASE)
    src = re.sub(r"<[^>]+>", " ", src)
    src = htmllib.unescape(src)
    return re.sub(r"\s+", " ", src).strip()


def main():
    # 1) 목록에서 최신 글의 dataid / title / espam 확보
    resp = requests.get(LIST_URL, headers=HEADERS, cookies=DAUM_COOKIES, timeout=15)
    resp.encoding = "utf-8"
    block = re.search(r"articles\.push\(\{(.*?)\}\)", resp.text, re.DOTALL)
    if not block:
        print("목록 파싱 실패 — 쿠키 확인 필요")
        return
    b = block.group(1)
    dataid = re.search(r"dataid:\s*'([^']+)'", b).group(1)
    title_raw = re.search(r"title:\s*'([^']*)'", b).group(1)
    title = title_raw.replace("\\/", "/").encode("raw_unicode_escape").decode("unicode_escape")
    esp = re.search(r"espam:\s*'([^']*)'", b)
    espam = esp.group(1) if esp else ""
    print(f"대상 글: {dataid} / {title}")
    print(f"espam: {espam[:30]}{'...' if len(espam) > 30 else ''} (길이 {len(espam)})\n")
    tkey = normalize_text(title)[:6]

    candidates = [
        ("모바일", MOBILE_HEADERS, f"https://m.cafe.daum.net/meetpeople/HoUW/{dataid}"),
        ("모바일+PC UA", HEADERS, f"https://m.cafe.daum.net/meetpeople/HoUW/{dataid}"),
        ("bbs_read 전체파라미터", HEADERS,
         f"https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW&datanum={dataid}&page=1&prev_page=0&firstbbsdepth=&lastbbsdepth=&contentval=&listnum=20"),
        ("bbs_read+espam", HEADERS,
         f"https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW&datanum={dataid}&page=1&prev_page=0&firstbbsdepth=&lastbbsdepth=&contentval=&listnum=20&espam={espam}"),
        ("bbs_read 최소+espam", HEADERS,
         f"https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW&datanum={dataid}&espam={espam}"),
    ]

    for name, hdrs, url in candidates:
        time.sleep(2.5)
        try:
            r = requests.get(url, headers=hdrs, cookies=DAUM_COOKIES, timeout=15)
            r.encoding = "utf-8"
            text = html_to_text(r.text)
            found = "✅ 제목 발견" if tkey in normalize_text(text) else "❌ 제목 없음"
            login = " [로그인페이지]" if "logins.daum.net" in r.url or "로그인이 필요" in r.text else ""
            print(f"[{name}] {found}{login}")
            print(f"  상태 {r.status_code} / HTML {len(r.text)}자 / 텍스트 {len(text)}자")
            print(f"  최종주소: {r.url[:100]}")
            print(f"  텍스트 앞부분: {text[:180]}")
            print()
        except Exception as e:
            print(f"[{name}] 오류: {e}\n")

    print("위 출력 전체를 Claude에게 붙여넣어 주세요.")


if __name__ == "__main__":
    main()