# -*- coding: utf-8 -*-
"""모바일 본문 주소 단일 정밀 테스트: https://m.cafe.daum.net/meetpeople/HoUW/{id}"""
import re
import requests
from monitor import DAUM_COOKIES

LIST_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"
PC = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Referer": "https://cafe.daum.net/meetpeople"}
MOBILE = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
          "Referer": "https://m.cafe.daum.net/meetpeople/HoUW",
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Language": "ko-KR,ko;q=0.9"}

def main():
    # 최신 글번호 하나 확보
    r = requests.get(LIST_URL, headers=PC, cookies=DAUM_COOKIES, timeout=15)
    r.encoding = "utf-8"
    m = re.search(r"dataid:\s*'(\d+)'", r.text)
    if not m:
        print("목록 파싱 실패 — 쿠키 확인 필요")
        return
    dataid = m.group(1)
    url = f"https://m.cafe.daum.net/meetpeople/HoUW/{dataid}"
    print(f"테스트 글: {dataid}\nURL: {url}\n")

    rr = requests.get(url, headers=MOBILE, cookies=DAUM_COOKIES, timeout=15)
    rr.encoding = "utf-8"
    h = rr.text
    print(f"상태 {rr.status_code} / {len(h)}자")

    guest = "손님" in h[:20000] or "정회원 이상" in h
    phones = re.findall(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}", h)
    has_label = "브랜드" in h and "업체명" in h
    print(f"손님 페이지: {'❌ 그렇다(접근 막힘)' if guest else '✅ 아니다(정상 접근)'}")
    print(f"양식 라벨(브랜드/업체명): {'✅ 있음' if has_label else '❌ 없음'}")
    print(f"전화번호: {phones[:3] if phones else '❌ 없음'}")

    if has_label or phones:
        print("\n🎉 본문 접근 성공! enrich_sell.py를 이 방식으로 확정합니다.")
        # 본문 텍스트 앞부분 표시
        text = re.sub(r"<script.*?</script>", " ", h, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        idx = text.find("브랜드")
        if idx >= 0:
            print("본문 발췌:", text[idx:idx+150])
    else:
        print("\n아직 본문이 안 보여요.")
        print(f"앞부분: {re.sub(chr(60)+'[^'+chr(62)+']*'+chr(62), ' ', h)[:300]}")

if __name__ == "__main__":
    main()