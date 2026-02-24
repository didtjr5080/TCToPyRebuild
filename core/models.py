from __future__ import annotations

"""데이터 스키마 정의 (dataclass 기반).

- JSON 키를 외우지 않고 IDE 자동완성을 활용하도록 필드를 엄격히 선언합니다.
- 향후 pydantic으로 교체하기 쉽게 설계했으며, 현재는 표준 라이브러리 dataclass를 사용합니다.
- 왜 dataclass인가? 간단한 데이터 컨테이너이면서 타입 검증/자동완성 이점을 주며,
  런타임 의존성이 없어서 초기에 부담이 적기 때문입니다.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# --------------------
# 공통 자료형
# --------------------
@dataclass
class Stats:
    attack: int = 0
    magic: int = 0
    defense: int = 0
    magic_resist: int = 0
    max_hp: int = 0


@dataclass
class SkillScale:
    attack: float = 0.0
    magic: float = 0.0


@dataclass
class ItemSpecial:
    type: str
    chance: Optional[float] = None
    effect: Optional[str] = None
    duration: Optional[int] = None
    stat: Optional[str] = None
    mult: Optional[float] = None
    power: Optional[float] = None


@dataclass
class UseEffect:
    type: str
    target: str = "self"
    power: int = 0
    remove: List[str] = field(default_factory=list)
    duration: int = 0
    stats: Dict[str, int] = field(default_factory=dict)
    scope: str = "battle"


@dataclass
class Item:
    id: str
    name: str
    type: str  # equipment|consumable|material
    rarity: str
    desc: str
    icon: Optional[str]
    slot: Optional[str]
    stats: Stats = field(default_factory=Stats)
    special: Optional[ItemSpecial] = None
    use_effect: Optional[UseEffect] = None


@dataclass
class DropEntry:
    item: str
    chance: float
    min: int = 1
    max: int = 1


@dataclass
class ItemsData:
    version: str
    items: Dict[str, Item] = field(default_factory=dict)
    drop_tables: Dict[str, List[DropEntry]] = field(default_factory=dict)


@dataclass
class SkillEffect:
    type: str
    target: str = "enemy"
    chance: float = 1.0
    duration: int = 0
    power: float = 0.0
    stats: Dict[str, int] = field(default_factory=dict)
    scope: str = "battle"


@dataclass
class Skill:
    id: str
    name: str
    type: str
    base_physical: float
    base_magic: float
    scale: SkillScale = field(default_factory=SkillScale)
    cost: int = 0
    cooldown: int = 0
    apply_effects: List[SkillEffect] = field(default_factory=list)


@dataclass
class SkillsData:
    version: str
    skills: Dict[str, Skill] = field(default_factory=dict)


@dataclass
class Monster:
    id: str
    name: str
    stats: Stats
    ai: str = "basic"
    skills: List[str] = field(default_factory=list)
    gimmicks: List[Dict[str, object]] = field(default_factory=list)
    drop_table: Optional[str] = None


@dataclass
class Boss(Monster):
    drop_table: Optional[str] = None
    is_special: bool = False


@dataclass
class MonstersData:
    version: str
    monsters: Dict[str, Monster] = field(default_factory=dict)


@dataclass
class BossesData:
    version: str
    dungeon_bosses: Dict[str, Boss] = field(default_factory=dict)
    special_bosses: Dict[str, Boss] = field(default_factory=dict)


@dataclass
class DungeonStage:
    stage_id: str
    monster_pool: List[str] = field(default_factory=list)
    boss_id: Optional[str] = None
    exp: int = 0


@dataclass
class DungeonZone:
    zone_id: str
    stages: Dict[str, DungeonStage] = field(default_factory=dict)


@dataclass
class DungeonsData:
    version: str
    zones: Dict[str, DungeonZone] = field(default_factory=dict)


@dataclass
class PlayerProgress:
    level: int = 1
    exp: int = 0
    exp_to_next: int = 0
    stat_points: int = 0
    allocated_stats: Dict[str, int] = field(default_factory=dict)
    hp: int = 0
    inventory: Dict[str, int] = field(default_factory=dict)
    equipment: Dict[str, Optional[str]] = field(default_factory=lambda: {"weapon": None, "armor": None, "accessory": None})
    dungeon_progress: Dict[str, object] = field(default_factory=dict)


@dataclass
class SaveData:
    version: str
    selected_player_id: Optional[str]
    players: Dict[str, PlayerProgress] = field(default_factory=dict)


@dataclass
class PlayerProfile:
    id: str
    name: str
    base_stats: Stats
    skills: List[str] = field(default_factory=list)


@dataclass
class PlayersData:
    version: str
    default_player_id: Optional[str]
    players: Dict[str, PlayerProfile] = field(default_factory=dict)


# --------------------
# 경로 번들 (향후 DB 경로로 대체 용이)
# --------------------
@dataclass
class DataPaths:
    base_dir: Path
    items: Path
    skills: Path
    players: Path
    monsters: Path
    bosses: Path
    dungeons: Path
    progress: Path

    @staticmethod
    def from_base(base_dir: Path) -> "DataPaths":
        return DataPaths(
            base_dir=base_dir,
            items=base_dir / "items.json",
            skills=base_dir / "skills.json",
            players=base_dir / "players.json",
            monsters=base_dir / "monsters.json",
            bosses=base_dir / "bosses.json",
            dungeons=base_dir / "dungeons.json",
            progress=base_dir.parent / "save" / "progress.json",
        )
