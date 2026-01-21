import streamlit as st
import pandas as pd
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

# 사이드바에 새로고침 버튼 추가
with st.sidebar:
    if st.button("🔄 데이터 강제 새로고침"):
        st.cache_data.clear()
        st.success("최신 데이터를 다시 불러왔습니다!")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRocR7hlvITGPXeQ9nqPXWpxm7jtgE2IS47eodGR6IAIHk_MxFCxSeo2R4OmtVW5AHJGjAe1VH42AGY/pub?output=csv"

@st.cache_data(ttl=10) # 10초 주기로 캐시 갱신
def load_data():
    try:
        # 1. 데이터 로드
        df = pd.read_csv(GOOGLE_SHEET_URL)
        
        # 2. 제목 및 데이터 공백 제거
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 3. 중복 데이터 제거
        df = df.drop_duplicates()
        
        # 4. 날짜순 정렬 (가장 중요)
        if '날짜' in df.columns:
            # 날짜를 계산 가능한 형태로 변환 (실패시 NaT 처리)
            df['날짜_temp'] = pd.to_datetime(df['날짜'], errors='coerce')
            # NaT(날짜 없는 칸)는 맨 뒤로(last), 유효한 날짜는 최신순(ascending=False)으로 정렬
            df = df.sort_values(by='날짜_temp', ascending=False, na_position='last')
            # 정렬 후 임시 열 삭제
            df = df.drop(columns=['날짜_temp'])
            
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()

df = load_data()

# 검색창
search_term = st.text_input("부위명, 브랜드 또는 날짜를 입력하세요", "")

if search_term and not df.empty:
    # 검색 수행
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask].copy()

    if not results.empty:
        st.success(f"검색 결과: {len(results)}건 (최신 날짜순)")
        
        # 열 필터링 (사장님 요청 열 제외)
        exclude_keywords = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if not any(key in c for key in exclude_keywords)]
        
        # 열 순서 조정 (날짜 -> 품목 -> 단가 순)
        final_cols = []
        if '날짜' in display_cols: final_cols.append('날짜')
        if '품목' in display_cols: final_cols.append('품목')
        if '단가' in display_cols: final_cols.append('단가')
        
        remaining_cols = [c for c in display_cols if c not in final_cols]
        final_cols = final_cols + remaining_cols
            
        st.dataframe(results[final_cols], use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요. 오늘 입력한 데이터가 최상단에 표시됩니다.")

# 하단 정보
if not df.empty:
    st.divider()
    st.caption(f"📍 전체 데이터: {len(df)}건 | 마지막 동기화: {datetime.now().strftime('%H:%M:%S')}")
