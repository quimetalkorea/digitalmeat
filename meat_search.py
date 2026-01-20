import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 새로운 구글 시트 주소 적용 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKO5PoTHdZnzt_liTQAGsvyfg1DCyz2ja7o8OKojMpsVVJSgL87cvJx6BhIuGf7fGmFrRwa9tU5R0y/pub?output=csv"
@st.cache_data(ttl=30) # 30초마다 최신 데이터를 확인합니다.
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        
        # 제목줄 및 내용의 공백 제거
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 중복 데이터 제거
        df = df.drop_duplicates()
        
        # '날짜' 열 처리 (최신 날짜순 정렬)
        if '날짜' in df.columns:
            df['날짜_temp'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.sort_values(by='날짜_temp', ascending=False).drop(columns=['날짜_temp'])
            
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()

df = load_data()

# 검색창
search_term = st.text_input("부위명, 브랜드 또는 날짜를 입력하세요", "")

if search_term and not df.empty:
    # 전체 데이터에서 검색 수행
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건")
        
        # --- 열 필터링 로직 ---
        # 1. '업체' 또는 '창고' 글자가 들어간 열은 제외
        display_cols = [c for c in results.columns if '업체' not in c and '창고' not in c]
        
        # 2. '날짜' 열을 맨 앞으로 이동
        if '날짜' in display_cols:
            display_cols.insert(0, display_cols.pop(display_cols.index('날짜')))
            
        # 중복을 한 번 더 제거하고 화면에 출력
        st.dataframe(results[display_cols].drop_duplicates(), use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요. (예: 막창, 2026-01-19)")

# 하단 정보 및 점검 도구
if not df.empty:
    st.divider()
    with st.expander("데이터 연결 상태 확인"):
        st.write("현재 앱이 인식한 제목들:", list(df.columns))
        st.write("마지막 업데이트 확인: 30초 주기")
