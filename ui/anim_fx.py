from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets


class FloatingText(QtWidgets.QLabel):
    """위로 떠오르며 사라지는 숫자/텍스트 연출."""

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        text: str,
        start_pos: QtCore.QPoint,
        distance: int = 42,
        duration: int = 820,
        is_crit: bool = False,
    ):
        super().__init__(parent)
        # 크리티컬은 더 크고 두껍게 표시
        font_size = 20 if is_crit else 16
        weight = QtGui.QFont.Weight.Black if is_crit else QtGui.QFont.Weight.Bold
        self.setText(text)
        # Qt 스타일시트는 text-shadow를 지원하지 않으므로 그림자는 QGraphicsDropShadowEffect로 처리
        self.setStyleSheet(
            f"color: #ffffff; font-size: {font_size}px; font-weight: {int(weight)};"
        )
        # 가독성을 위한 그림자
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(14 if is_crit else 12)
        shadow.setOffset(0, 0)
        shadow.setColor(QtGui.QColor(0, 0, 0, 190))
        self.setGraphicsEffect(shadow)
        self.adjustSize()
        self.move(start_pos - QtCore.QPoint(self.width() // 2, self.height() // 2))

        # 위치/투명도 애니메이션
        self._anim_pos = QtCore.QPropertyAnimation(self, b"pos")
        self._anim_pos.setDuration(duration)
        self._anim_pos.setStartValue(self.pos())
        self._anim_pos.setEndValue(self.pos() - QtCore.QPoint(0, distance))
        self._anim_pos.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)

        self._anim_op = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self._anim_op.setDuration(duration)
        self._anim_op.setStartValue(1.0)
        self._anim_op.setEndValue(0.0)

        self._group = QtCore.QParallelAnimationGroup(self)
        self._group.addAnimation(self._anim_pos)
        self._group.addAnimation(self._anim_op)
        self._group.finished.connect(self.deleteLater)
        self.show()
        self._group.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


class TurnBanner(QtWidgets.QLabel):
    """턴 시작을 크게 알리는 배너."""

    def __init__(self, parent: QtWidgets.QWidget, turn_index: int, duration: int = 650):
        super().__init__(parent)
        self.setText(f"TURN {turn_index}")
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background: rgba(20, 32, 58, 200);"
            "color: #e6f0ff;"
            "border: 2px solid rgba(134, 176, 255, 200);"
            "border-radius: 10px;"
            "padding: 10px 16px;"
            "font-size: 20px; font-weight: 800;"
        )
        # 화면 중앙 상단 배치
        parent_rect = parent.rect()
        self.adjustSize()
        x = (parent_rect.width() - self.width()) // 2
        y = int(parent_rect.height() * 0.12)
        self.move(x, y)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.show()

        effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QtCore.QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.deleteLater)
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def shake_widget(widget: QtWidgets.QWidget, strength: int = 8, duration: int = 240):
    """좌우로 흔들어 타격감을 준다."""
    if not widget:
        return
    base_pos = widget.pos()
    anim = QtCore.QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration)
    anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)
    anim.setKeyValueAt(0.0, base_pos)
    anim.setKeyValueAt(0.2, base_pos + QtCore.QPoint(strength, 0))
    anim.setKeyValueAt(0.5, base_pos - QtCore.QPoint(strength, 0))
    anim.setKeyValueAt(0.8, base_pos + QtCore.QPoint(strength // 2, 0))
    anim.setKeyValueAt(1.0, base_pos)
    anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def flash_widget(widget: QtWidgets.QWidget, color: QtGui.QColor = QtGui.QColor(255, 255, 255, 140), duration: int = 180, intensity: float = 1.0):
    """짧은 플래시로 피격 효과를 준다. intensity로 강도 조절."""
    if not widget:
        return
    alpha = min(255, max(30, int(color.alpha() * intensity)))
    overlay = QtWidgets.QWidget(widget.parent())
    overlay.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    overlay.setStyleSheet(
        f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {alpha}); border-radius: 6px;"
    )
    overlay.setGeometry(widget.geometry())
    overlay.show()

    effect = QtWidgets.QGraphicsOpacityEffect(overlay)
    overlay.setGraphicsEffect(effect)
    anim = QtCore.QPropertyAnimation(effect, b"opacity", overlay)
    anim.setDuration(max(120, int(duration * intensity)))
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)

    def cleanup():
        overlay.deleteLater()

    anim.finished.connect(cleanup)
    anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def animate_hpbar(hpbar: QtWidgets.QProgressBar, from_value: int, to_value: int, duration: int = 350):
    """HP바 값을 부드럽게 보간한다."""
    if hpbar is None:
        return
    anim = QtCore.QPropertyAnimation(hpbar, b"value", hpbar)
    anim.setDuration(duration)
    anim.setStartValue(from_value)
    anim.setEndValue(to_value)
    anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)
    anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


class SkillOverlay(QtWidgets.QWidget):
    """스킬 사용 시 잠깐 표시되는 오버레이."""

    def __init__(self, target: QtWidgets.QWidget, pixmap: QtGui.QPixmap | None, duration: int = 420):
        parent = target.parent()
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(target.geometry())
        self._pixmap = pixmap
        self._duration = duration
        self._effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self.show()
        # 플래시/라이트 위젯들보다 위에 오도록 올림
        self.raise_()
        self._run()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if self._pixmap and not self._pixmap.isNull():
            # 대상 영역에 맞춰 반투명하게 그림
            scaled = self._pixmap.scaled(
                self.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            painter.setOpacity(0.75)
            offset_x = (scaled.width() - self.width()) // 2
            offset_y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(-offset_x, -offset_y, scaled)
        else:
            # 기본 플레이스홀더: 번쩍이는 원형 라이트
            center = QtCore.QPointF(self.rect().center())
            grad = QtGui.QRadialGradient(center, float(max(self.width(), self.height()) * 0.6))
            grad.setColorAt(0.0, QtGui.QColor(255, 255, 255, 180))
            grad.setColorAt(0.4, QtGui.QColor(255, 180, 120, 120))
            grad.setColorAt(1.0, QtGui.QColor(255, 120, 120, 0))
            painter.fillRect(self.rect(), grad)
            pen = QtGui.QPen(QtGui.QColor(255, 220, 200, 160))
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawEllipse(self.rect().adjusted(6, 6, -6, -6))
        painter.end()

    def _run(self):
        anim = QtCore.QPropertyAnimation(self._effect, b"opacity", self)
        anim.setDuration(self._duration)
        anim.setStartValue(0.9)
        anim.setEndValue(0.0)
        anim.finished.connect(self.deleteLater)
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
