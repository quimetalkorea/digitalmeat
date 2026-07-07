"""
미트피플 구매게시판 모니터링 + 시세 매칭 알림 + 거래처 문의 문구 생성
- 10분마다 미트피플 구매게시판 크롤링
- 내 시세 데이터와 품목 매칭
- 매칭되면 소리 알림 + latest_posts.csv 저장
- 매칭 품목의 거래처 담당자 문의 문구를 클립보드에 자동 복사
"""

import requests
import pandas as pd
import time
import os
import re
import json
import winsound
from datetime import datetime

# pyperclip 없으면 클립보드 기능만 끄고 계속 동작
try:
    import pyperclip
    CLIPBOARD_OK = True
except ImportError:
    CLIPBOARD_OK = False

# =============================================
# 설정
# =============================================

# 구글 시트 시세 데이터 URL (meat_search.py와 동일한 URL)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

# 미트피플 구매게시판 URL (iframe 내부 URL)
MEETPEOPLE_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoTs"

# 미트피플 판매게시판 URL (구매↔판매 교차 매칭용)
SELL_BOARD_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"

# CSV 저장 경로 (Streamlit 앱과 같은 폴더)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "latest_posts.csv")
MATCHED_CSV_PATH = CSV_PATH.replace(".csv", "_matched.csv")

# 거래처 연락처 파일 (로컬 전용 - .gitignore에 추가할 것!)
CONTACTS_PATH = os.path.join(BASE_DIR, "contacts.csv")

# 시세 시트에서 거래처를 나타내는 열 이름 후보 (앞에서부터 먼저 찾은 것 사용)
SUPPLIER_COLUMN_CANDIDATES = ["업체명", "거래처", "업체", "거래처명"]

# 시세 시트 열 이름 후보 (시트 표기가 달라도 자동으로 찾음)
COLUMN_CANDIDATES = {
    "날짜": ["날짜", "일자", "기준일", "단가일자", "등록일"],
    "브랜드": ["브랜드", "브랜드명", "BRAND"],
    "품명": ["품명", "상품명", "제품명", "품목명"],
    "창고": ["창고", "창고명", "보관창고", "보관장소"],
    "단가": ["단가(원/kg)", "단가", "판가", "단가(원)", "가격"],
    "EST": ["EST", "est", "EST번호", "작업장", "작업장번호", "공장번호"],
    "등급": ["등급", "GRADE", "Grade", "grade"],
    "원산지": ["원산지", "국가", "산지", "ORIGIN"],
}

# 원산지 별칭 사전: 게시글 표기 → 시트 표기 후보
ORIGIN_ALIASES = {
    "국산": ["국산", "국내산", "국내", "한국"],
    "미국": ["미국", "USA", "US"],
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
    "뉴질랜드": ["뉴질랜드", "NZ", "NEW ZEALAND"],
    "프랑스": ["프랑스", "FRANCE"],
    "오스트리아": ["오스트리아", "AUSTRIA"],
    "아일랜드": ["아일랜드", "IRELAND"],
    "영국": ["영국", "UK"],
    "브라질": ["브라질", "BRAZIL"],
    "헝가리": ["헝가리", "HUNGARY"],
    "이탈리아": ["이탈리아", "이태리", "ITALY"],
    "우루과이": ["우루과이", "URUGUAY"],
    "아르헨티나": ["아르헨티나", "ARGENTINA"],
    "핀란드": ["핀란드", "FINLAND"],
}

# 브랜드 별칭 사전: 게시글의 한글 호칭 → 시트의 브랜드명
# 새 브랜드가 생기면 여기에 한 줄씩 추가하면 됨
BRAND_ALIASES = {
    "네셔널": "NBP",
    "내셔널": "NBP",
    "엔비피": "NBP",
    "타이슨": "TYSON",
    "아이비피": "IBP",
    "스위프트": "SWIFT",
    "제이비에스": "JBS",
    "엑셀": "EXCEL",
    "카길": "CARGILL",
    "티스": "TYS",
    "수카네": "SUKARNE",
    "프리고소르노": "FRIGOSORNO",
    "아그로수퍼": "AGROSUPER",
    "스미스필드": "SMITHFIELD",
    "시보드": "SEABOARD",
    "하이라이프": "HYLIFE",
    "데니쉬": "DANISH CROWN",
    "다니쉬": "DANISH CROWN",
    "뎀코타": "DEMKOTA",
    "덴코타": "DEMKOTA",
    "크릭스톤": "CREEKSTONE",
    "크릭스턴": "CREEKSTONE",
    "헬라비": "HELLABY",
    "그레이터오마하": "GREATER OMAHA",
}

# 등급 별칭 사전: 게시글의 한글 표기 → 시트의 등급 표기 후보
GRADE_ALIASES = {
    "프라임": ["PRIME", "PR"],
    "초이스": ["CHOICE", "CH"],
    "셀렉트": ["SELECT", "SEL"],
    "노롤": ["NO ROLL", "NOROLL", "NR"],
}

# 재고에 이 단어가 붙어 있으면, 게시글에 명시됐을 때만 매칭
# 형식: "재고 표기": [게시글에서 인정되는 표기들]
# 예: 돈사골 재고는 글에 '돈사골' 또는 '돼지사골'이 있어야 매칭 ('사골 구합니다'에는 안 나옴)
QUALIFIERS_REQUIRE_MENTION = {
    "동결": ["동결"],
    "돈사골": ["돈사골", "돼지사골"],
}


def resolve_columns(price_df):
    """시트의 실제 열 이름을 후보 목록에서 찾아 매핑."""
    resolved = {}
    for key, candidates in COLUMN_CANDIDATES.items():
        for c in candidates:
            if c in price_df.columns:
                resolved[key] = c
                break
    return resolved

# 확인 주기 (초)
CHECK_INTERVAL = 10 * 60  # 10분

# 운영 시간 설정
# 테스트할 때는 USE_OPERATING_HOURS = False 로 바꾸면 24시간 즉시 동작
USE_OPERATING_HOURS = False  # 테스트 끝나면 True로 되돌리기!
OPERATING_START = "09:00"
OPERATING_END = "17:30"

# 보유 내역 표시 개수 (최신 날짜순 상위 N개)
MAX_DETAILS_DISPLAY = 5

# 거래처 문의 표시 개수 (담당자 등록된 거래처 우선)
MAX_INQUIRIES_DISPLAY = 10

