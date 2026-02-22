#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assets_check.py
- data/*.json에서 player_id / monster_id / boss_id / effect_id를 추출
- assets 디렉토리에서 필요한 png 파일이 있는지 검사
- 누락된 파일 목록을 출력

실행:
  python tools/assets_check.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, Set, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"

CHAR_DIR = ASSETS_DIR / "characters"
ENEMY_DIR = ASSETS_DIR / "enemies"
BG_DIR = ASSETS_DIR / "backgrounds"
ICON_DIR = ASSETS_DIR / "icons"
EFFECT_DIR = ASSETS_DIR / "effects"
EXT_PRIORITY = [".png", ".webp", ".jpg", ".jpeg"]


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"[JSON 파싱 오류] {path}: {e}") from e


def _collect_player_ids(players_json: Dict[str, Any]) -> Set[str]:
    players = players_json.get("players", {})
    if isinstance(players, dict):
        return set(players.keys())
    return set()


def _collect_monster_ids(monsters_json: Dict[str, Any]) -> Set[str]:
    monsters = monsters_json.get("monsters", {})
    if isinstance(monsters, dict):
        return set(monsters.keys())
    return set()


def _collect_skill_ids(skills_json: Dict[str, Any]) -> Set[str]:
    skills = skills_json.get("skills", {})
    if isinstance(skills, dict):
        return set(skills.keys())
    return set()


def _collect_boss_ids(bosses_json: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    dungeon_bosses = bosses_json.get("dungeon_bosses", {})
    special_bosses = bosses_json.get("special_bosses", {})
    if isinstance(dungeon_bosses, dict):
        out |= set(dungeon_bosses.keys())
    if isinstance(special_bosses, dict):
        out |= set(special_bosses.keys())
    return out


def _collect_effect_ids(skills_json: Dict[str, Any], items_json: Dict[str, Any]) -> Set[str]:
    """
    아이콘(effect id) 후보:
      - skills.json: apply_effect.type 혹은 apply_effect.effect (bleed/stun 등)
      - items.json: items[*].special.effect (예: stun)
    기본적으로 bleed/stun/buff/debuff는 항상 포함.
    """
    effects: Set[str] = {"bleed", "stun", "buff", "debuff"}

    skills = skills_json.get("skills", {})
    if isinstance(skills, dict):
        for _, sk in skills.items():
            ae = sk.get("apply_effect", None)
            _collect_effect_from_apply_effect(ae, effects)

    items = items_json.get("items", {})
    if isinstance(items, dict):
        for _, it in items.items():
            sp = it.get("special", None)
            if isinstance(sp, dict):
                eff = sp.get("effect")
                if isinstance(eff, str) and eff.strip():
                    effects.add(eff.strip())
                # special 타입이 buff/debuff 같은 경우 대비
                t = sp.get("type")
                if isinstance(t, str) and t.strip() in {"buff_stats", "debuff_stats"}:
                    effects.add("buff" if t.strip() == "buff_stats" else "debuff")

    return effects


def _collect_effect_from_apply_effect(ae: Any, effects: Set[str]) -> None:
    if ae is None:
        return

    # 단일 dict
    if isinstance(ae, dict):
        _collect_effect_from_apply_effect_dict(ae, effects)
        return

    # 리스트(다중 효과)
    if isinstance(ae, list):
        for item in ae:
            if isinstance(item, dict):
                _collect_effect_from_apply_effect_dict(item, effects)


def _collect_effect_from_apply_effect_dict(ae: Dict[str, Any], effects: Set[str]) -> None:
    # 표준 스키마: type=buff_stats/debuff_stats/bleed/stun/heal/lifesteal 등
    t = ae.get("type")
    if isinstance(t, str) and t.strip():
        tt = t.strip()
        if tt in {"buff_stats", "debuff_stats"}:
            effects.add("buff" if tt == "buff_stats" else "debuff")
        elif tt in {"bleed", "stun"}:
            effects.add(tt)
        # heal/lifesteal은 별도 아이콘이 필요 없다면 안 넣어도 됨(원하면 추가 가능)

    # 보스 기믹 action 스키마처럼 effect 필드가 따로 있을 수 있음
    eff = ae.get("effect")
    if isinstance(eff, str) and eff.strip():
        effects.add(eff.strip())


def _collect_background_names() -> Set[str]:
    """
    기본 배경 파일명(프로젝트 기준)
    필요하면 여기 추가하면 됨.
    """
    return {"battle_bg"}  # battle_bg.png


def _normalize(raw: str) -> str:
    """에셋 로더와 동일한 규칙으로 스킬 id를 정규화."""
    text = (raw or "").strip()
    text = text.lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_") or raw


def _skill_effect_candidates(skill_id: str) -> List[str]:
    """원본/접두어 추가/접두어 제거 모두 포함해 후보 생성."""
    candidates: List[str] = []
    # 원본
    candidates.append(skill_id)
    nrm = _normalize(skill_id)
    if nrm and nrm != skill_id:
        candidates.append(nrm)
    # skill_ 접두어 추가 (이미 있는 경우에도 한 번 더 붙은 파일을 대비해 항상 추가)
    p = f"skill_{skill_id}"
    candidates.append(p)
    np = _normalize(p)
    if np and np not in candidates:
        candidates.append(np)
    # skill_ 접두어 제거
    if skill_id.startswith("skill_"):
        trimmed = skill_id[len("skill_") :]
        candidates.append(trimmed)
        nt = _normalize(trimmed)
        if nt and nt not in candidates:
            candidates.append(nt)
    # 중복 제거, 순서 유지
    uniq: List[str] = []
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        uniq.append(c)
    return uniq


def _resolve_with_ext(base_dir: Path, stem_candidates: List[str]) -> Tuple[bool, Path]:
    """우선순위 확장자 목록을 돌며 존재 여부 확인."""
    for stem in stem_candidates:
        for ext in EXT_PRIORITY:
            path = base_dir / f"{stem}{ext}"
            if path.exists():
                return True, path
    # 추천 경로: 첫 번째 후보 + png
    fallback = base_dir / f"{stem_candidates[0]}.png"
    return False, fallback


def _expected_paths(player_ids: Set[str], monster_ids: Set[str], boss_ids: Set[str],
                    effect_ids: Set[str], bg_names: Set[str]) -> List[Tuple[str, Path]]:
    expected: List[Tuple[str, Path]] = []

    for pid in sorted(player_ids):
        expected.append(("character", CHAR_DIR / f"{pid}.png"))

    for mid in sorted(monster_ids):
        expected.append(("enemy", ENEMY_DIR / f"{mid}.png"))

    for bid in sorted(boss_ids):
        expected.append(("boss", ENEMY_DIR / f"{bid}.png"))

    for eff in sorted(effect_ids):
        expected.append(("icon", ICON_DIR / f"{eff}.png"))

    for bg in sorted(bg_names):
        expected.append(("background", BG_DIR / f"{bg}.png"))

    return expected


def _expected_skill_effects(skill_ids: Set[str]) -> List[Tuple[str, Path]]:
    expected: List[Tuple[str, Path]] = []
    for sid in sorted(skill_ids):
        stems = _skill_effect_candidates(sid)
        exists, path = _resolve_with_ext(EFFECT_DIR, stems)
        if exists:
            expected.append(("skill_effect_present", path))
        else:
            expected.append(("skill_effect_missing", path))
    return expected


def main() -> None:
    # JSON 로드
    players_json = _read_json(DATA_DIR / "players.json")
    monsters_json = _read_json(DATA_DIR / "monsters.json")
    bosses_json = _read_json(DATA_DIR / "bosses.json")
    skills_json = _read_json(DATA_DIR / "skills.json")
    items_json = _read_json(DATA_DIR / "items.json")

    # ID 수집
    player_ids = _collect_player_ids(players_json)
    monster_ids = _collect_monster_ids(monsters_json)
    boss_ids = _collect_boss_ids(bosses_json)
    effect_ids = _collect_effect_ids(skills_json, items_json)
    skill_ids = _collect_skill_ids(skills_json)
    bg_names = _collect_background_names()

    expected = _expected_paths(player_ids, monster_ids, boss_ids, effect_ids, bg_names)
    skill_expected = _expected_skill_effects(skill_ids)

    # 디렉토리 존재 여부 안내(없어도 "누락"으로 잡힘)
    ASSETS_DIR.mkdir(exist_ok=True)
    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    ENEMY_DIR.mkdir(parents=True, exist_ok=True)
    BG_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    EFFECT_DIR.mkdir(parents=True, exist_ok=True)

    missing = [(kind, p) for (kind, p) in expected if not p.exists()]
    present = [(kind, p) for (kind, p) in expected if p.exists()]
    skill_missing = [(kind, p) for (kind, p) in skill_expected if kind == "skill_effect_missing"]
    skill_present = [(kind, p) for (kind, p) in skill_expected if kind == "skill_effect_present"]

    print("=== Assets Check ===")
    print(f"- Project root: {PROJECT_ROOT}")
    print(f"- Data dir     : {DATA_DIR}")
    print(f"- Assets dir   : {ASSETS_DIR}")
    print()

    print(
        f"[요약] 캐릭터 {len(player_ids)} / 몬스터 {len(monster_ids)} / 보스 {len(boss_ids)} / "
        f"아이콘 {len(effect_ids)} / 배경 {len(bg_names)} / 스킬이펙트 {len(skill_ids)}"
    )
    print(f"[파일] 존재 {len(present)} / 누락 {len(missing)} / 스킬이펙트 존재 {len(skill_present)} / 누락 {len(skill_missing)}")
    print()

    if missing:
        print("=== 누락된 에셋 목록(이 파일명으로 추가하면 자동 로드됨) ===")
        for kind, p in missing:
            rel = p.relative_to(PROJECT_ROOT)
            print(f"- ({kind}) {rel}")
        print()

    if skill_missing:
        print("=== 누락된 스킬 이펙트 목록(assets/effects, png/webp/jpg/jpeg 중 하나 추가) ===")
        for _, p in skill_missing:
            rel = p.relative_to(PROJECT_ROOT)
            print(f"- (skill_effect) {rel}")
        print()

    print("=== 현재 존재하는 에셋(참고) ===")
    for kind, p in present:
        rel = p.relative_to(PROJECT_ROOT)
        print(f"- ({kind}) {rel}")
    if skill_present:
        print("=== 현재 존재하는 스킬 이펙트(참고) ===")
        for _, p in skill_present:
            rel = p.relative_to(PROJECT_ROOT)
            print(f"- (skill_effect) {rel}")


if __name__ == "__main__":
    main()