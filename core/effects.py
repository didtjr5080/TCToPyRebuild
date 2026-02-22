from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EffectInstance:
    """전투 한정 상태이상/버프 정보를 담는 인스턴스."""

    kind: str
    duration: int
    power: float = 0.0
    stats_delta: Dict[str, int] = field(default_factory=dict)
    source: Optional[str] = None

    @property
    def id(self) -> str:
        """기존 코드 호환용 id 별칭."""
        return self.kind


def roll_chance(chance: float, rng=random) -> bool:
    """확률 굴림 헬퍼."""
    return rng.random() <= chance


def has_effect(target, effect_kind: str) -> bool:
    """특정 효과가 남아 있는지 확인."""
    return any(e.kind == effect_kind and e.duration > 0 for e in getattr(target, "effects", []))


def _target_max_hp(target, items=None) -> int:
    """대상의 최대 HP를 안전하게 얻는다."""
    if hasattr(target, "get_total_stats"):
        try:
            stats = target.get_total_stats(items) if items is not None else target.get_total_stats()
            return stats.max_hp if stats else getattr(target, "stats", None).max_hp
        except TypeError:
            stats = target.get_total_stats()
            return stats.max_hp if stats else getattr(target, "stats", None).max_hp
    if hasattr(target, "stats"):
        return getattr(target.stats, "max_hp", 0)
    return getattr(target, "hp", 0)


def apply_effect(target, effect_spec: Dict[str, object], logs: List[str], rng=random, items=None) -> None:
    """스킬 정의의 apply_effect 사양을 실제 인스턴스로 부여한다."""
    if not hasattr(target, "effects"):
        return

    effect_type = effect_spec.get("type") or effect_spec.get("effect")
    chance = float(effect_spec.get("chance", 1.0))
    duration = int(effect_spec.get("duration", 0))
    power = float(effect_spec.get("power", 0))
    stats_delta = {k: int(v) for k, v in (effect_spec.get("stats") or {}).items()}
    source = effect_spec.get("note") or effect_spec.get("source")

    if chance < 1.0 and not roll_chance(chance, rng):
        logs.append("효과 실패!")
        return

    # 회복은 즉시 처리
    if effect_type == "heal":
        before = getattr(target, "hp", 0)
        max_hp = _target_max_hp(target, items=items)
        target.hp = min(max_hp, before + int(power))
        logs.append(f"{getattr(target, 'name', '대상')} 체력 회복 +{int(power)}")
        return

    # lifesteal은 combat에서 별도 처리
    if effect_type == "lifesteal":
        return

    # 지속 효과를 리스트에 저장
    inst = EffectInstance(kind=str(effect_type), duration=duration, power=power, stats_delta=stats_delta, source=source)

    if effect_type == "buff_stats":
        target.effects.append(inst)
        delta_text = _format_stats_delta(stats_delta, positive=True)
        logs.append(f"{getattr(target, 'name', '대상')}에게 버프: {delta_text} ({duration}턴)")
        return

    if effect_type == "debuff_stats":
        target.effects.append(inst)
        delta_text = _format_stats_delta(stats_delta, positive=False)
        logs.append(f"{getattr(target, 'name', '대상')}에게 약화: {delta_text} ({duration}턴)")
        return

    if effect_type == "bleed":
        target.effects.append(inst)
        logs.append(f"{getattr(target, 'name', '대상')}에게 출혈 부여! ({duration}턴)")
        return

    if effect_type == "stun":
        target.effects.append(inst)
        logs.append(f"{getattr(target, 'name', '대상')} 기절! ({duration}턴)")
        return

    # 정의되지 않은 타입은 무시
    logs.append(f"알 수 없는 효과: {effect_type}")


def _format_stats_delta(stats_delta: Dict[str, int], positive: bool) -> str:
    """스탯 증감 요약 텍스트 생성."""
    name_map = {
        "attack": "공격",
        "magic": "마법",
        "defense": "방어",
        "magic_resist": "마저",
        "max_hp": "체력",
    }
    parts: List[str] = []
    for key in ["attack", "magic", "defense", "magic_resist", "max_hp"]:
        if key not in stats_delta:
            continue
        val = stats_delta[key]
        sign = "+" if val >= 0 else ""
        parts.append(f"{name_map.get(key, key)} {sign}{val}")
    return "/".join(parts) if parts else ("증가" if positive else "감소")


def tick_end_of_turn(target, logs: List[str]) -> None:
    """턴 종료 시 bleed 틱과 지속 감소를 처리."""
    if not hasattr(target, "effects"):
        return
    remaining: List[EffectInstance] = []
    for effect in list(target.effects):
        if effect.kind == "bleed":
            before = getattr(target, "hp", 0)
            target.hp = max(0, before - effect.power)
            logs.append(f"{getattr(target, 'name', '대상')} 출혈 피해 {effect.power} (HP {before}->{target.hp})")
        effect.duration -= 1
        if effect.duration > 0:
            remaining.append(effect)
        else:
            logs.append(f"{getattr(target, 'name', '대상')}의 {effect.kind} 종료")
    target.effects = remaining


def clear_all_battle_effects(target) -> None:
    """전투 종료 시 효과를 모두 제거."""
    if hasattr(target, "effects"):
        target.effects = []


def can_act(target, logs: List[str]) -> bool:
    """스턴이면 행동 불가 로그를 남기고 False 반환."""
    if has_effect(target, "stun"):
        logs.append(f"{getattr(target, 'name', '대상')}은(는) 기절해 움직일 수 없다!")
        return False
    return True
