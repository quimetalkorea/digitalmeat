"""
미트피플 판매게시판 ↔ 구매게시판 크로스 매칭 (monitor.py와 별도 운영)
- 판매게시판(HoUW) 글을 sell_posts.csv에 누적 (backfill_sell.py/merge_sell.py와 같은 파일)
- 구매게시판(HoTs) 글을 buy_posts.csv에 누적

v1.1: 원산지 오탐 수정('미국산'속 '국산'), 백필 파일 연계, 카톡 토큰 잠금, 시작 지연
- 새 구매글 ↔ 최근 판매글 / 새 판매글 ↔ 최근 구매글 양방향 매칭
- 매칭되면 소리 알림 + matched_pairs.csv 저장 + 카톡 전송

실행: python sales_monitor.py
"""

import requests
import pandas as pd
import time
import os
import re
import json
import winsound
from datetime import datetime, timedelta

# =============================================
# 설정
# =============================================

VERSION = "v1.1"

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

BUY_BOARD_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoTs"    # 구매게시판
SELL_BOARD_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"   # 판매게시판

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SALES_CSV = os.path.join(BASE_DIR, "sell_posts.csv")             # 판매글 누적 (백필과 같은 파일!)
BUY_CSV = os.path.join(BASE_DIR, "buy_posts.csv")                # 구매글 누적
PAIRS_CSV = os.path.join(BASE_DIR, "matched_pairs.csv")          # 매칭된 짝
LOG_PATH = os.path.join(BASE_DIR, "sales_monitor_log.txt")

CHECK_INTERVAL = 10 * 60      # 확인 주기 (초)
STARTUP_DELAY_SEC = 120       # 시작 지연 (monitor.py와 요청 시점 분산)
INITIAL_FULL_SCAN = True      # 시작 시 누적 구매글(최근 7일) ↔ 누적 판매글 전체를 1회 대조
MIN_PAIR_SCORE = 3            # 이 점수 미만은 알림 안 함 (브랜드/원산지/EST 중 하나는 겹쳐야 함)
MAX_PAIRS_PER_POST = 3        # 구매글 1건당 알림할 판매글 후보 최대 수

# 거래 끝난 글 제외 키워드
DONE_WORDS = ["판매완료", "구매완료", "거래완료", "완판", "마감"]
SALES_MAX_AGE_DAYS = 365      # 판매글 매칭 유효 기간 (백필 1년치 활용; 시끄러우면 30 등으로 축소)
BUY_MAX_AGE_DAYS = 7          # 구매글 유효 기간

USE_OPERATING_HOURS = False   # True면 아래 시간에만 동작
OPERATING_START = "09:00"
OPERATING_END = "17:30"

# 중개 문구 설정
SENDER_NAME = "디지털미트 서종현"
CLOSING_LINE = "연락 함 해보세요. https://open.kakao.com/o/g0Zywnmd"

# 카톡 '나에게 보내기' (monitor.py와 같은 토큰 파일 사용)
KAKAO_ENABLED = True
KAKAO_TOKEN_PATH = os.path.join(BASE_DIR, "kakao_token.json")
KAKAO_LOCK_PATH = KAKAO_TOKEN_PATH + ".lock"
KAKAO_MAX_SEND = 3

# =============================================
# 다음 카페 쿠키 (monitor.py와 동일하게 유지)
# =============================================
DAUM_COOKIES = {
    "__T_": "1",
    "__T_SECURE": "1",
    "NOTI_Mbmh_HoUW": "Y",
    "NOTI_Mbmh_HoOi": "Y",
    "HM_CU": "562UzJ5yPrq",
    "PROF": "0603012032024064024192UiQPJk7X-6w0mlxoempuua9QsdGeNIag3O1dpXj_gbkQKuZP3z7wEl2bxriNh5SdkQ00LYYSA9A1_cGNLCyhCzrwOgj61xkRhz7hDHbz3NH3TPhotxsi_HxV.ZeBXdFBFd3ofIauQlo8OTLLnHHY.bHDTw00vcQtS7zilQDLGZ8G3iSvt1Okkw1SdF7si3NZE2RfySxeElXDnNK2.GGi-FMJ1bLfiXZFiEe7R2buqNP6DuNTyApBuUCkhis3ZM7CbYtTS4v_Cn81JJotyokPqTzBHRDQjyBXmYEKGlxBdC1p1XiyLXO3CYrQvN1gPN.ltqjW8uhEX7nLHx4ANm125NdGii-7",
    "ENAI": "zbw9+J5BDZX1OLiunUh+C87G1PxlVwR6hNOGfjthFaM=",
    "AUID": "EY5Fcs8hG5ibAWDkynBmXl+d4T0707WgfMGbSNENvNM=",
    "webid": "30c5178014b04bfcb30945796007b17e",
    "webid_ts": "1783521738810",
    "webid_sync": "1783583982883",
    "TS": "1783583984",
    "HTS": "59ZwWfqUbSBz_SFSQgPo-w00",
    "ALID": "McQO3yDeJ3UqJ6leNW5Ygn9fCMgjvakPJvukmgyoKFteGKPJDEnIN5oszMeiixP2w999UI",
    "LSID": "93978c25-3dc2-454c-9e9c-e3ee1941bfe61783583984740",
    "__gads": "ID=e158ed4c70cfa252:T=1783583984:RT=1783583984:S=ALNI_MY4y-uxsjNfdrZ_BkP5XSyYqf7mPw",
    "__gpi": "UID=000014b65e6d6cb6:T=1783583984:RT=1783583984:S=ALNI_MaCTJRABuXr9O5KHFjeLysV935IVw",
    "__eoi": "ID=2da8f27023eeae69:T=1783583984:RT=1783583984:S=AA-AfjbbDOOPRFsUIoquBTxyTtT_",
    "_T_ANO": "XnbBCA9PseDy5dpmxbbPX5miqSc6oaR9bry4QGsmA7t7VSQrLGtZBpiB0Xfv9pYtYMxGLzAAxRb81JSyNZJc33E9ZwwOnIK7Jzm7YkomTXYFk9HJ4X6EoHpt56I5H49Sr4SBaZQV875w/twSaAy6wp+v5jGhfbCHtf2ejH00jTWwBl01/wovrSRfE/ee+jMTHr/PFZwSEQAcCwTrRX5zsXaD4IPqUe2iitRnb8wP2N9cqE9lYRjP/+SD2+c4zeagFdfqF/9fLsnGJz7e9JRWC78ynzYGeO+5D9SH+LT4n5vNaIXAj+kGYSSoAsFHAJ8l90YuAmJPLNJUX/JEeZg7Jg==",
}