# 문의 문구에 들어갈 발신자 소개
SENDER_NAME = "디지털미트 서종현"

# 매칭 후 문의 번호 입력 대기 시간(초) - 시간 내 입력 없으면 모니터링 계속
INQUIRY_INPUT_TIMEOUT = 120

# 카톡 '나에게 보내기' 연동 (get_kakao_token.py 먼저 1회 실행)
KAKAO_ENABLED = True
KAKAO_TOKEN_PATH = os.path.join(BASE_DIR, "kakao_token.json")
KAKAO_MAX_SEND = 3  # 매칭 1회당 카톡으로 보낼 최대 문의 건수

# 매칭 결과 로그 파일 (화면에서 밀려도 여기서 다시 볼 수 있음)
LOG_PATH = os.path.join(BASE_DIR, "monitor_log.txt")

# 구매↔판매 교차 매칭용 누적 파일
SELL_ACCUM_PATH = os.path.join(BASE_DIR, "sell_posts.csv")
BUY_ACCUM_PATH = os.path.join(BASE_DIR, "buy_posts.csv")
CROSS_CSV_PATH = os.path.join(BASE_DIR, "cross_matched.csv")
ACCUM_RETENTION_DAYS = 365  # 누적 보관 일수 (1년치 백필 보존)

VERSION = "v2.6 (동결 필터 포함)"

# 이미 알림을 보낸 글번호 기록
notified_ids = set()

# =============================================
# 다음 카페 쿠키 설정
# =============================================
# 크롬 → 미트피플 로그인 → F12 → Application → Cookies → cafe.daum.net
# 각 쿠키 이름 클릭 → 하단에서 전체 값 복사
DAUM_COOKIES = {
    "HTS": "XUwrpyOXxWx9TFx_NPqLqw00",
    "JSESSIONID": "FABAC0B35048CDFFA8426677DAE9BA60",
    "PROF": "0603012032024064024192UiQPJk7X-6w0mlxoempuua9QsdGeNIag3O1dpXj_gbkQKuZP3z7wEl2bxriNh5SdkQ00LYYSA9A1_cGNLCyhCzrwOgj61xkRhz7hDHbz3NH3TPhotxsi_HxV.ZeBXdFBFd3ofIauQlo8OTLLnHHY.bHDTw00vcQtS7zilQDLGZ8G3iSvt1Okkw1SdF7si3NZE2RfySxeElXDnNK2.GGi-FMJ1bLfiXZFiEe7R2buqNP6DuNTyApBuUCkhis3ZM7CbYtTS4v_Cn81JJotyokPqTzBHRDQjyBXmYEKGlxBdC1p1XiyLXO3CYrQvN1gPN.ltqjW8uhEX7nLHx4ANm125NdGii-7",
    "ALID": "KN6XC2KuL5bGq0vzhLQhPSZvFgslAvu4jPIHdBwWDl5Hn4fnDEnIN5oszMeiixP2w999UI",
    "HM_CU": "562UzJ5yPrq",
}

# =============================================
# 유틸: 가격 문자열 → 숫자
# =============================================

def to_number(value):
    """'10,200' 같은 문자열을 숫자로 변환. 실패하면 None."""
    try:
        n = float(str(value).replace(",", "").replace("원", "").strip())
        return n
    except (ValueError, TypeError):
        return None


def extract_numbers(value):
    """셀 안의 모든 숫자 추출. '700~800' 같은 범위 표기도 처리."""
    nums = []
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", str(value)):
        n = to_number(tok)
        if n is not None and n > 0:
            nums.append(n)
    return nums


def format_price_range(values):
    """단가 리스트를 '9,200~10,200원' 형태로 (숫자 기준 min/max)."""
    nums = []
    for v in values:
        nums.extend(extract_numbers(v))
    if not nums:
        return "시세 확인 필요"
    lo, hi = int(min(nums)), int(max(nums))
    if lo == hi:
        return f"{lo:,}원"
    return f"{lo:,}~{hi:,}원"


# =============================================
# 시세 데이터 로드
# =============================================

def load_my_prices():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df = df.dropna(how="all")

        # 열 자동 탐색 + 진단 출력
        cols = resolve_columns(df)
        price_col = cols.get("단가")
        if price_col:
            df = df[df[price_col].notna() & (df[price_col] != "")]
        print(f"[시세] {len(df)}개 품목 로드 완료")

        supplier_col = find_supplier_column(df)
        diag = []
        for key in ["날짜", "브랜드", "품명", "창고", "단가", "원산지", "EST", "등급"]:
            found = cols.get(key)
            diag.append(f"{key}:{found if found else '❌없음'}")
        diag.append(f"업체명:{supplier_col if supplier_col else '❌없음'}")
        print(f"[시세] 열 확인 → {' / '.join(diag)}")
        missing = [k for k in ["브랜드", "품명", "창고", "날짜"] if k not in cols]
        if missing:
            print(f"  ⚠️ 못 찾은 열: {', '.join(missing)} → 실제 시트 열 이름을 알려주시면 맞춰드려요")
            print(f"  (시트 전체 열: {', '.join(str(c) for c in df.columns[:15])})")
        return df
    except Exception as e:
        print(f"[시세] 로드 실패: {e}")
        return pd.DataFrame()


# =============================================
# 거래처 연락처 로드 (contacts.csv - 로컬 전용)
# =============================================

def load_contacts(verbose=True):
    if not os.path.exists(CONTACTS_PATH):
        if verbose:
            print(f"[연락처] contacts.csv 없음 → 거래처 문의 기능은 거래처명만 표시됩니다")
            print(f"          ({CONTACTS_PATH} 에 거래처,담당자,전화번호 형식으로 만들어주세요)")
        return pd.DataFrame()
    # 엑셀이 CP949로 저장했을 수도 있으니 인코딩 순차 시도
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            df = pd.read_csv(CONTACTS_PATH, encoding=enc, dtype=str)
            df.columns = [str(c).strip() for c in df.columns]
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
            if verbose:
                names = df["거래처"].dropna().tolist() if "거래처" in df.columns else []
                print(f"[연락처] {len(df)}개 거래처 로드 완료 ({enc}): {', '.join(names[:10])}")
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            if verbose:
                print(f"[연락처] 로드 실패: {e}")
            return pd.DataFrame()
    if verbose:
        print(f"[연락처] 인코딩 인식 실패 - 엑셀에서 'CSV UTF-8' 형식으로 다시 저장해주세요")
    return pd.DataFrame()


