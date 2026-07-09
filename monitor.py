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
    "엔비": "NB",
    "NB": "NB",
    "AMH": "AMH",
    "에이엠에이치": "AMH",
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
    "호멜": "HORMEL",
    "홀멜": "HORMEL",
    "팜플로나": "PAMPLONA",
    "메이플": "MAPLE",
    "킬코이": "KILCOY",
    "코엑스카": "COEXCA",
    "팜랜드": "FARMLAND",
}

# 등급 별칭 사전: 게시글의 한글 표기 → 시트의 등급 표기 후보
GRADE_ALIASES = {
    "프라임": ["PRIME", "PR"],
    "초이스": ["CHOICE", "CH"],
    "셀렉트": ["SELECT", "SEL"],
    "노롤": ["NO ROLL", "NOROLL", "NR"],
}

# 알려진 등급 코드 (제목에서 '단어'로 정확히 등장할 때만 등급 조건으로 인정)
# 호주(GF/GR/YP/S/A/MSA)와 미국(PRIME/CHOICE/CAB/SELECT) 체계가 섞여 있어
# 부분 문자열(A가 CAB에 걸림)이 아니라 정확 일치로 판정해야 함
KNOWN_GRADE_CODES = [
    "PRIME", "CHOICE", "SELECT", "CAB", "NOROLL", "NR",
    "MSA", "GF", "GR", "YP", "YG", "PS", "SS",
    "MB1", "MB2", "MB3", "MB4", "MB5", "MB6", "MB7", "MB8", "MB9", "MB",
    "S", "A", "B", "PR", "CH", "SEL",
]
# 같은 계열로 취급하면 안 되는(서로 배타적인) 등급들 — 참고용
GRADE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,4}\d{0,2})(?![A-Za-z0-9])")


def grades_in_title(title):
    """제목에서 '단어 경계'로 등장하는 알려진 등급 코드만 추출 (대문자 기준)."""
    found = set()
    upper = str(title).upper()
    known = {normalize_text(g) for g in KNOWN_GRADE_CODES}
    for mm in GRADE_TOKEN_RE.finditer(upper):
        tok = normalize_text(mm.group(1))
        if tok in known:
            found.add(tok)
    return found

# 재고에 이 단어가 붙어 있으면, 게시글에 명시됐을 때만 매칭
# 형식: "재고 표기": [게시글에서 인정되는 표기들]
# 예: 돈사골 재고는 글에 '돈사골' 또는 '돼지사골'이 있어야 매칭 ('사골 구합니다'에는 안 나옴)
QUALIFIERS_REQUIRE_MENTION = {
    "동결": ["동결"],
    "돈사골": ["돈사골", "돼지사골"],
}

# 시트 브랜드 열에서 로드하는 브랜드 사전 (교차 매칭 시 서로 다른 브랜드 차단)
SHEET_BRANDS = set()

# 거래가 끝난 글 제외 키워드
DONE_WORDS = ["판매완료", "구매완료", "거래완료", "완판", "마감"]


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

# 문의 문구 마무리 (연락 유도 + 오픈카톡 링크)
CLOSING_LINE = "연락 함 해보세요. https://open.kakao.com/o/g0Zywnmd"

# 매칭 후 문의 번호 입력 대기 시간(초) - 시간 내 입력 없으면 모니터링 계속
INQUIRY_INPUT_TIMEOUT = 120

# 카톡 '나에게 보내기' 연동 (get_kakao_token.py 먼저 1회 실행)
KAKAO_ENABLED = True
KAKAO_TOKEN_PATH = os.path.join(BASE_DIR, "kakao_token.json")
KAKAO_MAX_SEND = 3  # 매칭 1회당 카톡으로 보낼 최대 문의 건수

# 매칭 결과 로그 파일 (화면에서 밀려도 여기서 다시 볼 수 있음)
LOG_PATH = os.path.join(BASE_DIR, "monitor_log.txt")

