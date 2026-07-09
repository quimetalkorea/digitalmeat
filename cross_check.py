# -*- coding: utf-8 -*-
"""
교차 매칭 즉시 확인 스크립트
- 지금 구매게시판에 떠 있는 글들을 누적 판매글(sell_posts.csv)과 바로 대조
- sales_monitor.py를 켜지 않고도 백필/병합 결과를 즉시 검증

사용법: python cross_check.py
"""

import pandas as pd

from sales_monitor import (
    load_vocabulary, load_archive, fetch_posts, find_pairs, report_pairs,
    load_seen_pairs, recent_rows,
    SALES_CSV, BUY_BOARD_URL, SALES_MAX_AGE_DAYS,
)


def main():
    print("=" * 55)
    print("구매게시판 현재 글 ↔ 누적 판매글 즉시 대조")
    print("=" * 55)

    items = load_vocabulary()
    if not items:
        print("품목 사전 로드 실패 — 인터넷/시트 확인 필요")
        return

    sell_archive = load_archive(SALES_CSV)
    print(f"[누적] 판매글 {len(sell_archive)}건 로드")
    if sell_archive.empty:
        print("판매글 누적이 비어 있어요. 백필 → 병합 먼저 실행하세요.")
        return

    buy_posts = fetch_posts(BUY_BOARD_URL, "구매게시판", "HoTs")
    if not buy_posts:
        print("구매게시판 수집 실패 (쿠키 확인 필요)")
        return

    seen = load_seen_pairs()
    print(f"[매칭] 기존 발견 짝 {len(seen)}건 제외하고 대조")

    pairs = find_pairs(
        pd.DataFrame(buy_posts),
        recent_rows(sell_archive, SALES_MAX_AGE_DAYS),
        items, seen,
    )
    if pairs:
        report_pairs(pairs)
        print(f"\n✅ 새로운 매칭 {len(pairs)}건 발견 (중개 문구는 패널 문의 목록에서 복사)")
    else:
        print("\n새로운 매칭 없음 (이미 발견한 짝 제외 기준)")
        print("전부 다시 보려면 matched_pairs.csv 를 지우고 다시 실행하세요.")


if __name__ == "__main__":
    main()