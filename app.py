from __future__ import annotations

import json
import os
import random
import traceback
from pathlib import Path
from typing import Dict, Any, Optional

from PyQt6 import QtWidgets

from core.entities import Player, Enemy, Stats
from core import progression, save as save_module
from core.combat import BattleEngine
from core import items as items_util
from core.dungeon import DungeonProgress
from core.data_store import DataStore
from ui.main_window import MainWindow

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SAVE_PATH = BASE_DIR / "save" / "progress.json"


class GameController:
    """데이터/전투/저장 로직을 묶는 컨트롤러."""

    def __init__(self) -> None:
        self.data_store = DataStore()
        self.data_store.load_all(DATA_DIR)
        print(
            f"[로드 요약] players={len(self.data_store.players)}, skills={len(self.data_store.skills)}, "
            f"monsters={len(self.data_store.monsters)}"
        )
        print(f"[로드 요약] default_player_id={self.data_store.default_player_id}")

        self.data_items = self.data_store.items
        self.data_drop_tables = self.data_store.drop_tables
        self.data_dungeons = self._load_json(DATA_DIR / "dungeons.json")
        self.data_bosses = self.data_store.bosses or {}

        self.progress = save_module.load_progress(
            str(SAVE_PATH),
            self.data_store.players,
            self.data_store.default_player_id,
        )
        self.selected_player_id = self.progress.get("selected_player_id") or self._select_player_id()
        print(
            f"[로드 요약] 선택된 플레이어: {self.selected_player_id}, 스킬={self.data_store.players.get(self.selected_player_id, {}).get('skills', [])}"
        )

        self._load_player_state(self.selected_player_id)

        self.battle_engine = BattleEngine(self.data_store)
        self.current_battle = None
        self.last_zone_stage: Optional[tuple[str, int]] = None
        self.last_boss_type: Optional[str] = None

    # 데이터 로드/세이브
    def _load_json(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_player(self) -> Player:
        # 선택된 플레이어 상태를 기반으로 Player 객체 생성
        pdata = self.data_store.get_player(self.selected_player_id)
        entry = self.progress.get("players", {}).get(self.selected_player_id, {})
        p_state = entry.get("player_state", {})
        base_stats_dict = pdata.get("base_stats", {})
        base_stats = Stats(
            attack=base_stats_dict.get("attack", 0),
            magic=base_stats_dict.get("magic", 0),
            defense=base_stats_dict.get("defense", 0),
            magic_resist=base_stats_dict.get("magic_resist", 0),
            max_hp=base_stats_dict.get("max_hp", 0),
        )
        allocated = p_state.get("allocated_stats", {})
        level = p_state.get("level", 1)
        exp = p_state.get("exp", 0)
        stat_points = p_state.get("stat_points", 0)
        skills = pdata.get("skills", [])
        inventory = items_util._ensure_inventory_dict(entry.get("inventory", {"potion_small": 1}))
        equipment = entry.get("equipment", {"weapon": None, "armor": None, "accessory": None})
        hp_saved = p_state.get("hp", base_stats.max_hp)
        current_hp = min(hp_saved or base_stats.max_hp, base_stats.max_hp)
        return Player(
            player_id=self.selected_player_id,
            name=pdata.get("name", "모험가"),
            level=level,
            exp=exp,
            exp_to_next=progression.exp_to_next(level),
            stat_points=stat_points,
            skills=skills,
            inventory=inventory,
            equipment=equipment,
            allocated_stats=allocated,
            effects=[],
            base_stats=base_stats,
            stats=base_stats,
            hp=current_hp,
        )

    def _select_player_id(self) -> str:
        """기본 플레이어 ID 결정."""
        preferred_id = "char_0" if "char_0" in self.data_store.players else self.data_store.default_player_id
        if not preferred_id and self.data_store.players:
            preferred_id = next(iter(self.data_store.players.keys()))
        return preferred_id

    def _load_player_state(self, player_id: str) -> None:
        """저장 데이터에서 플레이어 상태를 불러온다."""
        self.selected_player_id = player_id
        self.player = self._build_player()
        entry = self.progress.get("players", {}).get(player_id, {})
        dungeon_state = entry.get("dungeon_progress", {})
        self.dungeon_progress = DungeonProgress(
            unlocked_zones=dungeon_state.get("unlocked_zones", ["1"]),
            unlocked_stage_by_zone=dungeon_state.get("unlocked_stage_by_zone", {"1": 1}),
        )
        # 캐릭터 전환 시에는 체력을 최대치로 회복하여 이전 전투 피해가 남지 않도록 처리
        max_hp = self.player.get_total_stats(self.data_items).max_hp
        self.player.hp = max_hp

    def _store_player_state(self) -> None:
        """현재 플레이어 상태를 progress에 반영."""
        entry = self.progress.setdefault("players", {}).setdefault(self.selected_player_id, {})
        entry["player_state"] = {
            "level": self.player.level,
            "exp": self.player.exp,
            "exp_to_next": self.player.exp_to_next,
            "stat_points": self.player.stat_points,
            "allocated_stats": self.player.allocated_stats,
            "hp": self.player.hp,
        }
        entry["inventory"] = dict(self.player.inventory)
        entry["equipment"] = dict(self.player.equipment)
        entry["dungeon_progress"] = {
            "unlocked_zones": list(self.dungeon_progress.unlocked_zones),
            "unlocked_stage_by_zone": dict(self.dungeon_progress.unlocked_stage_by_zone),
        }
        self.progress["selected_player_id"] = self.selected_player_id

    def save(self) -> None:
        self._store_player_state()
        save_module.save_progress(str(SAVE_PATH), self.progress)

    # 요약/헬퍼
    def player_summary(self) -> str:
        stats = self.player.get_total_stats(self.data_items)
        exp_need = progression.exp_to_next(self.player.level)
        return (
            f"Lv {self.player.level} / EXP {self.player.exp}/{exp_need} / 포인트 {self.player.stat_points}\n"
            f"공격 {stats.attack} / 방어 {stats.defense} / HP {self.player.hp}/{stats.max_hp}"
        )

    def stats_summary(self) -> str:
        stats = self.player.get_total_stats(self.data_items)
        exp_need = progression.exp_to_next(self.player.level)
        return (
            f"레벨 {self.player.level}\n"
            f"EXP {self.player.exp}/{exp_need}\n"
            f"공격 {stats.attack} / 방어 {stats.defense} / 체력 {stats.max_hp}\n"
            f"남은 포인트 {self.player.stat_points}"
        )

    def skill_pairs(self):
        return [(sid, self.data_store.skills.get(sid, {}).get("name", sid)) for sid in self.player.skills]

    def usable_consumables(self):
        inv = items_util._ensure_inventory_dict(self.player)
        return [item_id for item_id, cnt in inv.items() if cnt > 0 and self.data_items.get(item_id, {}).get("type") == "consumable"]

    def sync_player_hp(self) -> None:
        max_hp = self.player.get_total_stats(self.data_items).max_hp
        self.player.hp = min(self.player.hp, max_hp)

    # 던전/전투 시작
    def start_stage(self, zone: str, stage: int):
        stages = self.data_dungeons.get("zones", {}).get(zone, {}).get("stages", {})
        stage_data = stages.get(str(stage))
        if not stage_data:
            return None
        expected_exp = stage_data.get("exp", 0)
        drop_table = None
        if stage == 5:
            boss_id = stage_data.get("boss_id") or self.data_store.get_dungeon_boss_id(zone)
            boss_data = self.data_store.get_boss(boss_id) if boss_id else {}
            if boss_data:
                drop_table = boss_data.get("drop_table") if boss_data else None
                enemy = self._build_enemy(boss_id or "unknown_boss", boss_data, is_boss=True, drop_table=drop_table)
            else:
                pool = stage_data.get("monster_pool", [])
                if not pool:
                    return None
                monster_id = random.choice(pool)
                monster_data = self.data_store.monsters.get(monster_id, {})
                enemy = self._build_enemy(monster_id, monster_data, is_boss=False)
        else:
            pool = stage_data.get("monster_pool", [])
            if not pool:
                return None
            monster_id = random.choice(pool)
            monster_data = self.data_store.monsters.get(monster_id, {})
            enemy = self._build_enemy(monster_id, monster_data, is_boss=False)
        state = self.battle_engine.start_battle(self.player, enemy, expected_exp=expected_exp, drop_table_id=drop_table or getattr(enemy, "drop_table", None))
        self.current_battle = state
        self.last_zone_stage = (zone, stage)
        self.last_boss_type = None
        return state

    def start_special_boss(self, boss_id: str):
        boss_data = self.data_store.bosses.get("special_bosses", {}).get(boss_id, {})
        if not boss_data:
            return None
        enemy = self._build_enemy(boss_id, boss_data, is_boss=True, drop_table=boss_data.get("drop_table"))
        state = self.battle_engine.start_battle(self.player, enemy, expected_exp=0, drop_table_id=enemy.drop_table)
        self.current_battle = state
        self.last_zone_stage = None
        self.last_boss_type = boss_id
        return state

    def _build_enemy(self, enemy_id: str, data: Dict[str, Any], is_boss: bool, drop_table: Optional[str] = None) -> Enemy:
        stats_dict = data.get("stats", {})
        stats = Stats(
            attack=stats_dict.get("attack", 0),
            magic=stats_dict.get("magic", 0),
            defense=stats_dict.get("defense", 0),
            magic_resist=stats_dict.get("magic_resist", 0),
            max_hp=stats_dict.get("max_hp", 1),
        )
        return Enemy(
            enemy_id=enemy_id,
            name=data.get("name", enemy_id),
            stats=stats,
            ai=data.get("ai", "basic"),
            skills=data.get("skills", []),
            gimmicks=data.get("gimmicks", []),
            drop_table=drop_table or data.get("drop_table"),
            is_boss=is_boss,
        )

    # 전투 액션
    def player_basic(self):
        result = self.battle_engine.player_basic_attack(self.current_battle)
        return result

    def player_use_skill(self, skill_id: str):
        result = self.battle_engine.player_use_skill(self.current_battle, skill_id)
        return result

    def player_use_item(self, item_id: str):
        result = self.battle_engine.player_use_item(self.current_battle, item_id)
        return result

    def finish_battle(self, result):
        """전투 종료 후 보상/저장."""
        if result.winner == "player":
            logs = progression.gain_exp(self.player, result.exp)
            self.current_battle.logs.extend(logs)
            self.player.exp_to_next = progression.exp_to_next(self.player.level)
            drop_list = getattr(result, "drop_details", []) or []
            for drop_id, qty in drop_list:
                items_util.add_item_to_inventory(self.player, drop_id, qty)
            if self.last_zone_stage:
                zone, stage = self.last_zone_stage
                self.dungeon_progress.clear_stage(zone, stage)
        else:
            # 패배 시 체력 회복 후 복귀
            self.player.hp = self.player.get_total_stats(self.data_items).max_hp
        self.save()
        self.current_battle = None

    # 인벤토리/장비
    def equip_item(self, item_id: str):
        success, msg = items_util.equip_item(self.player, item_id, self.data_store)
        if not success:
            print(f"[장착 실패] {msg}")
            return
        self.sync_player_hp()
        self.save()

    def unequip(self, slot: str):
        success, msg = items_util.unequip_slot(self.player, slot, self.data_store)
        if not success:
            print(f"[해제 실패] {msg}")
            return
        self.sync_player_hp()
        self.save()

    def apply_stat_points(self, spend: Dict[str, int]):
        total = sum(spend.values())
        if total > self.player.stat_points:
            return
        self.player.stat_points -= total
        for key, value in spend.items():
            if value <= 0:
                continue
            self.player.allocated_stats[key] = self.player.allocated_stats.get(key, 0) + value
        self.sync_player_hp()
        self.save()

    def switch_player(self, player_id: str):
        """현재 상태 저장 후 다른 캐릭터로 전환."""
        if player_id not in self.data_store.players:
            return
        self._store_player_state()
        self.selected_player_id = player_id
        self._load_player_state(player_id)
        self.save()


def main():
    stage = "start"
    controller: Optional[GameController] = None
    last_player_id = None
    last_monster_id = None
    try:
        stage = "load_all"
        controller = GameController()
        last_player_id = getattr(controller, "selected_player_id", None)

        stage = "ui_init"
        app = QtWidgets.QApplication([])
        app.setStyleSheet(
            """
            QWidget { background-color: #0f1b2c; color: #e8f1ff; font-family: 'Segoe UI', 'Noto Sans KR', 'Malgun Gothic'; }
            QPushButton { background-color: #1f3552; border: 1px solid #3a5c8a; padding: 10px 14px; border-radius: 6px; color: #e8f1ff; }
            QPushButton:hover { background-color: #2a4670; }
            QPushButton:disabled { background-color: #1a2636; color: #6b7b91; border-color: #24364c; }
            QPushButton[locked="true"] { background-color: #141c28; color: #556070; border-color: #1f2b3b; }
            QPushButton[locked="true"]:hover { background-color: #141c28; }
            QGroupBox { border: 1px solid #24405f; border-radius: 8px; margin-top: 12px; padding: 8px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: #8fb4ff; }
            QLabel { font-size: 14px; }
            QTextEdit { background-color: #0c1522; border: 1px solid #1e2d45; border-radius: 6px; }
            QListWidget { background-color: #0c1522; border: 1px solid #1e2d45; border-radius: 6px; }
            QProgressBar { background-color: #0c1522; border: 1px solid #1e2d45; border-radius: 6px; text-align: center; }
            QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #49c6ff, stop:1 #3fa5ff); border-radius: 6px; }
            QScrollArea { border: none; }
            """
        )

        stage = "ui_show"
        window = MainWindow(controller)
        window.show()

        stage = "qt_exec"
        app.exec()
    except Exception:
        print(f"[오류] stage={stage}, data_dir={DATA_DIR}")
        if last_player_id:
            print(f"[오류] 선택된 player_id={last_player_id}")
        if last_monster_id:
            print(f"[오류] 마지막 monster_id={last_monster_id}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