# 구매↔판매 교차 매칭은 sales_monitor.py 담당 (여기서는 사용 안 함)

VERSION = "v3.0 (구매 전용 - 교차매칭은 sales_monitor.py)"

# 이미 알림을 보낸 글번호 기록
notified_ids = set()

# =============================================
# 다음 카페 쿠키 설정
# =============================================
# 크롬 → 미트피플 로그인 → F12 → Application → Cookies → cafe.daum.net
# 각 쿠키 이름 클릭 → 하단에서 전체 값 복사
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

        # 브랜드 사전 구축 (교차 매칭용)
        brand_col = cols.get("브랜드")
        if brand_col:
            for b in df[brand_col].dropna().astype(str).str.strip().unique():
                bn = normalize_text(b)
                if len(bn) >= 3:  # 짧은 표기 오탐 방지
                    SHEET_BRANDS.add(bn)

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


PORK_MARKERS = ["돼지", "돈"]
BEEF_MARKERS = ["한우", "와규", "비프", "beef", "우사골", "소사골", "거세", "앵거스", "육우"]


def detect_species(text):
    """텍스트에서 소/돼지 구분. 확실할 때만 반환."""
    t = normalize_text(text)
    pork = any(normalize_text(m) in t for m in PORK_MARKERS)
    beef = any(normalize_text(m) in t for m in BEEF_MARKERS)
    if pork and not beef:
        return "돈"
    if beef and not pork:
        return "우"
    return None


def detect_origins(title):
    """제목에서 원산지 감지. 한글 부분 문자열 오탐 방지:
    '미국산'의 '국산'처럼 앞에 다른 한글이 붙은 경우는 제외."""
    found = set()
    t_norm = normalize_text(title)
    for key, variants in ORIGIN_ALIASES.items():
        for v in variants:
            if re.search(r"[가-힣]", v):
                # 앞에 한글이 붙어 있으면 다른 단어의 일부 ('미국산'의 '국산')
                if re.search(r"(?<![가-힣])" + re.escape(v) + r"(?:산)?(?![가-힣])", title):
                    found.add(key)
                    break
            elif len(normalize_text(v)) >= 3 and normalize_text(v) in t_norm:
                found.add(key)
                break
    return found


