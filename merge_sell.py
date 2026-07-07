"""
판매글 백필 병합 스크립트
- D:\digitalmeat 폴더의 sell_backfill*.csv 파일들을 전부 읽어서
- sell_posts.csv 에 글번호 기준 중복 없이 합침

사용법: 백필 CSV들을 이 폴더에 저장한 뒤
    python merge_sell.py
"""

import glob
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SELL_PATH = os.path.join(BASE_DIR, "sell_posts.csv")
COLUMNS = ["글번호", "제목", "글쓴이", "작성일", "링크", "수집일"]


def read_csv_any(path):
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
    print(f"  ⚠️ 인코딩 인식 실패, 건너뜀: {path}")
    return pd.DataFrame()


def main():
    # 기존 누적 파일
    if os.path.exists(SELL_PATH):
        base = read_csv_any(SELL_PATH)
        print(f"[기존] sell_posts.csv {len(base)}건")
    else:
        base = pd.DataFrame(columns=COLUMNS)
        print("[기존] sell_posts.csv 없음 → 새로 생성")

    # 백필 파일들
    files = sorted(glob.glob(os.path.join(BASE_DIR, "sell_backfill*.csv")))
    if not files:
        print("sell_backfill*.csv 파일이 없습니다. 백필 CSV를 이 폴더에 저장 후 다시 실행하세요.")
        return

    frames = [base]
    for f in files:
        df = read_csv_any(f)
        df.columns = [str(c).strip() for c in df.columns]
        missing = [c for c in ["글번호", "제목"] if c not in df.columns]
        if missing:
            print(f"  ⚠️ 필수 열({', '.join(missing)}) 없음, 건너뜀: {os.path.basename(f)}")
            continue
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = ""
        frames.append(df[COLUMNS])
        print(f"[읽음] {os.path.basename(f)} {len(df)}건")

    merged = pd.concat(frames, ignore_index=True)
    merged["글번호"] = merged["글번호"].astype(str).str.strip()
    before = len(merged)
    merged = merged.drop_duplicates(subset="글번호", keep="first")
    merged = merged[merged["글번호"] != ""]
    print(f"[병합] 총 {before}건 → 중복 제거 후 {len(merged)}건")

    merged.to_csv(SELL_PATH, index=False, encoding="utf-8-sig")
    print(f"✅ 저장 완료: {SELL_PATH}")
    print("이제 monitor.py를 실행하면 누적 판매글과 교차 매칭이 시작됩니다.")


if __name__ == "__main__":
    main()