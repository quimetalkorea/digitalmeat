import streamlit as st
import requests

st.set_page_config(page_title="Digitalmeat 주문", page_icon="📝")

st.title("📝 Digitalmeat 구매 신청")
st.info("💡 각 칸을 채우고, 하단의 [주문 신청하기] 버튼을 클릭하세요.")

# 💡 사장님의 웹 앱 URL을 확인해 주세요!
URL = "https://script.google.com/macros/s/AKfycbySS1mKduoFo40pRyfrEgJF6ojb9Zn9zMMBCXnMSC55YCUhmsCgRGj2vd5S2FRjKeyuRA/exec"

o_company = st.text_input("업체명 (필수)*", placeholder="사장님 업체 이름을 적어주세요")

# 💡 품목명 입력 칸에 사장님이 요청하신 가이드를 추가했습니다.
o_item = st.text_input(
    "품목명 / 브랜드 / EST / 평중 /유통기한 (필수)*", 
    placeholder="품목명 / 브랜드 / EST / 평중 /유통기한 순서로 기입해주세요 (예: 알목심 / IBP / 4625 / 25kg /1년이상 )"
)

col1, col2, col3 = st.columns(3)
with col1:
    o_qty = st.text_input("희망 수량 (kg)", placeholder="예: 150.5")
with col2:
    o_price = st.text_input("희망 단가 (원)", placeholder="예: 12500")
with col3:
    o_phone = st.text_input("연락처 (필수)*", placeholder="010-0000-0000")

# 버튼 클릭 시 전송
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
            # 💡 구글 시트 웹 앱으로 데이터 전송
            response = requests.post(URL, json=data)
            if response.status_code == 200:
                st.success(f"✅ {o_company} 사장님, 주문이 정상 접수되었습니다!")
                st.balloons()
            else:
                st.error("전송 실패! 구글 시트의 웹 앱 URL과 배포 설정을 확인해주세요.")
        except:
            st.error("연결 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
    else:
        st.warning("필수 항목(업체명, 품목 상세, 수량, 연락처)을 모두 입력해주세요.")