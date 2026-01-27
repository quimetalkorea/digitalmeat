import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

@st.cache_data(ttl=5)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # [추가] 단가가 없는 데이터는 삭제 (빈칸 또는 NaN 제거)
        if '단가' in df.columns:
            df = df[df['단가'].notna() & (df['단가'] != "")]
        
        if '날짜' in df.columns:
            # 날짜 정렬을 위한 전처리
            df['날짜_clean'] = df['날짜'].astype(str).str.replace('.', '-', regex=False).str.replace('/', '-', regex=False)
            df['날짜_dt'] = pd.to_datetime(df['날짜_clean'], errors='coerce')
            
            # 최신 날짜순 정렬
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')

            # 품목, 브랜드 등 주요 정보가 같으면 가장 최신 날짜만 남김
            duplicate_check_cols = [c for c in df.columns if c not in ['날짜', '날짜_clean', '날짜_dt']]
            df = df.drop_duplicates(subset=duplicate_check_cols, keep='first')

            df = df.drop(columns=['날짜_dt', '날짜_clean'])
            
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return pd.DataFrame()

df = load_data()

# 2. 사이드바 설정
with st.sidebar:
    st.header("⚙️ 관리 메뉴")
    if st.button("🔄 데이터 강제 새로고침"):
        st.cache_data.clear()
        st.rerun()
    st.info("💡 단가가 있는 최신 견적만 표시됩니다.")

# 3. 메인 검색창
search_input = st.text_input("🔍 검색어를 입력하세요 (예: 삼겹, 목심)", "")

if search_input and not df.empty:
    keywords = search_input.split()
    results = df.copy()
    
    for kw in keywords:
        results = results[results.apply(lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1)]

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건")
        
        # 상세 필터 (브랜드/품목)
        col1, col2 = st.columns(2)
        with col1:
            if '브랜드' in results.columns:
                brand_list = ["전체"] + sorted([str(b) for b in results['브랜드'].dropna().unique()])
                selected_brand = st.selectbox("📍 브랜드 선택", brand_list)
                if selected_brand != "전체":
                    results = results[results['브랜드'] == selected_brand]
        with col2:
            if '품목' in results.columns:
                item_list = ["전체"] + sorted([str(i) for i in results['품목'].dropna().unique()])
                selected_item = st.selectbox("📍 상세 품목 선택", item_list)
                if selected_item != "전체":
                    results = results[results['품목'] == selected_item]

        # [순서 조정] 열 필터링 및 재배치
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if not any(k in c for k in exclude)]
        
        # 순서: 날짜 -> 브랜드 -> 품목 -> 단가 -> 나머지 순
        final_order = []
        if '날짜' in display_cols: final_order.append('날짜')
        if '브랜드' in display_cols: final_order.append('브랜드')
        if '품목' in display_cols: final_order.append('품목')
        if '단가' in display_cols: final_order.append('단가')
        
        # 나머지 열들 뒤에 붙이기
        for c in display_cols:
            if c not in final_order:
                final_order.append(c)

        st.dataframe(results[final_order], use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_input}'에 대한 검색 결과가 없습니다.")
else:
    # 초기 화면 (최신순 미리보기)
    if not df.empty:
        st.info("검색어를 입력하시면 상세 필터가 나타납니다. (아래는 품목별 최신 견적)")
        p_exclude = ['업체', '창고', '비고', '원산지']
        p_cols = [c for c in df.columns if not any(k in c for k in p_exclude)]
        
        # 미리보기 표 순서도 조정
        p_order = []
        if '날짜' in p_cols: p_order.append('날짜')
        if '브랜드' in p_cols: p_order.append('브랜드')
        if '품목' in p_cols: p_order.append('품목')
        if '단가' in p_cols: p_order.append('단가')
        for c in p_cols:
            if c not in p_order: p_order.append(c)
            
        st.table(df[p_order].head(20))

# 하단 정보
if not df.empty:
    st.divider()
    st.caption(f"📅 업데이트: {datetime.now().strftime('%H:%M:%S')} | 유효 품목: {len(df)}종")
