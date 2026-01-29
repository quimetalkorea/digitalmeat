import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 구매 신청", page_icon="📝")

st.title("📝 Digitalmeat 구매 희망 신청")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. 입력 폼
with st.form("order_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        o_company = st.text_input("업체명 (필수)*")
        o_item = st.text_input("품목명 (필수)*")
    with col2:
        o_qty = st.number_input("희망 수량 (BOX)", min_value=1, step=1)
        o_phone = st.text_input("연락처 (필수)*")
    
    submit = st.form_submit_button("신청하기")

    if submit:
        if not o_company or not o_item or not o_phone:
            st.error("필수 항목을 모두 입력해 주세요.")
        else:
            try:
                # 💡 핵심 수정: 시트 이름 지정 없이 데이터를 읽어옵니다.
                existing_data = conn.read()
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_row = pd.DataFrame([{
                    "날짜": now, "업체": o_company, "품목": o_item, 
                    "수량": o_qty, "연락처": o_phone, "상태": "접수대기"
                }])
                
                # 기존 데이터에 새 주문 추가
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                
                # 시트 업데이트
                conn.update(data=updated_df)
                st.success("✅ 신청이 성공적으로 완료되었습니다!")
                st.balloons() # 축하 효과!
                
            except Exception as e:
                st.error(f"기록 중 오류가 발생했습니다. 공유 설정을 다시 확인해 주세요. ({e})")
