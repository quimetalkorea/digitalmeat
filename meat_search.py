import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# 구글 시트 웹 게시 주소
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRPI4EEFi_0oWxYkVh0jL6dT1PScbAikQIV6QM14U3KkWrZkoQ3WlDMzUzrkPGGuVd0-T7UNlKRURC-/pub?output=csv"

@st.cache_data(ttl=30)
def load_data():
    try:
        # 구글 시트에서 데이터를 직접 읽어옵니다.
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # '날짜' 열이 있다면 최신순으로 정렬합니다.
        if '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce').dt.date
            df = df.sort_values(by='날짜', ascending=False)
            
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df = load_data()

# 검색창
search_term = st.text_input("부위명, 원산지 또는 날짜(예: 2026-01-18)를 입력하세요", "")

if search_term and not df.empty:
    # 전체 열(업체명 포함)에서 검색을 수행합니다.
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건")
        
        # '업체' 열만 제외하고 '날짜'를 포함하여 출력합니다.
        cols_to_show = [col for col in results.columns if '업체' not in col]
        st.dataframe(results[cols_to_show], use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요. (날짜로도 검색이 가능합니다)")

if not df.empty:
    st.divider()
    st.caption(f"📍 전체 품목 수: {len(df)}개 | 데이터 출처: 구글 스프레드시트")
