import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")
st.title("📝 Digitalmeat 구매 희망 신청")

# 2. 구글 시트 연결 (이 부분이 버튼을 만듭니다)
# 'gsheets'라는 이름으로 연결을 시도합니다.
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. 데이터 읽기 테스트 (인증 전에는 여기서 버튼이 떠야 합니다)
try:
    df = conn.read()
    st.write("✅ 연결 성공! 시트 데이터를 확인했습니다.")
except Exception as e:
    st.info("💡 아래 [Connect to Google Sheets] 버튼을 눌러 구글 로그인을 완료해 주세요.")
    # 버튼이 안 보일 경우를 대비해 안내 문구를 띄웁니다.

# 4. 입력 폼
with st.form("order_form"):
    o_company = st.text_input("업체명 (필수)*")
    o_item = st.text_input("품목명 (필수)*")
    o_qty = st.number_input("희망 수량 (BOX)", min_value=1)
    o_phone = st.text_input("연락처 (필수)*")
    submit = st.form_submit_button("신청하기")

    if submit:
        if not o_company or not o_item or not o_phone:
            st.error("필수 항목을 모두 입력해 주세요.")
        else:
            st.warning("먼저 구글 로그인을 완료해야 신청이 가능합니다.")
