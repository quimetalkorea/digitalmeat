"""
미트피플 판매게시판 ↔ 구매게시판 크로스 매칭 (monitor.py와 별도 운영)
- 판매게시판(HoUW) 글을 sales_posts.csv에 누적
- 구매게시판(HoTs) 글을 buy_posts_archive.csv에 누적
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

VERSION = "v1.0"

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

BUY_BOARD_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoTs"    # 구매게시판
SELL_BOARD_URL = "https://cafe.daum.net/_c21_/bbs_list?grpid=Mbmh&fldid=HoUW"   # 판매게시판

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SALES_CSV = os.path.join(BASE_DIR, "sales_posts.csv")            # 판매글 누적
BUY_CSV = os.path.join(BASE_DIR, "buy_posts_archive.csv")        # 구매글 누적
PAIRS_CSV = os.path.join(BASE_DIR, "matched_pairs.csv")          # 매칭된 짝
LOG_PATH = os.path.join(BASE_DIR, "sales_monitor_log.txt")

CHECK_INTERVAL = 10 * 60      # 확인 주기 (초)
SALES_MAX_AGE_DAYS = 14       # 판매글 유효 기간 (오래된 판매글은 매칭 제외)
BUY_MAX_AGE_DAYS = 7          # 구매글 유효 기간

USE_OPERATING_HOURS = False   # True면 아래 시간에만 동작
OPERATING_START = "09:00"
OPERATING_END = "17:30"

# 카톡 '나에게 보내기' (monitor.py와 같은 토큰 파일 사용)
KAKAO_ENABLED = True
KAKAO_TOKEN_PATH = os.path.join(BASE_DIR, "kakao_token.json")
KAKAO_MAX_SEND = 3

# =============================================
# 다음 카페 쿠키 (monitor.py와 동일하게 유지)
# =============================================
DAUM_COOKIES = {
    "HTS": "XUwrpyOXxWx9TFx_NPqLqw00",
    "JSESSIONID": "FABAC0B35048CDFFA8426677DAE9BA60",
    "PROF": "0603012032024064024192UiQPJk7X-6w0mlxoempuua9QsdGeNIag3O1dpXj_gbkQKuZP3z7wEl2bxriNh5SdkQ00LYYSA9A1_cGNLCyhCzrwOgj61xkRhz7hDHbz3NH3TPhotxsi_HxV.ZeBXdFBFd3ofIauQlo8OTLLnHHY.bHDTw00vcQtS7zilQDLGZ8G3iSvt1Okkw1SdF7si3NZE2RfySxeElXDnNK2.GGi-FMJ1bLfiXZFiEe7R2buqNP6DuNTyApBuUCkhis3ZM7CbYtTS4v_Cn81JJotyokPqTzBHRDQjyBXmYEKGlxBdC1p1XiyLXO3CYrQvN1gPN.ltqjW8uhEX7nLHx4ANm125NdGii-7",
    "ALID": "KN6XC2KuL5bGq0vzhLQhPSZvFgslAvu4jPIHdBwWDl5Hn4fnDEnIN5oszMeiixP2w999UI",
    "HM_CU": "562UzJ5yPrq",
}

# =============================================
# 매칭 사전 (monitor.py와 동일한 규칙)
# =============================================

BRAND_ALIASES = {
    "네셔널": "NBP", "내셔널": "NBP", "엔비피": "NBP",
    "타이슨": "TYSON", "아이비피": "IBP",
    "스위프트": "SWIFT", "제이비에스": "JBS",
    "엑셀": "EXCEL", "카길": "CARGILL",
    "티스": "TYS", "수카네": "SUKARNE",
    "프리고소르노": "FRIGOSORNO", "아그로수퍼": "AGROSUPER",
    "스미스필드": "SMITHFIELD", "시보드": "SEABOARD",
    "하이라이프": "HYLIFE",
    "데니쉬": "DANISH CROWN", "다니쉬": "DANISH CROWN",
    "뎀코타": "DEMKOTA", "덴코타": "DEMKOTA",
    "크릭스톤": "CREEKSTONE", "크릭스턴": "CREEKSTONE",
    "헬라비": "HELLABY", "그레이터오마하": "GREATER OMAHA",
    "쇼케이스": "SHOWCASE",
}

ORIGIN_ALIASES = {
    "국산": ["국산", "국내산", "국내", "한국"],
    "미국": ["미국", "USA"],
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


def normalize_text(s):
    return str(s).replace(" ", "").lower()


# =============================================
# 품목 사전 (구글 시트에서 로드)
# =============================================

SHEET_BRANDS = set()  # 시트 브랜드 열에서 로드한 브랜드 사전 (충돌 감지 강화)


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
        if brand_col:
            for b in df[brand_col].dropna().astype(str).str.strip().unique():
                bn = normalize_text(b)
                if len(bn) >= 3:  # 너무 짧은 표기는 오탐 방지 위해 제외
                    SHEET_BRANDS.add(bn)
        print(f"[사전] 품목 {len(items)}개 / 브랜드 {len(SHEET_BRANDS)}개 로드 완료")
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
        return pd.DataFrame(columns=["글번호", "제목", "글쓴이", "작성일", "링크", "수집일시"])
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        return df
    except Exception as e:
        print(f"[누적] {os.path.basename(path)} 읽기 실패: {e}")
        return pd.DataFrame(columns=["글번호", "제목", "글쓴이", "작성일", "링크", "수집일시"])


def append_new_posts(path, posts):
    """새 글만 누적 파일에 추가하고, 새 글 목록 반환."""
    archive = load_archive(path)
    known = set(archive["글번호"].astype(str)) if not archive.empty else set()
    new_posts = [p for p in posts if str(p["글번호"]) not in known]
    if new_posts:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_df = pd.DataFrame(new_posts)
        new_df["수집일시"] = now
        merged = pd.concat([archive, new_df], ignore_index=True)
        try:
            merged.to_csv(path, index=False, encoding="utf-8-sig")
        except PermissionError:
            print(f"  ⚠️ {os.path.basename(path)} 가 엑셀에 열려 있어 저장 건너뜀")
    return new_posts, load_archive(path)


def recent_rows(archive, max_age_days):
    """수집일시 기준 최근 N일 이내 글만."""
    if archive.empty:
        return archive
    cutoff = datetime.now() - timedelta(days=max_age_days)
    parsed = pd.to_datetime(archive["수집일시"], errors="coerce")
    return archive[parsed >= cutoff]


# =============================================
# 제목 특징 추출 및 짝 매칭
# =============================================

def extract_features(title):
    t_norm = normalize_text(title)
    feats = {"brands": set(), "origins": set(), "ests": set(), "state": None, "quals": set()}

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

    for key, variants in ORIGIN_ALIASES.items():
        for v in variants:
            if re.search(r"[가-힣]", v):
                if v in title:
                    feats["origins"].add(key)
                    break
            elif len(normalize_text(v)) >= 3 and normalize_text(v) in t_norm:
                feats["origins"].add(key)
                break

    # EST로 보이는 숫자 (수량/단위 숫자는 제외)
    for mm in re.finditer(r"(?<!\d)(\d{2,4})(?!\d)", title):
        tail = title[mm.end():mm.end() + 3]
        if re.match(r"\s*(톤|키로|kg|KG|박스|원|개|팔|판|년|월|일|시)", tail):
            continue
        feats["ests"].add(mm.group(1))

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


def pair_match(buy_title, sell_title, items):
    """구매글-판매글 짝 판정. 매칭이면 (점수, 근거태그들), 아니면 None."""
    bi = effective_item(buy_title, items)
    si = effective_item(sell_title, items)
    if not bi or not si:
        return None
    # 품목은 정확히 같아야 함 ('삼겹'과 '삼겹양지'는 다른 부위)
    if normalize_text(bi) != normalize_text(si):
        return None
    item_name = bi

    fb = extract_features(buy_title)
    fs = extract_features(sell_title)

    # 충돌 조건 → 탈락
    if fb["brands"] and fs["brands"] and not (fb["brands"] & fs["brands"]):
        return None
    if fb["origins"] and fs["origins"] and not (fb["origins"] & fs["origins"]):
        return None
    if fb["state"] and fs["state"] and fb["state"] != fs["state"]:
        return None
    if fb["quals"] != fs["quals"]:
        return None

    score = 1
    tags = [f"품목:{item_name}"]
    if fb["brands"] & fs["brands"]:
        score += 3
        tags.append("브랜드 일치")
    if fb["origins"] & fs["origins"]:
        score += 2
        tags.append("원산지 일치")
    if fb["ests"] and fs["ests"] and (fb["ests"] & fs["ests"]):
        score += 3
        tags.append(f"EST {', '.join(sorted(fb['ests'] & fs['ests']))} 일치")
    if fb["state"] and fb["state"] == fs["state"]:
        score += 1
        tags.append(fb["state"])
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
    """구매글 목록 x 판매글 목록 매칭. 이미 알림 보낸 짝은 제외."""
    pairs = []
    for _, b in buy_rows.iterrows():
        for _, s in sell_rows.iterrows():
            key = (str(b["글번호"]), str(s["글번호"]))
            if key in seen_pairs:
                continue
            result = pair_match(str(b["제목"]), str(s["제목"]), items)
            if result:
                score, tags = result
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
                    "발견일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                seen_pairs.add(key)
    pairs.sort(key=lambda p: p["점수"], reverse=True)
    return pairs


# =============================================
# 카톡 '나에게 보내기' (monitor.py와 동일)
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
        if r.status_code == 401 and tok.get("refresh_token"):
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
    for p in pairs:
        strong = " 🎯" if p["점수"] >= 4 else ""
        lines.append(f"  🔗{strong} ({p['근거']})")
        lines.append(f"     구매: {p['구매제목']}")
        lines.append(f"           {p['구매링크']}")
        lines.append(f"     판매: {p['판매제목']}  (판매자: {p['판매글쓴이']})")
        lines.append(f"           {p['판매링크']}")
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

    # 카톡 전송
    sent = 0
    for p in pairs[:KAKAO_MAX_SEND]:
        msg = f"🔗 판매↔구매 매칭!\n구매: {p['구매제목']}\n판매: {p['판매제목']} ({p['판매글쓴이']})"
        if kakao_send_to_me(msg):
            sent += 1
        time.sleep(0.5)
    if sent:
        print(f"  📱 카톡으로 매칭 {sent}건 전송 완료")


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