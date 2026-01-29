import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.title("📝 Digitalmeat 구매 희망 신청")

# 구글 시트 연결 (인증 방식 변경)
conn = st.connection("gsheets", type=GSheetsConnection)

with st.form("order_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        o_company = st.text_input("업체명 (필수)*")
        o_item = st.text_input("품목명 (필수)*")
    with col2:
        o_qty = st.number_input("희망 수량 (BOX)", min_value=1)
        o_phone = st.text_input("연락처 (필수)*")
    
    submit = st.form_submit_button("신청하기")

    if submit:
        if not o_company or not o_item or not o_phone:
            st.error("필수 항목을 입력해 주세요.")
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_data = pd.DataFrame([{
                "날짜": now, "업체": o_company, "품목": o_item, 
                "수량": o_qty, "연락처": o_phone, "상태": "접수대기"
            }])
            
            # 기존 시트 데이터 읽어오기
            existing_data = conn.read(worksheet="Sheet1")
            updated_df = pd.concat([existing_data, new_data], ignore_index=True)
            
            # 시트에 업데이트
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("✅ 신청이 완료되었습니다!")
