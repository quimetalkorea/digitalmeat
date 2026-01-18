import streamlit as st
import pandas as pd
import os

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 견적 검색기", page_icon="🥩", layout="wide")

st.title("🥩 Digitalmeat 실시간 견적기")

# 1. 데이터 로드 함수
@st.cache_data
def load_data():
    file_path = "data.csv"
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=["품목", "업체", "단가", "원산지/EST"])
    
    for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
        try:
            # 첫 줄을 제목으로 인식 (header=0)
            df = pd.read_csv(file_path, encoding=enc, header=0, on_bad_lines='skip')
            return df
        except:
            continue
    return pd.DataFrame()

df = load_data()

# 2. 검색창
search_term = st.text_input("부위명 또는 업체명을 입력하세요", "")

if search_term:
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"{len(results)}개의 품목을 찾았습니다.")
        # hide_index=True 설정을 통해 왼쪽 숫자 열을 완전히 제거합니다.
        st.dataframe(results, use_container_width=True, hide_index=True)
    else:
        st.warning("검색 결과가 없습니다.")
else:
    st.info("검색어를 입력하시면 전체 견적 리스트에서 찾아드립니다.")