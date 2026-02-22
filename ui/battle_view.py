from __future__ import annotations

import html
import random
import re
from PyQt6 import QtWidgets, QtCore, QtGui

from core.asset_loader import AssetLoader
from .anim_fx import FloatingText, TurnBanner, shake_widget, flash_widget, animate_hpbar, SkillOverlay
from .widgets import HPBar, EffectChips


class BattleView(QtWidgets.QWidget):
    """전투 화면."""

    action_basic = QtCore.pyqtSignal()
    action_skill = QtCore.pyqtSignal(str)
    action_item = QtCore.pyqtSignal(str)
    leave_battle = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 에셋 로더: ID만 전달하면 규칙 기반으로 탐색
        self.asset_loader = AssetLoader()
        self._player_pixmap: QtGui.QPixmap | None = None
        self._enemy_pixmap: QtGui.QPixmap | None = None
        self._bg_pixmap: QtGui.QPixmap | None = None

        root = QtWidgets.QGridLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.bg_label = QtWidgets.QLabel()
        self.bg_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.bg_label.setScaledContents(False)
        self.bg_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.bg_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QtWidgets.QHBoxLayout()
        self.player_hp = HPBar()
        self.enemy_hp = HPBar()
        self.player_effects = EffectChips()
        self.enemy_effects = EffectChips()
        self.player_effect_label = QtWidgets.QLabel("상태: 없음")
        self.enemy_effect_label = QtWidgets.QLabel("상태: 없음")
        self.player_effect_label.setStyleSheet("color:#c7d9ff;")
        self.enemy_effect_label.setStyleSheet("color:#c7d9ff;")

        self.player_image = QtWidgets.QLabel()
        self.player_image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.player_image.setScaledContents(False)
        self.player_image.setFixedSize(200, 200)
        self.enemy_image = QtWidgets.QLabel()
        self.enemy_image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.enemy_image.setScaledContents(False)
        self.enemy_image.setFixedSize(200, 200)

        self.player_icon_row = QtWidgets.QHBoxLayout()
        self.player_icon_row.setSpacing(4)
        self.enemy_icon_row = QtWidgets.QHBoxLayout()
        self.enemy_icon_row.setSpacing(4)

        # 피해량 계산을 위한 이전 HP 저장
        self._prev_player_hp = None
        self._prev_enemy_hp = None
        self._prev_turn_index = None
        self._last_skill_used: str | None = None
        self._skill_buttons: list[QtWidgets.QPushButton] = []
        # 스킬 정보: 라벨/순서/쿨타임 관리
        self._skill_labels: dict[str, str] = {}
        self._skill_order: dict[str, int] = {}
        self._skill_cooldowns: dict[str, int] = {}

        self.player_card = QtWidgets.QGroupBox("플레이어")
        self.enemy_card = QtWidgets.QGroupBox("적")
        pc_layout = QtWidgets.QVBoxLayout(self.player_card)
        ec_layout = QtWidgets.QVBoxLayout(self.enemy_card)
        pc_layout.addWidget(self.player_image, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        pc_layout.addWidget(self.player_hp)
        pc_layout.addLayout(self.player_icon_row)
        pc_layout.addWidget(self.player_effects)
        pc_layout.addWidget(self.player_effect_label)
        ec_layout.addWidget(self.enemy_image, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        ec_layout.addWidget(self.enemy_hp)
        ec_layout.addLayout(self.enemy_icon_row)
        ec_layout.addWidget(self.enemy_effects)
        ec_layout.addWidget(self.enemy_effect_label)
        header.addWidget(self.player_card)
        header.addWidget(self.enemy_card)
        layout.addLayout(header)

        status_row = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("상태: 준비")
        self.status_label.setStyleSheet("font-weight: bold; color: #8fb4ff;")
        self.turn_label = QtWidgets.QLabel("턴 1")
        self.turn_label.setStyleSheet("color: #a5c7ff; font-weight: bold;")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        status_row.addWidget(self.turn_label)
        layout.addLayout(status_row)

        action_bar = QtWidgets.QHBoxLayout()
        self.basic_btn = QtWidgets.QPushButton("기본공격")
        self.basic_btn.setMinimumHeight(48)
        self.basic_btn.clicked.connect(self.action_basic.emit)
        action_bar.addWidget(self.basic_btn)

        self.item_btn = QtWidgets.QPushButton("아이템")
        self.item_btn.setMinimumHeight(48)
        action_bar.addWidget(self.item_btn)

        self.leave_btn = QtWidgets.QPushButton("도주/종료")
        self.leave_btn.setMinimumHeight(48)
        self.leave_btn.clicked.connect(self.leave_battle.emit)
        action_bar.addWidget(self.leave_btn)
        layout.addLayout(action_bar)

        skill_box = QtWidgets.QGroupBox("스킬")
        skill_box.setStyleSheet("QGroupBox { margin-top: 10px; }")
        skill_layout_wrapper = QtWidgets.QVBoxLayout(skill_box)
        self.skill_layout = QtWidgets.QHBoxLayout()
        skill_layout_wrapper.addLayout(self.skill_layout)
        layout.addWidget(skill_box)

        log_box = QtWidgets.QGroupBox("전투 로그")
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self.log_box = QtWidgets.QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family: 'Consolas', 'D2Coding', monospace;")
        log_layout.addWidget(self.log_box)
        layout.addWidget(log_box)

        self.item_menu = QtWidgets.QMenu(self)
        self.item_btn.setMenu(self.item_menu)

        root.addWidget(self.bg_label, 0, 0)
        root.addWidget(container, 0, 0)

    def set_items(self, items) -> None:
        """아이템 메뉴 재생성. 문자열 또는 (item_id, label) 튜플 허용."""
        self.item_menu.clear()
        if not items:
            act = self.item_menu.addAction("사용 가능 아이템 없음")
            act.setEnabled(False)
            self.item_btn.setEnabled(False)
            return
        self.item_btn.setEnabled(True)
        for entry in items:
            if isinstance(entry, tuple):
                item_id, label = entry
            else:
                item_id, label = entry, str(entry)
            action = self.item_menu.addAction(label)
            action.triggered.connect(lambda _, i=item_id: self.action_item.emit(i))

    def set_skills(self, skills: list[tuple[str, str]]) -> None:
        """스킬 버튼 재생성. skills: (id, name)."""
        while self.skill_layout.count():
            item = self.skill_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._skill_buttons = []
        self._skill_labels = {}
        self._skill_order = {}
        self._skill_cooldowns = {}
        for skill_id, name in skills:
            btn = QtWidgets.QPushButton(name)
            # 버튼 클릭 시 마지막 사용 스킬을 기록해 연출에서 활용
            btn.clicked.connect(lambda _, s=skill_id: self._on_skill_clicked(s))
            self._skill_buttons.append(btn)
            self._skill_labels[skill_id] = name
            self._skill_order[skill_id] = len(self._skill_order)
            self._skill_cooldowns[skill_id] = 0
            self.skill_layout.addWidget(btn)
        self._update_skill_buttons()

    def update_status(
        self,
        player_hp: tuple[int, int],
        enemy_hp: tuple[int, int],
        logs: list[str],
        player_effects=None,
        enemy_effects=None,
        turn_index: int | None = None,
    ) -> None:
        p_cur, p_max = player_hp
        e_cur, e_max = enemy_hp
        # 전투 UI 갱신 시마다 인벤 소모품을 다시 반영하여 수량 변동을 즉시 표시
        self._refresh_item_menu()
        self.player_effects.set_effects(player_effects or [])
        self.enemy_effects.set_effects(enemy_effects or [])
        self.player_effect_label.setText(self._summarize_effects(player_effects or []))
        self.enemy_effect_label.setText(self._summarize_effects(enemy_effects or []))
        self._set_effect_icons(player_effects or [], self.player_icon_row)
        self._set_effect_icons(enemy_effects or [], self.enemy_icon_row)
        # 턴 변경 시 배너 표시
        if turn_index is not None and turn_index != self._prev_turn_index:
            TurnBanner(self, turn_index)
            self._prev_turn_index = turn_index
            # 턴이 지날 때마다 스킬 쿨타임 감소
            self._tick_skill_cooldowns()
            self._update_skill_buttons()
        # HP 변화 기반 연출
        self._play_damage_fx(p_cur, e_cur, p_max, e_max)
        self._refresh_images()
        if turn_index is not None:
            self.turn_label.setText(f"턴 {turn_index}")
        self._set_logs(logs)

    def set_header(self, text: str) -> None:
        self.status_label.setText(text)

    def _set_logs(self, logs: list[str]) -> None:
        recent = logs[-80:]
        lines = []
        for line in recent:
            safe = html.escape(line)
            safe = re.sub(r"(물리\s*)([0-9]+)", r"\1<span style='color:#ffb37a;'>\2</span>", safe)
            safe = re.sub(r"(마법\s*)([0-9]+)", r"\1<span style='color:#8be0ff;'>\2</span>", safe)
            lines.append(safe)
        html_text = "<br>".join(lines)
        self.log_box.setHtml(html_text)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def _summarize_effects(self, effects) -> str:
        """효과 요약 문자열 생성."""
        if not effects:
            return "상태: 없음"
        name_map = {
            "attack": "공격",
            "magic": "마법",
            "defense": "방어",
            "magic_resist": "마저",
            "max_hp": "체력",
        }
        parts = []
        for eff in effects:
            kind = getattr(eff, "kind", getattr(eff, "id", ""))
            dur = getattr(eff, "duration", None)
            if kind in ("buff_stats", "debuff_stats"):
                stats_delta = getattr(eff, "stats_delta", {}) or {}
                stat_bits = []
                for key in ["attack", "magic", "defense", "magic_resist", "max_hp"]:
                    if key not in stats_delta:
                        continue
                    val = stats_delta[key]
                    sign = "+" if val >= 0 else ""
                    stat_bits.append(f"{name_map.get(key, key)}{sign}{val}")
                label = "버프" if kind == "buff_stats" else "디버프"
                stat_text = "/".join(stat_bits) if stat_bits else label
                if dur is not None:
                    stat_text = f"{stat_text}({dur}턴)"
                parts.append(stat_text)
            elif kind == "bleed":
                parts.append(f"출혈({dur})" if dur is not None else "출혈")
            elif kind == "stun":
                parts.append(f"기절({dur})" if dur is not None else "기절")
            else:
                tail = f"({dur})" if dur is not None else ""
                parts.append(f"{kind}{tail}")
        return "상태: " + ", ".join(parts)

    def _set_effect_icons(self, effects, layout: QtWidgets.QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not effects:
            spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
            layout.addItem(spacer)
            return
        seen = set()
        for eff in effects:
            kind = getattr(eff, "kind", getattr(eff, "id", ""))
            if kind in seen:
                continue
            seen.add(kind)
            lbl = QtWidgets.QLabel()
            lbl.setFixedSize(32, 32)
            pix = self.asset_loader.load_icon(kind)
            lbl.setPixmap(pix.scaled(32, 32, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
            dur = getattr(eff, "duration", None)
            if dur is not None:
                lbl.setToolTip(f"{kind} ({dur}턴 남음)")
            layout.addWidget(lbl)
        layout.addStretch(1)

    def _refresh_images(self) -> None:
        player_id, enemy_id = self._resolve_ids()
        if player_id:
            self._player_pixmap = self.asset_loader.load_character(player_id)
            self._set_pixmap_keep_aspect(self.player_image, self._player_pixmap)
        else:
            self.player_image.clear()
            self._player_pixmap = None
        if enemy_id:
            self._enemy_pixmap = self.asset_loader.load_enemy(enemy_id)
            self._set_pixmap_keep_aspect(self.enemy_image, self._enemy_pixmap)
        else:
            self.enemy_image.clear()
            self._enemy_pixmap = None

        self._bg_pixmap = self.asset_loader.load_background("battle_bg", size=self.size())
        self._set_background_scaled()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 창 크기 변경 시 배경/캐릭터 재스케일 (종횡비 유지)
        self._set_background_scaled()
        if self._player_pixmap:
            self._set_pixmap_keep_aspect(self.player_image, self._player_pixmap)
        if self._enemy_pixmap:
            self._set_pixmap_keep_aspect(self.enemy_image, self._enemy_pixmap)

    def _resolve_ids(self):
        """상위 윈도우의 controller를 통해 현재 전투 id를 알아낸다."""
        win = self.window()
        player_id = None
        enemy_id = None
        if win and hasattr(win, "controller"):
            ctrl = getattr(win, "controller")
            player_id = getattr(ctrl, "selected_player_id", None)
            battle = getattr(ctrl, "current_battle", None)
            if battle and getattr(battle, "enemy", None):
                enemy_id = getattr(battle.enemy, "enemy_id", None)
        return player_id, enemy_id

    # --------------------------------------------------
    # 연출/애니메이션
    # --------------------------------------------------
    def _play_damage_fx(self, p_cur: int, e_cur: int, p_max: int, e_max: int) -> None:
        """HP 변화를 감지해 연출/HP바 애니메이션을 수행."""
        fx_played = False
        overlay_player_shown = False
        # 이번 틱의 HP 변화 계산 (없으면 0)
        delta_p_total = p_cur - (self._prev_player_hp if self._prev_player_hp is not None else p_cur)
        delta_e_total = e_cur - (self._prev_enemy_hp if self._prev_enemy_hp is not None else e_cur)
        # 디버그: 이번 프레임에서 감지된 HP 변화와 마지막 스킬
        print(
            f"[연출] delta player={delta_p_total}"
            f", enemy={delta_e_total}"
            f", last_skill={self._last_skill_used}"
        )

        # 현재 HP바 최대치/텍스트를 먼저 세팅 (값은 이전 HP에서 시작)
        self.player_hp.setMaximum(max(1, p_max))
        self.enemy_hp.setMaximum(max(1, e_max))
        self.player_hp.setFormat(f"HP {p_cur}/{p_max}")
        self.enemy_hp.setFormat(f"HP {e_cur}/{e_max}")

        # 플레이어 HP 변화
        if self._prev_player_hp is None:
            self.player_hp.setValue(int(max(0, p_cur)))
        else:
            delta_p = p_cur - self._prev_player_hp
            start = int(max(0, self._prev_player_hp))
            end = int(max(0, p_cur))
            if delta_p < 0:
                dmg = abs(delta_p)
                crit = self._is_crit(dmg)
                self.player_hp.setValue(start)
                animate_hpbar(self.player_hp, start, end)
                self._spawn_floating_text(self.player_image, f"{'CRIT ' if crit else ''}-{dmg}", is_crit=crit)
                shake_widget(self.player_image, strength=12 if crit else 8)
                flash_widget(self.player_image, QtGui.QColor(255, 100, 100, 170), intensity=1.4 if crit else 1.0)
                fx_played = True
            elif delta_p > 0:
                self.player_hp.setValue(start)
                animate_hpbar(self.player_hp, start, end)
                self._spawn_floating_text(self.player_image, f"+{delta_p}")
                flash_widget(self.player_image, QtGui.QColor(120, 220, 140, 160), duration=220)
                # 자기 강화/회복 스킬은 적 HP 변화와 무관하게 자기쪽 오버레이 표시
                if self._last_skill_used:
                    self._spawn_skill_overlay(target_is_enemy=False)
                    overlay_player_shown = True
                fx_played = True
            else:
                self.player_hp.setValue(end)
                # HP 변화가 없더라도 버프형 스킬 연출을 표시
                if self._last_skill_used:
                    print(f"[연출] self buff overlay skill={self._last_skill_used}")
                    self._spawn_skill_overlay(target_is_enemy=False)
                    overlay_player_shown = True

        # 적 HP 변화
        if self._prev_enemy_hp is None:
            self.enemy_hp.setValue(int(max(0, e_cur)))
        else:
            delta_e = e_cur - self._prev_enemy_hp
            start = int(max(0, self._prev_enemy_hp))
            end = int(max(0, e_cur))
            if delta_e < 0:
                dmg = abs(delta_e)
                crit = self._is_crit(dmg)
                self.enemy_hp.setValue(start)
                animate_hpbar(self.enemy_hp, start, end)
                self._spawn_floating_text(self.enemy_image, f"{'CRIT ' if crit else ''}-{dmg}", is_crit=crit)
                shake_widget(self.enemy_image, strength=12 if crit else 8)
                flash_widget(self.enemy_image, QtGui.QColor(255, 255, 255, 160), intensity=1.6 if crit else 1.0)
                if self._last_skill_used:
                    self._spawn_skill_overlay(target_is_enemy=True)
                fx_played = True
            elif delta_e > 0:
                self.enemy_hp.setValue(start)
                animate_hpbar(self.enemy_hp, start, end)
                self._spawn_floating_text(self.enemy_image, f"+{delta_e}")
                flash_widget(self.enemy_image, QtGui.QColor(120, 180, 255, 140), duration=220)
                fx_played = True
            else:
                self.enemy_hp.setValue(end)

        # 플레이어 스킬인데 아직 자기 오버레이가 표시되지 않았고, 적에게만 대미지가 들어가 오버레이가 가려졌을 때 보정
        if (
            self._last_skill_used
            and self._last_skill_used.startswith("skill_")
            and not overlay_player_shown
            and delta_e_total >= 0  # 적에게 피해가 없는 버프/보호 류일 때만 보정
        ):
            print(f"[연출] self overlay fallback skill={self._last_skill_used}")
            self._spawn_skill_overlay(target_is_enemy=False)

        # 연출 중 버튼 잠금
        if fx_played:
            self._lock_inputs()

        # 다음 비교를 위해 저장
        self._prev_player_hp = p_cur
        self._prev_enemy_hp = e_cur
        # 스킬 사용 기록 초기화 (1회용)
        self._last_skill_used = None

    def _spawn_floating_text(self, target_widget: QtWidgets.QWidget, text: str, is_crit: bool = False) -> None:
        """대상 위젯 근처에 떠오르는 텍스트 생성."""
        if not target_widget:
            return
        pos = target_widget.mapTo(self, target_widget.rect().center())
        FloatingText(self, text, pos, is_crit=is_crit)

    def _spawn_skill_overlay(self, target_is_enemy: bool = True) -> None:
        """스킬 오버레이를 대상 위젯 위에 표시."""
        target_widget = self.enemy_image if target_is_enemy else self.player_image
        pix = self.asset_loader.load_skill_effect(self._last_skill_used or "")
        # 디버그: 어떤 스킬이 어떤 대상에 표시되는지 콘솔에 남김
        print(f"[연출] skill overlay target={'enemy' if target_is_enemy else 'player'}, skill_id={self._last_skill_used}, pix_found={pix is not None}")
        SkillOverlay(target_widget, pix)

    def _is_crit(self, damage: int) -> bool:
        """단순 연출용 크리티컬 판정."""
        if damage >= 80:
            return True
        return random.random() < 0.15

    def _lock_inputs(self, duration_ms: int = 420) -> None:
        """연출 중 잠깐 입력을 잠가 버튼 동시 입력을 방지."""
        widgets = [self.basic_btn, self.item_btn, *self._skill_buttons]
        for w in widgets:
            w.setEnabled(False)
        QtCore.QTimer.singleShot(duration_ms, lambda: self._unlock_inputs(widgets))

    def _unlock_inputs(self, widgets: list[QtWidgets.QWidget]) -> None:
        for w in widgets:
            w.setEnabled(True)

    def remember_skill(self, skill_id: str | None) -> None:
        """외부에서 스킬 ID를 직접 기록할 때 사용 (버튼 외 호출 대비)."""
        self._last_skill_used = skill_id

    def _on_skill_clicked(self, skill_id: str) -> None:
        """버튼 클릭 시 스킬 ID를 기록 후 시그널 전달."""
        # 쿨타임 중이면 무시
        if self._skill_cooldowns.get(skill_id, 0) > 0:
            return
        self._last_skill_used = skill_id
        self.action_skill.emit(skill_id)

    def register_skill_use(self, skill_id: str) -> None:
        """스킬 사용 직전에 호출하여 쿨타임을 설정한다."""
        idx = self._skill_order.get(skill_id)
        if idx is None:
            return
        # 4번째 스킬(인덱스 3)은 5턴 쿨타임
        if idx == 3:
            self._skill_cooldowns[skill_id] = 5
        self._update_skill_buttons()

    def _tick_skill_cooldowns(self) -> None:
        """턴이 증가할 때 쿨타임을 1씩 감소."""
        for sid in list(self._skill_cooldowns.keys()):
            if self._skill_cooldowns[sid] > 0:
                self._skill_cooldowns[sid] = max(0, self._skill_cooldowns[sid] - 1)

    def _update_skill_buttons(self) -> None:
        """쿨타임 상태에 따라 버튼 라벨/활성화 갱신."""
        for sid, btn in zip(self._skill_labels.keys(), self._skill_buttons):
            remain = self._skill_cooldowns.get(sid, 0)
            base_label = self._skill_labels.get(sid, btn.text())
            if remain > 0:
                btn.setEnabled(False)
                btn.setText(f"{base_label}\n({remain}턴 뒤)")
            else:
                btn.setEnabled(True)
                btn.setText(base_label)

    # --------------------------------------------------
    # 이미지 스케일 헬퍼: 종횡비 유지
    # --------------------------------------------------
    def _set_pixmap_keep_aspect(self, label: QtWidgets.QLabel, pixmap: QtGui.QPixmap, padding: int = 0) -> None:
        """라벨 크기에 맞춰 종횡비를 유지하며 스케일링."""
        if pixmap is None:
            label.clear()
            return
        target_w = max(1, label.width() - padding)
        target_h = max(1, label.height() - padding)
        scaled = pixmap.scaled(target_w, target_h, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled)

    def _set_background_scaled(self) -> None:
        """배경은 꽉 채우되 종횡비를 유지하도록 스케일."""
        if not self._bg_pixmap:
            return
        scaled = self._bg_pixmap.scaled(
            self.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.bg_label.setPixmap(scaled)

    def _refresh_item_menu(self) -> None:
        """컨트롤러의 인벤토리 정보를 사용해 소모품 목록을 업데이트."""
        win = self.window()
        if not win or not hasattr(win, "controller"):
            return
        ctrl = getattr(win, "controller")
        try:
            inv = getattr(ctrl.player, "inventory", {}) or {}
            data_items = getattr(ctrl, "data_items", {}) or {}
            entries: list[tuple[str, str]] = []
            if isinstance(inv, dict):
                for item_id, count in inv.items():
                    if count <= 0:
                        continue
                    if data_items.get(item_id, {}).get("type") != "consumable":
                        continue
                    label = f"{data_items.get(item_id, {}).get('name', item_id)} x{count}"
                    entries.append((item_id, label))
            self.set_items(entries)
        except Exception as exc:  # 방어적 처리: UI가 망가지는 것을 방지
            print(f"[아이템 메뉴 갱신 실패] {exc}")
