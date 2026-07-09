# -*- coding: utf-8 -*-
"""
판매글 본문 수집 스크립트 (enrich)
- sell_posts.csv 의 각 글을 열어 본문에서 정보 추출:
  브랜드 / 품명 / 업체명 / 담당자 / 연락처
- 결과를 sell_posts.csv 에 새 열로 저장 (본문수집=Y 표시로 이어받기)
- 요청 간 3~6초 대기, 로그인 페이지 감지 시 중단

사용법:
    python enrich_sell.py 100     ← 이번에 100건 처리 (다음 실행 시 이어서)
수집 후:
    python harvest_contacts.py    ← 본문 연락처까지 contacts.csv 로
"""

import html as htmllib
import os
import random
import re
import sys
import time

import pandas as pd
import requests

from monitor import DAUM_COOKIES, GOOGLE_SHEET_URL, BRAND_ALIASES, normalize_text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SELL_PATH = os.path.join(BASE_DIR, "sell_posts.csv")

DELAY_MIN, DELAY_MAX = 3.0, 6.0
SAVE_EVERY = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cafe.daum.net/meetpeople",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

PHONE = re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")
COMPANY_HINTS = ["(주)", "㈜", "주식회사", "통상", "푸드", "미트", "유통", "축산",
                 "상사", "물산", "프레쉬", "컴퍼니", "팜스", "인터내셔널", "무역", "식품"]
TITLES = ["사장님", "사장", "이사님", "이사", "부장님", "부장", "과장님", "과장",
          "팀장님", "팀장", "대표님", "대표", "실장님", "실장", "차장", "주임"]

# 글 본문 URL 패턴 후보 (첫 글에서 작동하는 것을 자동 선택)
# 모바일 웹이 보안 토큰 없이 열리는 경우가 많아 우선 시도
READ_URL_PATTERNS = [
    # PC 본문이 가장 온전함 (진단 결과: 텍스트 710자, espam 불필요)
    "https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW&datanum={id}&page=1&prev_page=0&firstbbsdepth=&lastbbsdepth=&contentval=&listnum=20",
    "https://m.cafe.daum.net/meetpeople/HoUW/{id}",
    "https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoUW&datanum={id}",
]
_working_pattern = None


def html_to_text(src):
    src = re.sub(r"<script.*?</script>", " ", src, flags=re.DOTALL | re.IGNORECASE)
    src = re.sub(r"<style.*?</style>", " ", src, flags=re.DOTALL | re.IGNORECASE)
    src = re.sub(r"<br\s*/?>", "\n", src, flags=re.IGNORECASE)
    src = re.sub(r"</(p|div|tr|li)>", "\n", src, flags=re.IGNORECASE)
    src = re.sub(r"<[^>]+>", " ", src)
    src = htmllib.unescape(src)
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in src.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def fetch_body(dataid, title):
    """글 본문 텍스트 가져오기. (본문, 오류) 반환."""
    global _working_pattern
    patterns = [_working_pattern] if _working_pattern else READ_URL_PATTERNS
    tkey = normalize_text(title)[:6]
    last_err = None
    for pat in patterns:
        try:
            resp = requests.get(pat.format(id=dataid), headers=HEADERS,
                                cookies=DAUM_COOKIES, timeout=15)
            resp.encoding = "utf-8"
            h = resp.text
            if "logins.daum.net" in h and "articles.push" not in h and len(h) < 30000:
                last_err = "로그인 페이지로 이동됨 (쿠키 만료 또는 권한 부족)"
                continue
            text = html_to_text(h)
            # 제목 일부가 본문 페이지에 있으면 성공으로 판단
            if tkey and tkey in normalize_text(text):
                _working_pattern = pat
                return text, None
            last_err = f"본문 확인 실패 (패턴: {pat.split('?')[0].split('/')[-1]}, 응답 {len(h)}자)"
        except Exception as e:
            last_err = str(e)
    return None, last_err


def split_company_person(text):
    rest = str(text).replace("()", "").strip(" -·,/|")
    company, person = rest, ""
    m = re.match(r"^(.*?(?:\(주\)|㈜))\s*([가-힣]{2,4})$", rest)
    if m:
        company, person = m.group(1), m.group(2)
    else:
        parts = rest.split()
        # 끝에 붙은 직함 단어 제거 ('용푸드 조봉구 부장' → '용푸드 조봉구')
        while len(parts) >= 2 and parts[-1] in TITLES:
            parts.pop()
        if len(parts) >= 2:
            last = parts[-1]
            for t in TITLES:
                if last.endswith(t):
                    last = last[: -len(t)]
                    break
            if re.fullmatch(r"[가-힣]{2,4}", last) and not any(h in last for h in COMPANY_HINTS):
                company, person = " ".join(parts[:-1]), last
    for t in TITLES:
        if person.endswith(t):
            person = person[: -len(t)]
    return company.strip(), person.strip()


def load_vocab():
    """시세 시트에서 품목 목록 + 브랜드 사전(한→영 별칭 + 시트 브랜드)."""
    items, sheet_brands = [], set()
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        if "품목" in df.columns:
            items = df["품목"].dropna().astype(str).str.strip().unique().tolist()
            items.sort(key=lambda x: len(normalize_text(x)), reverse=True)
        bcol = next((c for c in ["브랜드", "브랜드명", "BRAND"] if c in df.columns), None)
        if bcol:
            for b in df[bcol].dropna().astype(str).str.strip().unique():
                if len(normalize_text(b)) >= 3:
                    sheet_brands.add(b.strip())
        print(f"[사전] 품목 {len(items)}개 / 브랜드 {len(sheet_brands)}개 로드")
    except Exception as e:
        print(f"[사전] 로드 실패: {e}")
    return items, sheet_brands