# =============================================
# 매칭 사전 (monitor.py와 동일한 규칙)
# =============================================

BRAND_ALIASES = {
    "네셔널": "NBP", "내셔널": "NBP", "엔비피": "NBP",
    "타이슨": "TYSON", "아이비피": "IBP",
    "스위프트": "SWIFT", "제이비에스": "JBS",
    "엑셀": "EXCEL", "EX": "EXCEL", "카길": "CARGILL",
    "티스": "TYS", "수카네": "SUKARNE",
    "프리고소르노": "FRIGOSORNO", "아그로수퍼": "AGROSUPER",
    "스미스필드": "SMITHFIELD", "시보드": "SEABOARD",
    "하이라이프": "HYLIFE",
    "데니쉬": "DANISH CROWN", "다니쉬": "DANISH CROWN",
    "뎀코타": "DEMKOTA", "덴코타": "DEMKOTA",
    "크릭스톤": "CREEKSTONE", "크릭스턴": "CREEKSTONE",
    "헬라비": "HELLABY", "그레이터오마하": "GREATER OMAHA",
    "쇼케이스": "SHOWCASE",
    "스위푸트": "SWIFT",
    "오마하": "OMAHA",
    "우드워드": "WOODWARD",
    "오키": "OAKEY",
    "놀란": "NOLAN",
    "잉카롭사": "INCARLOPSA",
    "마프리제스": "MAFRIGES",
    "크렉스톤": "CREEKSTONE",
    "크리스톤": "CREEKSTONE",
    "호멜": "HORMEL",
    "홀멜": "HORMEL",
    "팜플로나": "PAMPLONA",
    "메이플": "MAPLE",
    "킬코이": "KILCOY",
    "코엑스카": "COEXCA",
    "팜랜드": "FARMLAND",
}

ORIGIN_ALIASES = {
    "국산": ["국산", "국내산", "국내", "한국", "한우", "한돈"],
    "미국": ["미국", "미산", "USA"],
    "독일": ["독일", "GERMANY"],
    "스페인": ["스페인", "SPAIN"],
    "칠레": ["칠레", "CHILE"],
    "덴마크": ["덴마크", "DENMARK"],
    "폴란드": ["폴란드", "POLAND"],
    "네덜란드": ["네덜란드", "화란", "NETHERLANDS"],
    "벨기에": ["벨기에", "BELGIUM"],
    "캐나다": ["캐나다", "CANADA"],
    "멕시코": ["멕시코", "MEXICO"],
    "호주": ["호주", "AUSTRALIA"],
    "뉴질랜드": ["뉴질랜드", "NEW ZEALAND"],
    "프랑스": ["프랑스", "FRANCE"],
    "오스트리아": ["오스트리아", "AUSTRIA"],
    "아일랜드": ["아일랜드", "IRELAND"],
    "영국": ["영국"],
    "브라질": ["브라질", "BRAZIL"],
    "헝가리": ["헝가리", "HUNGARY"],
    "이탈리아": ["이탈리아", "이태리", "ITALY"],
    "우루과이": ["우루과이", "URUGUAY"],
    "아르헨티나": ["아르헨티나", "ARGENTINA"],
    "핀란드": ["핀란드", "FINLAND"],
}

# 양쪽 글에 모두 있거나 모두 없어야 매칭되는 단어
QUALIFIERS = {
    "동결": ["동결"],
    "돈사골": ["돈사골", "돼지사골"],
}


