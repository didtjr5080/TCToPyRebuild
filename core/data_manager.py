from __future__ import annotations

"""데이터 접근 전용 DataManager.

- JSON read/write는 이 클래스만 담당합니다. (향후 DB/API로 교체 가능)
- 버전 필드를 확인해 간단한 마이그레이션 훅을 제공합니다.
- 모든 반환값은 dataclass 모델을 사용하여 타입 안정성을 보장합니다.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    Boss,
    BossesData,
    DataPaths,
    DungeonStage,
    DungeonZone,
    DungeonsData,
    DropEntry,
    Item,
    ItemSpecial,
    ItemsData,
    Monster,
    MonstersData,
    PlayerProfile,
    PlayerProgress,
    PlayersData,
    SaveData,
    Skill,
    SkillEffect,
    SkillScale,
    SkillsData,
    Stats,
    UseEffect,
)


class DataManager:
    def __init__(self, data_dir: Path) -> None:
        self.paths = DataPaths.from_base(data_dir)
        self.log = logging.getLogger(__name__)
        self._items_cache: Optional[ItemsData] = None
        self._skills_cache: Optional[SkillsData] = None
        self._monsters_cache: Optional[MonstersData] = None
        self._bosses_cache: Optional[BossesData] = None
        self._dungeons_cache: Optional[DungeonsData] = None
        self._players_cache: Optional[PlayersData] = None

    # --------------------
    # Public load/save API
    # --------------------
    def load_items(self, force: bool = False) -> ItemsData:
        if self._items_cache and not force:
            return self._items_cache
        raw = self._safe_load_json(self.paths.items)
        version = raw.get("version", "0.0.0")
        raw_items = raw.get("items", {}) or {}
        raw_tables = raw.get("drop_tables", {}) or {}
        items: Dict[str, Item] = {}
        for item_id, payload in raw_items.items():
            try:
                items[item_id] = self._parse_item(item_id, payload)
            except Exception as exc:  # 방어적: 손상 데이터 폴백
                self.log.warning("items.json: '%s' 파싱 실패, 기본값으로 대체 (%s)", item_id, exc)
                items[item_id] = self._fallback_item(item_id)
        drop_tables: Dict[str, List[DropEntry]] = {}
        for table_name, entries in raw_tables.items():
            safe_entries: List[DropEntry] = []
            for entry in entries or []:
                try:
                    safe_entries.append(self._parse_drop(entry))
                except Exception as exc:
                    self.log.warning("items.json drop_table '%s' 엔트리 무시 (%s)", table_name, exc)
            drop_tables[table_name] = safe_entries
        self._items_cache = ItemsData(version=version, items=items, drop_tables=drop_tables)
        return self._items_cache

    def get_item(self, item_id: str) -> Item:
        data = self.load_items()
        found = data.items.get(item_id)
        if found:
            return found
        self.log.warning("아이템 '%s'을 찾지 못해 기본값을 반환합니다", item_id)
        return self._fallback_item(item_id)

    def load_skills(self, force: bool = False) -> SkillsData:
        if self._skills_cache and not force:
            return self._skills_cache
        raw = self._safe_load_json(self.paths.skills)
        version = raw.get("version", "0.0.0")
        skills_raw = raw.get("skills", {}) or {}
        skills: Dict[str, Skill] = {}
        for sid, payload in skills_raw.items():
            try:
                skills[sid] = self._parse_skill(sid, payload)
            except Exception as exc:
                self.log.warning("skills.json: '%s' 파싱 실패, 기본값으로 대체 (%s)", sid, exc)
                skills[sid] = self._fallback_skill(sid)
        if "__basic__" not in skills:
            skills["__basic__"] = self._fallback_skill("__basic__", name="기본 공격", base_physical=10, scale_attack=0.2)
        self._skills_cache = SkillsData(version=version, skills=skills)
        return self._skills_cache

    def get_skill(self, skill_id: str) -> Skill:
        data = self.load_skills()
        found = data.skills.get(skill_id)
        if found:
            return found
        self.log.warning("스킬 '%s'을 찾지 못해 기본 스킬을 반환합니다", skill_id)
        return self._fallback_skill(skill_id)

    def load_monsters(self, force: bool = False) -> MonstersData:
        if self._monsters_cache and not force:
            return self._monsters_cache
        raw = self._safe_load_json(self.paths.monsters)
        version = raw.get("version", "0.0.0")
        monsters_raw = raw.get("monsters", {}) or {}
        monsters: Dict[str, Monster] = {}
        for mid, payload in monsters_raw.items():
            try:
                monsters[mid] = self._parse_monster(mid, payload)
            except Exception as exc:
                self.log.warning("monsters.json: '%s' 파싱 실패, 기본 몬스터로 대체 (%s)", mid, exc)
                monsters[mid] = self._fallback_monster(mid)
        self._monsters_cache = MonstersData(version=version, monsters=monsters)
        return self._monsters_cache

    def get_monster(self, monster_id: str) -> Monster:
        data = self.load_monsters()
        found = data.monsters.get(monster_id)
        if found:
            return found
        self.log.warning("몬스터 '%s'을 찾지 못해 기본 몬스터를 반환합니다", monster_id)
        return self._fallback_monster(monster_id)

    def load_bosses(self, force: bool = False) -> BossesData:
        if self._bosses_cache and not force:
            return self._bosses_cache
        raw = self._safe_load_json(self.paths.bosses)
        version = raw.get("version", "0.0.0")
        dungeon_raw = raw.get("dungeon_bosses", {}) or {}
        special_raw = raw.get("special_bosses", {}) or {}
        dungeon_bosses: Dict[str, Boss] = {}
        for bid, payload in dungeon_raw.items():
            try:
                dungeon_bosses[bid] = self._parse_boss(bid, payload, is_special=False)
            except Exception as exc:
                self.log.warning("bosses.json: dungeon boss '%s' 파싱 실패 (%s)", bid, exc)
                dungeon_bosses[bid] = self._fallback_boss(bid)
        special_bosses: Dict[str, Boss] = {}
        for bid, payload in special_raw.items():
            try:
                special_bosses[bid] = self._parse_boss(bid, payload, is_special=True)
            except Exception as exc:
                self.log.warning("bosses.json: special boss '%s' 파싱 실패 (%s)", bid, exc)
                special_bosses[bid] = self._fallback_boss(bid, is_special=True)
        self._bosses_cache = BossesData(version=version, dungeon_bosses=dungeon_bosses, special_bosses=special_bosses)
        return self._bosses_cache

    def get_boss(self, boss_id: str) -> Boss:
        data = self.load_bosses()
        found = data.dungeon_bosses.get(boss_id) or data.special_bosses.get(boss_id)
        if found:
            return found
        self.log.warning("보스 '%s'을 찾지 못해 기본 보스를 반환합니다", boss_id)
        return self._fallback_boss(boss_id)

    def load_dungeons(self, force: bool = False) -> DungeonsData:
        if self._dungeons_cache and not force:
            return self._dungeons_cache
        raw = self._safe_load_json(self.paths.dungeons)
        version = raw.get("version", "0.0.0")
        zones_raw = raw.get("zones", {}) or {}
        zones: Dict[str, DungeonZone] = {}
        for zid, payload in zones_raw.items():
            try:
                zones[zid] = self._parse_zone(zid, payload)
            except Exception as exc:
                self.log.warning("dungeons.json: zone '%s' 파싱 실패, 빈 존으로 대체 (%s)", zid, exc)
                zones[zid] = DungeonZone(zone_id=zid)
        self._dungeons_cache = DungeonsData(version=version, zones=zones)
        return self._dungeons_cache

    def get_zone(self, zone_id: str) -> DungeonZone:
        data = self.load_dungeons()
        zone = data.zones.get(str(zone_id))
        if zone:
            return zone
        self.log.warning("존 '%s'을 찾지 못해 빈 존을 반환합니다", zone_id)
        return DungeonZone(zone_id=str(zone_id))

    def get_stage(self, zone_id: str, stage_id: str) -> DungeonStage:
        zone = self.get_zone(zone_id)
        stage = zone.stages.get(str(stage_id))
        if stage:
            return stage
        self.log.warning("존 '%s'의 스테이지 '%s'를 찾지 못해 빈 스테이지를 반환합니다", zone_id, stage_id)
        return DungeonStage(stage_id=str(stage_id))

    def load_players(self, force: bool = False) -> PlayersData:
        if self._players_cache and not force:
            return self._players_cache
        raw = self._safe_load_json(self.paths.players)
        version = raw.get("version", "0.0.0")
        default_player_id = raw.get("default_player_id")
        profiles_raw = raw.get("players", {}) or {}
        players: Dict[str, PlayerProfile] = {}
        for pid, payload in profiles_raw.items():
            try:
                players[pid] = self._parse_player_profile(pid, payload)
            except Exception as exc:
                self.log.warning("players.json: '%s' 파싱 실패, 기본 프로필로 대체 (%s)", pid, exc)
                players[pid] = self._fallback_profile(pid)
        self._players_cache = PlayersData(version=version, default_player_id=default_player_id, players=players)
        return self._players_cache

    def get_player_profile(self, player_id: str) -> PlayerProfile:
        data = self.load_players()
        profile = data.players.get(player_id)
        if profile:
            return profile
        self.log.warning("플레이어 프로필 '%s'을 찾지 못해 기본 프로필을 반환합니다", player_id)
        return self._fallback_profile(player_id)

    def load_save(self) -> SaveData:
        raw = self._safe_load_json(self.paths.progress, ensure_exists=True)
        version = raw.get("version", "0.0.0")
        players_block = raw.get("players", {}) or {}
        players: Dict[str, PlayerProgress] = {}
        for pid, pdata in players_block.items():
            try:
                players[pid] = self._parse_player_progress(pdata)
            except Exception as exc:
                self.log.warning("progress.json: '%s' 플레이어 진행도 파싱 실패, 기본값으로 대체 (%s)", pid, exc)
                players[pid] = PlayerProgress()
        return SaveData(version=version, selected_player_id=raw.get("selected_player_id"), players=players)

    def save_progress(self, save_data: SaveData) -> None:
        payload = {
            "version": save_data.version,
            "selected_player_id": save_data.selected_player_id,
            "players": {pid: self._dump_player(p) for pid, p in save_data.players.items()},
        }
        self._write_json(self.paths.progress, payload)

    # --------------------
    # Migration stub (version-aware)
    # --------------------
    def migrate_if_needed(self, current_version: str, target_version: str) -> None:
        """버전이 낮을 때 필요한 변환을 수행하는 훅. 현재는 골격만 제공합니다."""
        if current_version == target_version:
            return
        # 예: if current_version < "1.1.0": self._migrate_inventory_format()

    # --------------------
    # Parsing helpers
    # --------------------
    def _parse_item(self, item_id: str, payload: Dict[str, Any]) -> Item:
        stats_raw = payload.get("stats", {}) or {}
        special_raw = payload.get("special")
        use_effect_raw = payload.get("use_effect")
        return Item(
            id=item_id,
            name=payload.get("name", item_id),
            type=payload.get("type", "equipment"),
            rarity=payload.get("rarity", "common"),
            desc=payload.get("desc", ""),
            icon=payload.get("icon"),
            slot=payload.get("slot"),
            stats=Stats(**{k: int(stats_raw.get(k, 0)) for k in ["attack", "magic", "defense", "magic_resist", "max_hp"]}),
            special=ItemSpecial(**special_raw) if isinstance(special_raw, dict) else None,
            use_effect=UseEffect(**use_effect_raw) if isinstance(use_effect_raw, dict) else None,
        )

    def _parse_skill(self, skill_id: str, payload: Dict[str, Any]) -> Skill:
        scale_raw = payload.get("scale", {}) if isinstance(payload.get("scale", {}), dict) else {}
        effects_raw = payload.get("apply_effect")
        effect_list: List[Dict[str, Any]] = []
        if isinstance(effects_raw, list):
            effect_list = [e for e in effects_raw if isinstance(e, dict)]
        elif isinstance(effects_raw, dict):
            effect_list = [effects_raw]
        return Skill(
            id=skill_id,
            name=payload.get("name", skill_id),
            type=payload.get("type", "physical"),
            base_physical=float(payload.get("base_physical", 0)),
            base_magic=float(payload.get("base_magic", 0)),
            scale=SkillScale(attack=float(scale_raw.get("attack", 0.0)), magic=float(scale_raw.get("magic", 0.0))),
            cost=int(payload.get("cost", 0)),
            cooldown=int(payload.get("cooldown", 0)),
            apply_effects=[self._parse_skill_effect(eff) for eff in effect_list],
        )

    def _parse_skill_effect(self, payload: Dict[str, Any]) -> SkillEffect:
        return SkillEffect(
            type=payload.get("type") or payload.get("effect", "unknown"),
            target=payload.get("target", "enemy"),
            chance=float(payload.get("chance", 1.0)),
            duration=int(payload.get("duration", 0)),
            power=float(payload.get("power", 0.0)),
            stats={k: int(v) for k, v in (payload.get("stats") or {}).items()},
            scope=payload.get("scope", "battle"),
        )

    def _parse_monster(self, monster_id: str, payload: Dict[str, Any]) -> Monster:
        stats_raw = payload.get("stats", {}) or {}
        return Monster(
            id=monster_id,
            name=payload.get("name", monster_id),
            stats=Stats(**{k: int(stats_raw.get(k, 0)) for k in ["attack", "magic", "defense", "magic_resist", "max_hp"]}),
            ai=payload.get("ai", "basic"),
            skills=[str(s) for s in payload.get("skills", [])],
            gimmicks=payload.get("gimmicks", []) or [],
            drop_table=payload.get("drop_table"),
        )

    def _parse_boss(self, boss_id: str, payload: Dict[str, Any], is_special: bool) -> Boss:
        monster = self._parse_monster(boss_id, payload)
        return Boss(
            id=monster.id,
            name=monster.name,
            stats=monster.stats,
            ai=monster.ai,
            skills=monster.skills,
            gimmicks=monster.gimmicks,
            drop_table=payload.get("drop_table"),
            is_special=is_special,
        )

    def _parse_zone(self, zone_id: str, payload: Dict[str, Any]) -> DungeonZone:
        stages_raw = payload.get("stages", {}) or {}
        stages: Dict[str, DungeonStage] = {}
        for sid, sdata in stages_raw.items():
            try:
                stages[sid] = self._parse_stage(sid, sdata)
            except Exception as exc:
                self.log.warning("dungeons.json: zone '%s' stage '%s' 파싱 실패, 빈 스테이지로 대체 (%s)", zone_id, sid, exc)
                stages[sid] = DungeonStage(stage_id=sid)
        return DungeonZone(zone_id=str(zone_id), stages=stages)

    def _parse_stage(self, stage_id: str, payload: Dict[str, Any]) -> DungeonStage:
        monster_pool = payload.get("monster_pool", []) or []
        boss_id = payload.get("boss_id")
        exp = int(payload.get("exp", 0))
        return DungeonStage(stage_id=str(stage_id), monster_pool=[str(m) for m in monster_pool], boss_id=boss_id, exp=exp)

    def _parse_player_profile(self, player_id: str, payload: Dict[str, Any]) -> PlayerProfile:
        base_raw = payload.get("base_stats", {}) or {}
        return PlayerProfile(
            id=player_id,
            name=payload.get("name", player_id),
            base_stats=Stats(**{k: int(base_raw.get(k, 0)) for k in ["attack", "magic", "defense", "magic_resist", "max_hp"]}),
            skills=[str(s) for s in payload.get("skills", [])],
        )

    def _parse_drop(self, payload: Dict[str, Any]) -> DropEntry:
        return DropEntry(
            item=payload.get("item", ""),
            chance=float(payload.get("chance", 0)),
            min=int(payload.get("min", 1)),
            max=int(payload.get("max", 1)),
        )

    def _parse_player_progress(self, payload: Dict[str, Any]) -> PlayerProgress:
        return PlayerProgress(
            level=int(payload.get("level", 1)),
            exp=int(payload.get("exp", 0)),
            exp_to_next=int(payload.get("exp_to_next", 0)),
            stat_points=int(payload.get("stat_points", 0)),
            allocated_stats={k: int(v) for k, v in (payload.get("allocated_stats") or {}).items()},
            hp=int(payload.get("hp", 0)),
            inventory={k: int(v) for k, v in (payload.get("inventory") or {}).items()},
            equipment={k: payload.get("equipment", {}).get(k) for k in ["weapon", "armor", "accessory"]},
            dungeon_progress=payload.get("dungeon_progress", {}),
        )

    def _dump_player(self, player: PlayerProgress) -> Dict[str, Any]:
        return {
            "level": player.level,
            "exp": player.exp,
            "exp_to_next": player.exp_to_next,
            "stat_points": player.stat_points,
            "allocated_stats": dict(player.allocated_stats),
            "hp": player.hp,
            "inventory": dict(player.inventory),
            "equipment": dict(player.equipment),
            "dungeon_progress": dict(player.dungeon_progress),
        }

    # --------------------
    # Fallback builders
    # --------------------
    def _fallback_item(self, item_id: str) -> Item:
        return Item(
            id=item_id,
            name=item_id,
            type="material",
            rarity="common",
            desc="",
            icon=None,
            slot=None,
            stats=Stats(),
        )

    def _fallback_skill(self, skill_id: str, name: Optional[str] = None, base_physical: float = 0.0, scale_attack: float = 0.0) -> Skill:
        return Skill(
            id=skill_id,
            name=name or skill_id,
            type="physical",
            base_physical=base_physical,
            base_magic=0.0,
            scale=SkillScale(attack=scale_attack, magic=0.0),
            cost=0,
            cooldown=0,
            apply_effects=[],
        )

    def _fallback_monster(self, monster_id: str) -> Monster:
        return Monster(id=monster_id, name=monster_id, stats=Stats(), ai="basic", skills=["__basic__"], gimmicks=[])

    def _fallback_boss(self, boss_id: str, is_special: bool = False) -> Boss:
        base = self._fallback_monster(boss_id)
        return Boss(
            id=base.id,
            name=base.name,
            stats=base.stats,
            ai=base.ai,
            skills=base.skills,
            gimmicks=base.gimmicks,
            drop_table=None,
            is_special=is_special,
        )

    def _fallback_profile(self, player_id: str) -> PlayerProfile:
        return PlayerProfile(id=player_id, name=player_id, base_stats=Stats(max_hp=100), skills=["__basic__"])

    # --------------------
    # Low-level I/O (single choke point)
    # --------------------
    def _safe_load_json(self, path: Path, ensure_exists: bool = False) -> Dict[str, Any]:
        try:
            return self._load_json(path, ensure_exists=ensure_exists)
        except FileNotFoundError:
            self.log.warning("데이터 파일을 찾을 수 없습니다: %s", path)
            return {}
        except json.JSONDecodeError as exc:
            self.log.warning("JSON 파싱 오류(%s): %s", path, exc)
            return {}

    def _load_json(self, path: Path, ensure_exists: bool = False) -> Dict[str, Any]:
        if ensure_exists and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            return {"version": "0.0.0"}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
