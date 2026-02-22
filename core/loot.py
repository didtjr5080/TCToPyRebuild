from __future__ import annotations

import random
from typing import List, Tuple


def roll_drop(table_name: str, data_store, rng=random) -> List[Tuple[str, int]]:
    """드랍 테이블을 굴려 (아이템ID, 수량) 목록을 반환."""
    results: List[Tuple[str, int]] = []
    table = (getattr(data_store, "drop_tables", {}) or {}).get(table_name, [])
    for entry in table:
        chance = entry.get("chance", 0)
        if rng.random() <= chance:
            item_id = entry.get("item")
            if item_id:
                qty_min = int(entry.get("min", 1))
                qty_max = int(entry.get("max", qty_min))
                qty = rng.randint(min(qty_min, qty_max), max(qty_min, qty_max))
                results.append((item_id, qty))
    return results
