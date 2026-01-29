import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")
st.title("📝 Digitalmeat 구매 희망 신청")

# 1. 구글 시트 연결 (가장 단순한 방식으로 연결)
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 입력 폼
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
                # 💡 핵심: 복잡한 인증 없이 공개된 시트에 바로 기록 시도
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_row = pd.DataFrame([{
                    "날짜": now, "업체": o_company, "품목": o_item, 
                    "수량": o_qty, "연락처": o_phone, "상태": "접수대기"
                }])
                
                # 기존 데이터 읽기 (이건 이미 성공하셨던 부분입니다!)
                existing_data = conn.read()
                
                # 새 데이터 합쳐서 업데이트
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(data=updated_df)
                
                st.success("✅ 주문이 성공적으로 접수되었습니다!")
                st.balloons() 
            except Exception as e:
                # 여기서 에러가 나면 시트의 1행(제목)이 비어있는지 꼭 확인해야 합니다.
                st.error(f"기록 중 오류가 발생했습니다: {e}")