def normalize_text(s):
    """비교용: 공백 제거 + 소문자."""
    return str(s).replace(" ", "").lower()


def drop_unmentioned_qualifiers(title, rows):
    """게시글에 언급되지 않은 수식어(동결, 돈사골 등)가 붙은 재고를 제외.
    예: 글에 '동결'이 없으면 동결삼겹양지 행 제거,
        글에 '돈사골'(또는 '돼지사골')이 없으면 돈사골 행 제거."""
    if rows.empty:
        return rows
    t_norm = normalize_text(title)
    cols = resolve_columns(rows)
    name_col = cols.get("품명")

    def rtext(row):
        return normalize_text(
            " ".join(str(row.get(c, "")) for c in [name_col, "품목"] if c and c in rows.columns)
        )

    for stock_word, mentions in QUALIFIERS_REQUIRE_MENTION.items():
        if rows.empty:
            break
        sw = normalize_text(stock_word)
        mentioned = any(normalize_text(w) in t_norm for w in mentions)
        texts = rows.apply(rtext, axis=1)
        if mentioned:
            # 글에 명시됨 → 해당 재고로 좁힘 (돼지사골 글 → 돈사골 행만)
            rows = rows[texts.str.contains(sw)]
        else:
            # 글에 없음 → 해당 재고 제외 (사골 글 → 돈사골 행 제거)
            rows = rows[~texts.str.contains(sw)]
    return rows


def refine_rows(title, rows):
    """게시글 제목의 조건으로 행을 단계별로 좁힘.
    필터 순서: 브랜드 → EST번호 → 등급 → 냉장/냉동.
    반환: (좁혀진 행, 정밀매칭 여부, 안내 메모 목록)
    요청 브랜드/등급 재고가 없으면 메모로 알려줌."""
    if rows.empty:
        return rows, False, []

    cols = resolve_columns(rows)
    brand_col = cols.get("브랜드")
    est_col = cols.get("EST")
    grade_col = cols.get("등급")
    name_col = cols.get("품명")

    t_norm = normalize_text(title)
    refined = rows
    applied = False
    notes = []

    def norm_or_empty(v):
        n = normalize_text(v)
        return "" if n == "nan" else n

    # ── 1) 브랜드 필터 ──────────────────────────
    if brand_col:
        wanted = set()
        # 별칭 사전: 제목에 '네셔널'이 있으면 NBP를 원함
        for alias, brand in BRAND_ALIASES.items():
            if alias in title:
                wanted.add(normalize_text(brand))
        # 시트 브랜드명이 제목에 직접 등장 (NBP, TYS 등 영문 표기)
        for bv in rows[brand_col].dropna().astype(str).unique():
            bvn = norm_or_empty(bv)
            if len(bvn) >= 2 and bvn in t_norm:
                wanted.add(bvn)
        if wanted:
            def brand_ok(x):
                xn = norm_or_empty(x)
                if not xn:
                    return False
                return any(w == xn or w in xn or xn in w for w in wanted)
            sub = refined[refined[brand_col].astype(str).apply(brand_ok)]
            if not sub.empty:
                refined = sub
                applied = True
            else:
                names = ", ".join(sorted(w.upper() for w in wanted))
                notes.append(f"요청 브랜드({names}) 미보유 — 아래는 다른 브랜드 보유 내역")

    # ── 1.5) 원산지 필터 (독일산, 미국산 등) ─────
    origin_col = cols.get("원산지")
    if origin_col:
        wanted_origins = set()
        origin_name = None
        for key, variants in ORIGIN_ALIASES.items():
            hit = False
            for v in variants:
                if re.search(r"[가-힣]", v):
                    if v in title:
                        hit = True
                else:
                    if len(normalize_text(v)) >= 2 and normalize_text(v) in t_norm:
                        hit = True
            if hit:
                origin_name = key
                wanted_origins.update(normalize_text(v) for v in variants)
                break
        if wanted_origins:
            def origin_ok(x):
                xn = norm_or_empty(x)
                if not xn:
                    return False
                return any(w == xn or w in xn or xn in w for w in wanted_origins)
            sub = refined[refined[origin_col].astype(str).apply(origin_ok)]
            if not sub.empty:
                refined = sub
                applied = True
            else:
                notes.append(f"요청 원산지({origin_name}) 미보유")

    # ── 2) EST 번호 필터 ────────────────────────
    if est_col:
        wanted_ests = set()
        for ev in refined[est_col].dropna().astype(str).unique():
            digits = re.sub(r"\D", "", ev)
            if len(digits) >= 2 and re.search(r"(?<!\d)" + re.escape(digits) + r"(?!\d)", title):
                wanted_ests.add(digits)
        if wanted_ests:
            sub = refined[refined[est_col].astype(str).apply(
                lambda x: re.sub(r"\D", "", str(x)) in wanted_ests
            )]
            if not sub.empty:
                refined = sub
                applied = True

    # ── 3) 등급 필터 (CAB, 프라임→Prime 등) ─────
    if grade_col:
        wanted_grades = set()
        grade_cue = False
        cue_names = []
        # 시트 등급값이 제목에 직접 등장 (CAB 등)
        for gv in refined[grade_col].dropna().astype(str).unique():
            gvn = norm_or_empty(gv)
            if len(gvn) >= 2 and gvn in t_norm:
                wanted_grades.add(gvn)
        # 한글 등급 표기 → 영문 후보 (프라임 → PRIME/PR)
        for alias, engs in GRADE_ALIASES.items():
            if alias in title:
                grade_cue = True
                cue_names.append(alias)
                wanted_grades.update(normalize_text(e) for e in engs)
                wanted_grades.add(normalize_text(alias))  # 시트가 한글 표기일 수도
        if wanted_grades:
            def grade_ok(x):
                xn = norm_or_empty(x)
                if not xn:
                    return False
                return any(w == xn or w in xn or xn in w for w in wanted_grades)
            sub = refined[refined[grade_col].astype(str).apply(grade_ok)]
            if not sub.empty:
                refined = sub
                applied = True
            elif grade_cue:
                notes.append(f"요청 등급({', '.join(cue_names)}) 미보유 — 아래는 다른 등급 보유 내역")

    # ── 4) 냉장/냉동 필터 ───────────────────────
    def row_text(row):
        return normalize_text(
            " ".join(str(row.get(c, "")) for c in [name_col, "품목"] if c and c in rows.columns)
        )

    for state, other in (("냉장", "냉동"), ("냉동", "냉장")):
        if state in title:
            texts = refined.apply(row_text, axis=1)
            sub = refined[texts.str.contains(state)]
            if not sub.empty:
                refined = sub
                applied = True
            else:
                # 상태 표기가 없는 시트면 반대 상태 행만 제거
                sub2 = refined[~texts.str.contains(other)]
                if not sub2.empty and len(sub2) < len(refined):
                    refined = sub2
                    applied = True
            break

    return refined, applied, notes


