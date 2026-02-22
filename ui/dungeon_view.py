from PyQt6 import QtWidgets, QtCore


class DungeonView(QtWidgets.QWidget):
    """던전 선택 화면."""

    start_stage = QtCore.pyqtSignal(str, int)
    back_main = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self.info = QtWidgets.QLabel("구역/스테이지를 선택하세요")
        self.info.setStyleSheet("font-weight: bold; color: #8fb4ff;")
        layout.addWidget(self.info)

        self.zone_container = QtWidgets.QScrollArea()
        self.zone_container.setWidgetResizable(True)
        self.zone_root = QtWidgets.QWidget()
        self.zone_layout = QtWidgets.QVBoxLayout(self.zone_root)
        self.zone_container.setWidget(self.zone_root)
        layout.addWidget(self.zone_container)

        back_btn = QtWidgets.QPushButton("뒤로")
        back_btn.clicked.connect(self.back_main.emit)
        layout.addWidget(back_btn)

    def refresh(self, zones: dict, unlocked_zones: list, unlocked_stage_by_zone: dict) -> None:
        """구역/스테이지 버튼을 재구성."""
        # 기존 버튼 제거
        while self.zone_layout.count():
            item = self.zone_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for zone_id, zone_data in zones.items():
            zone_box = QtWidgets.QGroupBox(f"구역 {zone_id}")
            v = QtWidgets.QGridLayout(zone_box)
            stages = zone_data.get("stages", {})
            unlocked_stage = unlocked_stage_by_zone.get(zone_id, 0)
            for idx, (stage_id_str, stage_data) in enumerate(stages.items()):
                stage_id = int(stage_id_str)
                btn = QtWidgets.QPushButton(f"스테이지 {stage_id}")
                locked = zone_id not in unlocked_zones or stage_id > unlocked_stage
                if stage_id == 5:
                    btn.setText(f"스테이지 {stage_id} (Boss)")
                    btn.setStyleSheet("font-weight: bold; color: #ffb347;")
                btn.setEnabled(not locked)
                if locked:
                    btn.setProperty("locked", True)
                btn.setMinimumHeight(50)
                btn.clicked.connect(lambda _, z=zone_id, s=stage_id: self.start_stage.emit(z, s))
                row, col = divmod(idx, 3)
                v.addWidget(btn, row, col)
            self.zone_layout.addWidget(zone_box)
        self.zone_layout.addStretch(1)
