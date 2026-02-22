from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # 순환 참조 방지용 타입 체크
    from .effects import EffectInstance


@dataclass
class Stats:
    """공격/마법/방어/마법저항/체력 스탯."""

    attack: int = 0
    magic: int = 0
    defense: int = 0
    magic_resist: int = 0
    max_hp: int = 0

    def with_bonus(self, bonus: Dict[str, int]) -> "Stats":
        """추가 스탯을 더한 새 Stats 반환."""
        return Stats(
            attack=self.attack + bonus.get("attack", 0),
            magic=self.magic + bonus.get("magic", 0),
            defense=self.defense + bonus.get("defense", 0),
            magic_resist=self.magic_resist + bonus.get("magic_resist", 0),
            max_hp=self.max_hp + bonus.get("max_hp", 0),
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "attack": self.attack,
            "magic": self.magic,
            "defense": self.defense,
            "magic_resist": self.magic_resist,
            "max_hp": self.max_hp,
        }


@dataclass
class BattleResult:
    """전투 결과."""

    winner: str  # "player" 또는 "enemy"
    exp: int = 0
    drops: List[str] = field(default_factory=list)  # 표시용 문자열
    drop_details: List[tuple[str, int]] = field(default_factory=list)  # (item_id, qty)
    logs: List[str] = field(default_factory=list)


@dataclass
class Actor:
    """플레이어/적 공통 속성."""

    name: str
    stats: Stats
    hp: int = 0
    skills: List[str] = field(default_factory=list)
    effects: List["EffectInstance"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hp <= 0:
            self.hp = self.stats.max_hp

    def apply_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)

    def heal(self, amount: int) -> None:
        self.hp = min(self.stats.max_hp, self.hp + amount)

    def _effect_bonus(self) -> Dict[str, int]:
        """버프/디버프 지속 효과에서 스탯 보정치를 합산."""
        bonus: Dict[str, int] = {}
        for eff in getattr(self, "effects", []):
            if getattr(eff, "duration", 0) <= 0:
                continue
            if eff.kind not in ("buff_stats", "debuff_stats"):
                continue
            for key, val in (eff.stats_delta or {}).items():
                bonus[key] = bonus.get(key, 0) + int(val)
        return bonus

    def get_total_stats(self, items: Optional[Dict[str, object]] = None) -> Stats:
        """적 전용 기본 스탯 + 효과 버프를 반환."""
        base = self.stats
        eff_bonus = self._effect_bonus()
        return base.with_bonus(eff_bonus)

    @property
    def current_hp(self) -> int:
        """기존 코드 호환용 HP alias."""
        return self.hp

    @current_hp.setter
    def current_hp(self, value: int) -> None:
        self.hp = value

    def is_dead(self) -> bool:
        return self.hp <= 0


@dataclass
class Player(Actor):
    """플레이어 상태."""

    player_id: str = ""
    level: int = 1
    exp: int = 0
    exp_to_next: int = 0
    stat_points: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)
    equipment: Dict[str, Optional[str]] = field(default_factory=dict)
    allocated_stats: Dict[str, int] = field(default_factory=dict)
    base_stats: Stats = field(default_factory=Stats)

    def __post_init__(self) -> None:
        super().__post_init__()
        # 구버전 리스트 인벤을 dict로 자동 변환
        if isinstance(self.inventory, list):
            migrated: Dict[str, int] = {}
            for item_id in self.inventory:
                migrated[item_id] = migrated.get(item_id, 0) + 1
            self.inventory = migrated
        if self.inventory is None:
            self.inventory = {}
        if not self.equipment:
            self.equipment = {"weapon": None, "armor": None, "accessory": None}

    def total_stats(self, items: Optional[object] = None) -> Stats:
        """장비/스탯분배/전투 버프가 반영된 총합 스탯 계산."""
        bonus: Dict[str, int] = {k: int(v) for k, v in self.allocated_stats.items()}
        resolver = None
        if items:
            # data_store 인스턴스 또는 dict 모두 지원
            resolver = items.get if hasattr(items, "get") else None
            if hasattr(items, "get_item"):
                resolver = items.get_item
        for slot, item_id in self.equipment.items():
            if not item_id:
                continue
            item_obj = resolver(item_id) if resolver else None
            if not item_obj:
                continue
            stats_dict = item_obj.get("stats", {}) if isinstance(item_obj, dict) else getattr(item_obj, "stats", {})
            for key, value in stats_dict.items():
                bonus[key] = bonus.get(key, 0) + int(value)

        # 장비 특수효과: stat_multiplier 는 스탯을 곱연산으로 강화 (예: 주문력 20% 증가)
        multipliers: Dict[str, float] = {k: 1.0 for k in ["attack", "magic", "defense", "magic_resist", "max_hp"]}
        for slot, item_id in self.equipment.items():
            if not item_id:
                continue
            item_obj = resolver(item_id) if resolver else None
            if not item_obj:
                continue
            special = item_obj.get("special") if isinstance(item_obj, dict) else getattr(item_obj, "special", None)
            if isinstance(special, dict) and special.get("type") == "stat_multiplier":
                stat_key = special.get("stat")
                mult = float(special.get("mult", 1.0))
                if stat_key in multipliers and mult > 0:
                    multipliers[stat_key] *= mult

        # 전투 한정 버프/디버프 합산
        for key, val in self._effect_bonus().items():
            bonus[key] = bonus.get(key, 0) + val

        base = self.base_stats.with_bonus(bonus)
        # 곱연산 적용 후 최종 Stats 생성
        return Stats(
            attack=int(base.attack * multipliers["attack"]),
            magic=int(base.magic * multipliers["magic"]),
            defense=int(base.defense * multipliers["defense"]),
            magic_resist=int(base.magic_resist * multipliers["magic_resist"]),
            max_hp=int(base.max_hp * multipliers["max_hp"]),
        )

    def get_total_stats(self, items: Optional[Dict[str, object]] = None) -> Stats:
        """total_stats 별칭."""
        return self.total_stats(items)

    def sync_hp_to_total(self, items: Optional[Dict[str, object]] = None) -> None:
        """총합 HP 변경 시 현재 HP 클램프."""
        max_hp = self.total_stats(items).max_hp
        self.hp = min(self.hp, max_hp)


@dataclass
class Enemy(Actor):
    """적/보스 정보."""

    enemy_id: str = ""
    ai: str = "basic"
    gimmicks: List[Dict] = field(default_factory=list)
    drop_table: Optional[str] = None
    is_boss: bool = False
