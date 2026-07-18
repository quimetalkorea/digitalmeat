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

# 세션: 요청마다 쿠키를 새로 보내는 대신, 서버가 회전시키는 세션 쿠키를 자동 반영
SESSION = requests.Session()
SESSION.cookies.update(DAUM_COOKIES)

ENRICH_VERSION = "v2.1 (이름정리+최신우선)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SELL_PATH = os.path.join(BASE_DIR, "sell_posts.csv")

DELAY_MIN, DELAY_MAX = 3.0, 6.0
SAVE_EVERY = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Referer": "https://m.cafe.daum.net/meetpeople/HoUW",
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
    # 모바일 본문만 실제 내용을 반환함 (PC는 로그인돼도 껍데기만 옴 - 검증 완료)
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
    src = htmllib.unescape(src)            # &#160; → nbsp
    src = src.replace("\u00a0", " ")       # nbsp → 일반 공백
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in src.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def fetch_body(dataid, title):
    """글 본문 텍스트 가져오기. (본문, 오류) 반환.
    오류가 '손님'이면 접근권한 문제(중단 사유), 그 외는 개별 글 문제(스킵)."""
    global _working_pattern
    patterns = [_working_pattern] if _working_pattern else READ_URL_PATTERNS
    last_err = None
    for pat in patterns:
        try:
            resp = SESSION.get(pat.format(id=dataid), headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            h = resp.text
            text = html_to_text(h)
            # 양식 라벨이 본문에 있으면 성공 (품/브랜드/업체/연락처/담당/수량/등급 중 2개 이상)
            # '품 목'처럼 공백이 섞여도 잡히도록 압축 텍스트로 검사
            compact = text.replace(" ", "")
            label_hits = sum(1 for lb in ("품목", "품명", "브랜드", "업체명", "연락처", "담당자", "수량", "등급")
                             if lb in compact)
            if label_hits >= 2:
                _working_pattern = pat
                return text, None
            # 본문 라벨이 없음 → 손님 페이지인지 개별 글 문제인지 구분
            hc = h.replace(" ", "")   # 공백 제거하고 문구 검사
            is_guest = ("정회원이상" in hc or "회원님은현재손님" in hc or "손님이세요" in hc
                        or "로그인을하지" in hc or "가입후모든" in hc
                        or "login" in resp.url.lower()
                        or 13000 <= len(h) <= 14500)   # 모바일 손님 페이지 크기 시그니처
            if is_guest:
                last_err = "GUEST"   # 접근권한 문제 (쿠키 만료) — 여러 번이면 중단
            else:
                last_err = f"본문없음(응답 {len(h)}자, 라벨 {label_hits}개)"  # 삭제/구조이상 글 (스킵)
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
    "브랜드": re.compile(r"브\s*랜\s*드\s*[:：]\s*(.+)"),
    "품명": re.compile(r"품\s*목?\s*명?\s*[:：]\s*(.+)"),
    "등급": re.compile(r"등\s*급(?:\s*및\s*스펙)?\s*[:：]\s*(.+)"),
    "수량": re.compile(r"수\s*량\s*[:：]\s*(.+)"),
    "업체명": re.compile(r"업\s*체\s*명?\s*[:：]\s*(.+)"),
    "담당자": re.compile(r"담\s*당\s*자?\s*[:：]\s*(.+)"),
    "연락처": re.compile(r"(?:연\s*락\s*처|전화번호|전화|휴대폰|H\.?P)\s*[:：]\s*(.+)", re.IGNORECASE),
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


PERSON_TITLES = ["사장님","사장","이사님","이사","부장님","부장","과장님","과장",
                 "팀장님","팀장","대표님","대표","실장님","실장","차장","주임","님"]
PERSON_COMPANY_WORDS = ["주식회사","(주)","㈜","푸드","미트","유통","축산","상사","물산",
                        "프레쉬","컴퍼니","무역","식품","코퍼레이션","앤씨","티앤씨"]


def clean_person_name(raw):
    """담당자 라벨값에서 사람 이름만 추출.
    '주니푸드 주식회사 이대신' → '이대신', '유진호 이정민 김유군' → '유진호',
    '이 대신' 같이 잘못 띄운 것도 붙여서 복원."""
    s = str(raw).strip()
    if not s:
        return ""
    # 전화번호/직함 제거
    s = PHONE.sub("", s)
    # 회사성 단어가 포함된 토큰 제거
    toks = [t for t in re.split(r"\s+", s) if t]
    name_toks = []
    for t in toks:
        t2 = t
        for tt in PERSON_TITLES:
            if t2.endswith(tt):
                t2 = t2[:-len(tt)]
        if not t2:
            continue
        if any(w in t2 for w in PERSON_COMPANY_WORDS):
            continue          # 회사명 토큰은 건너뜀
        if not re.search(r"[가-힣]", t2):
            continue          # 한글 없는 토큰(영문 코드 등) 건너뜀
        name_toks.append(t2)
    if not name_toks:
        return ""
    # 한 글자짜리가 연속이면 붙임('이','대신' → '이대신'), 아니면 첫 이름
    if len(name_toks[0]) == 1 and len(name_toks) >= 2 and len(name_toks[1]) <= 3:
        cand = name_toks[0] + name_toks[1]
        if 2 <= len(cand) <= 4:
            return cand
    return name_toks[0]


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
    # 담당자 정리: 여러 명이면 첫 명, 회사/직함 잡토큰 제거, 한 글자 성만 남는 것 방지
    labeled_person = clean_person_name(labeled.get("담당자", ""))
    # 연락처: 라벨 줄에 여러 개면 모두 (010-.. / 010-.. / 010-..)
    labeled_phones = []
    if labeled.get("연락처"):
        labeled_phones = [re.sub(r"[\s.]", "-", p) for p in PHONE.findall(labeled["연락처"])]
    return {
        "브랜드": labeled.get("브랜드") or ", ".join(brands[:3]),
        "품명": labeled.get("품명") or ", ".join(found_items),
        "등급": labeled.get("등급", ""),
        "수량": labeled.get("수량", ""),
        "업체명": labeled.get("업체명") or company,
        "담당자": labeled_person or person,
        "연락처": "; ".join(labeled_phones[:3]) or label_phone or "; ".join(phones[:3]),
    }


def main():
    # E(접근불가) 표시 초기화 모드: 쿠키 만료로 억울하게 막힌 글 되살리기
    if len(sys.argv) > 1 and sys.argv[1] == "reset-e":
        df = None
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                df = pd.read_csv(SELL_PATH, encoding=enc, dtype=str)
                break
            except UnicodeDecodeError:
                continue
        df = df.fillna("")
        n = int((df["본문수집"] == "E").sum())
        df.loc[df["본문수집"] == "E", "본문수집"] = ""
        df.to_csv(SELL_PATH, index=False, encoding="utf-8-sig")
        print(f"E 표시 {n}건을 초기화했어요. 다시 수집 대상이 됩니다.")
        return

    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    print(f"enrich_sell {ENRICH_VERSION}")
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
    for col in ["브랜드", "품명", "등급", "수량", "업체명", "담당자", "연락처", "본문수집"]:
        if col not in df.columns:
            df[col] = ""

    # 최신 글부터 처리 (글번호 큰 순) — 세션이 짧으니 유효한 최신 글 우선
    df["_gnum"] = pd.to_numeric(df["글번호"], errors="coerce").fillna(0).astype("int64")
    df = df.sort_values("_gnum", ascending=False).reset_index(drop=True)
    skipped_e = int((df["본문수집"] == "E").sum())
    todo = df[~df["본문수집"].isin(["Y", "E"])]
    if skipped_e:
        print(f"[안내] 접근불가(E) 표시 글 {skipped_e}건은 건너뜀 — 되살리려면: python enrich_sell.py reset-e")
    print(f"[대상] 전체 {len(df)}건 중 미수집 {len(todo)}건 → 이번에 {min(count, len(todo))}건 처리")
    print(f"       예상 소요: 약 {int(min(count, len(todo)) * (DELAY_MIN + DELAY_MAX) / 2 / 60) + 1}분")
    if todo.empty:
        print("모든 글의 본문을 이미 수집했습니다.")
        return

    items, sheet_brands = load_vocab()

    # 시작 전 쿠키 생존 점검: 최신 글 하나를 열어봄
    try:
        first_id = str(todo.iloc[0]["글번호"])
        _, err0 = fetch_body(first_id, str(todo.iloc[0]["제목"]))
        if err0 == "GUEST":
            print("\n⛔ 시작 점검: 쿠키(로그인 세션)가 이미 만료 상태예요.")
            print("→ 크롬에서 판매글 본문 연 상태로 cookie Copy value → python update_cookies.py")
            print("  갱신 직후 바로 이 명령을 다시 실행하세요 (세션은 짧게는 수십 분이면 회전됩니다)")
            return
    except Exception:
        pass

    done = 0
    consecutive_guest = 0   # 손님(권한) 오류 연속 횟수
    guest_indices = []      # 연속 손님으로 E 표시된 행 (중단 시 되돌림용)
    for idx in todo.index[:count]:
        dataid = str(df.at[idx, "글번호"])
        title = str(df.at[idx, "제목"])
        body, err = fetch_body(dataid, title)
        if err and body is None:
            if err == "GUEST":
                consecutive_guest += 1
                guest_indices.append(idx)
                if consecutive_guest >= 5:
                    # 연속 손님 = 쿠키 만료 가능성 → 이번 연속분 E 표시를 되돌림 (억울한 영구 제외 방지)
                    for gi in guest_indices[-5:]:
                        df.at[gi, "본문수집"] = ""
                    print(f"\n⛔ 중단: 손님 페이지 연속 5회 — 쿠키(로그인 세션)가 만료됐을 가능성이 높아요.")
                    print("→ 본문 열린 상태에서 쿠키 복사 → update_cookies.py → 같은 명령으로 재개")
                    print("   (연속 5건은 E 표시하지 않고 다시 시도 대상으로 남겨둠)")
                    break
                # 개별 글이 권한글일 수도 있으니 E 표시하고 계속
                df.at[idx, "본문수집"] = "E"
                print(f"  [{dataid}] ⚠️ 접근 불가(손님/권한글) — 건너뜀 ({consecutive_guest}/5)")
                done += 1
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                continue
            df.at[idx, "본문수집"] = "E"  # 개별 글 문제 (삭제/구조 이상) → 스킵
            print(f"  [{dataid}] ⚠️ {err}")
        else:
            consecutive_guest = 0   # 성공하면 카운터 리셋
            guest_indices = []
            info = extract_info(title, body, items, sheet_brands)
            for k, v in info.items():
                df.at[idx, k] = v
            df.at[idx, "본문수집"] = "Y"
            got = " / ".join(f"{k}:{v}" for k, v in info.items() if v)
            print(f"  [{dataid}] {title[:24]} → {got if got else '(추출 정보 없음)'}")

        done += 1
        if done % SAVE_EVERY == 0:
            df.drop(columns=["_gnum"], errors="ignore").to_csv(SELL_PATH, index=False, encoding="utf-8-sig")
            print(f"  💾 중간 저장 ({done}건 처리)")
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    df.drop(columns=["_gnum"], errors="ignore").to_csv(SELL_PATH, index=False, encoding="utf-8-sig")
    remain = len(df[df["본문수집"] == ""])
    print(f"\n완료: 이번에 {done}건 처리 / 남은 미수집 {remain}건")
    print("다음 단계: python harvest_contacts.py  ← 본문 연락처를 contacts.csv 로")


if __name__ == "__main__":
    main()