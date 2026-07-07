"""
카카오 REST API 키 진단 스크립트
- 가짜 code로 토큰을 요청해서 키/시크릿이 유효한지 판별
- KOE320이 나오면 키는 정상 (code 문제였다는 뜻)
- KOE010이 나오면 키 또는 시크릿 자체가 잘못됨

실행: python check_kakao_key.py
"""

import requests


def main():
    print("=" * 55)
    print("카카오 REST API 키 진단")
    print("=" * 55)

    rest_key = input("\nREST API 키: ").strip()
    secret = input("Client Secret (없으면 Enter): ").strip()

    print(f"\n입력된 키 확인: {rest_key[:4]}...{rest_key[-4:]} (길이 {len(rest_key)}자)")
    if len(rest_key) != 32:
        print("⚠️ REST API 키는 보통 32자입니다. 복사가 잘렸거나 공백이 섞였을 수 있어요.")

    data = {
        "grant_type": "authorization_code",
        "client_id": rest_key,
        "redirect_uri": "https://localhost",
        "code": "DUMMY_CODE_FOR_KEY_CHECK",
    }
    if secret:
        data["client_secret"] = secret

    r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=15)
    body = r.json()
    err = body.get("error_code", "")
    print(f"\n응답: {body}\n")

    if err == "KOE320":
        print("✅ 키/시크릿은 정상입니다! (일부러 넣은 가짜 code라서 KOE320이 나온 것)")
        print("→ 그럼 아까 실패 원인은 code 쪽이에요. get_kakao_token.py를 다시 실행하되:")
        print("  - 반드시 스크립트가 새로 여는 브라우저 창에서 인증하세요")
        print("  - 예전 브라우저 탭의 URL을 재사용하면 안 됩니다 (code는 일회용+몇 분 만료)")
        print("  - URL 복사 후 1분 안에 붙여넣으세요")
    elif err == "KOE010":
        print("❌ 키 또는 시크릿이 잘못됐습니다. 순서대로 확인하세요:")
        print("  1. developers.kakao.com → 내 애플리케이션 → 앱 선택 → [앱 키]")
        print("     네 가지 키 중 반드시 'REST API 키' 줄에서 복사")
        print("  2. [카카오 로그인] 설정을 한 앱과 키를 복사한 앱이 같은 앱인지 확인")
        print("     (앱이 여러 개면 헷갈리기 쉬워요)")
        print("  3. [카카오 로그인 → 보안] Client Secret 상태:")
        print("     - '사용함'이면: 그 화면의 시크릿 코드를 정확히 입력")
        print("     - 확실하게 하려면 '사용 안 함'으로 변경 후 시크릿 없이 재시도")
    elif err == "KOE303":
        print("❌ Redirect URI 불일치: [카카오 로그인]에 https://localhost 가 등록됐는지 확인")
    else:
        print(f"예상 밖 응답이에요. 위 내용을 Claude에게 붙여넣어 주세요.")


if __name__ == "__main__":
    main()