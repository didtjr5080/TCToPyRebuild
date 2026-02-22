from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DungeonProgress:
    """던전 해금 상태."""

    unlocked_zones: List[str] = field(default_factory=lambda: ["1"])
    unlocked_stage_by_zone: Dict[str, int] = field(default_factory=lambda: {"1": 1})

    def is_stage_unlocked(self, zone: str, stage: int) -> bool:
        if zone not in self.unlocked_zones:
            return False
        return stage <= self.unlocked_stage_by_zone.get(zone, 0)

    def clear_stage(self, zone: str, stage: int) -> None:
        current = self.unlocked_stage_by_zone.get(zone, 1)
        if stage >= current:
            self.unlocked_stage_by_zone[zone] = min(5, stage + 1)
        # 5스테이지 클리어 시 다음 구역 해금
        if stage >= 5:
            next_zone = str(int(zone) + 1)
            if next_zone not in self.unlocked_zones and int(next_zone) <= 10:
                self.unlocked_zones.append(next_zone)
                self.unlocked_stage_by_zone[next_zone] = 1