def normalize_company(name):
    """회사명 비교용 정규화: (주), ㈜, 주식회사, 공백 제거."""
    s = str(name)
    for token in ["(주)", "㈜", "주식회사", "(유)", "(합)", " "]:
        s = s.replace(token, "")
    return s.strip().lower()


def find_supplier_column(price_df):
    """시세 시트에서 거래처 열 이름 찾기."""
    for col in SUPPLIER_COLUMN_CANDIDATES:
        if col in price_df.columns:
            return col
    return None


def lookup_contact(contacts_df, supplier):
    """거래처명으로 담당자/전화번호 조회.
    (주)/㈜/주식회사/공백 차이는 무시하고 매칭."""
    if contacts_df.empty or "거래처" not in contacts_df.columns:
        return None, None
    target = normalize_company(supplier)
    norm = contacts_df["거래처"].astype(str).apply(normalize_company)
    row = contacts_df[norm == target]
    if row.empty:
        # 부분 일치도 시도 (표기가 조금 다를 수 있음)
        row = contacts_df[norm.apply(lambda x: bool(x) and (x in target or target in x))]
    if row.empty:
        return None, None
    name = row.iloc[0].get("담당자")
    phone = row.iloc[0].get("전화번호")
    return (name if pd.notna(name) else None), (phone if pd.notna(phone) else None)


# =============================================
# 미트피플 크롤링 (JavaScript에서 데이터 추출)
# =============================================

def fetch_posts(board_url=MEETPEOPLE_URL, fldid="HoTs", label="크롤링"):
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

        # JavaScript articles 배열에서 dataid, title, author, created 추출
        pattern = re.compile(
            r"articles\.push\(\{.*?dataid:\s*'([^']+)'.*?title:\s*'([^']+)'.*?author:\s*'([^']+)'.*?created:\s*'([^']+)'",
            re.DOTALL
        )
        matches = pattern.findall(html)

        posts = []
        for dataid, title_raw, author_raw, created in matches:
            # 유니코드 이스케이프 디코딩 (\uC2A4 → 스)
            # '\/' 같은 비표준 이스케이프는 미리 정리 (DeprecationWarning 방지)
            title_raw = title_raw.replace("\\/", "/")
            author_raw = author_raw.replace("\\/", "/")
            title = title_raw.encode('raw_unicode_escape').decode('unicode_escape')
            author = author_raw.encode('raw_unicode_escape').decode('unicode_escape')

            posts.append({
                "글번호": dataid,
                "제목": title,
                "글쓴이": author,
                "작성일": created,
                "링크": f"https://cafe.daum.net/meetpeople/{fldid}/{dataid}",
            })

        print(f"[{label}] {len(posts)}개 글 수집")
        return posts

    except Exception as e:
        print(f"[{label}] 실패: {e}")
        return []


# =============================================
# 품목 매칭
# =============================================

def build_details(item_rows, supplier_col):
    """매칭 품목의 보유 내역을 브랜드/품명/창고/업체명별로 정리.
    같은 조합이 여러 날짜에 걸쳐 누적돼 있으면 가장 최신 날짜의 단가만 사용
    (옛날 단가가 시세 범위에 섞이는 것 방지)."""
    cols = resolve_columns(item_rows)
    brand_col = cols.get("브랜드")
    name_col = cols.get("품명")
    wh_col = cols.get("창고")
    date_col = cols.get("날짜")
    price_col = cols.get("단가")
    origin_col = cols.get("원산지")

    group_cols = [c for c in [brand_col, name_col, origin_col, wh_col] if c]
    if supplier_col and supplier_col in item_rows.columns:
        group_cols.append(supplier_col)
    if not group_cols:
        return []

    def clean(v):
        return "" if pd.isna(v) else str(v).strip()

    details = []
    for keys, g in item_rows.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        d = dict(zip(group_cols, keys))

        # 날짜 열이 있으면 최신 날짜 행만 남김
        date_str = ""
        sort_date = pd.NaT
        if date_col:
            parsed = pd.to_datetime(g[date_col], errors="coerce")
            if parsed.notna().any():
                latest = parsed.max()
                g = g[parsed == latest]
                date_str = clean(g[date_col].iloc[0])
                sort_date = latest
            else:
                date_str = clean(g[date_col].iloc[0])

        price = ""
        if price_col:
            price = format_price_range(g[price_col].tolist())

        details.append({
            "날짜": date_str,
            "브랜드": clean(d.get(brand_col, "")) if brand_col else "",
            "품명": clean(d.get(name_col, "")) if name_col else "",
            "내시세": price,
            "원산지": clean(d.get(origin_col, "")) if origin_col else "",
            "창고": clean(d.get(wh_col, "")) if wh_col else "",
            "업체명": clean(d.get(supplier_col, "")) if supplier_col else "",
            "_sort_date": sort_date,
        })

    # 최신 날짜가 앞으로 오게 정렬
    details.sort(
        key=lambda x: x["_sort_date"] if not pd.isna(x["_sort_date"]) else pd.Timestamp.min,
        reverse=True,
    )
    for det in details:
        det.pop("_sort_date", None)
    return details


