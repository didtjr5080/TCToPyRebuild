from __future__ import annotations

import json
import os
from typing import Dict, Any


DEFAULT_PLAYER_STATE = {
    "player_state": {
        "level": 1,
        "exp": 0,
        "exp_to_next": 0,
        "stat_points": 0,
        "allocated_stats": {},
        "hp": 0,
    },
    "inventory": {"potion_small": 1},
    "equipment": {"weapon": None, "armor": None, "accessory": None},
    "dungeon_progress": {
        "unlocked_zones": ["1"],
        "unlocked_stage_by_zone": {"1": 1},
    },
}

DEFAULT_SAVE = {
    "selected_player_id": None,
    "players": {},
}


def _write(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _ensure_player_slot(save_data: Dict[str, Any], player_id: str) -> Dict[str, Any]:
    """플레이어 슬롯을 보정하고 기본값을 채움."""
    players = save_data.setdefault("players", {})
    if player_id not in players:
        players[player_id] = json.loads(json.dumps(DEFAULT_PLAYER_STATE))
    else:
        # 누락 필드 보정
        merged = json.loads(json.dumps(DEFAULT_PLAYER_STATE))
        merged.update(players[player_id])
        if "player_state" in players[player_id]:
            merged["player_state"].update(players[player_id].get("player_state", {}))
        if "dungeon_progress" in players[player_id]:
            merged["dungeon_progress"].update(players[player_id].get("dungeon_progress", {}))
        merged["equipment"].update(players[player_id].get("equipment", {}))
        merged["inventory"] = _to_inventory_dict(players[player_id].get("inventory", merged["inventory"]))
        players[player_id] = merged
    return players[player_id]


def _migrate_legacy(loaded: Dict[str, Any], default_player_id: str | None) -> Dict[str, Any]:
    """구버전 저장 구조를 새 구조로 변환."""
    save_data = json.loads(json.dumps(DEFAULT_SAVE))
    target_id = loaded.get("selected_player_id") or default_player_id or "char_0"
    if "player" in loaded:
        player_block = loaded.get("player", {})
        entry = _ensure_player_slot(save_data, target_id)
        entry["player_state"].update(
            {
                "level": player_block.get("level", 1),
                "exp": player_block.get("exp", 0),
                "stat_points": player_block.get("stat_points", 0),
                "hp": player_block.get("current_hp", 0),
            }
        )
        entry["inventory"] = _to_inventory_dict(player_block.get("inventory", entry["inventory"]))
        entry["equipment"].update(player_block.get("equipment", {}))
    if "dungeon" in loaded:
        entry = _ensure_player_slot(save_data, target_id)
        entry["dungeon_progress"].update(loaded.get("dungeon", {}))
    save_data["selected_player_id"] = target_id
    return save_data


def load_progress(save_path: str, players_data: Dict[str, Any], default_player_id: str | None) -> Dict[str, Any]:
    """progress.json 로드 및 스키마 보정/마이그레이션."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    if not os.path.exists(save_path):
        data = json.loads(json.dumps(DEFAULT_SAVE))
        data["selected_player_id"] = default_player_id or next(iter(players_data.keys()), "char_0")
        _ensure_player_slot(data, data["selected_player_id"])
        _write(save_path, data)
        return data

    with open(save_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    # 구버전 마이그레이션 처리
    if "players" not in loaded:
        migrated = _migrate_legacy(loaded, default_player_id)
        _write(save_path, migrated)
        return migrated

    save_data = json.loads(json.dumps(DEFAULT_SAVE))
    save_data.update(loaded)
    # 플레이어 슬롯 보정 및 기본 선택 복원
    for pid in players_data.keys():
        _ensure_player_slot(save_data, pid)
    if not save_data.get("selected_player_id"):
        save_data["selected_player_id"] = default_player_id or next(iter(players_data.keys()), "char_0")
    _ensure_player_slot(save_data, save_data["selected_player_id"])
    _write(save_path, save_data)
    return save_data


def save_progress(save_path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    _write(save_path, data)


def _to_inventory_dict(inv) -> Dict[str, int]:
    """리스트/딕셔너리를 dict[str,int] 형태로 정규화."""
    if isinstance(inv, dict):
        return { _normalize_item_id(str(k)): int(v) for k, v in inv.items()}
    if isinstance(inv, list):
        counts: Dict[str, int] = {}
        for item_id in inv:
            key = _normalize_item_id(str(item_id))
            counts[key] = counts.get(key, 0) + 1
        return counts
    return {}


def _normalize_item_id(item_id: str) -> str:
    """구버전 아이템 ID를 신규 ID로 맵핑."""
    legacy_map = {"minor_potion": "potion_small"}
    return legacy_map.get(item_id, item_id)
