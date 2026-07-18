# -*- coding: utf-8 -*-
"""
미스매칭 자가 점검 (audit)
- 게시글 제목에서 '사전에 없는 단어'를 찾아 보고
  (미스매칭의 주원인 = 미등록 브랜드/등급/원산지 표현)
- 최근 매칭 결과 중 미등록 단어가 포함된 건 → 검토 필요 목록

사용법: python audit_matches.py
출력을 Claude에게 붙여넣으면 사전에 일괄 등록해드립니다.
"""

import os
import re
from collections import Counter, defaultdict

import pandas as pd

from monitor import (
    BRAND_ALIASES, ORIGIN_ALIASES, KNOWN_GRADE_CODES, GRADE_ALIASES,
    QUALIFIERS_REQUIRE_MENTION, DONE_WORDS, GOOGLE_SHEET_URL, normalize_text,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 게시글에 흔한 일반 단어 (브랜드/등급이 아님)
STOPWORDS = set("""
구매 구매합니다 구입 구입합니다 삽니다 구합니다 구해요 구매요 매입 삽니다
판매 판매합니다 판매중 팝니다 팔아요 팔며 급처 급처분 처분 처분합니다 정리 정리합니다
문의 문의주세요 연락 연락주세요 연락처 부탁 부탁드립니다 주세요 합니다 해요 드립니다
냉동 냉장 박스 진공 개별 수입 국내 국산 사진 스펙 가격 단가 시세 견적
톤 키로 킬로 팔레트 파렛트 대량 소량 직거래 상차 하차 창고 도착 입고 출고
유통기한 임박 신선 최상 최고 저렴 특가 할인 이벤트 한정 재고 물량 수량
오늘 내일 금일 명일 이번주 다음주 월 화 수 목 금 토 일 부터 까지 남았습니다
있습니다 있어요 없습니다 필요 필요합니다 원합니다 원해요 찾습니다 찾아요
전국 서울 경기 인천 부산 대구 광주 대전 울산 지역 배송 배달 퀵 화물
전화 카톡 톡 문자 댓글 쪽지 클릭 링크 확인 참고 사장님 대표님 담당자
""".split())

# 품목 꼬리말 (제목에서 품목 뒤에 붙는 말)
COMMON_SUFFIX = {"팝니다", "삽니다", "합니다", "해요", "드려요", "있어요"}

# 서술/수식어 추가 (감사에서 확인된 비브랜드 단어)
STOPWORDS |= set("""
주식회사 무관 브랜드무관 수입소 수입돼지 등급 와규 듀록 이베리코 세보 셀렉타 저렴하게
사진첨부 판매중입니다 곡물 목초 언그레이드 스펙사진참고 스펙사진첨부 스펙사진 첨부 임박분
저가 완료 마감 짜투리 자투리 파지 오소리감투 돈위 트리밍 반진공 암소 거세 정육 한우 육우
LA KG CL EX UN AAA AA 케나다 네델란드 BEEF 비프 돈연골 경인냉장 카멜무역 TAR PRE 롱목살
""".split())


def load_sheet_vocab():
    """시트에서 품목/브랜드 로드."""
    items, brands = set(), set()
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        if "품목" in df.columns:
            items = {str(x).strip() for x in df["품목"].dropna().unique()}
        bcol = next((c for c in ["브랜드", "브랜드명", "BRAND"] if c in df.columns), None)
        if bcol:
            brands = {str(x).strip() for x in df[bcol].dropna().unique()}
        print(f"[사전] 품목 {len(items)}개 / 브랜드 {len(brands)}개 로드")
    except Exception as e:
        print(f"[사전] 시트 로드 실패: {e} — 내장 사전만 사용")
    return items, brands


def build_known_set(items, brands):
    """알려진 모든 어휘의 정규화 집합."""
    known = set()
    for x in items | brands:
        known.add(normalize_text(x))
        # 브랜드 '팜랜드(미국)' → 팜랜드 도 등록
        base = re.sub(r"\([^)]*\)", "", str(x)).strip()
        if base:
            known.add(normalize_text(base))
    for k, v in BRAND_ALIASES.items():
        known.add(normalize_text(k))
        known.add(normalize_text(v))
    for k, vs in ORIGIN_ALIASES.items():
        known.add(normalize_text(k))
        known.add(normalize_text(k) + "산")
        for v in vs:
            known.add(normalize_text(v))
            known.add(normalize_text(v) + "산")
    for g in KNOWN_GRADE_CODES:
        known.add(normalize_text(g))
    for k, vs in GRADE_ALIASES.items():
        known.add(normalize_text(k))
        for v in vs:
            known.add(normalize_text(v))
    for k, vs in QUALIFIERS_REQUIRE_MENTION.items():
        known.add(normalize_text(k))
        for v in vs:
            known.add(normalize_text(v))
    known |= {normalize_text(w) for w in DONE_WORDS}
    known |= {normalize_text(w) for w in STOPWORDS}
    return known


def tokenize(title):
    """제목 → 후보 토큰들 (한글 덩어리, 영문+숫자 코드)."""
    t = str(title)
    toks = re.findall(r"[가-힣]{2,}|\d{0,3}[A-Za-z][A-Za-z0-9]{0,14}", t)
    return toks


EST_LIKE = re.compile(r"^\d{2,4}[A-Za-z]{0,2}$")
QTY_LIKE = re.compile(r"^\d+(?:톤|키로|kg|박스|팔레트)?$", re.IGNORECASE)


def unknown_tokens(title, known, item_norms):
    """제목에서 사전에 없는 토큰만."""
    out = []
    for tok in tokenize(title):
        n = normalize_text(tok)
        if not n or len(n) < 2:
            continue
        if n in known:
            continue
        if EST_LIKE.match(tok) or QTY_LIKE.match(tok):
            continue
        # 품목명을 포함한 복합어(돈목뼈구합니다)는 품목 부분 제거 후 재검사
        core = n
        for it in item_norms:
            if it and it in core:
                core = core.replace(it, "")
        if not core or core in known or len(core) < 2:
            continue
        # 꼬리말 제거
        for suf in COMMON_SUFFIX:
            sn = normalize_text(suf)
            if core.endswith(sn):
                core = core[: -len(sn)]
        if core and core not in known and len(core) >= 2:
            out.append(tok)
    return out


def main():
    items, brands = load_sheet_vocab()
    known = build_known_set(items, brands)
    item_norms = sorted({normalize_text(i) for i in items}, key=len, reverse=True)

    # ── 1) 누적 게시글에서 미등록 단어 빈도 ──
    counter = Counter()
    examples = defaultdict(list)
    total_titles = 0
    for fname in ("buy_posts.csv", "sell_posts.csv", "latest_posts.csv"):
        path = os.path.join(BASE_DIR, fname)
        if not os.path.exists(path):
            continue
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                df = pd.read_csv(path, encoding=enc, dtype=str)
                break
            except UnicodeDecodeError:
                continue
        if "제목" not in df.columns:
            continue
        for title in df["제목"].dropna().unique():
            total_titles += 1
            for tok in set(unknown_tokens(title, known, item_norms)):
                counter[tok] += 1
                if len(examples[tok]) < 2:
                    examples[tok].append(str(title)[:40])

    print(f"\n{'='*55}")
    print(f"미등록 단어 상위 (제목 {total_titles}개 스캔)")
    print(f"  → 브랜드/등급/원산지 표현이면 알려주세요. 사전에 등록하면")
    print(f"    그 단어가 낀 미스매칭이 사라집니다.")
    print(f"{'='*55}")
    for tok, cnt in counter.most_common(30):
        ex = examples[tok][0] if examples[tok] else ""
        print(f"  {cnt:4}회  {tok:14}  예: {ex}")

    # ── 2) 최근 매칭 결과 중 검토 필요 건 ──
    lp = os.path.join(BASE_DIR, "latest_posts.csv")
    flagged = []
    if os.path.exists(lp):
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                df = pd.read_csv(lp, encoding=enc, dtype=str)
                break
            except UnicodeDecodeError:
                continue
        if "제목" in df.columns:
            for title in df["제목"].dropna().unique():
                toks = sorted(set(unknown_tokens(title, known, item_norms)))
                if toks:
                    flagged.append((title, toks))

    if flagged:
        print(f"\n{'='*55}")
        print(f"검토 필요 매칭 {len(flagged)}건 (제목에 미등록 단어 포함)")
        print(f"{'='*55}")
        for title, toks in flagged[:15]:
            print(f"  ⚠️ {str(title)[:44]}")
            print(f"     미등록: {', '.join(toks)}")
        if len(flagged) > 15:
            print(f"  ... 외 {len(flagged)-15}건")
    else:
        print("\n최근 매칭 결과에 미등록 단어 없음 — 사전이 잘 갖춰졌어요 ✅")

    print("\n위 출력 전체를 Claude에게 붙여넣으면 사전에 일괄 등록해드립니다.")


if __name__ == "__main__":
    main()