LABEL_PATTERNS = {
    "브랜드": re.compile(r"브랜드\s*[:：]\s*(.+)"),
    "품명": re.compile(r"품\s*명\s*[:：]\s*(.+)"),
    "수량": re.compile(r"수\s*량\s*[:：]\s*(.+)"),
    "업체명": re.compile(r"업체\s*명?\s*[:：]\s*(.+)"),
    "담당자": re.compile(r"담당자?\s*[:：]\s*(.+)"),
    "연락처": re.compile(r"(?:연락처|전화번호|전화|휴대폰|H\.?P)\s*[:：]\s*(.+)", re.IGNORECASE),
}


def extract_labeled(body):
    """판매게시판 양식(브랜드 : / 품명 : / 업체명 : ...)에서 라벨 그대로 추출."""
    out = {}
    for ln in body.splitlines():
        for key, pat in LABEL_PATTERNS.items():
            if key in out:
                continue
            mm = pat.search(ln)
            if mm:
                val = mm.group(1).strip(" .,~-·|")
                if val and len(val) <= 60:
                    out[key] = val
    return out


def extract_info(title, body, items, sheet_brands):
    """제목+본문에서 브랜드/품명/업체명/담당자/연락처 추출.
    본문에 양식 라벨이 있으면 그것을 우선 사용."""
    labeled = extract_labeled(body)
    combined = f"{title}\n{body}"
    c_norm = normalize_text(combined)

    # 브랜드: 별칭 사전(한글 호칭) + 시트 브랜드 직접 표기
    brands = []
    for alias, brand in BRAND_ALIASES.items():
        if alias in combined and brand not in brands:
            brands.append(brand)
    for b in sheet_brands:
        if normalize_text(b) in c_norm and b not in brands:
            brands.append(b)

    # 품명: 시트 품목 키워드 (긴 이름 우선, 최대 3개)
    found_items = []
    for it in items:
        if normalize_text(it) in c_norm:
            if not any(normalize_text(it) in normalize_text(f) for f in found_items):
                found_items.append(it)
        if len(found_items) >= 3:
            break

    # 연락처 + 서명 줄에서 업체명/담당자
    phones, company, person = [], "", ""
    for ln in body.splitlines():
        for mm in PHONE.finditer(ln):
            ph = re.sub(r"[\s.]", "-", mm.group(0))
            if ph not in phones:
                phones.append(ph)
            if not company:
                sig = PHONE.sub("", ln).strip(" -·,/|:")
                if re.search(r"[가-힣]", sig):
                    company, person = split_company_person(sig)

    # 양식 라벨 값이 있으면 우선, 없으면 사전/서명 추출값 사용
    label_phone = ""
    if labeled.get("연락처"):
        pm = PHONE.search(labeled["연락처"])
        if pm:
            label_phone = re.sub(r"[\s.]", "-", pm.group(0))
    return {
        "브랜드": labeled.get("브랜드") or ", ".join(brands[:3]),
        "품명": labeled.get("품명") or ", ".join(found_items),
        "수량": labeled.get("수량", ""),
        "업체명": labeled.get("업체명") or company,
        "담당자": labeled.get("담당자") or person,
        "연락처": label_phone or "; ".join(phones[:3]),
    }


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    if not os.path.exists(SELL_PATH):
        print("sell_posts.csv 가 없습니다. backfill_sell.py → merge_sell.py 먼저 실행하세요.")
        return
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            df = pd.read_csv(SELL_PATH, encoding=enc, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    df = df.fillna("")
    for col in ["브랜드", "품명", "수량", "업체명", "담당자", "연락처", "본문수집"]:
        if col not in df.columns:
            df[col] = ""

    todo = df[df["본문수집"] != "Y"]
    print(f"[대상] 전체 {len(df)}건 중 미수집 {len(todo)}건 → 이번에 {min(count, len(todo))}건 처리")
    print(f"       예상 소요: 약 {int(min(count, len(todo)) * (DELAY_MIN + DELAY_MAX) / 2 / 60) + 1}분")
    if todo.empty:
        print("모든 글의 본문을 이미 수집했습니다.")
        return

    items, sheet_brands = load_vocab()

    done = 0
    for idx in todo.index[:count]:
        dataid = str(df.at[idx, "글번호"])
        title = str(df.at[idx, "제목"])
        body, err = fetch_body(dataid, title)
        if err and body is None:
            if "로그인" in str(err):
                print(f"\n⛔ 중단: {err}")
                print("→ 쿠키 갱신 후 같은 명령으로 이어서 실행하세요.")
                break
            df.at[idx, "본문수집"] = "E"  # 오류 표시 (재시도 대상 아님)
            print(f"  [{dataid}] ⚠️ {err}")
        else:
            info = extract_info(title, body, items, sheet_brands)
            for k, v in info.items():
                df.at[idx, k] = v
            df.at[idx, "본문수집"] = "Y"
            got = " / ".join(f"{k}:{v}" for k, v in info.items() if v)
            print(f"  [{dataid}] {title[:24]} → {got if got else '(추출 정보 없음)'}")

        done += 1
        if done % SAVE_EVERY == 0:
            df.to_csv(SELL_PATH, index=False, encoding="utf-8-sig")
            print(f"  💾 중간 저장 ({done}건 처리)")
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    df.to_csv(SELL_PATH, index=False, encoding="utf-8-sig")
    remain = len(df[df["본문수집"] == ""])
    print(f"\n완료: 이번에 {done}건 처리 / 남은 미수집 {remain}건")
    print("다음 단계: python harvest_contacts.py  ← 본문 연락처를 contacts.csv 로")


if __name__ == "__main__":
    main()