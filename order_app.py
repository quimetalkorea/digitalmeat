import streamlit as st
import requests

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")

st.title("📝 Digitalmeat 구매 신청")
st.info("💡 각 칸을 채우고, 마지막에 하단 [주문 신청하기] 버튼을 클릭하세요.")

URL = "https://script.google.com/macros/s/AKfycbzE3TOaH6D0pnaTwmshUXDWzXNqvcSoT6qnwD0cNm96BnOtwC4mJKIjm5bmDqo96B2f_w/exec"

# form을 제거하고 일반 입력창으로 구성하면 엔터를 쳐도 전송되지 않습니다.
st.subheader("📦 상품 주문 정보")

o_company = st.text_input("업체명 (필수)*", placeholder="사장님 업체 이름을 적어주세요")
o_item = st.text_input("품목명 (필수)*", placeholder="예: 삼겹살, 차돌박이 등")

col1, col2, col3 = st.columns(3)
with col1:
    o_qty = st.text_input("희망 수량 (kg)", placeholder="예: 150.5")
with col2:
    o_price = st.text_input("희망 단가 (원)", placeholder="예: 12500")
with col3:
    o_phone = st.text_input("연락처 (필수)*", placeholder="010-0000-0000")

# 버튼을 눌러야만 실행되도록 설정
if st.button("🚀 주문 신청하기"):
    if o_company and o_item and o_phone and o_qty:
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
                st.success(f"✅ {o_company} 사장님, 주문이 정상 접수되었습니다!")
                st.balloons()
            else:
                st.error("전송 실패! URL을 확인해주세요.")
        except:
            st.error("연결 오류가 발생했습니다.")
    else:
        st.warning("필수 항목(업체명, 품목, 수량, 연락처)을 모두 입력해주세요.")
