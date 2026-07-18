# -*- coding: utf-8 -*-
"""PC 본문 주소 정밀 테스트 (bbs_read). 최신 글번호를 목록에서 확보해 사용."""
import re
import requests
from monitor import DAUM_COOKIES

LIST_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"
PC = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Referer": "https://cafe.daum.net/meetpeople",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "ko-KR,ko;q=0.9"}

def main():
    r = requests.get(LIST_URL, headers=PC, cookies=DAUM_COOKIES, timeout=15)
    r.encoding = "utf-8"
    # 가장 큰 글번호(최신) 선택 — 목록 정렬이 이상해도 최신 글로 테스트
    ids = [int(x) for x in re.findall(r"dataid:\s*'(\d+)'", r.text)]
    if not ids:
        print("목록 파싱 실패 — 쿠키 확인")
        return
    dataid = max(ids)
    print(f"목록 글번호들: 최소 {min(ids)} ~ 최대 {max(ids)} (총 {len(ids)}개)")
    print(f"테스트 글(최신): {dataid}\n")

    urls = [
        ("bbs_read 전체파라미터",
         f"https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW&datanum={dataid}&page=1&prev_page=0&firstbbsdepth=&lastbbsdepth=&contentval=&listnum=20"),
        ("bbs_read 최소",
         f"https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW&datanum={dataid}"),
    ]
    for name, url in urls:
        rr = requests.get(url, headers=PC, cookies=DAUM_COOKIES, timeout=15)
        rr.encoding = "utf-8"
        h = rr.text
        has_label = "브랜드" in h and "업체명" in h
        phones = re.findall(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}", h)
        guest = "정회원 이상" in h or "회원님은 현재 손님" in h
        print(f"[{name}] 상태 {rr.status_code} / {len(h)}자")
        print(f"  손님: {'❌막힘' if guest else '✅정상'} / 양식: {'✅' if has_label else '❌'} / 전화: {phones[:2] if phones else '❌'}")
        if has_label:
            text = re.sub(r"<script.*?</script>", " ", h, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            idx = text.find("브랜드")
            print(f"  🎉 본문 발췌: {text[idx:idx+140]}")
            print(f"\n  → 이 방식으로 확정합니다!")
            return
    print("\n두 방식 다 본문이 안 보여요. 위 출력을 Claude에게 붙여주세요.")

if __name__ == "__main__":
    main()