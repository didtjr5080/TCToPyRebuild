from __future__ import annotations

"""로그인 화면 위젯.

- ID/비밀번호를 입력받아 AuthManager로 검증합니다.
- 성공 시 login_successful 시그널을 방출해 상위 컨트롤러가 화면을 전환하도록 합니다.
"""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel

from core.auth_manager import AuthManager


class LoginWidget(QWidget):
    login_successful = pyqtSignal()

    def __init__(self, auth_manager: AuthManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.auth_manager = auth_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(12)

        self.label_title = QLabel("로그인")
        self.label_title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(self.label_title)

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("아이디")
        layout.addWidget(self.input_id)

        self.input_pw = QLineEdit()
        self.input_pw.setPlaceholderText("비밀번호")
        self.input_pw.setEchoMode(QLineEdit.EchoMode.Password)  # '*' 처리
        layout.addWidget(self.input_pw)

        self.btn_login = QPushButton("로그인")
        self.btn_login.clicked.connect(self._on_login_clicked)
        layout.addWidget(self.btn_login)

        self.label_error = QLabel("")
        self.label_error.setStyleSheet("color:#ff6b6b;")
        layout.addWidget(self.label_error)

    def _on_login_clicked(self) -> None:
        user_id = self.input_id.text().strip()
        password = self.input_pw.text().strip()
        ok, msg = self.auth_manager.login(user_id, password)
        if ok:
            self.label_error.setText("")
            self.login_successful.emit()
        else:
            self.label_error.setText(msg)


__all__ = ["LoginWidget"]
