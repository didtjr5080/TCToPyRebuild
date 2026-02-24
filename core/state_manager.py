from __future__ import annotations

"""게임 상태 중앙 관리자.

- UI는 이 클래스를 통해서만 진행도/인벤토리를 수정합니다.
- 데이터 접근은 DataManager를 통해서만 수행해 MVC/MVVM 경계를 유지합니다.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from . import effects, progression
from .data_manager import DataManager
from .entities import Player
from .models import ItemsData, PlayerProgress, PlayersData, SaveData, Stats


class GameStateManager(QObject):
    # UI 업데이트용 시그널
    on_inventory_changed = pyqtSignal(dict)
    on_hp_changed = pyqtSignal(int, int)  # current, max
    on_exp_changed = pyqtSignal(int, int)  # current, need
    on_level_up = pyqtSignal(int)
    on_stat_points_changed = pyqtSignal(int)
    on_progress_saved = pyqtSignal(object)
    on_player_changed = pyqtSignal(str)
    on_error = pyqtSignal(str)

    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.log = logging.getLogger(__name__ + ".state")
        self.data_manager = DataManager(data_dir)

        # 캐시된 데이터 (읽기 전용 데이터셋)
        self.items_data: ItemsData = self.data_manager.load_items()
        self.skills_data = self.data_manager.load_skills()
        self.monsters_data = self.data_manager.load_monsters()
        self.bosses_data = self.data_manager.load_bosses()
        self.dungeons_data = self.data_manager.load_dungeons()
        self.players_data: PlayersData = self.data_manager.load_players()

        # 진행도/현재 플레이어
        self.save_data: SaveData = self.data_manager.load_save()
        self.active_player_id: Optional[str] = self._decide_active_player_id()
        self._legacy_items_cache: Optional[Dict[str, Dict[str, object]]] = None
        if self.active_player_id and self.active_player_id not in self.save_data.players:
            base_hp = self._profile_base_hp(self.active_player_id)
            self.save_data.players[self.active_player_id] = PlayerProgress(hp=base_hp)
        self.player: Player = self._build_player(self.active_player_id) if self.active_player_id else Player(name="", stats=Stats())
        self._emit_initial_state()

    # --------------------
    # Public actions (UI entrypoints)
    # --------------------
    def select_player(self, player_id: str) -> None:
        """캐릭터 선택 화면에서 슬롯을 선택했을 때 호출됨."""
        if player_id == self.active_player_id:
            return
        self.active_player_id = player_id
        if self.active_player_id not in self.save_data.players:
            self.save_data.players[self.active_player_id] = PlayerProgress(hp=self._profile_base_hp(player_id))
        self.player = self._build_player(player_id)
        self._emit_initial_state()
        self.on_player_changed.emit(player_id)

    def reload_static_data(self) -> None:
        """옵션에서 '데이터 리로드' 버튼을 눌렀을 때 호출됨 (핫로드)."""
        self.items_data = self.data_manager.load_items(force=True)
        self.skills_data = self.data_manager.load_skills(force=True)
        self.monsters_data = self.data_manager.load_monsters(force=True)
        self.bosses_data = self.data_manager.load_bosses(force=True)
        self.dungeons_data = self.data_manager.load_dungeons(force=True)
        self.players_data = self.data_manager.load_players(force=True)
        self._legacy_items_cache = None
        if self.active_player_id:
            self.player = self._build_player(self.active_player_id)
            self._emit_initial_state()

    def use_item(self, item_id: str) -> bool:
        """인벤토리/전투 UI에서 포션(소모품) 버튼 클릭 시 호출됨."""
        progress = self._get_progress()
        inv = progress.inventory
        if inv.get(item_id, 0) <= 0:
            self.on_error.emit("해당 아이템이 없습니다")
            return False

        item = self.data_manager.get_item(item_id)
        if item.type != "consumable" or not item.use_effect:
            self.on_error.emit("사용할 수 없는 아이템입니다")
            return False

        effect = item.use_effect
        max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
        changed = False

        if effect.type == "heal":
            before = self.player.hp
            heal_amount = max(0, int(effect.power))
            self.player.hp = min(max_hp, self.player.hp + heal_amount)
            progress.hp = self.player.hp
            changed = True
            self.on_hp_changed.emit(self.player.hp, max_hp)
            self.log.info("%s 회복 %s->%s", item_id, before, self.player.hp)

        elif effect.type == "cleanse":
            remove_list = effect.remove or []
            before_len = len(self.player.effects)
            self.player.effects = [eff for eff in self.player.effects if getattr(eff, "kind", None) not in remove_list]
            changed = before_len != len(self.player.effects)

        elif effect.type == "buff_stats":
            spec = {
                "type": "buff_stats",
                "duration": int(effect.duration),
                "stats": dict(effect.stats),
                "target": effect.target,
                "scope": effect.scope,
            }
            effects.apply_effect(self.player, spec, logs=[], items=self._items_as_legacy())
            self.player.sync_hp_to_total(self._items_as_legacy())
            progress.hp = self.player.hp
            max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
            self.on_hp_changed.emit(self.player.hp, max_hp)
            changed = True

        if not changed:
            self.on_error.emit("효과가 없습니다")
            return False

        if not self._deduct_inventory(item_id, 1):
            return False
        self._sync_progress_from_player()
        self.data_manager.save_progress(self.save_data)
        self.on_inventory_changed.emit(dict(self.player.inventory))
        self.on_progress_saved.emit(self.save_data)
        return True

    def take_damage(self, amount: int) -> int:
        """전투 중 피해가 계산된 뒤 HP 반영 시 호출됨."""
        dmg = max(0, int(amount))
        before = self.player.hp
        self.player.apply_damage(dmg)
        self._sync_progress_from_player()
        max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
        self.on_hp_changed.emit(self.player.hp, max_hp)
        self.log.info("피해 %s 적용: %s->%s", dmg, before, self.player.hp)
        return self.player.hp

    def gain_exp(self, amount: int) -> int:
        """전투 결과 창에서 '보상 받기' 클릭 시 호출됨."""
        exp_gain = max(0, int(amount))
        before_level = self.player.level
        logs = progression.gain_exp(self.player, exp_gain)
        if self.player.level > before_level:
            self.on_level_up.emit(self.player.level)
        need = progression.exp_to_next(self.player.level)
        self._sync_progress_from_player()
        self.on_exp_changed.emit(self.player.exp, need)
        self.on_stat_points_changed.emit(self.player.stat_points)
        self.log.info("EXP +%s (%s)", exp_gain, "; ".join(logs))
        return self.player.level

    def allocate_stat(self, stat_key: str, points: int = 1) -> bool:
        """스탯 분배 UI에서 적용 버튼을 눌렀을 때 호출됨."""
        allowed = {"attack", "magic", "defense", "magic_resist", "max_hp"}
        if stat_key not in allowed:
            self.on_error.emit("잘못된 스탯입니다")
            return False
        spend = max(1, int(points))
        if self.player.stat_points < spend:
            self.on_error.emit("포인트가 부족합니다")
            return False

        self.player.stat_points -= spend
        self.player.allocated_stats[stat_key] = self.player.allocated_stats.get(stat_key, 0) + spend
        self.player.sync_hp_to_total(self._items_as_legacy())
        self._sync_progress_from_player()
        max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
        self.on_hp_changed.emit(self.player.hp, max_hp)
        self.on_stat_points_changed.emit(self.player.stat_points)
        self.data_manager.save_progress(self.save_data)
        self.on_progress_saved.emit(self.save_data)
        return True

    def save(self) -> None:
        """설정/인벤토리 화면의 저장 버튼 클릭 시 호출됨."""
        self._sync_progress_from_player()
        self.data_manager.save_progress(self.save_data)
        self.on_progress_saved.emit(self.save_data)

    def add_items(self, drops: Dict[str, int]) -> None:
        """전투 보상/퀘스트 보상 수령 시 호출됨."""
        if not drops:
            return
        for item_id, qty in drops.items():
            self._add_inventory(item_id, qty)
        self._sync_progress_from_player()
        self.data_manager.save_progress(self.save_data)
        self.on_inventory_changed.emit(dict(self.player.inventory))
        self.on_progress_saved.emit(self.save_data)

    def equip(self, item_id: str) -> bool:
        """인벤토리 UI에서 장비 더블클릭/장착 버튼 클릭 시 호출됨."""
        item = self.data_manager.get_item(item_id)
        if item.type != "equipment" or not item.slot:
            self.on_error.emit("장착할 수 없는 아이템입니다")
            return False
        inv = self.player.inventory
        if inv.get(item_id, 0) <= 0:
            self.on_error.emit("인벤토리에 없습니다")
            return False
        slot = item.slot
        prev = self.player.equipment.get(slot)
        if prev:
            self._add_inventory(prev, 1)
        inv[item_id] -= 1
        if inv[item_id] <= 0:
            inv.pop(item_id, None)
        self.player.equipment[slot] = item_id
        self.player.sync_hp_to_total(self._items_as_legacy())
        self._sync_progress_from_player()
        max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
        self.on_hp_changed.emit(self.player.hp, max_hp)
        self.on_inventory_changed.emit(dict(self.player.inventory))
        self.data_manager.save_progress(self.save_data)
        self.on_progress_saved.emit(self.save_data)
        return True

    def unequip(self, slot: str) -> bool:
        """장비 슬롯 우클릭/해제 버튼 클릭 시 호출됨."""
        if slot not in {"weapon", "armor", "accessory"}:
            self.on_error.emit("잘못된 슬롯입니다")
            return False
        current = self.player.equipment.get(slot)
        if not current:
            self.on_error.emit("해제할 장비가 없습니다")
            return False
        self._add_inventory(current, 1)
        self.player.equipment[slot] = None
        self.player.sync_hp_to_total(self._items_as_legacy())
        self._sync_progress_from_player()
        max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
        self.on_hp_changed.emit(self.player.hp, max_hp)
        self.on_inventory_changed.emit(dict(self.player.inventory))
        self.data_manager.save_progress(self.save_data)
        self.on_progress_saved.emit(self.save_data)
        return True

    def heal_full(self) -> None:
        """마을/캠프에서 휴식 버튼 클릭 시 호출됨."""
        max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
        self.player.hp = max_hp
        self._sync_progress_from_player()
        self.on_hp_changed.emit(self.player.hp, max_hp)
        self.data_manager.save_progress(self.save_data)
        self.on_progress_saved.emit(self.save_data)

    # --------------------
    # Internal helpers
    # --------------------
    def _decide_active_player_id(self) -> Optional[str]:
        if self.save_data.selected_player_id:
            return self.save_data.selected_player_id
        if self.players_data.default_player_id:
            return self.players_data.default_player_id
        return next(iter(self.players_data.players.keys()), None)

    def _build_player(self, player_id: str) -> Player:
        profile = self.data_manager.get_player_profile(player_id)
        progress = self.save_data.players.get(player_id, PlayerProgress())
        base_stats = profile.base_stats
        hp = progress.hp or base_stats.max_hp
        player = Player(
            name=profile.name,
            stats=base_stats,
            hp=hp,
            skills=profile.skills,
            player_id=player_id,
            level=progress.level,
            exp=progress.exp,
            exp_to_next=progress.exp_to_next,
            stat_points=progress.stat_points,
            inventory=dict(progress.inventory),
            equipment=dict(progress.equipment),
            allocated_stats=dict(progress.allocated_stats),
            base_stats=base_stats,
        )
        player.sync_hp_to_total(self._items_as_legacy())
        return player

    def _profile_base_hp(self, player_id: str) -> int:
        profile = self.data_manager.get_player_profile(player_id)
        return profile.base_stats.max_hp if profile and profile.base_stats else 0

    def _get_progress(self) -> PlayerProgress:
        return self.save_data.players.setdefault(self.active_player_id, PlayerProgress())

    def _deduct_inventory(self, item_id: str, qty: int) -> bool:
        inv = self.player.inventory
        need = max(1, int(qty))
        if inv.get(item_id, 0) < need:
            self.on_error.emit("인벤토리에 수량이 부족합니다")
            return False
        inv[item_id] -= need
        if inv[item_id] <= 0:
            inv.pop(item_id, None)
        self.save_data.players[self.active_player_id].inventory = dict(inv)
        return True

    def _add_inventory(self, item_id: str, qty: int) -> None:
        inv = self.player.inventory
        inv[item_id] = max(0, inv.get(item_id, 0)) + max(1, int(qty))
        self.save_data.players[self.active_player_id].inventory = dict(inv)

    def _sync_progress_from_player(self) -> None:
        if not self.active_player_id:
            return
        prog = self.save_data.players.setdefault(self.active_player_id, PlayerProgress())
        prog.level = self.player.level
        prog.exp = self.player.exp
        prog.exp_to_next = progression.exp_to_next(self.player.level)
        prog.stat_points = self.player.stat_points
        prog.allocated_stats = dict(self.player.allocated_stats)
        prog.hp = self.player.hp
        prog.inventory = dict(self.player.inventory)
        prog.equipment = dict(self.player.equipment)
        self.save_data.selected_player_id = self.active_player_id

    def _emit_initial_state(self) -> None:
        if not self.active_player_id:
            return
        max_hp = self.player.get_total_stats(self._items_as_legacy()).max_hp
        self.on_hp_changed.emit(self.player.hp, max_hp)
        self.on_exp_changed.emit(self.player.exp, progression.exp_to_next(self.player.level))
        self.on_stat_points_changed.emit(self.player.stat_points)
        self.on_inventory_changed.emit(dict(self.player.inventory))

    def _items_as_legacy(self) -> Dict[str, Dict[str, object]]:
        if self._legacy_items_cache is not None:
            return self._legacy_items_cache
        legacy: Dict[str, Dict[str, object]] = {}
        for item_id, item in self.items_data.items.items():
            stats_obj = item.stats or Stats()
            stats_dict = {
                "attack": getattr(stats_obj, "attack", 0),
                "magic": getattr(stats_obj, "magic", 0),
                "defense": getattr(stats_obj, "defense", 0),
                "magic_resist": getattr(stats_obj, "magic_resist", 0),
                "max_hp": getattr(stats_obj, "max_hp", 0),
            }
            special = None
            if item.special:
                special = {
                    "type": getattr(item.special, "type", None),
                    "chance": getattr(item.special, "chance", None),
                    "effect": getattr(item.special, "effect", None),
                    "duration": getattr(item.special, "duration", None),
                    "stat": getattr(item.special, "stat", None),
                    "mult": getattr(item.special, "mult", None),
                    "power": getattr(item.special, "power", None),
                }
            use_effect = None
            if item.use_effect:
                use_effect = {
                    "type": item.use_effect.type,
                    "target": item.use_effect.target,
                    "power": item.use_effect.power,
                    "remove": list(item.use_effect.remove),
                    "duration": item.use_effect.duration,
                    "stats": dict(item.use_effect.stats),
                    "scope": item.use_effect.scope,
                }
            legacy[item_id] = {
                "id": item_id,
                "name": item.name,
                "type": item.type,
                "rarity": item.rarity,
                "desc": item.desc,
                "icon": item.icon,
                "slot": item.slot,
                "stats": stats_dict,
                "special": special,
                "use_effect": use_effect,
            }
        self._legacy_items_cache = legacy
        return legacy