import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

@st.cache_data(ttl=60)
def load_data():
    try:
        # 데이터 불러오기 및 기본 정리
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 1. 단가 없는 데이터 삭제
        if '단가' in df.columns:
            df = df[df['단가'].notna() & (df['단가'] != "")]
        
        # 2. [핵심] 날짜 정렬 처리
        if '날짜' in df.columns:
            # 다양한 날짜 형식(점, 슬래시 등)을 통일하여 날짜형 데이터로 변환
            df['날짜_dt'] = pd.to_datetime(df['날짜'].astype(str).str.replace('.', '-', regex=False), errors='coerce')
            
            # 최신 날짜가 위로 오게(내림차순) 정렬
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')
            
            # 품목/브랜드/등급이 같은 데이터 중 가장 최신 것만 남김 (중복 제거)
            dup_cols = [c for c in df.columns if c not in ['날짜', '날짜_dt']]
            df = df.drop_duplicates(subset=dup_cols, keep='first')
            
            # 정렬용 임시 열 삭제
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

# 3. 메인 검색 및 필터 로직
search_input = st.text_input("🔍 검색어 입력 (예: 삼겹, 목심)", "")

# 출력 순서: 날짜, 품목, 브랜드, 등급, EST, 단가
FIXED_ORDER = ['날짜', '품목', '브랜드', '등급', 'EST', '단가']

if search_input and not df.empty:
    keywords = search_input.split()
    results = df.copy()
    
    # 키워드 검색
    for kw in keywords:
        results = results[results.apply(lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1)]

    if not results.empty:
        # 검색 결과 내에서도 최신 날짜순 유지 (데이터 로드 시 정렬되어 있으므로 순서 유지됨)
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

        # 열 재배치
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if c not in exclude]
        
        final_cols = [c for c in FIXED_ORDER if c in display_cols]
        other_cols = [c for c in display_cols if c not in final_cols]
        
        st.dataframe(results[final_cols + other_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("결과가 없습니다.")
else:
    # 초기 화면 미리보기 (최신순 TOP 20)
    if not df.empty:
        st.write("### 🕒 최신 견적 현황 (최근 날짜순)")
        preview_cols = [c for c in FIXED_ORDER if c in df.columns]
        st.table(df[preview_cols].head(20))

if not df.empty:
    st.divider()
    st.caption(f"Digitalmeat | 유효 품목 수: {len(df)}종 | 마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")
