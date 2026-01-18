import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# 사장님의 구글 시트 웹 게시 주소
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQtjrNWpCXSK3LKHNg8bTrnme_u_yMjSfHVeGjuHBxdOA29Q5yeOgYKsdvVWogwRFrFqlstUj5mbKAF/pub?output=csv"
@st.cache_data(ttl=30)
def load_data():
    try:
        # 데이터 로드
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # '날짜' 열을 문자열로 강제 변환하여 화면에 꼭 나오게 함
        if '날짜' in df.columns:
            # 날짜 형식이면 정렬용 임시 열 생성 후 정렬
            temp_date = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.iloc[temp_date.argsort()[::-1]]
            df['날짜'] = df['날짜'].astype(str) # 화면 표시를 위해 문자열 변환
            
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df = load_data()

# 검색창
search_term = st.text_input("부위명, 브랜드 또는 날짜를 입력하세요", "")

if search_term and not df.empty:
    # 전체 열(업체명 포함)에서 검색
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건")
        
        # '업체' 열 제외 및 '날짜' 열 위치 조정
        cols = [col for col in results.columns if '업체' not in col]
        if '날짜' in cols:
            cols.insert(0, cols.pop(cols.index('날짜')))
            
        st.dataframe(results[cols], use_container_width=True, hide_index=True) # 행 번호 숨김
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요. '날짜' 열이 안 보인다면 구글 시트 제목을 확인해 주세요.")

if not df.empty:
    st.divider()
    st.caption(f"📍 현재 연결된 데이터 총 개수: {len(df)}개")
