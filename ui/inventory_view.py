from PyQt6 import QtWidgets, QtCore


class InventoryView(QtWidgets.QWidget):
    """인벤토리 화면."""

    back_main = QtCore.pyqtSignal()
    equip_item = QtCore.pyqtSignal(str)
    unequip_slot = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.list_widget = QtWidgets.QListWidget()
        self.detail = QtWidgets.QTextEdit()
        self.detail.setReadOnly(True)
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.detail)
        splitter.setSizes([200, 400])
        layout.addWidget(splitter)

        btns = QtWidgets.QHBoxLayout()
        self.btn_equip = QtWidgets.QPushButton("장착")
        self.btn_unequip = QtWidgets.QPushButton("해제")
        self.btn_back = QtWidgets.QPushButton("뒤로")
        for btn in [self.btn_equip, self.btn_unequip, self.btn_back]:
            btn.setMinimumHeight(44)
        btns.addWidget(self.btn_equip)
        btns.addWidget(self.btn_unequip)
        btns.addWidget(self.btn_back)
        layout.addLayout(btns)

        self.list_widget.currentItemChanged.connect(self._update_detail)
        self.btn_back.clicked.connect(self.back_main.emit)
        self.btn_equip.clicked.connect(self._emit_equip)
        self.btn_unequip.clicked.connect(self._emit_unequip)

        self.item_data: dict[str, dict] = {}
        self.equipment: dict[str, str | None] = {}
        self.inventory_counts: dict[str, int] = {}

    def set_inventory(self, inventory: dict[str, int], items: dict[str, dict], equipment: dict[str, str | None]) -> None:
        """인벤토리 목록을 dict 기반으로 표시."""
        self.item_data = items
        self.equipment = equipment
        self.inventory_counts = dict(inventory)
        self.list_widget.clear()
        rarity_order = {"legendary": 0, "epic": 1, "rare": 2, "common": 3, None: 4}
        entries = []
        for item_id, count in inventory.items():
            if count <= 0:
                continue
            data = items.get(item_id, {})
            entries.append(
                (rarity_order.get(data.get("rarity"), 4), data.get("name", item_id), item_id, count)
            )
        entries.sort()
        for _, name, item_id, count in entries:
            self.list_widget.addItem(f"{name} x{count} ({item_id})")
        self._update_detail()

    def _update_detail(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            self.detail.setPlainText("")
            self.btn_equip.setEnabled(False)
            self.btn_unequip.setEnabled(False)
            return
        text = item.text()
        item_id = text.split("(")[-1].strip(")")
        data = self.item_data.get(item_id, {})
        lines = [f"이름: {data.get('name', item_id)}"]
        lines.append(f"등급: {data.get('rarity', 'unknown')}")
        lines.append(f"종류: {data.get('type')}")
        count = self.inventory_counts.get(item_id, 0)
        lines.append(f"수량: {count}")
        if data.get("slot"):
            equipped = None
            for slot, eq in self.equipment.items():
                if eq == item_id:
                    equipped = slot
                    break
            slot_text = f"슬롯: {data.get('slot')}"
            if equipped:
                slot_text += f" (현재 {equipped} 장착)"
            lines.append(slot_text)
        stats = data.get("stats", {})
        if stats:
            lines.append(f"스탯: {stats}")
        if data.get("special"):
            lines.append(f"특수: {data.get('special')}")
        desc = data.get("desc") or data.get("description")
        if desc:
            lines.append(desc)
        if data.get("type") == "consumable":
            lines.append("사용: 전투 중에만 사용 가능합니다.")
        self.detail.setPlainText("\n".join(lines))

        itype = data.get("type")
        self.btn_equip.setEnabled(itype == "equipment" and count > 0)
        self.btn_unequip.setEnabled(bool(data.get("slot")))

    def _emit_equip(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        item_id = item.text().split("(")[-1].strip(")")
        self.equip_item.emit(item_id)

    def _emit_unequip(self) -> None:
        # 액세서리/무기/방어구 해제를 위한 간단한 선택 다이얼로그
        slot, ok = QtWidgets.QInputDialog.getText(self, "해제", "슬롯 입력 (weapon/armor/accessory)")
        if ok and slot:
            self.unequip_slot.emit(slot)
