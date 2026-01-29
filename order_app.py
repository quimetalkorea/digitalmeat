import streamlit as st
import requests

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")
st.title("📝 Digitalmeat 구매 희망 신청")

# 💡 사장님의 웹 앱 URL을 여기에 꼭 넣어주세요!
URL = "https://script.google.com/u/0/home/projects/1AsCbiBuRuhNRkLPBgC4igt-1shIxFWQLMD0VGaBqXjMT-CGZoi54fY3Y/edit" 

with st.form("order_form", clear_on_submit=True):
    st.subheader("📦 상품 주문 정보")
    o_company = st.text_input("업체명 (필수)*")
    o_item = st.text_input("품목명 (필수)*")
    
    col1, col2, col3 = st.columns(3) # 3열로 배치
    with col1:
        o_qty = st.number_input("희망 수량 (BOX)", min_value=1, step=1)
    with col2:
        o_price = st.text_input("희망 단가 (원)") # 👈 단가 입력창
    with col3:
        o_phone = st.text_input("연락처 (필수)*")
    
    submit = st.form_submit_button("🚀 주문 신청하기")

    if submit:
        if o_company and o_item and o_phone:
            # 보낼 데이터에 price 추가
            data = {
                "company": o_company, 
                "item": o_item, 
                "qty": o_qty, 
                "price": o_price, # 👈 데이터 전송
                "phone": o_phone
            }
            try:
                response = requests.post(URL, json=data)
                if response.status_code == 200:
                    st.success(f"✅ {o_company} 사장님, 희망단가 {o_price}원으로 접수되었습니다!")
                    st.balloons()
                else:
                    st.error("전송 실패! URL을 확인해주세요.")
            except:
                st.error("연결 오류가 발생했습니다.")
        else:
            st.warning("필수 항목을 모두 입력해주세요.")
