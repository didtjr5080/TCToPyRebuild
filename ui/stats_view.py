from PyQt6 import QtWidgets, QtCore


class StatsView(QtWidgets.QWidget):
    """스탯 분배 화면."""

    back_main = QtCore.pyqtSignal()
    apply_points = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self.info = QtWidgets.QLabel("스탯 정보를 확인하세요")
        self.info.setStyleSheet("font-weight: bold; color: #8fb4ff;")
        layout.addWidget(self.info)

        form = QtWidgets.QFormLayout()
        self.spin_attack = QtWidgets.QSpinBox()
        self.spin_defense = QtWidgets.QSpinBox()
        self.spin_hp = QtWidgets.QSpinBox()
        self.spin_magic = QtWidgets.QSpinBox()
        for spin in [self.spin_attack, self.spin_defense, self.spin_hp, self.spin_magic]:
            spin.setRange(0, 999)
        form.addRow("공격 추가", self.spin_attack)
        form.addRow("방어 추가", self.spin_defense)
        form.addRow("체력 추가", self.spin_hp)
        form.addRow("마법 추가", self.spin_magic)
        layout.addLayout(form)

        btn_apply = QtWidgets.QPushButton("적용")
        btn_back = QtWidgets.QPushButton("뒤로")
        for btn in [btn_apply, btn_back]:
            btn.setMinimumHeight(44)
        btn_apply.clicked.connect(self._emit_apply)
        btn_back.clicked.connect(self.back_main.emit)
        layout.addWidget(btn_apply)
        layout.addWidget(btn_back)

        self.available_points = 0

    def set_player_info(self, text: str, available_points: int) -> None:
        self.info.setText(text)
        self.available_points = available_points
        for spin in [self.spin_attack, self.spin_defense, self.spin_hp, self.spin_magic]:
            spin.setValue(0)
            spin.setMaximum(available_points)

    def _emit_apply(self) -> None:
        spend = {
            "attack": self.spin_attack.value(),
            "defense": self.spin_defense.value(),
            "max_hp": self.spin_hp.value(),
            "magic": self.spin_magic.value(),
        }
        total = sum(spend.values())
        if total > self.available_points:
            QtWidgets.QMessageBox.warning(self, "경고", "포인트가 부족합니다")
            return
        self.apply_points.emit(spend)