QTY_PATTERN = re.compile(r"약?\s*(\d+(?:\.\d+)?)\s*(톤|키로|kg|KG|박스|팔레트|파렛트)")
PHONE_PATTERN = re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")
SELL_SUFFIXES = ["판매합니다", "판매 합니다", "팝니다", "팔아요", "급처분", "급처",
                 "처분합니다", "처분", "정리합니다", "정리", "판매중", "판매", "저렴히"]


def extract_sell_phrase(title):
    """판매글 제목에서 품목 표현만 추출: '메이플 목전지 판매합니다' → '메이플 목전지'"""
    t = str(title).strip()
    for p in SELL_SUFFIXES:
        idx = t.find(p)
        if idx > 0:
            t = t[:idx]
            break
    t = QTY_PATTERN.sub("", t)
    return t.strip(" .,~!?-·/()[]") or str(title).strip()


def josa_eul(word):
    w = str(word).strip()
    if not w:
        return "를"
    ch = w[-1]
    if "가" <= ch <= "힣":
        return "을" if (ord(ch) - 0xAC00) % 28 else "를"
    return "를"


def clean_person(name):
    """닉네임 정리: 전화번호 분리, 영문 아이디는 '미트피플 회원 ~' 표기."""
    n = str(name).strip()
    phone = ""
    mm = PHONE_PATTERN.search(n)
    if mm:
        phone = mm.group(0)
        n = PHONE_PATTERN.sub("", n).strip(" -·,/()")
    if n and not re.search(r"[가-힣]", n):
        n = f"미트피플 회원 {n}"
    return n, phone


def broker_message(buy_title, buy_author, sell_title, sell_author,
                   seller_company="", seller_person="", sell_item=""):
    """판매자에게 보낼 중개 문구 생성.
    본문에서 추출한 업체명/담당자가 있으면 실명으로 인사, 품명이 있으면 그것을 사용."""
    buyer, buyer_phone = clean_person(buy_author)
    if not buyer_phone:
        buyer_phone = extract_first_phone(buy_title)
    if seller_company in ("nan",):
        seller_company = ""
    if seller_person in ("nan",):
        seller_person = ""
    if sell_item in ("nan",):
        sell_item = ""
    if seller_person or seller_company:
        # 담당자 이름에 번호/직함이 섞여 있으면 정리
        sp = PHONE_PATTERN.sub("", seller_person).strip(" -·,/()")
        sp = sp.split()[0] if sp else ""
        seller = f"{seller_company} {sp}".strip()
    else:
        seller, _ = clean_person(sell_author)
    item = extract_sell_phrase(sell_title)
    # 제목 추출이 흐릿하면(재고/정리/물량 등) 본문 품명으로 대체
    vague = ("재고", "정리", "물량", "임박", "떨이", "급처", "판매")
    if sell_item and (not item or item in vague or len(item) <= 2 or any(v == item for v in vague)):
        item = sell_item.split(",")[0].strip()
    qty = ""
    mm = QTY_PATTERN.search(str(buy_title))
    if mm:
        qty = f" 약 {mm.group(1)}{mm.group(2)}"

    intro = f"안녕하세요 {seller}님, {SENDER_NAME}입니다." if seller else f"안녕하세요, {SENDER_NAME}입니다."
    buyer_part = f"{buyer}님" if buyer else "구매자가"
    if buyer_phone:
        buyer_part += f"({buyer_phone})"
    body = f" 판매하고 계신 {item}{josa_eul(item)} {buyer_part}이{qty} 구매를 원하고 있습니다."
    return f"{intro}{body} {CLOSING_LINE}"


def extract_first_phone(text):
    mm = PHONE_PATTERN.search(str(text))
    return mm.group(0) if mm else ""


def normalize_text(s):
    return str(s).replace(" ", "").lower()


# 알려진 등급 코드 (제목에 '단어'로 정확히 등장할 때만 등급으로 인정)
KNOWN_GRADE_CODES = [
    "PRIME", "CHOICE", "SELECT", "CAB", "NOROLL", "NR",
    "MSA", "GF", "GR", "YP", "YG", "PS", "SS",
    "MB1", "MB2", "MB3", "MB4", "MB5", "MB6", "MB7", "MB8", "MB9", "MB",
    "S", "A", "B", "PR", "CH", "SEL",
]
GRADE_ALIASES_SM = {
    "프라임": ["PRIME", "PR"], "초이스": ["CHOICE", "CH"],
    "셀렉트": ["SELECT", "SEL"], "노롤": ["NOROLL", "NR"],
}


def grades_in_text(text):
    """텍스트에서 단어 경계로 등장하는 등급 코드 + 한글 등급 표기 → 정규화 토큰 집합."""
    found = set()
    upper = str(text).upper()
    known = {normalize_text(g) for g in KNOWN_GRADE_CODES}
    for mm in re.finditer(r"(?<![A-Z0-9])([A-Z]{1,4}\d{0,2})(?![A-Z0-9])", upper):
        tok = normalize_text(mm.group(1))
        if tok in known:
            found.add(tok)
    for alias, engs in GRADE_ALIASES_SM.items():
        if alias in str(text):
            found.update(normalize_text(e) for e in engs)
    return found


