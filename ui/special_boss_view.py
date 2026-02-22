from PyQt6 import QtWidgets, QtCore, QtGui

from core.asset_loader import AssetLoader


class SpecialBossView(QtWidgets.QWidget):
    """특수 보스 선택 화면."""

    enter_boss = QtCore.pyqtSignal(str)
    back_main = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assets = AssetLoader()
        layout = QtWidgets.QVBoxLayout(self)

        self.list_widget = QtWidgets.QListWidget()
        # 가로로 넓고 카드 형태의 선택 UI
        self.list_widget.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.list_widget.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.list_widget.setWrapping(True)
        self.list_widget.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.list_widget.setSpacing(12)
        self.list_widget.setIconSize(QtCore.QSize(140, 140))
        self.list_widget.setGridSize(QtCore.QSize(220, 230))
        layout.addWidget(self.list_widget)
        self.setMinimumWidth(1000)

        btns = QtWidgets.QHBoxLayout()
        self.btn_enter = QtWidgets.QPushButton("입장")
        self.btn_back = QtWidgets.QPushButton("뒤로")
        btns.addWidget(self.btn_enter)
        btns.addWidget(self.btn_back)
        layout.addLayout(btns)

        self.btn_enter.clicked.connect(self._emit_enter)
        self.btn_back.clicked.connect(self.back_main.emit)

    def refresh(self, bosses: dict) -> None:
        self.list_widget.clear()
        for boss_id, data in bosses.items():
            name = data.get("name", boss_id)
            title = data.get("title", "")
            label = f"{name}\n{boss_id}"
            if title:
                label = f"{label}\n{title}"
            pix = self.assets.load_enemy(boss_id, QtCore.QSize(220, 220))
            icon = QtGui.QIcon(pix)
            item = QtWidgets.QListWidgetItem(icon, label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, boss_id)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _emit_enter(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        boss_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        self.enter_boss.emit(boss_id)
