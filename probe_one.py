# -*- coding: utf-8 -*-
"""모바일 본문 단건 확인. 사용: python probe_one.py [글번호]"""
import re, sys, html as H
import requests
from monitor import DAUM_COOKIES

MOBILE = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
          "Referer": "https://m.cafe.daum.net/meetpeople/HoUW",
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Language": "ko-KR,ko;q=0.9"}
PC = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
LIST_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"

def main():
    if len(sys.argv) > 1:
        dataid = sys.argv[1]
    else:
        r = requests.get(LIST_URL, headers=PC, cookies=DAUM_COOKIES, timeout=15)
        r.encoding = "utf-8"
        ids = [int(x) for x in re.findall(r"dataid:\s*'(\d+)'", r.text)]
        dataid = str(max(ids))
    url = f"https://m.cafe.daum.net/meetpeople/HoUW/{dataid}"
    print(f"글 {dataid}\nURL: {url}\n")
    r = requests.get(url, headers=MOBILE, cookies=DAUM_COOKIES, timeout=15)
    r.encoding = "utf-8"
    h = r.text
    print(f"상태 {r.status_code} / {len(h)}자")
    guest = "손님" in h[:20000] or "정회원 이상" in h
    labels = [lb for lb in ("품","브랜드","업체명","연락처","담당자","수량","등급") if lb in h]
    print(f"손님: {'❌막힘' if guest else '✅정상'} / 라벨: {labels}")

    # 본문 영역 추출 (품목~연락처)
    h2 = re.sub(r'<br\s*/?>', '\n', h)
    m = re.search(r'(품[^<\n]{0,3}[목명][^<]*?[:：].{0,600}?연락처[^<\n]*?[:：][^<\n]*)', h2, re.DOTALL)
    if m:
        txt = H.unescape(re.sub(r'<[^>]+>', ' ', m.group(1)))
        txt = re.sub(r'[ \t\u00a0]+', ' ', txt)
        print("\n=== 본문 발췌 ===")
        for line in txt.split('\n'):
            if line.strip():
                print(" ", line.strip()[:80])
    else:
        idx = h.find("연락처")
        print(f"\n본문 라벨 못 찾음. '연락처' 위치: {idx}")
        if idx > 0:
            seg = H.unescape(re.sub(r'<[^>]+>', ' ', h[max(0,idx-200):idx+100]))
            print("  주변:", re.sub(r'\s+', ' ', seg))

if __name__ == "__main__":
    main()