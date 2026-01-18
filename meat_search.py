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
        return pd.DataFrame(columns=["품목", "단가", "원산지/EST"])
    
    for enc in ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8']:
        try:
            # 첫 줄을 제목으로 인식
            df = pd.read_csv(file_path, encoding=enc, header=0, on_bad_lines='skip')
            return df
        except:
            continue
    return pd.DataFrame()

df = load_data()

# 2. 검색창
search_term = st.text_input("부위명 또는 원산지를 입력하세요", "")

if search_term:
    # 검색은 전체 데이터(업체명 포함)에서 수행하여 검색 효율 유지
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)
    results = df[mask]

    if not results.empty:
        st.success(f"{len(results)}개의 품목을 찾았습니다.")
        
        # --- 업체명 열 제외 로직 ---
        # 엑셀 파일의 '업체' 또는 '업체명' 열이 있다면 제외합니다.
        # 열 이름을 정확히 모를 경우를 대비해 '업체'라는 글자가 포함된 열을 뺍니다.
        cols_to_show = [col for col in results.columns if '업체' not in col]
        display_df = results[cols_to_show]
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning("검색 결과가 없습니다.")
else:
    st.info("검색어를 입력하시면 견적 리스트에서 찾아드립니다.")
