import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# 구글 시트 웹 게시 주소
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQHAoBVsnxWHcvK9vgurKTLo-Ly_C-DzxcJyrnqLQ9kKuk-bhPnOX2IwV3k1zjS5P3OWhIvC3TJ3v57/pub?output=csv"
@st.cache_data(ttl=30)
def load_data():
    try:
        # 데이터 로드
        df = pd.read_csv(GOOGLE_SHEET_URL)
        
        # 1. 앞뒤 공백 제거
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 2. 완전히 똑같은 행(중복 데이터) 제거 ★ 핵심 수정 사항
        df = df.drop_duplicates()
        
        # '날짜' 열 처리 및 정렬
        if '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce').dt.date
            df = df.sort_values(by='날짜', ascending=False)
            
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df = load_data()

# 검색창
search_term = st.text_input("부위명, 브랜드 또는 날짜를 입력하세요", "")

if search_term and not df.empty:
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건 (중복 제거 완료)")
        
        # 업체명 제외 및 열 순서 조정
        cols = [col for col in results.columns if '업체' not in col]
        if '날짜' in cols:
            cols.insert(0, cols.pop(cols.index('날짜')))
            
        # 화면 출력 전 시각적 중복도 한 번 더 제거
        display_df = results[cols].drop_duplicates()
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요.")

if not df.empty:
    st.divider()
    st.caption(f"📍 현재 등록된 순수 품목 수: {len(df)}개")
