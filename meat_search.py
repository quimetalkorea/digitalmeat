import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRocR7hlvITGPXeQ9nqPXWpxm7jtgE2IS47eodGR6IAIHk_MxFCxSeo2R4OmtVW5AHJGjAe1VH42AGY/pub?output=csv"

@st.cache_data(ttl=20)
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
        # 2. 날짜순 정렬 (최신순)
        if '날짜' in results.columns:
            results['날짜_temp'] = pd.to_datetime(results['날짜'], errors='coerce')
            results = results.sort_values(by='날짜_temp', ascending=False).drop(columns=['날짜_temp'])

        st.success(f"검색 결과: {len(results)}건")
        
        # 3. 열 필터링 (업체, 창고, 비고, 원산지 제외)
        exclude_keywords = ['업체', '창고', '비고', '원산지']
        available_cols = [c for c in results.columns if not any(key in c for key in exclude_keywords)]
        
        # 4. 중요 열 순서 재배치 (날짜 -> 품목 -> 단가 -> 나머지 순) ★ 핵심 수정 ★
        final_cols = []
        # 날짜가 있으면 첫 번째
        if '날짜' in available_cols: final_cols.append('날짜')
        # 품목이 있으면 두 번째
        if '품목' in available_cols: final_cols.append('품목')
        # 단가가 있으면 세 번째 (품목 바로 옆)
        if '단가' in available_cols: final_cols.append('단가')
        
        # 나머지 열들(브랜드, 등급, EST 등)을 뒤에 붙임
        remaining_cols = [c for c in available_cols if c not in final_cols]
        final_cols = final_cols + remaining_cols
            
        # 5. 최종 출력 (중복 제거 포함)
        st.dataframe(results[final_cols].drop_duplicates(), use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}' 검색 결과가 없습니다.")
else:
    st.info("검색어를 입력해 주세요. (날짜 -> 품목 -> 단가 순으로 표시됩니다.)")

# 하단 정보 및 점검 도구
if not df.empty:
    st.divider()
    with st.expander("데이터 연결 상태 확인"):
        st.write("현재 앱이 인식한 전체 제목들:", list(df.columns))
        st.write("마지막 업데이트 확인: 20초 주기")
