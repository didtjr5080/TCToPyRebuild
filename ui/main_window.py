from PyQt6 import QtWidgets, QtCore, QtGui

from core import progression
from core.asset_loader import AssetLoader

from .main_view import MainView
from .dungeon_view import DungeonView
from .battle_view import BattleView
from .inventory_view import InventoryView
from .stats_view import StatsView
from .special_boss_view import SpecialBossView


class CharacterSelectDialog(QtWidgets.QDialog):
    """전용 캐릭터 선택 창."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("캐릭터 선택")
        self.setModal(True)
        # 가로로 넓게 보여주기 위해 기본 폭 확장
        self.setMinimumWidth(1000)
        self.controller = controller
        self.assets = AssetLoader()

        layout = QtWidgets.QVBoxLayout(self)
        desc = QtWidgets.QLabel("전환할 캐릭터를 선택하세요.")
        layout.addWidget(desc)

        self.list_widget = QtWidgets.QListWidget()
        # 카드 형태로 가로 배치
        self.list_widget.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.list_widget.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.list_widget.setWrapping(True)
        self.list_widget.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.list_widget.setSpacing(12)
        self.list_widget.setIconSize(QtCore.QSize(108, 108))
        self.list_widget.setGridSize(QtCore.QSize(180, 200))
        layout.addWidget(self.list_widget)

        self.detail = QtWidgets.QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setStyleSheet("color:#a5c7ff; background: #0c1522; border: 1px solid #1e2d45; border-radius: 6px;")
        self.detail.setMinimumHeight(120)
        layout.addWidget(self.detail)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(btn_box)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        self._populate()
        self.list_widget.currentItemChanged.connect(self._update_detail)

    def _populate(self):
        current_id = getattr(self.controller, "selected_player_id", None)
        for pid, data in self.controller.data_store.players.items():
            state = self.controller.progress.get("players", {}).get(pid, {}).get("player_state", {})
            level = state.get("level", 1)
            name = data.get("name", pid)
            pix = self.assets.load_character(pid, QtCore.QSize(196, 196))
            icon = QtGui.QIcon(pix)
            subtitle = data.get("class", "") or data.get("title", "")
            label = f"{name}\nLv {level}"
            if subtitle:
                label = f"{label}\n{subtitle}"
            item = QtWidgets.QListWidgetItem(icon, label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, pid)
            if pid == current_id:
                item.setSelected(True)
            self.list_widget.addItem(item)
        if self.list_widget.count() and not self.list_widget.selectedItems():
            self.list_widget.setCurrentRow(0)

    def _update_detail(self):
        pid = self.selected_player_id()
        if not pid:
            self.detail.setText("")
            return
        data = self.controller.data_store.players.get(pid, {})
        state = self.controller.progress.get("players", {}).get(pid, {}).get("player_state", {})
        inv = self.controller.progress.get("players", {}).get(pid, {}).get("inventory", [])
        name = data.get("name", pid)
        level = state.get("level", 1)
        exp = state.get("exp", 0)
        stat_points = state.get("stat_points", 0)
        base_stats = data.get("base_stats", {})
        skills = data.get("skills", [])
        inventory_text = ", ".join(inv) if inv else "없음"
        lines = [
            f"이름: {name}",
            f"레벨: {level}",
            f"EXP: {exp}",
            f"남은 포인트: {stat_points}",
            f"기본 스탯 - 공격 {base_stats.get('attack', 0)}, 마법 {base_stats.get('magic', 0)}, 방어 {base_stats.get('defense', 0)}, 마저 {base_stats.get('magic_resist', 0)}, 체력 {base_stats.get('max_hp', 0)}",
            f"보유 스킬: {', '.join(skills) if skills else '없음'}",
            f"인벤토리: {inventory_text}",
        ]
        self.detail.setPlainText("\n".join(lines))

    def selected_player_id(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.data(QtCore.Qt.ItemDataRole.UserRole)


class MainWindow(QtWidgets.QMainWindow):
    """QStackedWidget 기반 메인 윈도우."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("TCToPyRebuild")
        self.resize(900, 600)

        self.stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stack)

        self.main_view = MainView()
        self.dungeon_view = DungeonView()
        self.battle_view = BattleView()
        self.inventory_view = InventoryView()
        self.stats_view = StatsView()
        self.special_boss_view = SpecialBossView()

        for view in [self.main_view, self.dungeon_view, self.battle_view, self.inventory_view, self.stats_view, self.special_boss_view]:
            self.stack.addWidget(view)

        self.status = self.statusBar()
        self.status.setStyleSheet("QStatusBar{background:#0c1522;color:#8fb4ff;font-weight:bold;}")

        # 신호 연결
        self.main_view.go_dungeon.connect(self.show_dungeon)
        self.main_view.go_inventory.connect(self.show_inventory)
        self.main_view.go_stats.connect(self.show_stats)
        self.main_view.go_special_boss.connect(self.show_special_boss)
        self.main_view.change_player.connect(self.choose_player)

        self.dungeon_view.start_stage.connect(self.start_stage)
        self.dungeon_view.back_main.connect(self.show_main)

        self.battle_view.action_basic.connect(self.player_basic)
        self.battle_view.action_skill.connect(self.player_skill)
        self.battle_view.action_item.connect(self.player_item)
        self.battle_view.leave_battle.connect(self.show_dungeon)

        self.inventory_view.back_main.connect(self.show_main)
        self.inventory_view.equip_item.connect(self.equip_item)
        self.inventory_view.unequip_slot.connect(self.unequip_slot)

        self.stats_view.back_main.connect(self.show_main)
        self.stats_view.apply_points.connect(self.apply_points)

        self.special_boss_view.enter_boss.connect(self.enter_special_boss)
        self.special_boss_view.back_main.connect(self.show_main)

        self.refresh_main()

    # 화면 전환
    def show_main(self):
        self.refresh_main()
        self.stack.setCurrentWidget(self.main_view)

    def show_dungeon(self):
        self.refresh_dungeon()
        self.stack.setCurrentWidget(self.dungeon_view)

    def show_inventory(self):
        self.refresh_inventory()
        self.stack.setCurrentWidget(self.inventory_view)

    def show_stats(self):
        self.refresh_stats()
        self.stack.setCurrentWidget(self.stats_view)

    def show_special_boss(self):
        self.refresh_special_boss()
        self.stack.setCurrentWidget(self.special_boss_view)

    def show_battle(self):
        self.stack.setCurrentWidget(self.battle_view)

    # 데이터 갱신
    def refresh_main(self):
        summary = self.controller.player_summary()
        self.main_view.update_summary(summary)
        self._update_hud()

    def refresh_dungeon(self):
        zones = self.controller.data_dungeons.get("zones", {})
        prog = self.controller.dungeon_progress
        self.dungeon_view.refresh(zones, prog.unlocked_zones, prog.unlocked_stage_by_zone)
        self._update_hud()

    def refresh_inventory(self):
        inv = self.controller.player.inventory
        items = self.controller.data_items
        equip = self.controller.player.equipment
        self.inventory_view.set_inventory(inv, items, equip)
        self._update_hud()

    def refresh_stats(self):
        self.controller.sync_player_hp()  # 최대 HP 반영
        text = self.controller.stats_summary()
        self.stats_view.set_player_info(text, self.controller.player.stat_points)
        self._update_hud()

    def refresh_special_boss(self):
        bosses = self.controller.data_bosses.get("special_bosses", {})
        self.special_boss_view.refresh(bosses)
        self._update_hud()

    # 전투 관련
    def start_stage(self, zone: str, stage: int):
        result = self.controller.start_stage(zone, stage)
        self._prepare_battle(result)

    def enter_special_boss(self, boss_id: str):
        result = self.controller.start_special_boss(boss_id)
        self._prepare_battle(result)

    def _prepare_battle(self, state):
        if not state:
            return
        self.battle_view.set_skills(self.controller.skill_pairs())
        consumables = self.controller.usable_consumables()
        self.battle_view.set_items(consumables)
        self.update_battle_ui()
        self.show_battle()

    def update_battle_ui(self):
        if not self.controller.current_battle:
            return
        p = self.controller.player
        e = self.controller.current_battle.enemy
        self.battle_view.update_status(
            (p.current_hp, p.get_total_stats(self.controller.data_items).max_hp),
            (e.current_hp, e.stats.max_hp),
            self.controller.current_battle.logs,
            player_effects=p.effects,
            enemy_effects=e.effects,
            turn_index=self.controller.current_battle.turn_index,
        )
        header = f"{p.name} vs {e.name} - 턴 {self.controller.current_battle.turn_index}"
        self.battle_view.set_header(header)

    def player_basic(self):
        result = self.controller.player_basic()
        self._handle_battle_result(result)

    def player_skill(self, skill_id: str):
        # 버튼 외 호출 대비: 연출을 위해 스킬 ID를 미리 기록
        self.battle_view.remember_skill(skill_id)
        # 4번째 스킬 5턴 쿨타임 적용을 위해 사용 기록
        self.battle_view.register_skill_use(skill_id)
        result = self.controller.player_use_skill(skill_id)
        self._handle_battle_result(result)

    def player_item(self, item_id: str):
        result = self.controller.player_use_item(item_id)
        self._handle_battle_result(result)

    def _handle_battle_result(self, result):
        self.update_battle_ui()
        if result:
            drop_names = [self.controller.data_items.get(d, {}).get("name", d) for d in result.drops]
            QtWidgets.QMessageBox.information(self, "전투 결과", f"승자: {result.winner}\nEXP: {result.exp}\n드랍: {', '.join(drop_names) if drop_names else '없음'}")
            self.controller.finish_battle(result)
            self.refresh_main()
            self.refresh_dungeon()
            self.refresh_inventory()
            self.refresh_stats()
            self.show_dungeon()

    # 인벤/스탯 처리
    def equip_item(self, item_id: str):
        self.controller.equip_item(item_id)
        self.refresh_inventory()
        self.refresh_main()
        self._update_hud()

    def unequip_slot(self, slot: str):
        self.controller.unequip(slot)
        self.refresh_inventory()
        self.refresh_main()
        self._update_hud()

    def apply_points(self, spend: dict):
        self.controller.apply_stat_points(spend)
        self.refresh_stats()
        self.refresh_main()
        self._update_hud()

    def _update_hud(self):
        stats = self.controller.player.get_total_stats(self.controller.data_items)
        exp_need = progression.exp_to_next(self.controller.player.level)
        self.status.showMessage(
            f"HP {self.controller.player.current_hp}/{stats.max_hp} | 공격 {stats.attack} | 방어 {stats.defense} | 레벨 {self.controller.player.level}"
            f" | EXP {self.controller.player.exp}/{exp_need} | 포인트 {self.controller.player.stat_points}"
        )

    def choose_player(self):
        """캐릭터 변경 다이얼로그를 띄워 전환."""
        dialog = CharacterSelectDialog(self.controller, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        pid = dialog.selected_player_id()
        if not pid or pid == self.controller.selected_player_id:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "캐릭터 변경",
            f"{pid} 캐릭터로 전환하시겠습니까? 현재 진행 상황이 저장됩니다.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.controller.switch_player(pid)
        self.refresh_main()
        self.refresh_dungeon()
        self.refresh_inventory()
        self.refresh_stats()
        self.refresh_special_boss()
        self._update_hud()
