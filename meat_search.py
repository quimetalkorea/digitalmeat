import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 (사장님의 최신 주소 확인) ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

@st.cache_data(ttl=5) # 5초 캐시
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        # 제목 및 데이터 공백 제거
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # [날짜 정렬 로직 수정]
        if '날짜' in df.columns:
            # 1. 날짜 열의 점(.)이나 슬래시(/)를 대시(-)로 통일
            df['날짜_clean'] = df['날짜'].astype(str).str.replace('.', '-', regex=False).str.replace('/', '-', regex=False)
            # 2. 날짜 변환 (에러 발생했던 fuzzy 인자 제거)
            df['날짜_dt'] = pd.to_datetime(df['날짜_clean'], errors='coerce')
            # 3. 최신순 정렬 (ascending=False: 큰 숫자인 최신 날짜가 위로)
            # na_position='last': 날짜 인식 안 되는 행은 맨 뒤로
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')
            # 4. 임시 열 삭제
            df = df.drop(columns=['날짜_dt', '날짜_clean'])
            
        return df.drop_duplicates()
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

# 3. 메인 검색창
search_input = st.text_input("🔍 검색어를 입력하세요 (예: 삼겹, 목심)", "")

if search_input and not df.empty:
    keywords = search_input.split()
    results = df.copy()
    
    # 다중 키워드 검색
    for kw in keywords:
        results = results[results.apply(lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1)]

    if not results.empty:
        # 검색 결과도 한 번 더 정렬 확인
        if '날짜' in results.columns:
            results['날짜_dt'] = pd.to_datetime(results['날짜'].astype(str).str.replace('.', '-', regex=False), errors='coerce')
            results = results.sort_values(by='날짜_dt', ascending=False, na_position='last').drop(columns=['날짜_dt'])

        st.success(f"검색 결과: {len(results)}건 (최신 날짜순)")
        
        # 2단계 상세 필터
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

        # 열 필터링 및 순서 (날짜, 품목, 단가 순)
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if not any(k in c for k in exclude)]
        
        final_order = []
        if '날짜' in display_cols: final_order.append('날짜')
        if '품목' in display_cols: final_order.append('품목')
        if '단가' in display_cols: final_order.append('단가')
        final_order += [c for c in display_cols if c not in final_order]

        st.dataframe(results[final_order], use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_input}'에 대한 검색 결과가 없습니다.")
else:
    # 초기 화면
    if not df.empty:
        st.info("검색어를 입력하시면 상세 필터가 나타납니다. (아래는 최근 등록 순서)")
        p_exclude = ['업체', '창고', '비고', '원산지']
        p_cols = [c for c in df.columns if not any(k in c for k in p_exclude)]
        p_order = ['날짜', '품목', '단가'] + [c for c in p_cols if c not in ['날짜', '품목', '단가']]
        st.table(df[p_order].head(20))

# 하단 정보
if not df.empty:
    st.divider()
    st.caption(f"📅 업데이트: {datetime.now().strftime('%H:%M:%S')} | 총 데이터: {len(df)}건")
