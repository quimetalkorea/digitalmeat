import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

# 스타일 설정
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stDataFrame { border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 단가 없는 데이터 삭제
        if '단가' in df.columns:
            df = df[df['단가'].notna() & (df['단가'] != "")]
        
        # 날짜 정렬 처리
        if '날짜' in df.columns:
            df['날짜_dt'] = pd.to_datetime(df['날짜'].astype(str).str.replace('.', '-', regex=False), errors='coerce')
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')
            
            # 중복 제거 (최신 정보 유지)
            dup_cols = [c for c in df.columns if c not in ['날짜', '날짜_dt']]
            df = df.drop_duplicates(subset=dup_cols, keep='first')
            df = df.drop(columns=['날짜_dt'])
            
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return pd.DataFrame()

df = load_data()

# 2. 사이드바 설정
with st.sidebar:
    st.header("⚙️ 관리 메뉴")
    if st.button("🔄 즉시 업데이트"):
        st.cache_data.clear()
        st.rerun()
    st.info("💡 1분마다 자동 새로고침")
    st.caption(f"마지막 확인: {datetime.now().strftime('%H:%M:%S')}")

# 3. 검색 및 출력 로직
search_input = st.text_input("🔍 검색어 입력 (품목, 브랜드 등)", "")

# 사장님이 요청하신 순서: 날짜, 품목, 등급, EST, 단가
FIXED_ORDER = ['날짜', '품목', '등급', 'EST', '단가']

if search_input and not df.empty:
    keywords = search_input.split()
    results = df.copy()
    for kw in keywords:
        results = results[results.apply(lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1)]

    if not results.empty:
        # 제외할 열
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if c not in exclude]
        
        # 순서 재배치
        final_cols = [c for c in FIXED_ORDER if c in display_cols]
        other_cols = [c for c in display_cols if c not in final_cols]
        
        st.dataframe(results[final_cols + other_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("결과가 없습니다.")
else:
    # 초기 화면 미리보기
    if not df.empty:
        st.write("### 🕒 최신 견적 현황")
        preview_cols = [c for c in FIXED_ORDER if c in df.columns]
        st.table(df[preview_cols].head(20))

if not df.empty:
    st.divider()
    st.caption(f"Digitalmeat | 유효 품목 수: {len(df)}종")
