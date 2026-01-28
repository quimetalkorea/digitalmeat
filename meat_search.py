import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 실시간 견적", page_icon="🥩", layout="wide")

# --- 스타일 설정 ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stTable { font-size: 16px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🥩 Digitalmeat 실시간 견적기")

# --- 구글 시트 주소 ---
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRkz-rmjbQOdFX7obN1ThrQ1IU7NLMLOiFP3p1LJzidK-4J0bmIYb7Tyg5HsBTgwTv4Lr8_PlzvtEuK/pub?output=csv"

@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # 1. 단가 없는 데이터 삭제
        if '단가' in df.columns:
            df = df[df['단가'].notna() & (df['단가'] != "")]
        
        # 2. 날짜 정렬 및 최신순 유지
        if '날짜' in df.columns:
            df['날짜_dt'] = pd.to_datetime(df['날짜'].astype(str).str.replace('.', '-', regex=False), errors='coerce')
            df = df.sort_values(by='날짜_dt', ascending=False, na_position='last')
            
            # 중복 제거 (핵심 정보 동일 시 최신 날짜만)
            dup_cols = [c for c in df.columns if c not in ['날짜', '날짜_dt']]
            df = df.drop_duplicates(subset=dup_cols, keep='first')
            df = df.drop(columns=['날짜_dt'])
            
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return pd.DataFrame()

df = load_data()

# 2. 사이드바 설정
with st.sidebar:
    st.header("⚙️ 관리 메뉴")
    if st.button("🔄 즉시 업데이트"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"최종 확인: {datetime.now().strftime('%H:%M:%S')}")

# 3. 검색 및 출력 로직
search_input = st.text_input("🔍 검색어 입력 (품목, 브랜드 등)", "")

# ⭐ 사장님이 요청하신 출력 순서 고정
FIXED_ORDER = ['날짜', '품목', '등급', 'EST', '단가']

if search_input and not df.empty:
    keywords = search_input.split()
    results = df.copy()
    for kw in keywords:
        results = results[results.apply(lambda row: row.astype(str).str.contains(kw, case=False, na=False).any(), axis=1)]

    if not results.empty:
        # 열 필터링 (업체, 창고 등 제외 항목 설정 - 필요시 수정)
        exclude = ['업체', '창고', '비고', '원산지']
        display_cols = [c for c in results.columns if c not in exclude]
        
        # 요청하신 순서대로 열 재배치
        final_cols = [c for c in FIXED_ORDER if c in display_cols]
        # 나머지 열들(브랜드 등)을 뒤에 추가
        other_cols = [c for c in display_cols if c not in final_cols]
        
        st.dataframe(results[final_cols + other_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("결과가 없습니다.")
else:
    # 초기 화면 미리보기
    if not df.empty:
        st.write("### 🕒 최신 견적 현황")
        # 미리보기 표도 요청하신 순서로 출력
        preview_cols = [c for c in FIXED_ORDER if c in df.columns]
        st.table(df[preview_cols].head(20))



---

### **💡 변경된 내용 확인**

1.  **순서 고정**: 검색 결과와 초기 화면 모두 **[날짜 - 품목 - 등급 - EST - 단가]** 순서로 가장 앞에 나타납니다.
2.  **가독성**: `st.table`과 `st.dataframe` 모두 이 순서를 따르므로 한눈에 가격 비교가 가능합니다.
3.  **브랜드 정보**: 브랜드나 다른 정보들은 사장님이 요청하신 5개 항목 바로 뒤에 이어서 나오도록 설정했습니다.

이 코드를 적용해서 깃허브에 올리시면 바로 반영될 거예요. 보시기에 훨씬 편해졌나요? 다음으로 더 고치고 싶은 부분이 있으면 말씀해 주세요! Would you like me to **adjust the column widths** so that the price stands out even more?
