"""
미트피플 매칭 글에서 연락처 추출
- latest_posts_matched.csv 읽기
- 각 글 본문에서 전화번호 추출
- contacts.csv 저장
"""

import requests
import pandas as pd
import re
import os
import time
from datetime import datetime

# =============================================
# 설정
# =============================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MATCHED_CSV_PATH = os.path.join(BASE_DIR, "latest_posts_matched.csv")
CONTACTS_CSV_PATH = os.path.join(BASE_DIR, "contacts.csv")

# 다음 카페 쿠키 (monitor.py와 동일하게)
DAUM_COOKIES = {
    "HTS": "여기에_HTS_값",
    "JSESSIONID": "여기에_JSESSIONID_값",
    "PROF": "여기에_PROF_값",
    "ALID": "여기에_ALID_값",
    "HM_CU": "여기에_HM_CU_값",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://cafe.daum.net/meetpeople",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# =============================================
# 전화번호 추출
# =============================================

def extract_phone_numbers(text):
    """본문에서 전화번호 추출"""
    patterns = [
        r'0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}',   # 010-1234-5678
        r'0\d{9,10}',                                # 01012345678
    ]
    phones = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        phones.extend(found)

    # 중복 제거 및 정리
    phones = list(set([re.sub(r'[\s.]', '-', p) for p in phones]))
    return ', '.join(phones) if phones else ""


def fetch_article_content(url):
    """게시글 본문 가져오기"""
    try:
        # 게시글 URL을 내부 URL로 변환
        # https://cafe.daum.net/meetpeople/HoTs/93240
        # → https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoTs&dataid=93240
        dataid = url.split('/')[-1]
        article_url = f"https://cafe.daum.net/_c21_/bbs_read?grpid=Mbmh&fldid=HoTs&dataid={dataid}"

        resp = requests.get(article_url, headers=HEADERS, cookies=DAUM_COOKIES, timeout=15)
        resp.encoding = 'utf-8'

        # JavaScript에서 본문 텍스트 추출
        text = resp.text

        # 본문 내용 추출 (다음 카페 본문은 article_content 또는 본문 div에 있음)
        content_pattern = re.compile(r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE)
        match = content_pattern.search(text)

        if match:
            raw = match.group(1)
            # HTML 태그 제거
            clean = re.sub(r'<[^>]+>', ' ', raw)
            return clean
        else:
            # HTML 태그 전체 제거 후 반환
            clean = re.sub(r'<[^>]+>', ' ', text)
            return clean

    except Exception as e:
        print(f"  [오류] {url}: {e}")
        return ""


# =============================================
# 메인
# =============================================

def main():
    print("=" * 50)
    print("연락처 추출 시작")
    print("=" * 50)

    if not os.path.exists(MATCHED_CSV_PATH):
        print(f"[오류] {MATCHED_CSV_PATH} 파일이 없어요. monitor.py를 먼저 실행해주세요.")
        return

    matched_df = pd.read_csv(MATCHED_CSV_PATH, encoding='utf-8-sig')
    print(f"매칭된 글: {len(matched_df)}건")

    results = []

    for _, row in matched_df.iterrows():
        url = row.get('링크', '')
        title = row.get('제목', '')
        writer = row.get('글쓴이', '')
        item = row.get('매칭품목', '')
        price = row.get('내시세', '')

        print(f"\n[{item}] {title}")
        print(f"  URL: {url}")

        content = fetch_article_content(url)
        phone = extract_phone_numbers(content)

        print(f"  전화번호: {phone if phone else '없음'}")

        results.append({
            '품목': item,
            '제목': title,
            '글쓴이': writer,
            '전화번호': phone,
            '내시세': price,
            '링크': url,
            '추출시각': datetime.now().strftime('%Y-%m-%d %H:%M'),
        })

        time.sleep(1)  # 과도한 요청 방지

    # CSV 저장
    result_df = pd.DataFrame(results)
    result_df.to_csv(CONTACTS_CSV_PATH, index=False, encoding='utf-8-sig')
    print(f"\n[완료] {CONTACTS_CSV_PATH} 저장됨")
    print(result_df[['품목', '글쓴이', '전화번호']].to_string(index=False))


if __name__ == "__main__":
    main()
