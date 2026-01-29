import streamlit as st
import requests

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")
st.title("📝 Digitalmeat 구매 희망 신청")

# 💡 사장님의 웹 앱 URL을 확인해 주세요!
URL = "https://script.google.com/macros/s/AKfycbzE3TOaH6D0pnaTwmshUXDWzXNqvcSoT6qnwD0cNm96BnOtwC4mJKIjm5bmDqo96B2f_w/exec" 

with st.form("order_form", clear_on_submit=True):
    st.subheader("📦 상품 주문 정보")
    o_company = st.text_input("업체명 (필수)*")
    o_item = st.text_input("품목명 (필수)*")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # text_input으로 바꿔서 사장님이 숫자를 마음대로 편하게 입력하게 했습니다.
        o_qty = st.text_input("희망 수량 (kg)", placeholder="예: 150.5")
    with col2:
        o_price = st.text_input("희망 단가 (원)", placeholder="예: 12500")
    with col3:
        o_phone = st.text_input("연락처 (필수)*", placeholder="010-0000-0000")
    
    submit = st.form_submit_button("🚀 주문 신청하기")

    if submit:
        if o_company and o_item and o_phone and o_qty:
            data = {
                "company": o_company, 
                "item": o_item, 
                "qty": o_qty, # 이제 입력한 그대로 문자와 숫자 상관없이 시트로 날아갑니다.
                "price": o_price,
                "phone": o_phone
            }
            try:
                response = requests.post(URL, json=data)
                if response.status_code == 200:
                    st.success(f"✅ {o_company} 사장님, {o_qty}kg 신청 완료!")
                    st.balloons()
                else:
                    st.error("전송 실패! 구글 시트 배포 URL을 확인해주세요.")
            except:
                st.error("연결 오류가 발생했습니다.")
        else:
            st.warning("필수 항목(업체명, 품목, 수량, 연락처)을 모두 입력해주세요.")
