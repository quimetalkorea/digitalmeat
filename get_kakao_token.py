"""
카카오 '나에게 보내기' 토큰 발급 스크립트 (최초 1회만 실행)

사전 준비 (5분):
1. https://developers.kakao.com 접속 → 로그인 → [내 애플리케이션] → [애플리케이션 추가하기]
   - 앱 이름: digitalmeat-monitor (아무거나)
2. 만든 앱 클릭 → [앱 키] 에서 "REST API 키" 복사해두기
3. 왼쪽 메뉴 [카카오 로그인] → 활성화 ON
   - Redirect URI 등록: https://localhost
4. 왼쪽 메뉴 [카카오 로그인 > 동의항목]
   - "카카오톡 메시지 전송 (talk_message)" → 선택 동의로 설정

그다음 이 스크립트 실행:
    python get_kakao_token.py
"""

import json
import os
import webbrowser
from urllib.parse import urlparse, parse_qs

import requests

TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kakao_token.json")
REDIRECT_URI = "https://localhost"


def main():
    print("=" * 55)
    print("카카오 '나에게 보내기' 토큰 발급")
    print("=" * 55)

    rest_key = input("\n1) REST API 키를 붙여넣으세요 (⚠️ 네이티브/JavaScript/Admin 키 아님!): ").strip()
    if not rest_key:
        print("REST API 키가 필요합니다. developers.kakao.com → 내 애플리케이션 → 앱 키")
        return

    print("\n   [카카오 로그인 → 보안] 에서 Client Secret이 '사용함'이면 시크릿 코드도 필요합니다.")
    client_secret = input("   Client Secret (없거나 '사용 안 함'이면 그냥 Enter): ").strip()

    auth_url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={rest_key}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        "&scope=talk_message"
    )

    print("\n2) 브라우저가 열리면 카카오 로그인 후 [동의하고 계속하기]를 누르세요.")
    print("   그러면 '사이트에 연결할 수 없음' 페이지가 뜨는데, 정상입니다!")
    print("   그 페이지의 주소창 URL 전체를 복사하세요.")
    print(f"   (https://localhost/?code=XXXX... 형태)\n")
    webbrowser.open(auth_url)

    redirected = input("3) 복사한 URL을 여기에 붙여넣으세요: ").strip()
    try:
        code = parse_qs(urlparse(redirected).query)["code"][0]
    except (KeyError, IndexError):
        print("URL에서 code를 찾지 못했습니다. ?code= 가 포함된 전체 URL을 붙여넣어 주세요.")
        return

    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": rest_key,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            **({"client_secret": client_secret} if client_secret else {}),
        },
        timeout=15,
    )
    data = resp.json()
    if "access_token" not in data:
        print(f"토큰 발급 실패: {data}")
        err = data.get("error_code", "")
        if err == "KOE010":
            print("\n→ KOE010 해결 방법:")
            print("  1. 붙여넣은 키가 'REST API 키'가 맞는지 확인 (네이티브/JS 키 아님)")
            print("  2. [카카오 로그인 → 보안] Client Secret이 '사용함'이면 시크릿 코드 입력 필요")
            print("     (또는 해당 화면에서 '사용 안 함'으로 바꿔도 됨)")
        elif err == "KOE320":
            print("\n→ code가 만료됐거나 이미 사용됐어요. 스크립트를 다시 실행해 새로 진행하세요.")
        return

    token = {
        "rest_api_key": rest_key,
        "client_secret": client_secret,
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
    }
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 토큰 저장 완료: {TOKEN_PATH}")

    # 테스트 전송
    test = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {token['access_token']}"},
        data={
            "template_object": json.dumps({
                "object_type": "text",
                "text": "✅ 미트피플 모니터링 카톡 연동 테스트 성공!",
                "link": {"web_url": "https://cafe.daum.net/meetpeople"},
            })
        },
        timeout=15,
    )
    if test.ok and test.json().get("result_code") == 0:
        print("✅ 테스트 메시지를 보냈습니다. 카톡 '나와의 채팅'을 확인하세요!")
        print("   이제 monitor.py를 실행하면 매칭 시 자동으로 카톡이 옵니다.")
    else:
        print(f"⚠️ 테스트 전송 실패: {test.status_code} {test.text}")
        print("   동의항목에서 talk_message가 켜져 있는지 확인하세요.")


if __name__ == "__main__":
    main()