from __future__ import annotations

"""간단한 로그인 인증 관리자.

- 현재는 하드코딩된 관리자 계정(ID: admin / PW: admin)만 허용합니다.
- 추후 DB 또는 API 연동 시 이 클래스를 확장하면 됩니다.
"""

from typing import Tuple


class AuthManager:
    def __init__(self) -> None:
        # 나중에 DB 커넥션, 세션 토큰 등을 붙일 자리를 남겨둔다.
        self._dummy_id = "admin"
        self._dummy_pw = "admin"

    def login(self, user_id: str, password: str) -> Tuple[bool, str]:
        """사용자 로그인 검증.

        Args:
            user_id: 입력된 아이디
            password: 입력된 비밀번호

        Returns:
            (성공 여부, 메시지)
        """
        if user_id == self._dummy_id and password == self._dummy_pw:
            return True, "로그인 성공"
        return False, "아이디 또는 비밀번호가 올바르지 않습니다"


__all__ = ["AuthManager"]
