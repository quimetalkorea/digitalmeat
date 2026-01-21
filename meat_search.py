import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRocR7hlvITGPXeQ9nqPXWpxm7jtgE2IS47eodGR6IAIHk_MxFCxSeo2R4OmtVW5AHJGjAe1VH42AGY/pub?output=csv"

@st.cache_data(ttl=10)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df = df.drop_duplicates()
        
        if '날짜' in df.columns:
            df['날짜_dt'] = pd.to_datetime(df['날짜'].str.replace('.', '-'), errors='coerce')
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')
            df = df.drop(columns=['날짜_dt'])
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return pd.DataFrame()

df = load_data()

# 2. 사이드바 새로고침
with st.sidebar:
    if st.button("🔄 데이터 즉시 새로고침"):
        st.cache_data.clear()
        st.rerun()

# 3. 메인 검색창
search_input = st.text_input("🔍 1단계: 검색어를 입력하세요 (예: 삼겹, 목심)", "")

if search_input and not df.empty:
    # 1차 검색 수행
    keywords = search_input.split()
    def filter_func(row):
        row_str = " ".join(row.astype(str).lower())
        return all(kw.lower() in row_str for kw in keywords)

    results = df[df.apply(filter_func, axis=1)].copy()

    if not results.empty:
        # --- 2단계: 결과 내 상세 필터 (핵심 추가 기능) ---
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            # 결과물에 포함된 브랜드들만 골라내기
            if '브랜드' in results.columns:
                brand_list = ["전체"] + sorted(results['브랜드'].dropna().unique().tolist())
                selected_brand = st.selectbox("📍 2단계: 브랜드 선택", brand_list)
                if selected_brand != "전체":
                    results = results[results['브랜드'] == selected_brand]

        with col2:
            # 결과물에 포함된 상세 품목들만 골라내기
            if '품목' in results.columns:
                item_list = ["전체"] + sorted(results['품목'].unique().tolist())
                selected_item = st.selectbox("📍 2단계: 상세 품목 선택", item_list)
                if selected_item != "전체":
                    results = results[results['품목'] == selected_item]

        # 정렬 및 출력 설정
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if not any(k in c for k in exclude)]
        
        final_order = []
        if '날짜' in display_cols: final_order.append('날짜')
        if '품목' in display_cols: final_order.append('품목')
        if '단가' in display_cols: final_order.append('단가')
        final_order += [c for c in display_cols if c not in final_order]

        st.success(f"최종 {len(results)}건이 선택되었습니다.")
        st.dataframe(results[final_order], use_container_width=True, hide_index=True)
        
    else:
        st.warning(f"'{search_input}'에 대한 결과가 없습니다.")
else:
    st.info("검색어를 입력하시면 상세하게 골라낼 수 있는 선택창이 나타납니다.")

if not df.empty:
    st.divider()
    st.caption(f"📅 총 {len(df)}건의 견적 데이터가 연결되어 있습니다.")
