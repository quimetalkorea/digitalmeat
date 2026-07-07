import pandas as pd

INPUT = "축산가공업.xlsx"
OUTPUT = "축산가공업_한글.xlsx"   # 원본 보존을 위해 새 파일로 저장

COLUMN_NAMES = {
    "BPLC_NM": "사업장명",
    "BZSTAT_SE_NM": "업종구분명",
    "SALS_STTS_NM": "영업상태명",
    "SALS_STTS_CD": "영업상태코드",
    "DTL_SALS_STTS_NM": "상세영업상태명",
    "DTL_SALS_STTS_CD": "상세영업상태코드",
    "LCPMT_YMD": "인허가일자",
    "CLSBIZ_YMD": "폐업일자",
    "ROAD_NM_ADDR": "도로명주소",
    "ROAD_NM_ZIP": "도로명우편번호",
    "LOTNO_ADDR": "지번주소",
    "LCTN_ZIP": "소재지우편번호",
    "TELNO": "전화번호",
    "LCTN_AREA": "소재지면적",
    "FCLT_TOTAL_SCL": "시설총규모",
    "BLDG_PSN_SE_NM": "건물소유구분명",
    "BIZPLC_SURRND_SE_NM": "사업장주변구분명",
    "GRD_SE_NM": "등급구분명",
    "MLT_UTZTN_BSNSSP_YN": "복합이용업소여부",
    "MNG_NO": "관리번호",
    "OPN_ATMY_GRP_CD": "개방자치단체코드",
    "CRD_INFO_X": "좌표X",
    "CRD_INFO_Y": "좌표Y",
    "MRNT_AMOUNT": "보증액",
    "GRNAMT": "보증금액",
    "HDOFC_EMP_CNT": "본사종업원수",
    "FCTRY_OFJB_EMP_CNT": "공장사무직종업원수",
    "FCTRY_PRODWK_EMP_CNT": "공장생산직종업원수",
    "FCTRY_SLSPOS_EMP_CNT": "공장판매직종업원수",
    "ML_PRCTR_CNT": "남성종사자수",
    "FML_PRCTR_CNT": "여성종사자수",
    "HPG": "홈페이지",
    "SNTTN_BZSTAT_NM": "위생업태명",
    "TRDTN_BSNSSP_DSGN_NO": "전통업소지정번호",
    "TRDTN_BSNSSP_PRINC_FD": "전통업소주된음식",
    "WTRSPPL_FCLT_SE_NM": "급수시설구분명",
    "LAST_MDFCN_PNT": "최종수정시점",
    "DAT_UPDT_PNT": "데이터갱신시점",
    "DAT_UPDT_SE": "데이터갱신구분",
}

df = pd.read_excel(INPUT)
df = df.rename(columns=COLUMN_NAMES)
df.to_excel(OUTPUT, index=False)
print(f"완료! 헤더를 한글로 바꿔 '{OUTPUT}' 로 저장했습니다. (행 수: {len(df)})")

# 어떤 컬럼이 한글로 안 바뀌었는지(매핑에 없는 컬럼) 확인용
남은영문 = [c for c in df.columns if any(ch.isascii() and ch.isalpha() for ch in c)]
if 남은영문:
    print("아직 영문으로 남은 컬럼:", 남은영문)