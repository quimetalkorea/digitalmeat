import streamlit as st
import pandas as pd
import os

# 페이지 설정
st.set_page_config(page_title="Digitalmeat 견적 검색기", page_icon="🥩")

st.title("🥩 Digitalmeat 실시간 견적기")

# 1. 데이터 로드 함수
@st.cache_data
def load_data():
    file_path = "data.csv" # GitHub에 함께 올릴 데이터 파일명
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=["품목", "업체", "단가", "원산지/EST"])
    
    for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
        try:
            df = pd.read_csv(file_path, encoding=enc, header=None, on_bad_lines='skip')
            return df
        except:
            continue
    return pd.DataFrame()

df = load_data()

# 2. 검색창
search_term = st.text_input("부위명 또는 업체명을 입력하세요 (예: 갈비, 벨기에)", "")

if search_term:
    # 전체 열에서 검색어 포함 여부 확인
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"{len(results)}개의 품목을 찾았습니다.")
        # 표 출력 (품목, 업체, 단가, 원산지 순서로 가정)
        st.dataframe(results, use_container_width=True, hide_index=True)
    else:
        st.warning("검색 결과가 없습니다.")
else:
    st.info("검색어를 입력하시면 전체 견적 리스트에서 찾아드립니다.")