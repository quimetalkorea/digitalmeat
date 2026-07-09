# -*- coding: utf-8 -*-
"""
다음 카페 쿠키 일괄 갱신 도우미
- 브라우저의 Cookie 헤더 전체를 붙여넣으면 monitor.py / sales_monitor.py 에 자동 반영
- 반영 후 실제로 로그인 상태인지, 판매글 본문이 열리는지까지 검증

사용법:
  1. 크롬에서 미트피플 접속 (로그인 상태)
  2. F12 → Network 탭 → 판매게시판에서 아무 글이나 클릭
  3. 목록에서 cafe.daum.net 요청 하나 클릭 → Headers → Request Headers
  4. 'cookie:' 항목 우클릭 → Copy value (전체 복사)
  5. python update_cookies.py 실행 → 붙여넣기 (cmd에서는 마우스 우클릭이 붙여넣기)
"""

import re

import requests

TARGET_FILES = ["monitor.py", "sales_monitor.py"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cafe.daum.net/meetpeople",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def parse_cookie_header(line):
    line = line.strip()
    if line.lower().startswith("cookie:"):
        line = line.split(":", 1)[1]
    cookies = {}
    for part in line.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                cookies[k] = v
    return cookies


def write_cookies(cookies):
    body_lines = "".join(f'    "{k}": "{v}",\n' for k, v in cookies.items())
    new_block = "DAUM_COOKIES = {\n" + body_lines + "}"
    pattern = re.compile(r"DAUM_COOKIES\s*=\s*\{.*?\n\}", re.DOTALL)
    for fname in TARGET_FILES:
        try:
            src = open(fname, encoding="utf-8").read()
        except FileNotFoundError:
            print(f"  ⚠️ {fname} 없음 → 건너뜀")
            continue
        if not pattern.search(src):
            print(f"  ⚠️ {fname} 에서 DAUM_COOKIES 블록을 못 찾음 → 건너뜀")
            continue
        src = pattern.sub(new_block, src, count=1)
        open(fname, "w", encoding="utf-8").write(src)
        print(f"  ✅ {fname} 쿠키 {len(cookies)}개 반영")


def verify(cookies):
    print("\n[검증 1] 로그인 상태 확인 중...")
    list_url = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"
    r = requests.get(list_url, headers=HEADERS, cookies=cookies, timeout=15)
    r.encoding = "utf-8"
    block = re.search(r"articles\.push\(\{(.*?)\}\)", r.text, re.DOTALL)
    if not block:
        print("  ❌ 게시판 목록도 안 열림 — 쿠키가 아예 잘못됐을 수 있어요")
        return
    dataid = re.search(r"dataid:\s*'([^']+)'", block.group(1)).group(1)
    title_raw = re.search(r"title:\s*'([^']*)'", block.group(1)).group(1)
    title = title_raw.replace("\\/", "/").encode("raw_unicode_escape").decode("unicode_escape")
    print(f"  목록 정상 (최신 글: {title[:30]})")

    print("[검증 2] 판매글 본문 열림 확인 중...")
    read_url = (f"https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW"
                f"&datanum={dataid}&page=1&prev_page=0&firstbbsdepth=&lastbbsdepth=&contentval=&listnum=20")
    r2 = requests.get(read_url, headers=HEADERS, cookies=cookies, timeout=15)
    r2.encoding = "utf-8"
    h = r2.text
    logged_in = "로그아웃" in h
    tkey = re.sub(r"\s+", "", title)[:6]
    body_open = tkey and tkey in re.sub(r"\s+", "", h)
    # 모바일 본문도 확인 (enrich가 모바일을 우선 시도)
    m_hdrs = {**HEADERS, "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"}
    r3 = requests.get(f"https://m.cafe.daum.net/meetpeople/HoUW/{dataid}",
                      headers=m_hdrs, cookies=cookies, timeout=15)
    r3.encoding = "utf-8"
    mobile_open = tkey and tkey in re.sub(r"\s+", "", r3.text) and "손님" not in r3.text[:20000]
    body_open = body_open or mobile_open
    print(f"  로그인 상태: {'✅ 로그인됨' if logged_in else '❌ 손님 (쿠키 부족/만료)'}")
    print(f"  본문 접근:   PC {'✅' if (tkey in re.sub(r'\\s+', '', h)) else '❌'} / 모바일 {'✅' if mobile_open else '❌'}")
    if logged_in and body_open:
        print("\n🎉 성공! 이제 패널에서 [본문 수집]을 다시 실행하세요.")
    elif logged_in and not body_open:
        print("\n로그인은 됐는데 본문이 안 열려요 — 카페 등급 제한이거나 페이지 구조 문제입니다.")
        print("이 출력을 Claude에게 붙여넣어 주세요.")
    else:
        print("\n여전히 손님 상태예요. 확인할 것:")
        print("  - 크롬 시크릿 창이 아닌, 실제 로그인된 창에서 복사했는지")
        print("  - Network 탭의 요청이 cafe.daum.net 도메인인지")
        print("  - Copy value로 쿠키 '전체'가 복사됐는지 (수천 자여야 정상)")


def main():
    print("=" * 55)
    print("다음 카페 쿠키 일괄 갱신")
    print("=" * 55)
    print("크롬 F12 → Network → 카페 글 클릭 → cafe.daum.net 요청 선택")
    print("→ Request Headers → cookie 우클릭 → Copy value\n")
    cookies = {}
    for attempt in range(3):
        line = input("쿠키 전체를 붙여넣으세요 (cmd에서는 마우스 우클릭=붙여넣기): ").strip()
        cookies = parse_cookie_header(line)
        if cookies:
            break
        print("  입력이 비었거나 형식이 달라요. 다시 붙여넣어 주세요. ('이름=값; 이름=값' 형태)")
    if not cookies:
        return
    print(f"\n인식된 쿠키 {len(cookies)}개: {', '.join(list(cookies.keys())[:12])}{' ...' if len(cookies) > 12 else ''}")
    if "HTS" not in cookies and "PROF" not in cookies:
        print("⚠️ HTS/PROF가 없어요 — daum.net 도메인 요청에서 복사했는지 확인하세요. 일단 진행합니다.")
    write_cookies(cookies)
    verify(cookies)


if __name__ == "__main__":
    main()