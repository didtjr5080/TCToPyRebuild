from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .entities import Player, Enemy, BattleResult
from .effects import apply_effect, tick_end_of_turn, can_act, clear_all_battle_effects, roll_chance
from . import loot
from . import items as items_util


@dataclass
class BattleState:
    """전투 진행 상태."""

    player: Player
    enemy: Enemy
    turn: int = 1
    turn_index: int = 1
    logs: List[str] = field(default_factory=list)
    expected_exp: int = 0
    drop_table_id: Optional[str] = None
    gimmick_used: Dict[int, bool] = field(default_factory=dict)


class BattleEngine:
    """턴제 전투 엔진."""

    def __init__(self, data_store) -> None:
        self.data_store = data_store
        self.skills = data_store.skills
        self.items = data_store.items
        self.drop_tables = data_store.drop_tables

    def start_battle(self, player: Player, enemy: Enemy, expected_exp: int = 0, drop_table_id: Optional[str] = None) -> BattleState:
        state = BattleState(player=player, enemy=enemy, expected_exp=expected_exp, drop_table_id=drop_table_id)
        state.logs.append(f"{enemy.name}와(과) 전투 시작!")
        return state

    def player_use_skill(self, state: BattleState, skill_id: str) -> Optional[BattleResult]:
        """플레이어 스킬 사용."""
        if not can_act(state.player, state.logs):
            return self._after_player_action(state)
        result = self._use_skill(state=state, attacker=state.player, defender=state.enemy, skill_id=skill_id, logs=state.logs, is_player=True)
        if result:
            return result
        if state.enemy.is_dead():
            return self._finish(state, winner="player")
        return self._after_player_action(state)

    def player_basic_attack(self, state: BattleState) -> Optional[BattleResult]:
        """기본공격은 내부 기본 스킬로 처리."""
        return self.player_use_skill(state, "__basic__")

    def player_use_item(self, state: BattleState, item_id: str) -> Optional[BattleResult]:
        if not can_act(state.player, state.logs):
            return self._after_player_action(state)
        # 인벤토리 보유 체크
        inv = items_util._ensure_inventory_dict(state.player)  # 내부 용도: dict 강제
        if inv.get(item_id, 0) <= 0:
            state.logs.append("해당 아이템이 없습니다")
            return self._after_player_action(state)
        success, msg = items_util.apply_consumable_in_battle(state.player, item_id, self.data_store, state.logs)
        if success:
            items_util.remove_item_from_inventory(state.player, item_id, 1)
        if msg:
            state.logs.append(msg)
        return self._after_player_action(state)

    def _after_player_action(self, state: BattleState) -> Optional[BattleResult]:
        # 적 행동
        result = self._enemy_action(state)
        if result:
            return result
        # 턴 종료 처리
        end_result = self._end_of_turn(state)
        state.turn += 1
        state.turn_index += 1
        return end_result

    def _enemy_action(self, state: BattleState) -> Optional[BattleResult]:
        if not can_act(state.enemy, state.logs):
            return None

        # 보스 기믹 선처리
        if state.enemy.ai == "boss":
            self._handle_gimmicks(state)

        # 기본 AI: 스킬 목록에서 랜덤 선택, 없으면 기본공격
        pool = state.enemy.skills if state.enemy.skills else ["__basic__"]
        skill_choice = random.choice(pool)

        result = self._use_skill(state=state, attacker=state.enemy, defender=state.player, skill_id=skill_choice, logs=state.logs, is_player=False)
        if result:
            return result
        if state.player.hp <= 0:
            return self._finish(state, winner="enemy")
        return None

    def _end_of_turn(self, state: BattleState) -> Optional[BattleResult]:
        for target in [state.player, state.enemy]:
            tick_end_of_turn(target, state.logs)
        if state.player.hp <= 0:
            return self._finish(state, winner="enemy")
        if state.enemy.is_dead():
            return self._finish(state, winner="player")
        return None

    def _finish(self, state: BattleState, winner: str) -> BattleResult:
        drops: List[tuple[str, int]] = []
        if winner == "player" and state.drop_table_id:
            drops = loot.roll_drop(state.drop_table_id, self.data_store, random)
            display = []
            for item_id, qty in drops:
                name = self.items.get(item_id, {}).get("name", item_id)
                display.append(f"{name} x{qty}")
            state.logs.append(f"드랍: {', '.join(display) if display else '없음'}")
        result = BattleResult(
            winner=winner,
            exp=state.expected_exp if winner == "player" else 0,
            drops=[f"{self.items.get(i, {}).get('name', i)} x{q}" for i, q in drops],
            drop_details=drops,
            logs=list(state.logs),
        )
        # 전투 종료 시 효과를 비워 전투 간 누적을 방지
        clear_all_battle_effects(state.player)
        clear_all_battle_effects(state.enemy)
        # 전투 종료 후 플레이어 체력을 최대치로 회복
        if isinstance(state.player, Player):
            try:
                max_hp = state.player.get_total_stats(self.items).max_hp
            except TypeError:
                max_hp = state.player.get_total_stats().max_hp
            state.player.hp = max_hp
        return result

    def _use_skill(self, state: BattleState, attacker: Player | Enemy, defender: Player | Enemy, skill_id: str, logs: List[str], is_player: bool) -> Optional[BattleResult]:
        """스킬 1회 사용 처리."""
        # 기본공격 가상 스킬
        skill_data = self.skills.get(skill_id)
        if skill_id == "__basic__" and not skill_data:
            skill_data = {
                "name": "기본 공격",
                "type": "physical",
                "base_physical": 10,
                "base_magic": 0,
                "scale": {"attack": 0.2, "magic": 0.0},
                "cost": 0,
                "cooldown": 0,
                "apply_effect": None,
            }
        if not skill_data:
            logs.append("알 수 없는 스킬")
            return None

        atk_stats = attacker.get_total_stats(self.items) if isinstance(attacker, Player) else attacker.get_total_stats()
        def_stats = defender.get_total_stats(self.items) if isinstance(defender, Player) else defender.get_total_stats()

        scale = skill_data.get("scale", {}) or {}
        base_physical = skill_data.get("base_physical", 0)
        base_magic = skill_data.get("base_magic", 0)
        scale_attack = scale.get("attack", 0)
        scale_magic = scale.get("magic", 0)

        # 데미지 계산
        physical = base_physical + atk_stats.attack * scale_attack
        magic = base_magic + atk_stats.magic * scale_magic

        phys_final = max(0, physical - def_stats.defense * scale_attack)
        magic_final = max(0, magic - def_stats.magic_resist * scale_magic)

        phys_int = int(phys_final)
        magic_int = int(magic_final)
        total_damage = phys_int + magic_int

        defender.apply_damage(total_damage)

        if is_player:
            logs.append(f"플레이어가 {skill_data.get('name', skill_id)} 사용!")
            logs.append(f"적에게 물리 {phys_int} / 마법 {magic_int} 피해!")
            logs.append(f"적 HP: {defender.hp}/{def_stats.max_hp}")
        else:
            logs.append(f"{attacker.name}가 {skill_data.get('name', skill_id)} 사용!")
            logs.append(f"플레이어에게 물리 {phys_int} / 마법 {magic_int} 피해!")
            logs.append(f"플레이어 HP: {defender.hp}/{def_stats.max_hp}")

        # apply_effect 처리 (배열/단일)
        lifesteal_power = 0.0
        apply_spec = skill_data.get("apply_effect")
        effect_list = []
        if isinstance(apply_spec, list):
            effect_list = apply_spec
        elif isinstance(apply_spec, dict):
            effect_list = [apply_spec]

        for eff in effect_list:
            target_label = eff.get("target", "self")
            target = attacker if target_label == "self" else defender
            eff_type = eff.get("type") or eff.get("effect")

            if eff_type == "lifesteal":
                lifesteal_power += float(eff.get("power", 0))
                continue
            apply_effect(target, eff, logs, rng=random, items=self.items if isinstance(target, Player) else None)

        # on_hit 장신구 처리 (플레이어만 대상)
        if is_player:
            accessory = attacker.equipment.get("accessory") if isinstance(attacker, Player) else None
            if accessory:
                item = self.items.get(accessory, {})
                special = item.get("special") if isinstance(item, dict) else None
                if special and special.get("type") == "on_hit":
                    if roll_chance(float(special.get("chance", 0)), random):
                        spec = {
                            "type": special.get("effect"),
                            "duration": special.get("duration", 1),
                            "power": special.get("power", 0),
                            "target": "enemy",
                        }
                        apply_effect(defender, spec, logs, rng=random, items=self.items if isinstance(defender, Player) else None)

        # lifesteal 처리 (총 피해량 기준)
        if lifesteal_power > 0:
            heal_amount = int(total_damage * lifesteal_power)
            before = attacker.hp
            max_hp = attacker.get_total_stats(self.items).max_hp if isinstance(attacker, Player) else attacker.get_total_stats().max_hp
            attacker.hp = min(max_hp, attacker.hp + heal_amount)
            logs.append(f"흡혈 발동, 체력 {before}->{attacker.hp}")

        if defender.hp <= 0:
            return self._finish(state, winner="player" if is_player else "enemy")
        return None

    def _handle_gimmicks(self, state: BattleState) -> None:
        """보스 기믹 발동 처리."""
        gimmicks = getattr(state.enemy, "gimmicks", []) or []
        for idx, gimmick in enumerate(gimmicks):
            if gimmick is None:
                continue
            once = gimmick.get("once", False)
            if once and state.gimmick_used.get(idx):
                continue
            trigger = gimmick.get("trigger")
            should_fire = False
            if trigger == "every_n_turns":
                n = gimmick.get("n", 1)
                should_fire = n > 0 and state.turn_index % n == 0
            elif trigger == "hp_below":
                ratio = gimmick.get("ratio", 0)
                max_hp = state.enemy.stats.max_hp or 1
                should_fire = (state.enemy.hp / max_hp) <= ratio
            if not should_fire:
                continue
            action = gimmick.get("action", {})
            if action.get("type") == "apply_effect":
                target_label = action.get("target", "player")
                target = state.player if target_label == "player" else state.enemy
                spec = {
                    "type": action.get("effect"),
                    "duration": action.get("duration", 1),
                    "power": action.get("power", 0),
                }
                apply_effect(target=target, effect_spec=spec, logs=state.logs, rng=random, items=self.items if isinstance(target, Player) else None)
            if once:
                state.gimmick_used[idx] = True