def origin_wanted_set(keys):
    """원산지 키들의 정확 일치용 표기 집합 (변형 + '산' 접미형)."""
    wanted = set()
    for key in keys:
        for v in ORIGIN_ALIASES.get(key, []):
            vn = normalize_text(v)
            wanted.add(vn)
            wanted.add(vn + "산")
    return wanted


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
        # 긴 별칭 우선 + 단어 경계로 부분 포함 오탐 방지 (엔비 vs 엔비피, NB vs NBP)
        for alias, brand in sorted(BRAND_ALIASES.items(), key=lambda kv: -len(kv[0])):
            an = normalize_text(alias)
            if re.fullmatch(r"[a-z0-9]+", an):
                # 영숫자 별칭: 앞뒤로 영숫자가 안 붙어야 함
                if re.search(r"(?<![a-z0-9])" + re.escape(an) + r"(?![a-z0-9])", t_norm):
                    wanted.add(normalize_text(brand))
            elif re.search(r"[가-힣]", alias):
                # 한글 별칭: 뒤에 한글이 더 붙으면 다른 단어 (엔비 ≠ 엔비피)
                if re.search(re.escape(alias) + r"(?![가-힣])", title):
                    wanted.add(normalize_text(brand))
            elif alias in title:
                wanted.add(normalize_text(brand))
        # 시트 브랜드명이 제목에 직접 등장 (NBP, TYS 등 영문 표기)
        # 단어 경계로 매칭해서 NB가 NBP에 딸려오는 것 방지
        for bv in rows[brand_col].dropna().astype(str).unique():
            bvn = norm_or_empty(bv)
            if len(bvn) < 2:
                continue
            # 영숫자 코드는 단어 경계로, 한글 포함은 부분 매칭 허용
            if re.fullmatch(r"[a-z0-9]+", bvn):
                if re.search(r"(?<![a-z0-9])" + re.escape(bvn) + r"(?![a-z0-9])", t_norm):
                    wanted.add(bvn)
            elif bvn in t_norm:
                wanted.add(bvn)
        if wanted:
            def brand_ok(x):
                xn = norm_or_empty(x)
                if not xn:
                    return False
                # 정확 일치 우선. 부분 포함은 한쪽이 4자 이상일 때만 (오탐 방지)
                for w in wanted:
                    if w == xn:
                        return True
                    if (w in xn or xn in w) and min(len(w), len(xn)) >= 4:
                        return True
                return False
            sub = refined[refined[brand_col].astype(str).apply(brand_ok)]
            if not sub.empty:
                refined = sub
                applied = True
            else:
                names = ", ".join(sorted(w.upper() for w in wanted))
                notes.append(f"요청 브랜드({names}) 미보유 — 아래는 다른 브랜드 보유 내역")

    # ── 1.5) 원산지 필터 (독일산, 미국산, 국산 등) ─────
    origin_col = cols.get("원산지")
    if origin_col:
        origin_keys = detect_origins(title)
        if origin_keys:
            wanted_exact = origin_wanted_set(origin_keys)
            def origin_ok(x):
                return norm_or_empty(x) in wanted_exact
            sub = refined[refined[origin_col].astype(str).apply(origin_ok)]
            if not sub.empty:
                refined = sub
                applied = True
            else:
                notes.append(f"요청 원산지({', '.join(sorted(origin_keys))}) 미보유")

    # ── 1.7) 축종(소/돼지) 필터 ─────────────────
    title_species = detect_species(title)
    if title_species:
        cols_for_species = [c for c in [name_col, "품목", brand_col] if c and c in refined.columns]

        def row_species(row):
            return detect_species(" ".join(str(row.get(c, "")) for c in cols_for_species))

        species_vals = refined.apply(row_species, axis=1)
        # 반대 축종이 확실한 행만 제거 (판별 안 되는 행은 유지)
        opposite = "우" if title_species == "돈" else "돈"
        sub = refined[species_vals != opposite]
        if not sub.empty:
            if len(sub) < len(refined):
                applied = True
            refined = sub
        else:
            label = "돼지" if title_species == "돈" else "소"
            notes.append(f"요청 축종({label}) 재고 없음")

    # ── 2) EST 번호 필터 ────────────────────────
    # EST 코드 구분: 245C ≠ 245E ≠ 245. EXCEL 갈비처럼 규격 글자(K/E/M/R)만 쓰기도 함.
    # 시트 EST 열에 실제 존재하는 코드/글자만 인식 대상으로 삼아 오탐 방지.
    if est_col:
        title_up = str(title).upper()

        def est_tokens(cell):
            # 시트 EST 값을 토큰으로 분리, 괄호 안 중량은 제거 (86K(25.5) → 86K)
            toks = set()
            cleaned = re.sub(r"\([^)]*\)", " ", str(cell).upper())
            for t in re.split(r"[\s/,]+", cleaned):
                t = t.strip()
                if re.fullmatch(r"\d{2,4}[A-Z]{0,2}", t):    # 숫자형 코드 (245C, 86K)
                    toks.add(t)
                elif re.fullmatch(r"[A-Z]{1,2}", t):          # 글자형 코드 (K, E, M)
                    toks.add(t)
            return toks

        # 시트에 실제 존재하는 EST 토큰 모음 + 규격 글자(끝 글자) 모음
        all_sheet_toks = set()
        sheet_suffix_letters = set()   # 86K → K, 86E → E ...
        for ev in refined[est_col].dropna().astype(str).unique():
            for tk in est_tokens(ev):
                all_sheet_toks.add(tk)
                mm = re.fullmatch(r"\d{2,4}([A-Z]{1,2})", tk)
                if mm:
                    sheet_suffix_letters.add(mm.group(1))
                elif re.fullmatch(r"[A-Z]{1,2}", tk):
                    sheet_suffix_letters.add(tk)

        # 제목에서 요청 코드 추출: 숫자형(245C/86K) + 시트에 있는 규격 글자 단독(K/E/M)
        wanted_ests = set()      # 숫자형 코드
        wanted_letters = set()   # 글자형 규격 코드
        for mm in re.finditer(r"(?<![A-Z0-9])(\d{2,4}[A-Z]{0,2})(?![A-Z0-9])", title_up):
            wanted_ests.add(mm.group(1))
        # 등급 글자(A/S/CH 등)와 혼동 방지: 등급으로 쓰이는 글자는 규격에서 제외
        grade_letters = {normalize_text(g).upper() for g in KNOWN_GRADE_CODES if len(g) <= 2}
        for mm in re.finditer(r"(?<![A-Z0-9])([A-Z]{1,2})(?![A-Z0-9])", title_up):
            letter = mm.group(1)
            if letter in sheet_suffix_letters and letter not in grade_letters:
                wanted_letters.add(letter)

        if wanted_ests or wanted_letters:
            exact = {w for w in wanted_ests if re.search(r"[A-Z]", w)}
            numeric_only = {w for w in wanted_ests if not re.search(r"[A-Z]", w)}

            def est_ok(cell):
                cell_toks = est_tokens(cell)
                if not cell_toks:
                    return False
                if exact & cell_toks:
                    return True
                # 글자형 요청(K) → 셀 코드의 끝 글자가 일치 (86K, 또는 K 단독)
                for L in wanted_letters:
                    for ct in cell_toks:
                        if ct == L or re.fullmatch(r"\d{2,4}" + re.escape(L), ct):
                            return True
                # 숫자만 요청(245) → 같은 숫자 계열 전체
                for n in numeric_only:
                    for ct in cell_toks:
                        if re.match(r"^" + re.escape(n) + r"[A-Z]{0,2}$", ct):
                            return True
                return False

            # 시트에 요청 코드가 실제 존재할 때만 필터 적용
            relevant = bool(exact & all_sheet_toks) or bool(wanted_letters)
            if not relevant:
                for n in numeric_only:
                    if any(re.match(r"^" + re.escape(n) + r"[A-Z]{0,2}$", ct) for ct in all_sheet_toks):
                        relevant = True
                        break

            if relevant:
                sub = refined[refined[est_col].astype(str).apply(est_ok)]
                if not sub.empty:
                    refined = sub
                    applied = True
                else:
                    req = sorted(wanted_ests | wanted_letters)
                    notes.append(f"요청 EST({', '.join(req)}) 미보유 — 아래는 다른 EST 보유 내역")

    # ── 3) 등급 필터 (호주 GF/GR/YP/S/A, 미국 PRIME/CHOICE/CAB 등) ─────
    # 등급 코드는 정확 일치로 판정 (A가 CAB에 부분 포함되는 오염 방지)
    if grade_col:
        wanted_grades = set()   # 정확 일치로 비교할 등급 토큰들
        cue_names = []
        # (a) 제목에 '단어'로 등장하는 알려진 등급 코드 (A, S, GF, PRIME 등)
        title_grades = grades_in_title(title)
        if title_grades:
            wanted_grades |= title_grades
            cue_names.extend(sorted(title_grades))
        # (b) 한글 등급 표기 → 영문 후보 (프라임 → PRIME/PR)
        for alias, engs in GRADE_ALIASES.items():
            if alias in title:
                cue_names.append(alias)
                wanted_grades.update(normalize_text(e) for e in engs)
                wanted_grades.add(normalize_text(alias))

        if wanted_grades:
            def grade_tokens(cell):
                # 시트 등급값을 토큰으로 분리 (예: 'GF', 'A/S', '640/1912 GF')
                return {normalize_text(t) for t in re.split(r"[\s/,+()]+", str(cell).upper()) if t}

            def grade_ok(x):
                cell_tokens = grade_tokens(x)
                if not cell_tokens:
                    return False
                # 요청 등급 중 하나라도 셀 토큰과 '정확히' 일치해야 통과
                return bool(cell_tokens & wanted_grades)

            sub = refined[refined[grade_col].astype(str).apply(grade_ok)]
            if not sub.empty:
                refined = sub
                applied = True
            else:
                notes.append(f"요청 등급({', '.join(dict.fromkeys(cue_names))}) 미보유 — 아래는 다른 등급 보유 내역")

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
    est_col = cols.get("EST")
    grade_col = cols.get("등급")

    group_cols = [c for c in [brand_col, name_col, est_col, grade_col, origin_col, wh_col] if c]
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
            "EST": clean(d.get(est_col, "")) if est_col else "",
            "등급": clean(d.get(grade_col, "")) if grade_col else "",
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
        # 거래가 끝난 글은 매칭 제외
        if any(w in title for w in DONE_WORDS):
            continue
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
                "EST": d.get("EST", ""),
                "등급": d.get("등급", ""),
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

