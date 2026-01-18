import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# 구글 시트 웹 게시용 CSV 주소 적용
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQK-pnMaAkUEQBD6sAKGpN_m6UL0iVRn_wUO4svZNu7HdUeyo4prYAj1DlZzqPMSTU0brPdtgSh0ycx/pub?output=csv"
@st.cache_data(ttl=60) # 60초마다 구글 시트의 최신 데이터를 확인합니다.
def load_data():
    try:
        # 구글 시트에서 데이터를 직접 읽어옵니다.
        df = pd.read_csv(GOOGLE_SHEET_URL)
        # 데이터 공백 제거 및 정리
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        return df
    except Exception as e:
        st.error(f"데이터를 불러오지 못했습니다: {e}")
        return pd.DataFrame()

df = load_data()

# 검색창
search_term = st.text_input("부위명, 브랜드 또는 원산지를 입력하세요", "")

if search_term and not df.empty:
    # 전체 열(업체명 포함)에서 검색 수행
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"'{search_term}' 검색 결과: {len(results)}건")
        
        # 업체명 열 제외 (사장님 요청사항 적용)
        cols_to_show = [col for col in results.columns if '업체' not in col]
        display_df = results[cols_to_show]
        
        # 표 출력 (숫자 인덱스 숨김)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}'에 대한 검색 결과가 없습니다.")
else:
    if df.empty:
        st.warning("구글 시트에서 데이터를 불러오는 중이거나 데이터가 비어 있습니다.")
    else:
        st.info("검색어를 입력하시면 구글 시트의 최신 견적을 찾아드립니다.")

# 하단 정보 표시
if not df.empty:
    st.divider()
    st.caption(f"📍 현재 연결된 총 품목 수: {len(df)}개 | 데이터 출처: 구글 스프레드시트")
