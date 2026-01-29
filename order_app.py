import streamlit as st
import requests

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")
st.title("📝 Digitalmeat 구매 희망 신청")

# 💡 사장님의 웹 앱 URL을 확인해 주세요!
URL = "https://script.google.com/u/0/home/projects/1AsCbiBuRuhNRkLPBgC4igt-1shIxFWQLMD0VGaBqXjMT-CGZoi54fY3Y/edit" 

with st.form("order_form", clear_on_submit=True):
    st.subheader("📦 상품 주문 정보")
    o_company = st.text_input("업체명 (필수)*")
    o_item = st.text_input("품목명 (필수)*")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # 소수점 입력을 위해 step=0.1로 변경했습니다
        o_qty = st.number_input("희망 수량 (kg)", min_value=0.1, step=0.1) 
    with col2:
        o_price = st.text_input("희망 단가 (원)")
    with col3:
        o_phone = st.text_input("연락처 (필수)*")
    
    submit = st.form_submit_button("🚀 주문 신청하기")

    if submit:
        if o_company and o_item and o_phone:
            data = {
                "company": o_company, 
                "item": o_item, 
                "qty": o_qty, 
                "price": o_price,
                "phone": o_phone
            }
            try:
                response = requests.post(URL, json=data)
                if response.status_code == 200:
                    st.success(f"✅ {o_company} 사장님, {o_qty}kg 신청 완료!")
                    st.balloons()
                else:
                    st.error("전송 실패! URL을 확인해주세요.")
            except:
                st.error("연결 오류가 발생했습니다.")
