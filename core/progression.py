from __future__ import annotations

from typing import List, Tuple

from .entities import Player


def exp_to_next(level: int) -> int:
    """레벨별 필요 경험치. 간단히 선형 증가."""
    return 20 + level * 10


def gain_exp(player: Player, amount: int) -> List[str]:
    """경험치 획득 및 레벨업 처리."""
    logs: List[str] = []
    player.exp += amount
    logs.append(f"EXP +{amount}")
    while player.exp >= exp_to_next(player.level):
        player.exp -= exp_to_next(player.level)
        player.level += 1
        player.stat_points += 4
        logs.append(f"레벨업! Lv {player.level} / 스탯 포인트 +4")
    return logs
