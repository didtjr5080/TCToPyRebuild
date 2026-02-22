from PyQt6 import QtWidgets, QtCore


class HPBar(QtWidgets.QProgressBar):
    """HP 표시용 프로그레스바."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(True)
        # 어두운 톤에 맞춘 스타일
        self.setStyleSheet(
            "QProgressBar {"
            "  background: #1d2533;"
            "  border: 1px solid #2f3b52;"
            "  border-radius: 6px;"
            "  color: #e6f0ff;"
            "  text-align: center;"
            "}"
            "QProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6eb1ff, stop:1 #8fd8ff);"
            "  border-radius: 5px;"
            "}"
        )
        self._anim = QtCore.QPropertyAnimation(self, b"value")
        self._anim.setDuration(320)

    def _update_format(self, current: int, maximum: int) -> None:
        """텍스트 포맷만 별도 갱신."""
        self.setFormat(f"HP {current}/{maximum}")

    def set_hp(self, current: int, maximum: int) -> None:
        maximum = max(1, maximum)
        self.setMaximum(maximum)
        target_value = max(0, current)
        # 부드러운 HP 변화 애니메이션
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(target_value)
        self._anim.start()
        self._update_format(current, maximum)

    def set_hp_instant(self, current: int, maximum: int) -> None:
        """애니메이션 없이 즉시 설정할 때 사용."""
        maximum = max(1, maximum)
        self.setMaximum(maximum)
        self._anim.stop()
        self.setValue(max(0, current))
        self._update_format(current, maximum)


class LabelValue(QtWidgets.QWidget):
    """라벨/값 수평 표시."""

    def __init__(self, label: str, value: str = "", parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        self.label_widget = QtWidgets.QLabel(label)
        self.value_widget = QtWidgets.QLabel(value)
        layout.addWidget(self.label_widget)
        layout.addWidget(self.value_widget)
        layout.addStretch(1)

    def set_value(self, text: str) -> None:
        self.value_widget.setText(text)


class EffectChips(QtWidgets.QWidget):
    """상태이상을 칩 형태로 나열."""

    EFFECT_STYLES = {
        "bleed": {"label": "Bleed", "color": "#d84a4a"},
        "stun": {"label": "Stun", "color": "#e0c36a"},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.layout.addStretch(1)

    def set_effects(self, effects) -> None:
        # 기존 칩 제거
        while self.layout.count() > 1:  # 마지막 stretch 제외
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        def _build_chip(text: str, color: str) -> QtWidgets.QLabel:
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet(
                f"QLabel {{ background: {color}; color: #0c1522; border-radius: 6px; padding: 4px 8px; font-weight: bold; }}"
            )
            return lbl

        if not effects:
            return

        for eff in effects:
            eff_id = getattr(eff, "id", str(eff))
            duration = getattr(eff, "duration", None)
            data = self.EFFECT_STYLES.get(eff_id, {"label": eff_id.title(), "color": "#6aa6ff"})
            label_text = data["label"]
            if duration is not None:
                label_text = f"{label_text} ({duration})"
            chip = _build_chip(label_text, data["color"])
            self.layout.insertWidget(self.layout.count() - 1, chip)
