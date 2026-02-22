from __future__ import annotations

"""아이템/인벤토리 헬퍼.

표준 라이브러리만 사용하며 전투와 UI에서 공통 호출할 수 있도록 구성한다.
"""

from typing import Dict, List, Tuple

from . import effects


def _ensure_inventory_dict(player_or_inv) -> Dict[str, int]:
    """플레이어 또는 인벤 오브젝트를 dict 형태로 강제 변환."""
    inv = player_or_inv if isinstance(player_or_inv, dict) else getattr(player_or_inv, "inventory", {})
    if isinstance(inv, list):
        migrated: Dict[str, int] = {}
        for item_id in inv:
            migrated[item_id] = migrated.get(item_id, 0) + 1
        if not isinstance(player_or_inv, dict):
            player_or_inv.inventory = migrated
        return migrated
    if inv is None:
        if not isinstance(player_or_inv, dict):
            player_or_inv.inventory = {}
            return player_or_inv.inventory
        return {}
    return inv


def add_item_to_inventory(player, item_id: str, qty: int = 1) -> None:
    """지정 수량만큼 인벤토리에 추가."""
    inv = _ensure_inventory_dict(player)
    inv[item_id] = inv.get(item_id, 0) + max(1, int(qty))


def remove_item_from_inventory(player, item_id: str, qty: int = 1) -> bool:
    """수량 차감. 부족하면 False 반환."""
    inv = _ensure_inventory_dict(player)
    need = max(1, int(qty))
    if inv.get(item_id, 0) < need:
        return False
    inv[item_id] -= need
    if inv[item_id] <= 0:
        inv.pop(item_id, None)
    return True


def equip_item(player, item_id: str, data_store) -> Tuple[bool, str]:
    """장비 장착 처리."""
    inv = _ensure_inventory_dict(player)
    item = data_store.get_item(item_id)
    if not item:
        return False, "아이템을 찾을 수 없습니다."
    if item.get("type") != "equipment":
        return False, "장비만 장착할 수 있습니다."
    slot = item.get("slot")
    if slot not in {"weapon", "armor", "accessory"}:
        return False, "장착할 슬롯이 올바르지 않습니다."
    if inv.get(item_id, 0) <= 0:
        return False, "인벤토리에 해당 장비가 없습니다."

    # 기존 장비는 인벤으로 되돌림
    prev = player.equipment.get(slot)
    if prev:
        add_item_to_inventory(player, prev, 1)
    # 새 장비 장착 후 인벤 차감
    player.equipment[slot] = item_id
    remove_item_from_inventory(player, item_id, 1)
    return True, f"{item.get('name', item_id)} 장착!"


def unequip_slot(player, slot: str, data_store) -> Tuple[bool, str]:
    """장비 해제 처리."""
    if slot not in {"weapon", "armor", "accessory"}:
        return False, "해제할 슬롯이 올바르지 않습니다."
    current = player.equipment.get(slot)
    if not current:
        return False, "해제할 장비가 없습니다."
    add_item_to_inventory(player, current, 1)
    player.equipment[slot] = None
    item = data_store.get_item(current) or {}
    return True, f"{item.get('name', current)} 해제"


def list_inventory_entries(player, data_store) -> List[Dict[str, object]]:
    """UI용 인벤토리 엔트리 목록."""
    inv = _ensure_inventory_dict(player)
    entries: List[Dict[str, object]] = []
    for item_id, count in inv.items():
        if count <= 0:
            continue
        data = data_store.get_item(item_id) or {}
        entries.append(
            {
                "item_id": item_id,
                "name": data.get("name", item_id),
                "count": int(count),
                "type": data.get("type"),
                "rarity": data.get("rarity"),
                "desc": data.get("desc") or data.get("description"),
            }
        )
    # 정렬: rarity>name
    rarity_order = {"legendary": 0, "epic": 1, "rare": 2, "common": 3, None: 4}
    entries.sort(key=lambda e: (rarity_order.get(e.get("rarity"), 4), e.get("name", "")))
    return entries


def apply_consumable_in_battle(player, item_id: str, data_store, logs: List[str]) -> Tuple[bool, str]:
    """전투 중 소모품 사용 처리."""
    item = data_store.get_item(item_id) if hasattr(data_store, "get_item") else None
    if not item:
        return False, "아이템을 찾을 수 없습니다."
    if item.get("type") != "consumable":
        return False, "소모품만 사용할 수 있습니다."
    effect = item.get("use_effect") or {}
    effect_type = effect.get("type")
    logs.append(f"플레이어가 {item.get('name', item_id)} 사용!")

    # heal
    if effect_type == "heal":
        power = int(effect.get("power", 0))
        before = player.hp
        max_hp = player.get_total_stats(data_store.items).max_hp
        player.hp = min(max_hp, player.hp + power)
        logs.append(f"체력 +{power} 회복! (HP {before}->{player.hp})")
        return True, "회복 완료"

    # cleanse
    if effect_type == "cleanse":
        remove_list = effect.get("remove", []) or []
        before_count = len(player.effects)
        player.effects = [eff for eff in player.effects if getattr(eff, "kind", None) not in remove_list]
        removed = before_count - len(player.effects)
        if removed > 0:
            logs.append("/".join(remove_list) + " 해제!")
            return True, "해제 완료"
        logs.append("해제할 상태이상이 없습니다.")
        return True, "변동 없음"

    # buff_stats
    if effect_type == "buff_stats":
        spec = {
            "type": "buff_stats",
            "duration": int(effect.get("duration", 1)),
            "stats": effect.get("stats", {}) or {},
            "target": "self",
            "scope": effect.get("scope", "battle"),
        }
        effects.apply_effect(player, spec, logs, items=data_store.items)
        try:
            max_hp = player.get_total_stats(data_store.items).max_hp
            player.hp = min(player.hp, max_hp)
        except Exception:
            pass
        return True, "버프 적용"

    return False, "알 수 없는 소모품"