def match_posts_with_prices(posts, price_df):
    if price_df.empty or not posts:
        return []

    my_items = []
    if "품목" in price_df.columns:
        my_items = price_df["품목"].dropna().unique().tolist()
        # 긴 품목명 우선: '돈사골 구합니다'가 '사골'이 아니라 '돈사골'로 매칭되게
        my_items.sort(key=lambda x: len(normalize_text(x)), reverse=True)

    supplier_col = find_supplier_column(price_df)

    matched = []
    for post in posts:
        title = post.get("제목", "")
        title_norm = normalize_text(title)
        for item in my_items:
            if normalize_text(item) in title_norm:
                # 기본: 품목 정확 일치 행
                exact_rows = price_df[price_df["품목"] == item]
                # 확장: 품목에 키워드가 포함된 행 (예: '냉장 갈비'도 '갈비'로 잡힘)
                expanded_rows = price_df[
                    price_df["품목"].astype(str).apply(
                        lambda x: normalize_text(item) in normalize_text(x)
                    )
                ]

                # 글에 언급 안 된 수식어(동결 등)가 붙은 재고 제외
                exact_rows = drop_unmentioned_qualifiers(title, exact_rows)
                expanded_rows = drop_unmentioned_qualifiers(title, expanded_rows)
                if expanded_rows.empty:
                    # 남은 재고가 없으면 매칭 제외 (예: 동결 재고만 보유)
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            f.write(
                                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                                f"제외: [{item}] {title} → 조건에 맞는 재고 없음 (동결 등 수식어 재고만 보유)\n"
                            )
                    except Exception:
                        pass
                    break

                # 제목 조건(브랜드/EST/등급/냉장냉동)으로 정밀 필터
                refined, is_refined, notes = refine_rows(title, expanded_rows)

                # 요청 브랜드/등급이 미보유면 매칭에서 제외 (알림 없음, 로그에만 기록)
                if notes:
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            f.write(
                                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                                f"제외: [{item}] {title} → {' / '.join(notes)}\n"
                            )
                    except Exception:
                        pass
                    break

                item_rows = refined if is_refined else exact_rows
                if item_rows.empty:
                    item_rows = expanded_rows

                # 단가 범위 (숫자 기준으로 min/max 계산)
                price_info = "시세 확인 필요"
                price_col = resolve_columns(item_rows).get("단가")
                if price_col:
                    price_info = format_price_range(item_rows[price_col].tolist())

                # 브랜드/품명/업체명별 상세 내역
                details = build_details(item_rows, supplier_col)

                # 이 품목을 보유한 거래처 목록
                suppliers = []
                if supplier_col:
                    suppliers = (
                        item_rows[supplier_col].dropna().astype(str).str.strip().unique().tolist()
                    )
                    suppliers = [s for s in suppliers if s]

                matched.append({
                    **post,
                    "매칭품목": item,
                    "내시세": price_info,
                    "거래처": ", ".join(suppliers) if suppliers else "",
                    "_suppliers": suppliers,   # 내부용
                    "_details": details,       # 내부용
                    "_refined": is_refined,    # 제목 조건(브랜드/EST/등급) 일치 여부
                    "_notes": notes,           # 미보유 안내 등
                })
                break

    return matched


def matched_to_rows(matched):
    """매칭 결과를 CSV 저장용 상세 행으로 변환.
    열 순서: 매칭품목, 제목, 날짜, 브랜드, 품명, 내시세, 창고, 업체명, 링크, ...
    """
    rows = []
    for m in matched:
        details = m.get("_details") or [{
            "날짜": "", "브랜드": "", "품명": "",
            "내시세": m.get("내시세", ""), "원산지": "", "창고": "", "업체명": "",
        }]
        for d in details:
            rows.append({
                "매칭품목": m.get("매칭품목", ""),
                "제목": m.get("제목", ""),
                "날짜": d.get("날짜", ""),
                "브랜드": d.get("브랜드", ""),
                "품명": d.get("품명", ""),
                "내시세": d.get("내시세", ""),
                "원산지": d.get("원산지", ""),
                "창고": d.get("창고", ""),
                "업체명": d.get("업체명", ""),
                "링크": m.get("링크", ""),
                "글쓴이": m.get("글쓴이", ""),
                "작성일": m.get("작성일", ""),
                "글번호": m.get("글번호", ""),
            })
    return pd.DataFrame(rows)


# =============================================
# 거래처 문의 문구 생성 + 클립보드 복사
# =============================================

def build_inquiry(supplier, item, contacts_df):
    """거래처 담당자에게 보낼 재고/단가 문의 문구 생성."""
    name, phone = lookup_contact(contacts_df, supplier)
    if name:
        msg = f"안녕하세요 {name}님, {item} 재고 있으신가요? 최근 단가도 부탁드립니다."
    else:
        msg = f"안녕하세요, {item} 재고 있으신가요? 최근 단가도 부탁드립니다."
    return msg, name, phone


# =============================================
# 카톡 '나에게 보내기' (REST API, 토큰 자동 갱신)
# =============================================

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
    """카톡 '나와의 채팅'으로 메시지 전송. 성공 시 True."""
    if not KAKAO_ENABLED:
        return False
    tok = _kakao_load_token()
    if not tok:
        print("  [카톡] kakao_token.json 없음 → python get_kakao_token.py 먼저 실행")
        return False

    def _send(access):
        return requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {access}"},
            data={
                "template_object": json.dumps({
                    "object_type": "text",
                    "text": text[:190],  # 텍스트 템플릿 200자 제한
                    "link": {"web_url": "https://cafe.daum.net/meetpeople"},
                })
            },
            timeout=10,
        )

    try:
        r = _send(tok.get("access_token", ""))
        if r.status_code == 401 and tok.get("refresh_token"):
            # access token 만료 → refresh token으로 자동 갱신
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
                r = _send(tok["access_token"])
        if r.ok and r.json().get("result_code") == 0:
            return True
        print(f"  [카톡] 전송 실패: {r.status_code} {r.text[:120]}")
        return False
    except Exception as e:
        print(f"  [카톡] 전송 오류: {e}")
        return False


def kakao_send_inquiries(inquiries):
    """문의 문구를 카톡으로 전송 (건당: 안내 1건 + 전달용 문구 1건)."""
    if not KAKAO_ENABLED or not inquiries:
        return
    if not os.path.exists(KAKAO_TOKEN_PATH):
        return  # 토큰 미설정 시 조용히 건너뜀 (클립보드 방식은 그대로 동작)
    sent = 0
    for q in inquiries[:KAKAO_MAX_SEND]:
        header = f"📌 {q['거래처']} / {q['담당자']} / {q['전화번호']} ↓ 아래 문구를 전달하세요"
        ok1 = kakao_send_to_me(header)
        ok2 = kakao_send_to_me(q["문의문구"])
        if ok1 and ok2:
            sent += 1
        time.sleep(0.5)
    if sent:
        extra = f" (외 {len(inquiries) - sent}건은 PC에서)" if len(inquiries) > sent else ""
        print(f"  📱 카톡 '나와의 채팅'으로 문의 {sent}건 전송 완료{extra}")


