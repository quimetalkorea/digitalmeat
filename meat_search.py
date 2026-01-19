import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 새로운 구글 시트 주소 적용 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR6WRSpWMH47AgEZQNyxgIewZeKGrouVPIANIfbXsCdhGGtF3AcjAQ1yQcUClQuvjtmvcjXwALyypam/pub?output=csv"

@st.cache_data(ttl=30) # 30초마다 최신 데이터 확인
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        
        # 제목줄의 앞뒤 공백 제거 (가장 흔한 에러 원인 해결)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 내용의 공백 제거
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 완전히 똑같은 줄 중복 제거
        df = df.drop_duplicates()
        
        # '날짜' 열 처리 (날짜가 있으면 최신순 정렬)
        if '날짜' in df.columns:
            # 다양한 날짜 형식을 인식하도록 설정
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
    # 전체 열에서 검색
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건")
        
        # 업체명 제외 및 날짜 우선 배치
        display_cols = [c for c in results.columns if '업체' not in c]
        
        if '날짜' in display_cols:
            # 날짜를 맨 앞으로 이동
            display_cols.insert(0, display_cols.pop(display_cols.index('날짜')))
            
        st.dataframe(results[display_cols], use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요. (예: 막창, 2026-01-19)")

# 하단 정보 및 점검 도구
if not df.empty:
    st.divider()
    with st.expander("데이터 연결 상태 확인"):
        st.write("현재 앱이 인식한 제목들:", list(df.columns))
        if '날짜' not in df.columns:
            st.error("⚠️ 구글 시트 첫 줄에 '날짜'라는 제목이 보이지 않습니다. 시트의 제목을 확인해 주세요!")
        st.write("마지막 업데이트 확인: 30초 주기")
