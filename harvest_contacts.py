# -*- coding: utf-8 -*-
"""
연락처 수확 스크립트
- sell_posts.csv / buy_posts.csv 의 글쓴이 닉네임에서 회사·담당자·전화번호 추출
- 전화번호가 있는 것만 contacts.csv 에 추가 (기존 항목과 중복이면 건너뜀)
- 실행 전 contacts.csv 를 contacts_backup.csv 로 백업

실행: python harvest_contacts.py
"""

import os
import re
import shutil
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACTS = os.path.join(BASE_DIR, "contacts.csv")
BACKUP = os.path.join(BASE_DIR, "contacts_backup.csv")
SOURCES = [
    (os.path.join(BASE_DIR, "sell_posts.csv"), "판매글"),
    (os.path.join(BASE_DIR, "buy_posts.csv"), "구매글"),
]

PHONE = re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")
# 상호로 볼 수 있는 키워드
COMPANY_HINTS = ["(주)", "㈜", "주식회사", "통상", "푸드", "미트", "유통", "축산",
                 "상사", "물산", "프레쉬", "컴퍼니", "팜스", "인터내셔널", "무역",
                 "냉장", "냉동", "식품", "에프앤", "F&B", "FS", "농산", "수산"]
TITLES = ["사장님", "사장", "이사님", "이사", "부장님", "부장", "과장님", "과장",
          "팀장님", "팀장", "대표님", "대표", "실장님", "실장", "차장", "주임"]


def normalize_company(name):
    s = str(name)
    for token in ["(주)", "㈜", "주식회사", "(유)", "(합)", " "]:
        s = s.replace(token, "")
    return s.strip().lower()


def parse_author(nick):
    """닉네임 → (거래처, 담당자, 전화번호). 전화 없으면 None."""
    raw = str(nick).strip()
    mm = PHONE.search(raw)
    if not mm:
        return None
    phone = re.sub(r"[\s.]", "-", mm.group(0))
    rest = PHONE.sub("", raw).replace("()", "").strip(" -·,/")
    if not rest or not re.search(r"[가-힣]", rest):
        # 회사/이름 정보가 없으면 닉네임 전체를 거래처 칸에
        return (rest or raw.replace(phone, "").strip() or "미상", "", phone)

    # 직함 제거하며 담당자 후보 찾기
    company, person = rest, ""

    # '(주)' 가 이름과 붙어 있는 형태: 육팔구통상(주)현기환
    m = re.match(r"^(.*?(?:\(주\)|㈜))\s*([가-힣]{2,4})$", rest)
    if m:
        company, person = m.group(1), m.group(2)
    else:
        # 공백 분리: 마지막 토큰이 사람 이름(2~4자 한글, 상호 키워드 없음)이면 담당자로
        parts = rest.split()
        if len(parts) >= 2:
            last = parts[-1]
            for t in TITLES:
                if last.endswith(t):
                    last = last[: -len(t)]
                    break
            if re.fullmatch(r"[가-힣]{2,4}", last) and not any(h in last for h in COMPANY_HINTS):
                company, person = " ".join(parts[:-1]), last

    # 직함이 회사명 쪽에 남아 있으면 제거
    for t in TITLES:
        if person.endswith(t):
            person = person[: -len(t)]
    return (company.strip(), person.strip(), phone)


def read_csv_any(path):
    """utf-8-sig → cp949 → euc-kr 순서로 시도 (엑셀 일반 저장 대응)."""
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("all", b"", 0, 1, f"{path} 인코딩 인식 실패")


def split_company_person(text):
    """전화번호 없는 닉네임에서 회사/담당자 분리 (parse_author와 같은 규칙)."""
    rest = str(text).replace("()", "").strip(" -·,/")
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


