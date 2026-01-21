import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 사장님이 새로 주신 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRocR7hlvITGPXeQ9nqPXWpxm7jtgE2IS47eodGR6IAIHk_MxFCxSeo2R4OmtVW5AHJGjAe1VH42AGY/pub?output=csv"

@st.cache_data(ttl=30)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        
        # 제목 및 데이터 공백 제거
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 중복 데이터 제거
        df = df.drop_duplicates()
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()

df = load_data()

# 검색창
search_term = st.text_input("부위명, 브랜드 또는 날짜를 입력하세요", "")

if search_term and not df.empty:
    # 1. 전체 데이터에서 검색 수행
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask].copy()

    if not results.empty:
        # 2. 날짜순 정렬 강화 (검색 결과 내에서 다시 한 번 정렬)
        if '날짜' in results.columns:
            # 다양한 날짜 형식을 인식하고 정렬
            results['날짜_temp'] = pd.to_datetime(results['날짜'], errors='coerce')
            results = results.sort_values(by='날짜_temp', ascending=False).drop(columns=['날짜_temp'])

        st.success(f"검색 결과: {len(results)}건 (최신 날짜순 정렬 완료)")
        
        # 3. 업체/창고 제외 및 열 순서 조정
        display_cols = [c for c in results.columns if '업체' not in c and '창고' not in c]
        
        if '날짜' in display_cols:
            display_cols.insert(0, display_cols.pop(display_cols.index('날짜')))
            
        # 4. 결과 출력 (중복 제거 포함)
        st.dataframe(results[display_cols].drop_duplicates(), use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요. (예: 막창, 2026-01-21)")

# 하단 정보 및 점검 도구
if not df.empty:
    st.divider()
    with st.expander("데이터 연결 및 정렬 상태 확인"):
        st.write("현재 인식된 제목들:", list(df.columns))
        if '날짜' in df.columns:
            st.write("날짜 데이터 예시:", df['날짜'].iloc[0] if not df['날짜'].empty else "데이터 없음")
        st.write("마지막 업데이트 확인: 30초 주기")
