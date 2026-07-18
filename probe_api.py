# -*- coding: utf-8 -*-
"""
다음 카페 bottomarticles API 진단 (정확한 주소 확보 버전)
- 목록에서 글별 dataid + bbsdepth를 얻어 bottomarticles API 호출
- 응답이 JSON인지, 본문이 어느 필드에 있는지 확인

사용법: python probe_api.py  →  출력 전체를 Claude에게
"""

import json
import re
import time

import requests

from monitor import DAUM_COOKIES

LIST_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Referer": "https://m.cafe.daum.net/meetpeople/HoUW",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


def get_samples(n=3):
    """목록에서 앞 n개 글의 dataid + bbsdepth + title 추출."""
    # 목록은 PC User-Agent로 (모니터/백필과 동일 방식)
    pc_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://cafe.daum.net/meetpeople",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    r = requests.get(LIST_URL, headers=pc_headers, cookies=DAUM_COOKIES, timeout=15)
    r.encoding = "utf-8"
    html = r.text
    if "articles.push" not in html:
        print(f"[진단] 목록에 articles.push 없음. 상태 {r.status_code} / {len(html)}자")
        if "logins.daum.net" in html or "로그인" in html[:5000]:
            print("  → 로그인 페이지로 이동됨. update_cookies.py로 쿠키 재갱신 필요")
        else:
            print(f"  → 앞부분: {re.sub(chr(92)+'s+', ' ', html)[:200]}")
        return []
    samples = []
    for block in re.findall(r"articles\.push\(\{(.*?)\}\)", r.text, re.DOTALL)[:n]:
        def field(name, b=block):
            mm = re.search(name + r":\s*'([^']*)'", b)
            return mm.group(1) if mm else ""
        title_raw = field("title")
        title = title_raw.replace("\\/", "/").encode("raw_unicode_escape").decode("unicode_escape")
        samples.append({
            "dataid": field("dataid"),
            "bbsdepth": field("bbsdepth"),
            "title": title,
        })
    return samples


def probe(dataid, bbsdepth, title):
    # 스크린샷에서 확인된 실제 주소
    url = (f"https://m.cafe.daum.net/meetpeople/HoUW/{dataid}/bottomarticles"
           f"?grpid=Mbmh&boardType=&bbsDepth={bbsdepth}&svc=&q=&searchCtx=")
    print(f"\n{'='*55}")
    print(f"글 {dataid}: {title[:30]}")
    print(f"URL: {url[:110]}")
    try:
        r = requests.get(url, headers=HEADERS, cookies=DAUM_COOKIES, timeout=15)
        r.encoding = "utf-8"
        body = r.text
        print(f"상태 {r.status_code} / {len(body)}자 / {r.headers.get('Content-Type','?')[:40]}")
        try:
            data = json.loads(body)
            # 리스트/딕셔너리 모두 처리
            if isinstance(data, dict):
                print(f"✅ JSON dict! 키: {list(data.keys())}")
            elif isinstance(data, list):
                print(f"✅ JSON list! 길이 {len(data)}")
                for i, item in enumerate(data[:5]):
                    if isinstance(item, dict):
                        print(f"   [{i}] 키: {list(item.keys())}")
                    else:
                        print(f"   [{i}] {str(item)[:60]}")
            flat = json.dumps(data, ensure_ascii=False)
            # 본문/연락처가 있을 만한 필드 전부 탐색
            found_fields = set()
            for key in ("content", "cont", "message", "body", "text", "articleContent",
                        "plainContent", "contents", "articleText", "desc", "description"):
                mm = re.search(r'"' + key + r'"\s*:\s*"((?:[^"\\]|\\.){5,})"', flat)
                if mm and key not in found_fields:
                    found_fields.add(key)
                    try:
                        val = json.loads('"' + mm.group(1) + '"')
                    except Exception:
                        val = mm.group(1)
                    val = re.sub(r"<[^>]+>", " ", str(val))
                    val = re.sub(r"\s+", " ", val)[:120]
                    print(f"   [본문후보] '{key}': {val}")
            ph = re.findall(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}", flat)
            if ph:
                print(f"   📞 전화번호: {ph}")
            # 본문 후보를 못 찾았으면 전체 구조 덤프 (첫 글만)
            if not found_fields and dataid == FIRST_ID:
                print(f"   [전체 JSON 앞 800자]:")
                print("   " + flat[:800])
        except json.JSONDecodeError:
            snippet = re.sub(r"\s+", " ", body)[:200]
            print(f"(JSON 아님) 앞부분: {snippet}")
    except Exception as e:
        print(f"오류: {e}")


FIRST_ID = None


def main():
    global FIRST_ID
    samples = get_samples(3)
    if not samples:
        print("목록 파싱 실패 — 쿠키 확인")
        return
    print(f"샘플 {len(samples)}건 확보")
    FIRST_ID_local = samples[0]["dataid"] if samples else None
    globals()["FIRST_ID"] = FIRST_ID_local
    for s in samples:
        if s["dataid"] and s["bbsdepth"]:
            probe(s["dataid"], s["bbsdepth"], s["title"])
            time.sleep(2.5)
    print("\n\n위 출력 전체를 Claude에게 붙여넣어 주세요.")


if __name__ == "__main__":
    main()