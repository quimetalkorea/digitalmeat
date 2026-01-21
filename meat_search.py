import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRLgM2vj52wClebWJJV7jqyghPytijDb9xYEgAGExjpziUnEBfegQfowjXrfxAJ_yg0MiEXsauCK-8z/pub?output=csv"

@st.cache_data(ttl=10)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        # 제목 공백 제거
        df.columns = [str(c).strip() for c in df.columns]
        # 데이터 내용 공백 제거
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        # 완전히 똑같은 줄 제거
        df = df.drop_duplicates()
        
        if '날짜' in df.columns:
            # 날짜 형식을 똑똑하게 변환하여 정렬
            df['날짜_dt'] = pd.to_datetime(df['날짜'].astype(str).str.replace('.', '-'), errors='coerce')
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
    # [에러 수정 포인트] 검색 로직을 더 안전하게 변경
    keywords = search_input.split()
    
    # 각 줄에서 키워드 포함 여부 확인
    results = df.copy()
    for kw in keywords:
        # 대소문자 구분 없이 각 키워드가 포함된 행만 남김
        results = results[results.apply(lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1)]

    if not results.empty:
        # --- 2단계: 결과 내 상세 필터 ---
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            if '브랜드' in results.columns:
                # 데이터가 있을 때만 리스트 생성
                unique_brands = results['브랜드'].dropna().unique().tolist()
                brand_list = ["전체"] + sorted([str(b) for b in unique_brands])
                selected_brand = st.selectbox("📍 2단계: 브랜드 선택", brand_list)
                if selected_brand != "전체":
                    results = results[results['브랜드'] == selected_brand]

        with col2:
            if '품목' in results.columns:
                unique_items = results['품목'].dropna().unique().tolist()
                item_list = ["전체"] + sorted([str(i) for i in unique_items])
                selected_item = st.selectbox("📍 2단계: 상세 품목 선택", item_list)
                if selected_item != "전체":
                    results = results[results['품목'] == selected_item]

        # 열 출력 설정 (사장님 요청 제외 항목)
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if not any(k in c for k in exclude)]
        
        # 순서 고정 (날짜 -> 품목 -> 단가 순)
        final_order = []
        if '날짜' in display_cols: final_order.append('날짜')
        if '품목' in display_cols: final_order.append('품목')
        if '단가' in display_cols: final_order.append('단가')
        final_order += [c for c in display_cols if c not in final_order]

        st.success(f"최종 {len(results)}건이 검색되었습니다.")
        st.dataframe(results[final_order], use_container_width=True, hide_index=True)
        
    else:
        st.warning(f"'{search_input}'에 대한 결과가 없습니다.")
else:
    st.info("검색어를 입력하시면 상세하게 골라낼 수 있는 선택창이 나타납니다.")

if not df.empty:
    st.divider()
    st.caption(f"📅 마지막 동기화: {datetime.now().strftime('%H:%M:%S')} | 총 데이터: {len(df)}건")
