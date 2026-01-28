import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

# --- 스타일 설정 ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTable { font-size: 16px; }
    .stDataFrame { border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

# 💡 업데이트 속도를 위해 TTL을 60(1분)으로 조정했습니다.
@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 1. 단가 없는 데이터 삭제
        if '단가' in df.columns:
            df = df[df['단가'].notna() & (df['단가'] != "")]
        
        # 2. 날짜 정렬 및 중복 제거
        if '날짜' in df.columns:
            df['날짜_clean'] = df['날짜'].astype(str).str.replace('.', '-', regex=False).str.replace('/', '-', regex=False)
            df['날짜_dt'] = pd.to_datetime(df['날짜_clean'], errors='coerce')
            
            # 최신순 정렬
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')

            # 품목/브랜드/등급/EST가 같으면 최신 데이터만 남김
            dup_cols = [c for c in df.columns if c not in ['날짜', '날짜_clean', '날짜_dt']]
            df = df.drop_duplicates(subset=dup_cols, keep='first')
            df = df.drop(columns=['날짜_dt', '날짜_clean'])
            
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return pd.DataFrame()

df = load_data()

# 2. 사이드바 설정
with st.sidebar:
    st.header("⚙️ 관리 메뉴")
    if st.button("🔄 데이터 즉시 새로고침"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.info("💡 1분마다 자동으로 최신 데이터를 체크합니다. 급할 때만 위 버튼을 눌러주세요.")
    st.caption(f"마지막 확인: {datetime.now().strftime('%H:%M:%S')}")

# 3. 메인 화면 로직
search_input = st.text_input("🔍 검색어를 입력하세요 (예: 삼겹, 목심, 슈퍼포크)", "")

# 표에 보여줄 순서 정의 (사장님 요청 순서)
# 품목, 등급, EST, 평균중량, 비고, 단가, 날짜, 업체, 브랜드, 원산지, 창고
DESIRED_ORDER = ['품목', '등급', 'EST', '평균중량', '비고', '단가', '날짜', '업체', '브랜드', '원산지', '창고']

if search_input and not df.empty:
    keywords = search_input.split()
    results = df.copy()
    
    for kw in keywords:
        results = results[results.apply(lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1)]

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건")
        
        # 상세 필터링
        col1, col2 = st.columns(2)
        with col1:
            if '브랜드' in results.columns:
                brand_list = ["전체"] + sorted(results['브랜드'].unique().tolist())
                selected_brand = st.selectbox("📍 브랜드 필터", brand_list)
                if selected_brand != "전체":
                    results = results[results['브랜드'] == selected_brand]
        with col2:
            if '품목' in results.columns:
                item_list = ["전체"] + sorted(results['품목'].unique().tolist())
                selected_item = st.selectbox("📍 품목 필터", item_list)
                if selected_item != "전체":
                    results = results[results['품목'] == selected_item]

        # 열 순서 맞추기 (있는 열만 배치)
        final_cols = [c for c in DESIRED_ORDER if c in results.columns]
        # 정의되지 않은 나머지 열들 뒤에 붙이기
        extra_cols = [c for c in results.columns if c not in final_cols]
        
        st.dataframe(results[final_cols + extra_cols], use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_input}'에 대한 결과가 없습니다.")

else:
    # 초기 화면 (최신순 20개 미리보기)
    if not df.empty:
        st.info("👆 상단에 검색어를 입력하시면 상세 품목을 보실 수 있습니다.")
        
        # 미리보기용 열 순서 (간소화)
        preview_order = ['날짜', '브랜드', '품목', '등급', '단가']
        final_preview = [c for c in preview_order if c in df.columns]
        
        st.write("### 🕒 실시간 최신 단가 (TOP 20)")
        st.table(df[final_preview].head(20))

# 하단 푸터
if not df.empty:
    st.divider()
    st.caption(f"Digitalmeat | 유효 품목 수: {len(df)}종 | 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