KAKAO_LOCK_PATH = KAKAO_TOKEN_PATH + ".lock"


def _kakao_try_lock():
    """토큰 갱신 잠금 획득 (다른 프로그램과 동시 갱신 방지)."""
    try:
        # 60초 넘은 잠금은 비정상 종료 잔재로 보고 제거
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
        return True  # 잠금 실패 시 그냥 진행 (기능 우선)


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
        if r.status_code == 401:
            # 다른 프로그램(sales_monitor)이 이미 갱신했을 수 있으니 디스크 재확인
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
                # 다른 프로그램이 갱신 중 → 잠시 기다렸다 새 토큰으로 재시도
                time.sleep(3)
                fresh = _kakao_load_token() or tok
                r = _send(fresh.get("access_token", ""))
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


QTY_PATTERN = re.compile(r"약?\s*(\d+(?:\.\d+)?)\s*(톤|키로|kg|KG|박스|팔레트|파렛트)")
PHONE_PATTERN = re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")


def extract_quantity(title):
    """제목에서 수량 추출: '2톤 구매합니다' → '약 2톤'"""
    mm = QTY_PATTERN.search(str(title))
    if mm:
        return f"약 {mm.group(1)}{mm.group(2)}"
    return ""


def extract_phone(*texts):
    """닉네임/제목에 전화번호가 있으면 추출."""
    for t in texts:
        mm = PHONE_PATTERN.search(str(t))
        if mm:
            return mm.group(0)
    return ""


