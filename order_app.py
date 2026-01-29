import streamlit as st
import requests

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")
st.title("📝 Digitalmeat 구매 희망 신청")

# 💡 여기에 아까 복사한 긴 주소를 붙여넣으세요!
URL = "여기에_아까_복사한_웹_앱_URL_붙여넣기"

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
        if o_company and o_item and o_phone:
            # 💡 사장님이 만든 구글 우체통으로 데이터를 던집니다!
            data = {"company": o_company, "item": o_item, "qty": o_qty, "phone": o_phone}
            try:
                response = requests.post(URL, json=data)
                if response.status_code == 200:
                    st.success("✅ 주문이 성공적으로 접수되었습니다!")
                    st.balloons()
                else:
                    st.error("전송에 실패했습니다. 주소를 확인해주세요.")
            except:
                st.error("연결 오류가 발생했습니다.")
