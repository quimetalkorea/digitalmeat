import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 (사장님께서 주신 최신 주소) ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRocR7hlvITGPXeQ9nqPXWpxm7jtgE2IS47eodGR6IAIHk_MxFCxSeo2R4OmtVW5AHJGjAe1VH42AGY/pub?output=csv"

# 2. 데이터 로드 함수
@st.cache_data(ttl=10) # 10초마다 자동으로 새 데이터를 체크합니다.
def load_data():
    try:
        # 데이터 가져오기
        df = pd.read_csv(GOOGLE_SHEET_URL)
        
        # 제목줄 공백 제거
        df.columns = [str(c).strip() for c in df.columns]
        
        # 데이터 내용의 앞뒤 공백 제거
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 완전히 똑같은 줄(중복) 제거
        df = df.drop_duplicates()
        
        # [핵심] 날짜 정렬 로직 강화
        if '날짜' in df.columns:
            # 점(.)이나 슬래시(/) 등 다양한 형식을 날짜로 변환 시도
            df['날짜_dt'] = pd.to_datetime(df['날짜'].str.replace('.', '-'), errors='coerce')
            # 최신순 정렬 (날짜 없는 행은 맨 뒤로)
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')
            # 정렬 후 임시 열 삭제
            df = df.drop(columns=['날짜_dt'])
            
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return pd.DataFrame()

# 데이터 불러오기
df = load_data()

# 3. 사이드바 - 강제 새로고침 버튼
with st.sidebar:
    st.header("⚙️ 설정")
    if st.button("🔄 데이터 즉시 새로고침"):
        st.cache_data.clear()
        st.rerun()

# 4. 검색창
search_term = st.text_input("🔍 부위명, 브랜드 또는 날짜를 입력하세요", "")

if search_term and not df.empty:
    # 대소문자 구분 없이 검색
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)
    results = df[mask].copy()

    if not results.empty:
        # 검색 결과 내에서 다시 한 번 최신순 정렬 (이중 확인)
        if '날짜' in results.columns:
            results['날짜_dt'] = pd.to_datetime(results['날짜'].str.replace('.', '-'), errors='coerce')
            results = results.sort_values(by='날짜_dt', ascending=False, na_position='last').drop(columns=['날짜_dt'])

        st.success(f"'{search_term}' 검색 결과: {len(results)}건 (최신 날짜순)")
        
        # 사장님 요청: 열 제외 (업체, 창고, 비고, 원산지)
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if not any(k in c for k in exclude)]
        
        # 사장님 요청: 순서 조정 (날짜 -> 품목 -> 단가 순)
        final_order = []
        if '날짜' in display_cols: final_order.append('날짜')
        if '품목' in display_cols: final_order.append('품목')
        if '단가' in display_cols: final_order.append('단가')
        
        remaining = [c for c in display_cols if c not in final_order]
        final_order += remaining
            
        # 결과 표 출력
        st.dataframe(results[final_order], use_container_width=True, hide_index=True)
    else:
        st.warning(f"'{search_term}'에 대한 검색 결과가 없습니다.")
else:
    # 검색어가 없을 때 최신 데이터 10개만 미리보기 (작동 확인용)
    if not df.empty:
        st.info("검색어를 입력하시면 전체 데이터를 찾아드립니다. (아래는 최신 등록 순서 예시입니다)")
        # 미리보기에서도 요청하신 열 제외 및 순서 적용
        preview_exclude = ['업체', '창고', '비고', '원산지']
        p_cols = [c for c in df.columns if not any(k in c for k in preview_exclude)]
        p_order = ['날짜', '품목', '단가'] + [c for c in p_cols if c not in ['날짜', '품목', '단가']]
        st.table(df[p_order].head(10)) # 깔끔한 표로 10개 표시

# 하단 정보
if not df.empty:
    st.divider()
    st.caption(f"📅 마지막 업데이트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 총 데이터: {len(df)}건")