def josa_eul(word):
    """을/를 조사 선택 (마지막 글자 받침 기준)."""
    w = str(word).strip()
    if not w:
        return "를"
    ch = w[-1]
    if "가" <= ch <= "힣":
        return "을" if (ord(ch) - 0xAC00) % 28 else "를"
    return "를"


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
    """거래처별로 매칭 건을 묶어 '구매자 연결형' 문의 문구 생성 + 클립보드 복사.
    예: 귀사가 팔고 계신 메이플 목전지를 아이엠프레쉬 이상인님이 약 2톤 구매를 원하고 있습니다."""
    # 거래처(정규화된 회사명 기준) → 매칭 건 목록
    supplier_groups = {}
    no_supplier_items = []
    for m in matched:
        title = m.get("제목", "")
        raw_phrase = extract_request_phrase(title) or m["매칭품목"]
        qty = extract_quantity(title)
        phrase = QTY_PATTERN.sub("", raw_phrase).strip(" ,·-") or m["매칭품목"]  # 수량은 따로 표기
        buyer = str(m.get("글쓴이", "")).strip()
        phone = extract_phone(m.get("글쓴이", ""), title)
        if phone:
            buyer = PHONE_PATTERN.sub("", buyer).strip(" -·,/()")  # 닉네임 속 번호는 괄호로만 표기
        # 영문 아이디 닉네임(barbar 등)은 '미트피플 회원 barbar님' 형태로
        if buyer and not re.search(r"[가-힣]", buyer):
            buyer = f"미트피플 회원 {buyer}"
        suppliers = m.get("_suppliers", [])
        if not suppliers:
            if m["매칭품목"] not in no_supplier_items:
                no_supplier_items.append(m["매칭품목"])
            continue
        entry = {"품목표현": phrase, "구매자": buyer, "전화": phone, "수량": qty}
        for supplier in suppliers:
            key = normalize_company(supplier)
            g = supplier_groups.setdefault(key, {"표시명": supplier, "건들": []})
            if len(str(supplier)) > len(str(g["표시명"])):
                g["표시명"] = supplier
            if not any(e["품목표현"] == phrase for e in g["건들"]):
                g["건들"].append(entry)

    for item in no_supplier_items:
        print(f"  ⚠️ [{item}] 시세 시트에 거래처 정보 없음 → 문의 문구 생략")

    if not supplier_groups:
        return

    inquiries = []
    for key, g in supplier_groups.items():
        supplier = g["표시명"]
        items = g["건들"]
        name, phone = lookup_contact(contacts_df, supplier)
        intro = f"안녕하세요 {name}님, {SENDER_NAME}입니다." if name else f"안녕하세요, {SENDER_NAME}입니다."

        first = items[0]
        buyer_part = f"{first['구매자']}님" if first["구매자"] else "구매자가"
        if first["전화"]:
            buyer_part += f"({first['전화']})"
        qty_part = f" {first['수량']}" if first["수량"] else ""
        body = (f" 귀사가 팔고 계신 {first['품목표현']}{josa_eul(first['품목표현'])} "
                f"{buyer_part}이{qty_part} 구매를 원하고 있습니다.")

        for e in items[1:]:
            b = f"{e['구매자']}님" if e["구매자"] else "다른 구매자가"
            if e["전화"]:
                b += f"({e['전화']})"
            q = f" {e['수량']}" if e["수량"] else ""
            body += f" 또한 {e['품목표현']}{'은' if josa_eul(e['품목표현'])=='을' else '는'} {b}이{q} 찾고 있습니다."

        body += f" {CLOSING_LINE}"

        inquiries.append({
            "거래처": supplier,
            "담당자": name or "(contacts.csv에 없음)",
            "전화번호": phone or "-",
            "품목": ", ".join(e["품목표현"] for e in items),
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
    # 컨트롤 패널 등에서 실행돼 콘솔 입력이 없으면 건너뜀
    try:
        import sys as _sys
        if not _sys.stdin or not _sys.stdin.isatty():
            return
    except Exception:
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

def main():
    print("=" * 50)
    print(f"미트피플 모니터링 시작  {VERSION}")
    print(f"확인 주기: {CHECK_INTERVAL // 60}분")
    print("=" * 50)

    price_df = load_my_prices()
    contacts_df = load_contacts()


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

        if posts:
            # CSV 저장 (엑셀에 열려 있으면 건너뛰고 계속 진행)
            df = pd.DataFrame(posts)
            safe_save_csv(df, CSV_PATH)

            # 새 글만 필터
            new_posts = [p for p in posts if p.get("글번호") not in notified_ids]

            if new_posts:
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
                            lines.append(f"     보유 내역:{tag} (날짜 | 브랜드 | 품명 | 시세 | EST | 등급 | 원산지 | 창고 | 업체명)")
                            for d in shown:
                                lines.append(f"       - {d['날짜']} | {d['브랜드']} | {d['품명']} | {d['내시세']} | {d.get('EST','')} | {d.get('등급','')} | {d.get('원산지','')} | {d['창고']} | {d['업체명']}")
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


        else:
            print("  게시글 수집 실패 (쿠키 확인 필요)")

        print(f"  다음 확인: {CHECK_INTERVAL // 60}분 후")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()