def est_codes_overlap(a, b):
    """두 EST 코드 집합의 매칭. 245C==245C 정확 일치,
    한쪽이 숫자만(245)이면 상대의 245계열(245C 등)과 매칭."""
    if not a or not b:
        return set()
    matched = set()
    for x in a:
        for y in b:
            if x == y:
                matched.add(x)
            elif not re.search(r"[A-Z]", x) and re.match(r"^" + re.escape(x) + r"[A-Z]{1,2}$", y):
                matched.add(y)
            elif not re.search(r"[A-Z]", y) and re.match(r"^" + re.escape(y) + r"[A-Z]{1,2}$", x):
                matched.add(x)
    return matched


def est_codes_in_text(text):
    """텍스트에서 EST 코드 추출 (숫자2~4 + 선택적 알파벳: 245, 245C 등). 수량 단위는 제외."""
    codes = set()
    up = str(text).upper()
    for mm in re.finditer(r"(?<![A-Z0-9])(\d{2,4}[A-Z]{0,2})(?![A-Z0-9])", up):
        code = mm.group(1)
        tail = up[mm.end():mm.end() + 3]
        if re.match(r"\s*(톤|키로|KG|박스|원|개|팔|판|년|월|일|시|BOX|T|컨)", tail):
            continue
        codes.add(code)
    return codes


PORK_MARKERS = ["돼지", "돈"]
BEEF_MARKERS = ["한우", "와규", "비프", "beef", "우사골", "소사골", "거세", "앵거스"]


def detect_species(title):
    """제목에서 소/돼지 구분. 확실할 때만 반환."""
    t = normalize_text(title)
    pork = any(normalize_text(m) in t for m in PORK_MARKERS)
    beef = any(normalize_text(m) in t for m in BEEF_MARKERS)
    if pork and not beef:
        return "돈"
    if beef and not pork:
        return "우"
    return None


def detect_origins(title):
    """제목에서 원산지 감지. '미국산'의 '국산' 같은 부분 문자열 오탐 차단."""
    found = set()
    t_norm = normalize_text(title)
    for key, variants in ORIGIN_ALIASES.items():
        for v in variants:
            if re.search(r"[가-힣]", v):
                if re.search(r"(?<![가-힣])" + re.escape(v) + r"(?:산)?(?![가-힣])", title):
                    found.add(key)
                    break
            elif len(normalize_text(v)) >= 3 and normalize_text(v) in t_norm:
                found.add(key)
                break
    return found


# =============================================
# 품목 사전 (구글 시트에서 로드)
# =============================================

SHEET_BRANDS = set()   # 시트 브랜드 열에서 로드한 브랜드 사전 (충돌 감지 강화)
BRAND_ORIGINS = {}     # 시트에서 학습한 브랜드→원산지 (예: omaha→{미국}, incarlopsa→{스페인})


def _origin_key_of(value):
    """시트 원산지 값('미국산' 등)을 ORIGIN_ALIASES 키로 변환."""
    vn = normalize_text(value)
    if not vn or vn == "nan":
        return None
    for key, variants in ORIGIN_ALIASES.items():
        for v in variants:
            v2 = normalize_text(v)
            if vn == v2 or vn == v2 + "산":
                return key
    return None


def load_vocabulary():
    """구글 시트에서 품목 사전 + 브랜드 사전 로드."""
    global SHEET_BRANDS
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        if "품목" not in df.columns:
            print("[사전] 시트에 품목 열이 없습니다")
            return []
        items = df["품목"].dropna().astype(str).str.strip().unique().tolist()
        items = [i for i in items if i]
        items.sort(key=lambda x: len(normalize_text(x)), reverse=True)  # 긴 이름 우선

        brand_col = next((c for c in ["브랜드", "브랜드명", "BRAND"] if c in df.columns), None)
        origin_col = next((c for c in ["원산지", "국가", "산지"] if c in df.columns), None)
        if brand_col:
            for b in df[brand_col].dropna().astype(str).str.strip().unique():
                bn = normalize_text(b)
                if len(bn) >= 3:  # 너무 짧은 표기는 오탐 방지 위해 제외
                    SHEET_BRANDS.add(bn)
            # 브랜드→원산지 지식 학습 (오마하=미국, 잉카롭사=스페인 등)
            if origin_col:
                for _, row in df[[brand_col, origin_col]].dropna().iterrows():
                    bn = normalize_text(row[brand_col])
                    ok = _origin_key_of(row[origin_col])
                    if len(bn) >= 3 and ok:
                        BRAND_ORIGINS.setdefault(bn, set()).add(ok)
        print(f"[사전] 품목 {len(items)}개 / 브랜드 {len(SHEET_BRANDS)}개 / 브랜드-원산지 {len(BRAND_ORIGINS)}개 로드 완료")
        return items
    except Exception as e:
        print(f"[사전] 로드 실패: {e}")
        return []


# =============================================
# 게시판 크롤링
# =============================================