def extract_request_phrase(title):
    """게시글 제목에서 요청 품목 표현만 추출.
    '네셔널 262 cab 냉장갈비 급구합니다' → '네셔널 262 cab 냉장갈비'"""
    t = str(title).strip()
    for p in ["급구합니다", "구매합니다", "사겠습니다", "구합니다", "삽니다",
              "찾습니다", "문의드립니다", "급구", "구매원합니다", "구매", "문의"]:
        idx = t.find(p)
        if idx > 0:
            t = t[:idx]
            break
    t = t.strip(" .,~!?-·")
    return t if t else str(title).strip()


def handle_inquiries(matched, contacts_df):
    """거래처별로 매칭 건을 묶어 문의 문구 생성 + 첫 번째 문구 클립보드 복사.
    품목 표현은 구매글 제목 그대로 사용."""
    # 거래처(정규화된 회사명 기준) → 요청 표현 목록
    # '나루푸드'와 '(주)나루푸드'는 같은 회사로 묶음
    supplier_groups = {}
    no_supplier_items = []
    for m in matched:
        phrase = extract_request_phrase(m.get("제목", "")) or m["매칭품목"]
        suppliers = m.get("_suppliers", [])
        if not suppliers:
            if m["매칭품목"] not in no_supplier_items:
                no_supplier_items.append(m["매칭품목"])
            continue
        for supplier in suppliers:
            key = normalize_company(supplier)
            g = supplier_groups.setdefault(key, {"표시명": supplier, "phrases": []})
            # 더 정식 표기((주) 포함 등 긴 쪽)를 표시명으로
            if len(str(supplier)) > len(str(g["표시명"])):
                g["표시명"] = supplier
            if phrase not in g["phrases"]:
                g["phrases"].append(phrase)

    for item in no_supplier_items:
        print(f"  ⚠️ [{item}] 시세 시트에 거래처 정보 없음 → 문의 문구 생략")

    if not supplier_groups:
        return

    inquiries = []
    for key, g in supplier_groups.items():
        supplier = g["표시명"]
        phrases = g["phrases"]
        name, phone = lookup_contact(contacts_df, supplier)
        intro = f"안녕하세요 {name}님, {SENDER_NAME}입니다." if name else f"안녕하세요, {SENDER_NAME}입니다."
        if len(phrases) == 1:
            body = f" 혹시 {phrases[0]} 재고 있으신가요? 재고 있으시면 최근 단가 부탁드립니다."
        else:
            rest = ", ".join(phrases[1:])
            body = f" 혹시 {phrases[0]} 재고 있으신가요? 그리고 {rest}도 재고 있으시면 단가 부탁드립니다."
        inquiries.append({
            "거래처": supplier,
            "담당자": name or "(contacts.csv에 없음)",
            "전화번호": phone or "-",
            "품목": ", ".join(phrases),
            "문의문구": intro + body,
        })

    # 담당자 등록된 거래처를 앞으로
    inquiries.sort(key=lambda q: q["전화번호"] == "-")

    print("\n" + "─" * 50)
    print(f"📞 거래처 문의 ({len(inquiries)}개 거래처)")
    shown = inquiries[:MAX_INQUIRIES_DISPLAY]
    for i, q in enumerate(shown, 1):
        print(f"\n  [{i}] {q['거래처']} / {q['담당자']} / {q['전화번호']}")
        print(f"      품목: {q['품목']}")
        print(f"      문구: {q['문의문구']}")
    if len(inquiries) > MAX_INQUIRIES_DISPLAY:
        print(f"\n  ... 외 {len(inquiries) - MAX_INQUIRIES_DISPLAY}개 거래처 (contacts.csv에 담당자를 등록하면 우선 표시)")

    # 첫 번째 문의 문구를 클립보드에 복사
    if CLIPBOARD_OK:
        try:
            pyperclip.copy(inquiries[0]["문의문구"])
            print(f"\n  📋 [1]번 문구가 클립보드에 복사됐어요 → 카톡에 바로 붙여넣기(Ctrl+V)")
        except Exception as e:
            print(f"\n  [클립보드] 복사 실패: {e}")
    else:
        print("\n  [클립보드] pyperclip 미설치 → pip install pyperclip")

    # 문의 목록을 로그 파일에도 기록 (나중에 복사 가능)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            for q in inquiries:
                f.write(f"  문의) {q['거래처']} / {q['담당자']} / {q['전화번호']}\n")
                f.write(f"        {q['문의문구']}\n")
            f.write("\n")
    except Exception:
        pass

    # 카톡 '나와의 채팅'으로도 전송 (폰에서 담당자에게 바로 전달)
    kakao_send_inquiries(inquiries)

    # 번호 입력으로 다음 문구 복사
    interactive_copy(inquiries)
    print("─" * 50)


def interactive_copy(inquiries, timeout=None):
    """번호 입력 → 해당 문의 문구 클립보드 복사.
    Enter만 누르거나 시간이 지나면 모니터링 계속. (모니터링을 막지 않음)"""
    if not CLIPBOARD_OK or len(inquiries) < 2:
        return
    try:
        import msvcrt
    except ImportError:
        return  # 윈도우가 아니면 건너뜀

    if timeout is None:
        timeout = INQUIRY_INPUT_TIMEOUT

    print(f"\n  ⌨️ 번호 입력 + Enter → 해당 문구 복사 / Enter만 → 계속 (입력 없으면 {timeout}초 후 자동 진행)")
    print("  번호: ", end="", flush=True)
    buf = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                print()
                if not buf.strip():
                    print("  ▶ 모니터링 계속")
                    return
                try:
                    i = int(buf.strip())
                    if 1 <= i <= len(inquiries):
                        pyperclip.copy(inquiries[i - 1]["문의문구"])
                        print(f"  📋 [{i}]번 복사됨 ({inquiries[i-1]['거래처']}) → 카톡에 붙여넣으세요")
                    else:
                        print(f"  1~{len(inquiries)} 사이 번호를 입력하세요")
                except ValueError:
                    print("  숫자만 입력하세요")
                buf = ""
                deadline = time.time() + timeout  # 입력하면 대기 시간 연장
                print("  번호: ", end="", flush=True)
            elif ch == "\x08":  # 백스페이스
                if buf:
                    buf = buf[:-1]
                    print("\b \b", end="", flush=True)
            else:
                buf += ch
                print(ch, end="", flush=True)
        else:
            time.sleep(0.05)
    print(f"\n  ⏱ 입력 시간 종료 → 모니터링 계속")


