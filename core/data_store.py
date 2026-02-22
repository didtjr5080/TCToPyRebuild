from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class DataStore:
    """JSON 데이터를 로드/조회하는 전용 클래스."""

    def __init__(self) -> None:
        self.players: Dict[str, Any] = {}
        self.default_player_id: str | None = None
        self.skills: Dict[str, Any] = {}
        self.monsters: Dict[str, Any] = {}
        self.items: Dict[str, Any] = {}
        self.drop_tables: Dict[str, Any] = {}
        self.bosses: Dict[str, Any] = {}

    def load_all(self, data_dir: Path) -> None:
        """players/skills/monsters/items JSON을 모두 읽고 검증한다."""
        try:
            players_data = self._load_json(data_dir / "players.json")
            self.players = players_data.get("players", {})
            self.default_player_id = players_data.get("default_player_id")
            self.skills = self._load_json(data_dir / "skills.json").get("skills", {})
            self.monsters = self._load_json(data_dir / "monsters.json").get("monsters", {})

            items_data = self._load_json(data_dir / "items.json")
            self.items = items_data.get("items", {})
            self.drop_tables = items_data.get("drop_tables", {})

            # bosses.json은 없을 수도 있으므로 실패 시 빈 dict
            bosses_path = data_dir / "bosses.json"
            if bosses_path.exists():
                self.bosses = self._load_json(bosses_path)
            else:
                self.bosses = {}

            # 폴백 스킬 보장 후 스키마 검증
            self._ensure_basic_skill()
            self.validate_all()
        except FileNotFoundError as exc:
            raise RuntimeError(f"데이터 파일을 찾을 수 없습니다: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"데이터 파일 파싱 오류: {exc}") from exc

    def get_player(self, player_id: str) -> Dict[str, Any]:
        """플레이어 데이터 조회. 없으면 KeyError 발생."""
        if player_id not in self.players:
            raise KeyError(f"플레이어를 찾을 수 없습니다: {player_id}")
        return self.players[player_id]

    def get_skill(self, skill_id: str) -> Dict[str, Any]:
        """스킬 데이터 조회. 없으면 KeyError 발생."""
        if skill_id not in self.skills:
            raise KeyError(f"스킬을 찾을 수 없습니다: {skill_id}")
        return self.skills[skill_id]

    def get_monster(self, monster_id: str) -> Dict[str, Any]:
        """몬스터 데이터 조회. 없으면 KeyError 발생."""
        if monster_id not in self.monsters:
            raise KeyError(f"몬스터를 찾을 수 없습니다: {monster_id}")
        return self.monsters[monster_id]

    def get_item(self, item_id: str) -> Dict[str, Any] | None:
        """아이템 데이터 조회. 없으면 None 반환."""
        return self.items.get(item_id)

    def get_boss(self, boss_id: str) -> Dict[str, Any]:
        """보스 데이터 조회."""
        return self.bosses.get("dungeon_bosses", {}).get(boss_id, {}) or self.bosses.get("special_bosses", {}).get(boss_id, {})

    def get_special_boss_ids(self) -> List[str]:
        """특수 보스 ID 목록."""
        return list(self.bosses.get("special_bosses", {}).keys())

    def get_dungeon_boss_id(self, zone: int | str) -> str | None:
        """존에 매칭되는 던전 보스 ID를 찾는다."""
        zid = str(zone)
        candidate = f"zone{zid}_boss"
        bosses = self.bosses.get("dungeon_bosses", {})
        if candidate in bosses:
            return candidate
        # 보스 id가 zone 숫자만으로도 있을 수 있으니 탐색
        for key in bosses.keys():
            if zid in key:
                return key
        return None

    # ------------------------------------------------------------------
    # 검증/정리 로직
    # ------------------------------------------------------------------
    def validate_all(self) -> None:
        """players/skills/monsters JSON 스키마 검증 및 스킬 정리."""
        # skills.json 검증
        for skill_id, skill in self.skills.items():
            required_skill_keys = ["name", "base_physical", "base_magic", "scale"]
            for key in required_skill_keys:
                if key not in skill:
                    raise ValueError(f"skills.json: skill '{skill_id}'에 '{key}'가 없습니다.")
            if not isinstance(skill.get("scale", {}), dict):
                raise ValueError(f"skills.json: skill '{skill_id}'의 scale이 객체가 아닙니다.")
            for scale_key in ["attack", "magic"]:
                if scale_key not in skill["scale"]:
                    raise ValueError(f"skills.json: skill '{skill_id}'의 scale.{scale_key}가 없습니다.")
                if not isinstance(skill["scale"][scale_key], (int, float)):
                    raise ValueError(
                        f"skills.json: skill '{skill_id}'의 scale.{scale_key} 값이 숫자가 아닙니다: {skill['scale'][scale_key]}"
                    )
            for num_key in ["base_physical", "base_magic"]:
                if not isinstance(skill.get(num_key), (int, float)):
                    raise ValueError(
                        f"skills.json: skill '{skill_id}'의 {num_key} 값이 숫자가 아닙니다: {skill.get(num_key)}"
                    )

        # players.json 검증
        if self.default_player_id and self.default_player_id not in self.players:
            raise ValueError(f"players.json: default_player_id '{self.default_player_id}'가 players에 없습니다.")
        for player_id, player in self.players.items():
            base_stats = player.get("base_stats", {})
            for key in ["attack", "magic", "defense", "magic_resist", "max_hp"]:
                if key not in base_stats:
                    raise ValueError(f"players.json: player '{player_id}'의 base_stats에 '{key}'가 없습니다.")
                if not isinstance(base_stats[key], (int, float)):
                    raise ValueError(
                        f"players.json: player '{player_id}'의 base_stats.{key} 값이 숫자가 아닙니다: {base_stats[key]}"
                    )
            skills = player.get("skills", [])
            player["skills"] = self._sanitize_actor_skills(skills, f"player '{player_id}'")

        # monsters.json 검증
        for monster_id, monster in self.monsters.items():
            stats = monster.get("stats", {})
            for key in ["attack", "magic", "defense", "magic_resist", "max_hp"]:
                if key not in stats:
                    raise ValueError(f"monsters.json: monster '{monster_id}'의 stats에 '{key}'가 없습니다.")
                if not isinstance(stats[key], (int, float)):
                    raise ValueError(
                        f"monsters.json: monster '{monster_id}'의 stats.{key} 값이 숫자가 아닙니다: {stats[key]}"
                    )
            skills = monster.get("skills", [])
            monster["skills"] = self._sanitize_actor_skills(skills, f"monster '{monster_id}'")

        # items.json 검증
        allowed_types = {"equipment", "consumable", "material"}
        allowed_slots = {"weapon", "armor", "accessory", None}
        allowed_use_effect_types = {"heal", "cleanse", "buff_stats"}
        for item_id, item in self.items.items():
            itype = item.get("type")
            if itype not in allowed_types:
                raise ValueError(f"items.json: item '{item_id}'의 type이 잘못되었습니다: {itype}")

            stats = item.get("stats", {}) or {}
            if not isinstance(stats, dict):
                raise ValueError(f"items.json: item '{item_id}'의 stats가 객체가 아닙니다.")
            for key in ["attack", "magic", "defense", "magic_resist", "max_hp"]:
                if key not in stats:
                    raise ValueError(f"items.json: item '{item_id}'의 stats에 '{key}'가 없습니다.")
                if not isinstance(stats[key], (int, float)):
                    raise ValueError(
                        f"items.json: item '{item_id}'의 stats.{key} 값이 숫자가 아닙니다: {stats[key]}"
                    )

            if itype == "equipment":
                slot = item.get("slot")
                if slot not in {"weapon", "armor", "accessory"}:
                    raise ValueError(f"items.json: equipment '{item_id}'의 slot이 잘못되었습니다: {slot}")
            if itype == "consumable":
                use_effect = item.get("use_effect")
                if not isinstance(use_effect, dict):
                    raise ValueError(f"items.json: consumable '{item_id}'의 use_effect가 객체가 아닙니다.")
                ue_type = use_effect.get("type")
                if ue_type not in allowed_use_effect_types:
                    raise ValueError(f"items.json: consumable '{item_id}'의 use_effect.type이 잘못되었습니다: {ue_type}")
                if use_effect.get("target") not in {"self"}:
                    raise ValueError(f"items.json: consumable '{item_id}'의 target은 self만 지원합니다.")
                # cleanse/remove 검증
                if ue_type == "cleanse":
                    remove = use_effect.get("remove", [])
                    if not isinstance(remove, list):
                        raise ValueError(f"items.json: consumable '{item_id}'의 remove가 배열이 아닙니다.")

        # drop_tables 참조 검증
        for table_name, entries in self.drop_tables.items():
            if not isinstance(entries, list):
                raise ValueError(f"items.json: drop_table '{table_name}'가 배열이 아닙니다.")
            for entry in entries:
                item_id = entry.get("item")
                if item_id not in self.items:
                    raise ValueError(f"items.json: drop_table '{table_name}'가 존재하지 않는 아이템 '{item_id}'를 참조합니다.")

    def _ensure_basic_skill(self) -> None:
        """폴백 기본 공격 스킬을 강제로 보장."""
        self.skills["__basic__"] = {
            "name": "기본 공격",
            "type": "physical",
            "base_physical": 10,
            "base_magic": 0,
            "scale": {"attack": 0.2, "magic": 0.0},
            "cost": 0,
            "cooldown": 0,
            "apply_effect": None,
        }

    def _sanitize_actor_skills(self, skill_ids: List[str], actor_label: str) -> List[str]:
        """존재하지 않는 스킬 제거 후 비면 기본공격 삽입."""
        sanitized: List[str] = []
        for sid in skill_ids:
            if sid in self.skills:
                sanitized.append(sid)
            else:
                print(f"[경고] {actor_label}의 skill_id '{sid}'가 skills.json에 없어 제거했습니다.")
        if not sanitized:
            sanitized.append("__basic__")
            print(f"[경고] {actor_label}의 스킬이 비어 기본 공격(__basic__)을 삽입했습니다.")
        return sanitized

    def _load_json(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