def fetch_posts(board_url, board_name, fldid):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://cafe.daum.net/meetpeople",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    try:
        resp = requests.get(board_url, headers=headers, cookies=DAUM_COOKIES, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text

        pattern = re.compile(
            r"articles\.push\(\{.*?dataid:\s*'([^']+)'.*?title:\s*'([^']+)'.*?author:\s*'([^']+)'.*?created:\s*'([^']+)'",
            re.DOTALL
        )
        matches = pattern.findall(html)

        posts = []
        for dataid, title_raw, author_raw, created in matches:
            title_raw = title_raw.replace("\\/", "/")
            author_raw = author_raw.replace("\\/", "/")
            title = title_raw.encode('raw_unicode_escape').decode('unicode_escape')
            author = author_raw.encode('raw_unicode_escape').decode('unicode_escape')
            posts.append({
                "글번호": str(dataid),
                "제목": title,
                "글쓴이": author,
                "작성일": created,
                "링크": f"https://cafe.daum.net/meetpeople/{fldid}/{dataid}",
            })
        print(f"[크롤링] {board_name} {len(posts)}개 글 수집")
        return posts
    except Exception as e:
        print(f"[크롤링] {board_name} 실패: {e}")
        return []


# =============================================
# 누적 저장 (글번호 기준 중복 제거)
# =============================================

def load_archive(path):
    if not os.path.exists(path):
        return pd.DataFrame(columns=["글번호", "제목", "글쓴이", "작성일", "링크", "수집일"])
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        return df
    except Exception as e:
        print(f"[누적] {os.path.basename(path)} 읽기 실패: {e}")
        return pd.DataFrame(columns=["글번호", "제목", "글쓴이", "작성일", "링크", "수집일"])


def append_new_posts(path, posts):
    """새 글만 누적 파일에 추가하고, 새 글 목록 반환."""
    archive = load_archive(path)
    known = set(archive["글번호"].astype(str)) if not archive.empty else set()
    new_posts = [p for p in posts if str(p["글번호"]) not in known]
    if new_posts:
        today = datetime.now().strftime("%Y-%m-%d")
        new_df = pd.DataFrame(new_posts)
        new_df["수집일"] = today
        merged = pd.concat([archive, new_df], ignore_index=True)
        try:
            merged.to_csv(path, index=False, encoding="utf-8-sig")
        except PermissionError:
            print(f"  ⚠️ {os.path.basename(path)} 가 엑셀에 열려 있어 저장 건너뜀")
    return new_posts, load_archive(path)


def recent_rows(archive, max_age_days):
    """수집일 기준 최근 N일 이내 글만 (예전 '수집일시' 열도 인식)."""
    if archive.empty:
        return archive
    col = "수집일" if "수집일" in archive.columns else ("수집일시" if "수집일시" in archive.columns else None)
    if not col:
        return archive
    cutoff = datetime.now() - timedelta(days=max_age_days)
    parsed = pd.to_datetime(archive[col], errors="coerce")
    return archive[parsed.isna() | (parsed >= cutoff)]


# =============================================
# 제목 특징 추출 및 짝 매칭
# =============================================

def extract_features(title):
    t_norm = normalize_text(title)
    feats = {"brands": set(), "origins": set(), "ests": set(), "grades": set(), "state": None, "quals": set()}

    for alias, brand in BRAND_ALIASES.items():
        if alias in title:
            feats["brands"].add(normalize_text(brand))
    for brand in set(BRAND_ALIASES.values()):
        bn = normalize_text(brand)
        if len(bn) >= 3 and bn in t_norm:
            feats["brands"].add(bn)
    # 시트 브랜드 사전 (수백 개 브랜드 감지 → 서로 다른 브랜드 매칭 차단)
    for bn in SHEET_BRANDS:
        if bn in t_norm:
            feats["brands"].add(bn)

    # 원산지: 정밀 감지 ('미국산' 안의 '국산' 오탐 차단)
    feats["origins"] = detect_origins(title)
    # 원산지가 명시 안 된 글만 브랜드로 추론 (오마하→미국, 잉카롭사→스페인)
    # 명시된 글('미국산 엑셀')은 명시가 우선 — 브랜드의 다른 가능 원산지로 확장하지 않음
    if not feats["origins"]:
        for bn in feats["brands"]:
            feats["origins"] |= BRAND_ORIGINS.get(bn, set())
    # 종(소/돼지)
    feats["species"] = detect_species(title)

    # EST 코드 (숫자+알파벳까지: 245C ≠ 245E ≠ 245)
    feats["ests"] = est_codes_in_text(title)
    # 등급 (A/S/GF/PRIME 등)
    feats["grades"] = grades_in_text(title)

    if "냉장" in title:
        feats["state"] = "냉장"
    elif "냉동" in title:
        feats["state"] = "냉동"

    for q, mentions in QUALIFIERS.items():
        if any(normalize_text(w) in t_norm for w in mentions):
            feats["quals"].add(q)

    return feats


def find_item(title, items):
    tn = normalize_text(title)
    for it in items:
        if normalize_text(it) in tn:
            return it
    return None


def effective_item(title, items):
    """제목에서 품목 판정. 수식어 표기가 있으면 정식 품목명으로 정규화.
    예: '돼지사골 판매' → find_item은 '사골'을 찾지만 → '돈사골'로 승격."""
    it = find_item(title, items)
    if not it:
        return None
    t_norm = normalize_text(title)
    for stock_word, mentions in QUALIFIERS.items():
        sw = normalize_text(stock_word)
        if normalize_text(it) in sw and any(normalize_text(w) in t_norm for w in mentions):
            return stock_word
    return it


def pair_match(buy_title, sell_title, items, sell_aux=""):
    """구매글-판매글 짝 판정. 매칭이면 (점수, 근거태그들), 아니면 None.
    sell_aux: 본문에서 추출한 브랜드/품명 텍스트 (enrich_sell.py 결과) — 제목을 보강."""
    # 거래 끝난 글 제외
    both = str(buy_title) + str(sell_title)
    if any(w in both for w in DONE_WORDS):
        return None

    sell_full = f"{sell_title} {sell_aux}".strip()
    bi = effective_item(buy_title, items)
    si = effective_item(sell_full, items)
    if not bi or not si:
        return None
    # 품목은 정확히 같아야 함 ('삼겹'과 '삼겹양지'는 다른 부위)
    if normalize_text(bi) != normalize_text(si):
        return None
    item_name = bi

    fb = extract_features(buy_title)
    fs = extract_features(sell_full)

    # 충돌 조건 → 탈락
    if fb["brands"] and fs["brands"] and not (fb["brands"] & fs["brands"]):
        return None
    if fb["origins"] and fs["origins"] and not (fb["origins"] & fs["origins"]):
        return None
    if fb["state"] and fs["state"] and fb["state"] != fs["state"]:
        return None
    if fb["quals"] != fs["quals"]:
        return None
    # 종(소/돼지) 충돌: '돈연골잡육' vs '한우 잡육'
    if fb.get("species") and fs.get("species") and fb["species"] != fs["species"]:
        return None
    # 등급 충돌: 양쪽 다 등급 명시인데 안 겹침 (A vs S/GF)
    if fb.get("grades") and fs.get("grades") and not (fb["grades"] & fs["grades"]):
        return None

    score = 1
    tags = [f"품목:{item_name}"]
    if fb["brands"] & fs["brands"]:
        score += 3
        tags.append("브랜드 일치")
    if fb["origins"] & fs["origins"]:
        score += 2
        tags.append("원산지 일치")
    est_match = est_codes_overlap(fb["ests"], fs["ests"])
    if est_match:
        score += 3
        tags.append(f"EST {', '.join(sorted(est_match))} 일치")
    if fb.get("grades") and fs.get("grades") and (fb["grades"] & fs["grades"]):
        score += 2
        tags.append(f"등급 {', '.join(sorted(g.upper() for g in fb['grades'] & fs['grades']))} 일치")
    if fb["state"] and fb["state"] == fs["state"]:
        score += 1
        tags.append(fb["state"])
    # 조건이 하나도 안 겹치는 짝(품목만 일치)은 소음 → 최소 점수 미달 시 탈락
    if score < MIN_PAIR_SCORE:
        return None
    return score, tags


def load_seen_pairs():
    if not os.path.exists(PAIRS_CSV):
        return set()
    try:
        df = pd.read_csv(PAIRS_CSV, encoding="utf-8-sig", dtype=str)
        return set(zip(df["구매글번호"].astype(str), df["판매글번호"].astype(str)))
    except Exception:
        return set()


def find_pairs(buy_rows, sell_rows, items, seen_pairs):
    """구매글 목록 x 판매글 목록 매칭.
    - 이미 알림 보낸 짝 제외
    - 같은 판매자의 반복 게시글은 최신 1건만
    - 구매글당 점수 상위 MAX_PAIRS_PER_POST건만"""
    pairs = []
    for _, b in buy_rows.iterrows():
        candidates = []
        for _, s in sell_rows.iterrows():
            key = (str(b["글번호"]), str(s["글번호"]))
            if key in seen_pairs:
                continue
            aux = " ".join(str(s.get(c, "")) for c in ("브랜드", "품명") if str(s.get(c, "")) not in ("", "nan"))
            result = pair_match(str(b["제목"]), str(s["제목"]), items, aux)
            if result:
                score, tags = result
                candidates.append((score, s, key, tags))

        if not candidates:
            continue

        # 같은 판매자 + 같은 제목의 반복글은 최신(글번호 큰 것) 1건만
        candidates.sort(key=lambda c: int(re.sub(r"\D", "", str(c[1]["글번호"])) or 0), reverse=True)
        dedup, seen_repost = [], set()
        for score, s, key, tags in candidates:
            rk = (str(s["글쓴이"]), re.sub(r"[^0-9a-z가-힣]", "", normalize_text(s["제목"])))
            if rk in seen_repost:
                seen_pairs.add(key)  # 반복글도 본 것으로 기록
                continue
            seen_repost.add(rk)
            dedup.append((score, s, key, tags))

        dedup.sort(key=lambda c: -c[0])
        for score, s, key, tags in dedup[:MAX_PAIRS_PER_POST]:
            seen_pairs.add(key)
            pairs.append({
                "점수": score,
                "근거": " / ".join(tags),
                "구매글번호": str(b["글번호"]),
                "구매제목": b["제목"],
                "구매링크": b["링크"],
                "판매글번호": str(s["글번호"]),
                "판매제목": s["제목"],
                "판매글쓴이": s["글쓴이"],
                "판매링크": s["링크"],
                "판매수집일": s.get("수집일", s.get("수집일시", "")),
                "판매업체": "" if str(s.get("업체명", "")) == "nan" else str(s.get("업체명", "") or ""),
                "판매담당자": str(s.get("담당자", "") or ""),
                "판매연락처": str(s.get("연락처", "") or "").split(";")[0].strip(),
                "판매수량": str(s.get("수량", "") or ""),
                "중개문구": broker_message(b["제목"], b.get("글쓴이", ""), s["제목"], s["글쓴이"],
                                       seller_company=str(s.get("업체명", "") or ""),
                                       seller_person=str(s.get("담당자", "") or ""),
                                       sell_item=str(s.get("품명", "") or "")),
                "발견일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
    pairs.sort(key=lambda p: p["점수"], reverse=True)
    return pairs


# =============================================
# 카톡 '나에게 보내기' (monitor.py와 동일)
# =============================================

def _kakao_try_lock():
    try:
        if os.path.exists(KAKAO_LOCK_PATH) and time.time() - os.path.getmtime(KAKAO_LOCK_PATH) > 60:
            os.remove(KAKAO_LOCK_PATH)
    except Exception:
        pass
    try:
        fd = os.open(KAKAO_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return True


def _kakao_unlock():
    try:
        os.remove(KAKAO_LOCK_PATH)
    except Exception:
        pass


def _kakao_load_token():
    if not os.path.exists(KAKAO_TOKEN_PATH):
        return None
    try:
        with open(KAKAO_TOKEN_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _kakao_save_token(tok):
    try:
        with open(KAKAO_TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(tok, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def kakao_send_to_me(text):
    if not KAKAO_ENABLED:
        return False
    tok = _kakao_load_token()
    if not tok:
        return False

    def _send(access):
        return requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {access}"},
            data={
                "template_object": json.dumps({
                    "object_type": "text",
                    "text": text[:190],
                    "link": {"web_url": "https://cafe.daum.net/meetpeople"},
                })
            },
            timeout=10,
        )

    try:
        r = _send(tok.get("access_token", ""))
        if r.status_code == 401:
            # monitor.py가 이미 갱신했을 수 있으니 디스크 재확인
            fresh = _kakao_load_token() or tok
            if fresh.get("access_token") != tok.get("access_token"):
                tok = fresh
                r = _send(tok.get("access_token", ""))
        if r.status_code == 401 and tok.get("refresh_token"):
            if _kakao_try_lock():
                try:
                    rr = requests.post(
                        "https://kauth.kakao.com/oauth/token",
                        data={
                            "grant_type": "refresh_token",
                            "client_id": tok.get("rest_api_key", ""),
                            "refresh_token": tok["refresh_token"],
                            **({"client_secret": tok["client_secret"]} if tok.get("client_secret") else {}),
                        },
                        timeout=10,
                    )
                    if rr.ok and "access_token" in rr.json():
                        nt = rr.json()
                        tok["access_token"] = nt["access_token"]
                        if nt.get("refresh_token"):
                            tok["refresh_token"] = nt["refresh_token"]
                        _kakao_save_token(tok)
                finally:
                    _kakao_unlock()
                r = _send(tok.get("access_token", ""))
            else:
                time.sleep(3)
                fresh = _kakao_load_token() or tok
                r = _send(fresh.get("access_token", ""))
        return r.ok and r.json().get("result_code") == 0
    except Exception:
        return False


# =============================================
# 알림 및 저장
# =============================================

def play_alert(count):
    print(f"\n🔗 판매↔구매 매칭 {count}건 발견!")
    for _ in range(3):
        winsound.Beep(1400, 300)
        time.sleep(0.2)


def report_pairs(pairs):
    lines = [f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 판매↔구매 매칭 {len(pairs)}건"]
    for i, p in enumerate(pairs, 1):
        strong = " 🎯" if p["점수"] >= 4 else ""
        lines.append(f"  🔗{strong} ({p['근거']})")
        lines.append(f"     구매: {p['구매제목']}")
        lines.append(f"           {p['구매링크']}")
        lines.append(f"     판매: {p['판매제목']}  (판매자: {p['판매글쓴이']}, 수집일: {p.get('판매수집일','')})")
        lines.append(f"           {p['판매링크']}")
        # 패널 문의 목록이 인식하는 형식 ([N] 이름 / 역할 / 연락처 → 문구:)
        comp, pers = p.get("판매업체", ""), p.get("판매담당자", "")
        if comp or pers:
            seller_name = f"{comp} {PHONE_PATTERN.sub('', pers).strip()}".strip()
        else:
            seller_name = PHONE.sub("", str(p["판매글쓴이"])).strip(" -·,/()") or "판매자"
        seller_phone = p.get("판매연락처", "") or extract_first_phone(p["판매글쓴이"]) or "-"
        lines.append(f"  [{i}] {seller_name} / 판매자 / {seller_phone}")
        lines.append(f"      문구: {p.get('중개문구', '')}")
    block = "\n".join(lines)
    print(block)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(block + "\n\n")
    except Exception:
        pass

    # 짝 목록 CSV 누적
    df_new = pd.DataFrame(pairs)
    if os.path.exists(PAIRS_CSV):
        try:
            old = pd.read_csv(PAIRS_CSV, encoding="utf-8-sig", dtype=str)
            df_new = pd.concat([old, df_new.astype(str)], ignore_index=True)
        except Exception:
            pass
    try:
        df_new.to_csv(PAIRS_CSV, index=False, encoding="utf-8-sig")
    except PermissionError:
        print(f"  ⚠️ {os.path.basename(PAIRS_CSV)} 가 엑셀에 열려 있어 저장 건너뜀")

    # 카톡 전송: 안내 + 전달용 중개 문구 (폰에서 판매자에게 바로 전달)
    sent = 0
    for p in pairs[:KAKAO_MAX_SEND]:
        header = f"🔗 매칭! 판매자 {p['판매글쓴이']} ↓ 아래 문구를 전달하세요\n{p['판매링크']}"
        ok1 = kakao_send_to_me(header)
        ok2 = kakao_send_to_me(p.get("중개문구", ""))
        if ok1 and ok2:
            sent += 1
        time.sleep(0.5)
    if sent:
        print(f"  📱 카톡으로 중개 문구 {sent}건 전송 완료")


# =============================================
# 메인 루프
# =============================================

def main():
    print("=" * 50)
    print(f"미트피플 판매↔구매 크로스 매칭 시작  {VERSION}")
    print(f"확인 주기: {CHECK_INTERVAL // 60}분 / 판매글 유효 {SALES_MAX_AGE_DAYS}일 / 구매글 유효 {BUY_MAX_AGE_DAYS}일")
    print("=" * 50)

    items = load_vocabulary()
    if not items:
        print("품목 사전이 비어 있어 매칭을 진행할 수 없습니다.")
        return

    seen_pairs = load_seen_pairs()
    print(f"[매칭] 기존 발견 짝 {len(seen_pairs)}건 로드")

    # 시작 시 1회: 누적 구매글 ↔ 누적 판매글 전체 대조 (백필 데이터 즉시 활용)
    if INITIAL_FULL_SCAN:
        sell_archive = load_archive(SALES_CSV)
        buy_archive = load_archive(BUY_CSV)
        recent_buys = recent_rows(buy_archive, BUY_MAX_AGE_DAYS)
        recent_sells = recent_rows(sell_archive, SALES_MAX_AGE_DAYS)
        print(f"[전체대조] 구매글 {len(recent_buys)}건 × 판매글 {len(recent_sells)}건 대조 중...")
        init_pairs = find_pairs(recent_buys, recent_sells, items, seen_pairs)
        if init_pairs:
            play_alert(len(init_pairs))
            report_pairs(init_pairs)
        else:
            print("[전체대조] 새로운 매칭 없음")

    if STARTUP_DELAY_SEC > 0:
        print(f"[대기] monitor.py와 요청 시점 분산을 위해 {STARTUP_DELAY_SEC}초 후 시작...")
        time.sleep(STARTUP_DELAY_SEC)

    while True:
        if USE_OPERATING_HOURS:
            now_time = datetime.now().time()
            start_time = datetime.strptime(OPERATING_START, "%H:%M").time()
            end_time = datetime.strptime(OPERATING_END, "%H:%M").time()
            if not (start_time <= now_time <= end_time):
                print(f"  운영 시간 외 ({now_time.strftime('%H:%M')}) - 대기 중...")
                time.sleep(3600)
                continue

        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] 게시판 확인 중...")

        sell_posts = fetch_posts(SELL_BOARD_URL, "판매게시판", "HoUW")
        buy_posts = fetch_posts(BUY_BOARD_URL, "구매게시판", "HoTs")

        new_sells, sell_archive = append_new_posts(SALES_CSV, sell_posts)
        new_buys, buy_archive = append_new_posts(BUY_CSV, buy_posts)
        print(f"[누적] 판매글 신규 {len(new_sells)}건 (총 {len(sell_archive)}건) / 구매글 신규 {len(new_buys)}건 (총 {len(buy_archive)}건)")

        pairs = []
        if new_buys:
            # 새 구매글 ↔ 최근 판매글 전체
            pairs += find_pairs(
                pd.DataFrame(new_buys),
                recent_rows(sell_archive, SALES_MAX_AGE_DAYS),
                items, seen_pairs,
            )
        if new_sells:
            # 새 판매글 ↔ 최근 구매글 전체
            pairs += find_pairs(
                recent_rows(buy_archive, BUY_MAX_AGE_DAYS),
                pd.DataFrame(new_sells),
                items, seen_pairs,
            )

        # 중복 제거 (양방향에서 같은 짝이 잡힐 수 있음)
        unique = {}
        for p in pairs:
            unique[(p["구매글번호"], p["판매글번호"])] = p
        pairs = sorted(unique.values(), key=lambda p: p["점수"], reverse=True)

        if pairs:
            play_alert(len(pairs))
            report_pairs(pairs)
        else:
            print("  매칭 없음")

        print(f"  다음 확인: {CHECK_INTERVAL // 60}분 후")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()