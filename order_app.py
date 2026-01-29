import streamlit as st
import requests

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")
st.title("📝 Digitalmeat 구매 희망 신청")

# 💡 이 아래 큰따옴표("") 사이에 아까 복사한 주소를 붙여넣으세요!
URL = "https://script.google.com/macros/s/AKfycbyYh5rvu_3Glgun9IHcAvVmCSY0JxcWuZ1QiUau-RhRHoRea5toVCnjILtMiUnIF1Qc-w/exec" 

with st.form("order_form", clear_on_submit=True):
    st.subheader("📦 상품 주문 정보")
    o_company = st.text_input("업체명 (필수)*")
    o_item = st.text_input("품목명 (필수)*")
    
    col1, col2 = st.columns(2)
    with col1:
        o_qty = st.number_input("희망 수량 (BOX)", min_value=1, step=1)
    with col2:
        o_phone = st.text_input("연락처 (필수)*")
    
    submit = st.form_submit_button("🚀 주문 신청하기")

    if submit:
        if o_company and o_item and o_phone:
            # 구글 우체통(Web App)으로 데이터 전송
            data = {"company": o_company, "item": o_item, "qty": o_qty, "phone": o_phone}
            try:
                response = requests.post(URL, json=data)
                if response.status_code == 200:
                    st.success(f"✅ {o_company} 사장님, 주문이 성공적으로 접수되었습니다!")
                    st.balloons() # 축하 풍선!
                else:
                    st.error("전송 실패! URL 주소를 다시 확인해주세요.")
            except:
                st.error("연결 오류가 발생했습니다.")
        else:
            st.warning("필수 항목을 모두 입력해주세요.")