# =============================================
# 안전한 CSV 저장 (엑셀에 파일이 열려 있어도 죽지 않음)
# =============================================

def safe_save_csv(df, path):
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[저장] {path}")
        return True
    except PermissionError:
        print(f"  ⚠️ [저장 건너뜀] {os.path.basename(path)} 가 엑셀에 열려 있어요. 닫으면 다음 확인 때 저장됩니다.")
        return False
    except Exception as e:
        print(f"  ⚠️ [저장 실패] {os.path.basename(path)}: {e}")
        return False


# =============================================
# 소리 알림
# =============================================

def play_alert(count):
    print(f"\n🔔 매칭 {count}건 발견!")
    for _ in range(3):
        winsound.Beep(1000, 300)
        time.sleep(0.2)


# =============================================
# 메인 루프
# =============================================

# =============================================
# 구매↔판매 교차 매칭
# =============================================

def load_accum(path):
    """누적 게시글 파일 로드 + 보관 기한 지난 글 정리."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=["글번호", "제목", "글쓴이", "작성일", "링크", "수집일"])
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        if "수집일" in df.columns:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=ACCUM_RETENTION_DAYS)
            parsed = pd.to_datetime(df["수집일"], errors="coerce")
            df = df[parsed.isna() | (parsed >= cutoff)]
        return df
    except Exception:
        return pd.DataFrame(columns=["글번호", "제목", "글쓴이", "작성일", "링크", "수집일"])


def accumulate_posts(path, accum_df, posts):
    """새 글을 누적 파일에 추가 (글번호 기준 중복 제거)."""
    if not posts:
        return accum_df
    known = set(accum_df["글번호"].astype(str)) if not accum_df.empty else set()
    today = datetime.now().strftime("%Y-%m-%d")
    fresh = [
        {**p, "수집일": today}
        for p in posts if str(p.get("글번호")) not in known
    ]
    if fresh:
        accum_df = pd.concat([accum_df, pd.DataFrame(fresh)], ignore_index=True)
        safe_save_csv(accum_df, path)
    return accum_df


def find_item_in_title(title, items_sorted):
    """제목에서 시세 시트 품목 키워드 찾기 (긴 이름 우선)."""
    t_norm = normalize_text(title)
    for item in items_sorted:
        if normalize_text(item) in t_norm:
            return item
    return None


def extract_signature(title):
    """제목에서 조건 시그니처 추출: 브랜드/원산지/상태/등급/숫자."""
    t_norm = normalize_text(title)
    sig = {"brands": set(), "origins": set(), "states": set(), "grades": set(), "nums": set()}
    for alias, brand in BRAND_ALIASES.items():
        if alias in title:
            sig["brands"].add(normalize_text(brand))
    for key, variants in ORIGIN_ALIASES.items():
        for v in variants:
            if re.search(r"[가-힣]", v):
                if v in title:
                    sig["origins"].add(key)
                    break
            elif len(normalize_text(v)) >= 3 and normalize_text(v) in t_norm:
                sig["origins"].add(key)
                break
    for s in ("냉장", "냉동", "동결"):
        if s in title:
            sig["states"].add(s)
    for alias, engs in GRADE_ALIASES.items():
        if alias in title:
            sig["grades"].add(alias)
        else:
            for e in engs:
                if len(e) >= 3 and normalize_text(e) in t_norm:
                    sig["grades"].add(alias)
                    break
    # 숫자 (EST 번호 등, 2~4자리) - 보너스 점수용
    sig["nums"] = set(re.findall(r"(?<!\d)(\d{2,4})(?!\d)", title))
    return sig


def signatures_conflict(a, b):
    """두 시그니처가 서로 충돌하면 True (매칭 불가)."""
    # 브랜드가 양쪽 다 명시됐는데 겹치지 않음
    if a["brands"] and b["brands"] and not (a["brands"] & b["brands"]):
        return True
    # 원산지 충돌
    if a["origins"] and b["origins"] and not (a["origins"] & b["origins"]):
        return True
    # 냉장 vs 냉동
    if ("냉장" in a["states"] and "냉동" in b["states"]) or ("냉동" in a["states"] and "냉장" in b["states"]):
        return True
    # 동결은 양쪽 모두 명시해야 매칭 (동결 규칙과 동일)
    if ("동결" in a["states"]) != ("동결" in b["states"]):
        return True
    return False


def signature_score(a, b):
    s = 0
    if a["brands"] & b["brands"]:
        s += 3
    if a["origins"] & b["origins"]:
        s += 2
    if a["nums"] & b["nums"]:
        s += 3
    if a["grades"] & b["grades"]:
        s += 2
    if a["states"] & b["states"]:
        s += 1
    return s


def cross_match(new_posts, accum_df, items_sorted, max_candidates=5):
    """새 글(구매 또는 판매)을 반대편 누적 글과 대조.
    반환: [{"글": p, "후보": [(score, row_dict), ...]}]"""
    if not new_posts or accum_df.empty:
        return []
    results = []
    for p in new_posts:
        item = find_item_in_title(p.get("제목", ""), items_sorted)
        if not item:
            continue
        sig = extract_signature(p.get("제목", ""))
        candidates = []
        for _, row in accum_df.iterrows():
            other_title = str(row.get("제목", ""))
            other_item = find_item_in_title(other_title, items_sorted)
            if other_item != item:
                continue
            other_sig = extract_signature(other_title)
            if signatures_conflict(sig, other_sig):
                continue
            candidates.append((signature_score(sig, other_sig), row.to_dict()))
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            results.append({"글": p, "매칭품목": item, "후보": candidates[:max_candidates]})
    return results


def report_cross_matches(results, direction):
    """교차 매칭 결과 출력 + 로그 + CSV.
    direction: '구매→판매' (새 구매글 ↔ 누적 판매글) 또는 '판매→구매'"""
    if not results:
        return
    lines = [f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔁 교차 매칭 ({direction}) {len(results)}건"]
    rows_for_csv = []
    for r in results:
        p = r["글"]
        src_label = "구매글" if direction.startswith("구매") else "판매글"
        dst_label = "판매글" if direction.startswith("구매") else "구매글"
        lines.append(f"  🔁 [{r['매칭품목']}] {src_label}: {p['제목']}")
        lines.append(f"     링크: {p['링크']}")
        for score, row in r["후보"]:
            star = "★" * min(score, 5) if score else ""
            lines.append(f"     ↔ {dst_label}: {row.get('제목','')} {star}")
            lines.append(f"        글쓴이: {row.get('글쓴이','')} / 수집일: {row.get('수집일','')} / {row.get('링크','')}")
            rows_for_csv.append({
                "방향": direction, "매칭품목": r["매칭품목"], "점수": score,
                "새글제목": p.get("제목", ""), "새글링크": p.get("링크", ""),
                "상대제목": row.get("제목", ""), "상대글쓴이": row.get("글쓴이", ""),
                "상대링크": row.get("링크", ""), "상대수집일": row.get("수집일", ""),
            })
    block = "\n".join(lines)
    print(block)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(block + "\n\n")
    except Exception:
        pass
    if rows_for_csv:
        try:
            old = pd.read_csv(CROSS_CSV_PATH, encoding="utf-8-sig") if os.path.exists(CROSS_CSV_PATH) else pd.DataFrame()
            safe_save_csv(pd.concat([old, pd.DataFrame(rows_for_csv)], ignore_index=True), CROSS_CSV_PATH)
        except Exception:
            safe_save_csv(pd.DataFrame(rows_for_csv), CROSS_CSV_PATH)


def main():
    print("=" * 50)
    print(f"미트피플 모니터링 시작  {VERSION}")
    print(f"확인 주기: {CHECK_INTERVAL // 60}분")
    print("=" * 50)

    price_df = load_my_prices()
    contacts_df = load_contacts()

    # 품목 키워드 목록 (긴 이름 우선)
    items_sorted = []
    if "품목" in price_df.columns:
        items_sorted = price_df["품목"].dropna().unique().tolist()
        items_sorted.sort(key=lambda x: len(normalize_text(x)), reverse=True)

    # 구매↔판매 교차 매칭용 누적 데이터
    sell_accum = load_accum(SELL_ACCUM_PATH)
    buy_accum = load_accum(BUY_ACCUM_PATH)
    print(f"[누적] 판매글 {len(sell_accum)}건 / 구매글 {len(buy_accum)}건 (최근 {ACCUM_RETENTION_DAYS}일)")
    notified_sell_ids = set(sell_accum["글번호"].astype(str)) if not sell_accum.empty else set()

    while True:
        # 운영 시간 체크 (USE_OPERATING_HOURS = False면 24시간 동작)
        if USE_OPERATING_HOURS:
            now_time = datetime.now().time()
            start_time = datetime.strptime(OPERATING_START, "%H:%M").time()
            end_time = datetime.strptime(OPERATING_END, "%H:%M").time()

            if not (start_time <= now_time <= end_time):
                print(f"  운영 시간 외 ({now_time.strftime('%H:%M')}) - 대기 중...")
                time.sleep(3600)  # 60분마다 체크
                continue
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] 게시판 확인 중...")

        # contacts.csv는 매번 다시 읽음 (실행 중에 수정해도 바로 반영)
        contacts_df = load_contacts(verbose=False)

        posts = fetch_posts()
        sell_posts = fetch_posts(SELL_BOARD_URL, "HoUW", "판매글")

        # 새 판매글 → 누적 구매글과 교차 매칭
        if sell_posts:
            new_sell = [p for p in sell_posts if str(p.get("글번호")) not in notified_sell_ids]
            if new_sell:
                cross = cross_match(new_sell, buy_accum, items_sorted)
                if cross:
                    play_alert(len(cross))
                    report_cross_matches(cross, "판매→구매")
                for p in new_sell:
                    notified_sell_ids.add(str(p.get("글번호")))
            sell_accum = accumulate_posts(SELL_ACCUM_PATH, sell_accum, sell_posts)

        if posts:
            # CSV 저장 (엑셀에 열려 있으면 건너뛰고 계속 진행)
            df = pd.DataFrame(posts)
            safe_save_csv(df, CSV_PATH)

            # 새 글만 필터
            new_posts = [p for p in posts if p.get("글번호") not in notified_ids]

            if new_posts:
                # 새 구매글 → 누적 판매글과 교차 매칭
                cross = cross_match(new_posts, sell_accum, items_sorted)
                if cross:
                    report_cross_matches(cross, "구매→판매")

                matched = match_posts_with_prices(new_posts, price_df)

                if matched:
                    play_alert(len(matched))
                    lines = []
                    lines.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 매칭 {len(matched)}건")
                    for m in matched:
                        lines.append(f"  ✅ [{m['매칭품목']}] {m['제목']}")
                        lines.append(f"     내 시세: {m['내시세']}")
                        details = m.get("_details", [])
                        if details:
                            shown = details[:MAX_DETAILS_DISPLAY]
                            tag = " 🎯 조건 일치(브랜드/원산지/EST/등급)" if m.get("_refined") else ""
                            lines.append(f"     보유 내역:{tag} (날짜 | 브랜드 | 품명 | 시세 | 원산지 | 창고 | 업체명)")
                            for d in shown:
                                lines.append(f"       - {d['날짜']} | {d['브랜드']} | {d['품명']} | {d['내시세']} | {d.get('원산지','')} | {d['창고']} | {d['업체명']}")
                            if len(details) > MAX_DETAILS_DISPLAY:
                                lines.append(f"       ... 외 {len(details) - MAX_DETAILS_DISPLAY}건 (CSV 참조)")
                        elif m.get("거래처"):
                            lines.append(f"     거래처: {m['거래처']}")
                        lines.append(f"     링크: {m['링크']}")

                    block = "\n".join(lines)
                    print(block)
                    # 로그 파일에도 기록 (화면에서 밀려도 확인 가능)
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            f.write(block + "\n\n")
                    except Exception:
                        pass

                    # 거래처 문의 문구 생성 + 클립보드 복사
                    handle_inquiries(matched, contacts_df)

                    # CSV 저장 (매칭품목,제목,날짜,브랜드,품명,내시세,창고,업체명,링크 형식)
                    save_df = matched_to_rows(matched)
                    safe_save_csv(save_df, MATCHED_CSV_PATH)
                else:
                    print("  매칭 품목 없음")

                for p in new_posts:
                    notified_ids.add(p.get("글번호"))

            # 구매글도 누적 (판매글 교차 매칭용)
            buy_accum = accumulate_posts(BUY_ACCUM_PATH, buy_accum, posts)

        else:
            print("  게시글 수집 실패 (쿠키 확인 필요)")

        print(f"  다음 확인: {CHECK_INTERVAL // 60}분 후")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()