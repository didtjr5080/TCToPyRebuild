from PyQt6 import QtWidgets, QtCore


class MainView(QtWidgets.QWidget):
    """메인 메뉴 화면."""

    go_dungeon = QtCore.pyqtSignal()
    go_inventory = QtCore.pyqtSignal()
    go_stats = QtCore.pyqtSignal()
    go_special_boss = QtCore.pyqtSignal()
    change_player = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("던전 캠프")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #8fb4ff;")
        layout.addWidget(title)

        self.summary_frame = QtWidgets.QFrame()
        self.summary_frame.setStyleSheet("QFrame { border: 1px solid #24405f; border-radius: 8px; background:#122238; }")
        summary_layout = QtWidgets.QVBoxLayout(self.summary_frame)
        self.summary_label = QtWidgets.QLabel("플레이어 요약")
        summary_layout.addWidget(self.summary_label)
        layout.addWidget(self.summary_frame)

        grid = QtWidgets.QGridLayout()
        btn_dungeon = QtWidgets.QPushButton("던전 진입")
        btn_inventory = QtWidgets.QPushButton("인벤토리")
        btn_stats = QtWidgets.QPushButton("스탯 관리")
        btn_special = QtWidgets.QPushButton("특수 보스")
        btn_change = QtWidgets.QPushButton("캐릭터 변경")

        for i, btn in enumerate([btn_dungeon, btn_inventory, btn_stats, btn_special, btn_change]):
            row, col = divmod(i, 2)
            btn.setMinimumHeight(60)
            grid.addWidget(btn, row, col)

        btn_dungeon.clicked.connect(self.go_dungeon.emit)
        btn_inventory.clicked.connect(self.go_inventory.emit)
        btn_stats.clicked.connect(self.go_stats.emit)
        btn_special.clicked.connect(self.go_special_boss.emit)
        btn_change.clicked.connect(self.change_player.emit)

        layout.addLayout(grid)
        layout.addStretch(1)

    def update_summary(self, text: str) -> None:
        """메인 요약 텍스트 갱신."""
        self.summary_label.setText(text)