def main():
    # 기존 연락처
    if os.path.exists(CONTACTS):
        shutil.copy(CONTACTS, BACKUP)
        existing = read_csv_any(CONTACTS).fillna("")
        print(f"[기존] contacts.csv {len(existing)}건 (백업: contacts_backup.csv)")
    else:
        existing = pd.DataFrame(columns=["거래처", "담당자", "전화번호"])
        print("[기존] contacts.csv 없음 → 새로 생성")

    known_companies = set(existing["거래처"].astype(str).apply(normalize_company)) if not existing.empty else set()
    known_phones = set(re.sub(r"\D", "", p) for p in existing.get("전화번호", pd.Series(dtype=str)).astype(str))

    # 게시판에서 수확: 닉네임 + 글 제목의 전화번호 + 본문 추출 정보(enrich)
    author_phones = {}     # 닉네임 → 제목에서 발견한 전화번호들
    harvested_body = {}    # 본문에서 추출된 연락처 (enrich_sell.py 결과)
    authors = set()
    for path, source in SOURCES:
        if not os.path.exists(path):
            continue
        df = read_csv_any(path)
        if "글쓴이" not in df.columns:
            continue
        enriched = "연락처" in df.columns and "업체명" in df.columns
        for _, row in df.iterrows():
            nick = str(row.get("글쓴이", "")).strip()
            if not nick or nick == "nan":
                continue
            authors.add((nick, source))
            mm = PHONE.search(str(row.get("제목", "")))
            if mm:
                author_phones.setdefault(nick, set()).add(
                    re.sub(r"[\s.]", "-", mm.group(0)))
            # enrich_sell.py 가 본문에서 추출한 연락처/업체명/담당자 활용
            if enriched and str(row.get("연락처", "")).strip():
                phone0 = str(row["연락처"]).split(";")[0].strip()
                digits0 = re.sub(r"\D", "", phone0)
                if not digits0 or digits0 in known_phones:
                    continue
                comp = str(row.get("업체명", "")).strip() or split_company_person(nick)[0]
                pers = str(row.get("담당자", "")).strip() or split_company_person(nick)[1]
                if comp and normalize_company(comp) in known_companies:
                    continue
                if digits0 not in harvested_body:
                    harvested_body[digits0] = {"거래처": comp, "담당자": pers,
                                               "전화번호": phone0, "출처": f"미트피플 {source} 본문"}

    # 본문에서 나온 (정규화 회사명 → 연락처/담당자) 사전 — 후보 번호 자동 채우기용
    company_phone_from_body = {}
    for path, source in SOURCES:
        if not os.path.exists(path):
            continue
        df = read_csv_any(path)
        if "연락처" not in df.columns or "업체명" not in df.columns:
            continue
        for _, row in df.iterrows():
            comp = str(row.get("업체명", "")).strip()
            phone_raw = str(row.get("연락처", "")).strip()
            if not comp or comp == "nan" or not phone_raw or phone_raw == "nan":
                continue
            pm = PHONE.search(phone_raw)
            if not pm:
                continue
            ck = normalize_company(comp)
            if ck and ck not in company_phone_from_body:
                company_phone_from_body[ck] = {
                    "전화번호": re.sub(r"[\s.]", "-", pm.group(0)),
                    "담당자": str(row.get("담당자", "")).strip(),
                    "거래처": comp,
                }

    harvested = dict(harvested_body)    # 본문 추출분 우선 포함 → contacts.csv
    candidates = {}   # 전화 없음 + 회사형 닉네임 → contacts_candidates.csv
    auto_filled = 0
    for nick, source in authors:
        parsed = parse_author(nick)
        if parsed:
            company, person, phone = parsed
        else:
            # 닉네임엔 번호가 없음 → 그 사람 글 제목의 번호 사용
            title_phones = author_phones.get(nick)
            company, person = split_company_person(nick)
            if title_phones:
                phone = sorted(title_phones)[0]
            else:
                phone = ""

        digits = re.sub(r"\D", "", phone)
        if phone:
            if digits in known_phones:
                continue
            if company and normalize_company(company) in known_companies:
                continue
            if digits not in harvested:
                harvested[digits] = {"거래처": company, "담당자": person,
                                     "전화번호": phone, "출처": f"미트피플 {source}"}
        else:
            # 회사형 닉네임만 후보로 (한글 포함 + 상호 키워드 또는 2어절 이상)
            if not re.search(r"[가-힣]", nick):
                continue
            looks_company = any(h in nick for h in COMPANY_HINTS) or len(nick.split()) >= 2
            if not looks_company:
                continue
            if company and normalize_company(company) in known_companies:
                continue
            # 같은 회사의 본문 연락처가 있으면 번호 채워서 contacts.csv로 승격
            ck = normalize_company(company)
            body_match = company_phone_from_body.get(ck)
            if body_match:
                d = re.sub(r"\D", "", body_match["전화번호"])
                if d and d not in known_phones and d not in harvested:
                    harvested[d] = {"거래처": company, "담당자": person or body_match.get("담당자", ""),
                                    "전화번호": body_match["전화번호"], "출처": f"미트피플 {source} 본문대조"}
                    auto_filled += 1
                continue
            key = normalize_company(company) + "|" + person
            if key not in candidates:
                candidates[key] = {"거래처": company, "담당자": person,
                                   "전화번호": "", "출처": f"미트피플 {source}"}

    # 후보 파일 저장 (검토용, contacts.csv와 별도)
    if candidates:
        cand_df = pd.DataFrame(candidates.values())
        cand_path = os.path.join(BASE_DIR, "contacts_candidates.csv")
        cand_df.to_csv(cand_path, index=False, encoding="utf-8-sig")
        print(f"[후보] 전화번호 없는 회사형 닉네임 {len(cand_df)}건 → contacts_candidates.csv")
        print("       (검토 후 번호를 채워 contacts.csv에 붙여넣으세요)")
    if auto_filled:
        print(f"[자동채움] 본문 대조로 후보 {auto_filled}건에 번호를 채워 contacts.csv로 승격")

    if not harvested:
        print("추가할 새 연락처가 없습니다. (전화번호 포함 닉네임 기준)")
        return

    new_df = pd.DataFrame(harvested.values())
    print(f"\n[수확] 새 연락처 {len(new_df)}건:")
    for _, r in new_df.head(20).iterrows():
        print(f"  - {r['거래처']} / {r['담당자'] or '-'} / {r['전화번호']}  ({r['출처']})")
    if len(new_df) > 20:
        print(f"  ... 외 {len(new_df) - 20}건")

    merged = pd.concat([existing, new_df], ignore_index=True)
    merged.to_csv(CONTACTS, index=False, encoding="utf-8-sig")
    print(f"\n✅ contacts.csv 저장 완료: 총 {len(merged)}건")
    print("   (monitor.py는 다음 확인 주기에 자동 반영, 이상하면 contacts_backup.csv로 복구)")


if __name__ == "__main__":
    main()