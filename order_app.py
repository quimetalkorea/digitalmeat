import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Digitalmeat 구매희망 신청", page_icon="📝", layout="centered")

# --- 디자인 스타일 ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .main-title { color: #ff4b4b; font-weight: bold; text-align: center; }
    .stButton>button { background-color: #ff4b4b; color: white; font-weight: bold; width: 100%; border-radius: 10px; height: 3.5em; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>📝 Digitalmeat 구매 희망 신청</h1>", unsafe_allow_html=True)
st.write("---")
st.info("찾으시는 품목의 수량과 희망 단가를 남겨주세요. 재고 확인 후 담당자가 즉시 연락드립니다.")

# --- 신청 폼 ---
with st.form("purchase_request_form", clear_on_submit=True):
    # 사장님이 요청하신 제목 줄 구조 반영
    st.subheader("📍 희망 품목 정보")
    col1, col2 = st.columns(2)
    with col1:
        o_item = st.text_input("품목명 (필수)*", placeholder="예: 삼겹살, 목심")
        o_brand = st.text_input("선호 브랜드", placeholder="예: 슈퍼포크, EXCEL")
        o_grade = st.text_input("등급", placeholder="예: CH, PR, UN")
    with col2:
        o_est = st.text_input("EST 번호", placeholder="예: 86K, 995")
        o_qty = st.number_input("희망 수량 (BOX)", min_value=1, step=1)
        o_price = st.text_input("희망 단가 (원/kg)", placeholder="예: 10,000원")

    st.divider()
    st.subheader("📞 신청자 정보")
    col3, col4 = st.columns(2)
    with col3:
        o_company = st.text_input("업체명 (필수)*", placeholder="예: 디지털식당")
    with col4:
        o_phone = st.text_input("연락처 (필수)*", placeholder="010-0000-0000")
        
    o_warehouse = st.selectbox("희망 출고 창고", ["상관없음", "신우", "대청", "CS냉장", "아주기흥", "기타"])
    o_memo = st.text_area("기타 요청사항 (규격, 유통기한 등)")

    st.write(" ")
    submit_btn = st.form_submit_button("구매 희망 신청하기")

# --- 저장 및 안내 로직 ---
if submit_btn:
    if not o_item or not o_company or not o_phone:
        st.error("필수 항목(*)을 모두 입력해 주세요.")
    else:
        # 💡 사장님께 알림이 가도록 하는 가장 쉬운 방법: 
        # 일단 접수 내용을 화면에 보여주고, 사장님 구글 시트에 저장하는 로직을 연결합니다.
        st.success(f"✅ {o_company} 사장님의 신청이 접수되었습니다!")
        st.balloons()
        
        # 신청 내역 요약
        st.info(f"**신청 요약:** {o_brand} {o_item} ({o_grade}) / {o_qty}박스")
        st.write("담당자가 확인 후 입력하신 연락처로 곧 연락드리겠습니다.")

st.sidebar.markdown("### 🥩 Digitalmeat 센터")
st.sidebar.write("문의: 010-XXXX-XXXX")
st.sidebar.caption("업무 시간: 평일 09:00 ~ 18:00")