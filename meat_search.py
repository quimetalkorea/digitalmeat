import streamlit as st
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 시세 검색", page_icon="🥩", layout="wide")

# 스타일
st.markdown("""
<style>
h1 { font-size: 1.5rem !important; }
table {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
    width: 100%;
    font-size: 13px;
}
th, td {
    padding: 6px 10px;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
}
</style>
""", unsafe_allow_html=True)

st.title("🥩 Digitalmeat 시세 검색")

# --- 구글 시트 주소 (.env에서 불러오기) ---
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")

@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL, low_memory=False)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df = df.dropna(how='all')

        if '단가(원/kg)' in df.columns:
            df = df[df['단가(원/kg)'].notna() & (df['단가(원/kg)'] != "")]

        if '날짜' in df.columns:
            df['날짜_dt'] = pd.to_datetime(
                df['날짜'].astype(str).str.replace(r'\s+', '', regex=True).str.replace('.', '-', regex=False),
                errors='coerce'
            )
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')
            df = df.drop(columns=['날짜_dt'])

        df = df.fillna("")
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

# 3. 메인 검색 및 필터 로직
search_input = st.text_input("🔍 검색어 입력 (예: IBP 목전지 244M)", "")

# 출력 순서 정의
FIXED_ORDER = ['날짜', '품목', '브랜드', '단가(원/kg)', '등급', 'EST']

if not df.empty:
    if search_input:
        keywords = search_input.split()
        results = df.copy()

        for kw in keywords:
            results = results[results.apply(
                lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1
            )]

        if not results.empty:
            col1, col2 = st.columns(2)
            with col1:
                if '브랜드' in results.columns:
                    brand_options = ["전체"] + sorted([str(b) for b in results['브랜드'].unique() if b])
                    selected_brand = st.selectbox("📍 브랜드별 보기", brand_options)
                    if selected_brand != "전체":
                        results = results[results['브랜드'] == selected_brand]
            with col2:
                if '품목' in results.columns:
                    item_options = ["전체"] + sorted([str(i) for i in results['품목'].unique() if i])
                    selected_item = st.selectbox("📍 품목별 보기", item_options)
                    if selected_item != "전체":
                        results = results[results['품목'] == selected_item]

            st.success(f"검색 결과: {len(results)}건 (최신순)")

            exclude = ['업체', '창고', '원산지']
            display_cols = [c for c in results.columns if c not in exclude]
            final_cols = [c for c in FIXED_ORDER if c in display_cols]
            other_cols = [c for c in display_cols if c not in final_cols]

            st.markdown(
                results[final_cols + other_cols].to_html(index=False),
                unsafe_allow_html=True
            )
        else:
            st.warning("결과가 없습니다.")
    else:
        preview_cols = [c for c in FIXED_ORDER if c in df.columns]
        st.markdown(
            df[preview_cols].to_html(index=False),
            unsafe_allow_html=True
        )

    st.write("")
    st.caption(f"Digitalmeat | 유효 품목 수: {len(df)}종 | 마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")
    st.caption("© 2026 Digitalmeat 실시간 견적 시스템")

else:
    st.warning("데이터를 불러올 수 없습니다. 구글 시트 설정을 확인해주세요.")