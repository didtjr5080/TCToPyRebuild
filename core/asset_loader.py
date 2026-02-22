from __future__ import annotations

from pathlib import Path
import re
from typing import Optional, Tuple, Dict

from PyQt6 import QtGui, QtCore


class AssetLoader:
    """이미지 파일을 규칙 기반으로 탐색하고, 없으면 플레이스홀더를 제공하는 로더."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
        self.asset_dir = root / "assets"
        self.asset_dir.mkdir(exist_ok=True)
        self._cache: Dict[Tuple[str, str, int, int], QtGui.QPixmap] = {}
        self._exts = [".png", ".webp", ".jpg", ".jpeg"]
        self._icon_alias = {
            "buff_stats": "buff",
            "debuff_stats": "debuff",
            "bleed": "bleed",
            "stun": "stun",
        }

    # -------------------------------------------------------------
    # Public loaders
    # -------------------------------------------------------------
    def load_character(self, player_id: str, size: QtCore.QSize = QtCore.QSize(256, 256)) -> QtGui.QPixmap:
        return self._load_with_candidates(
            category="characters",
            ids=self._candidate_ids(player_id),
            fallback_text=player_id or "player",
            size=size,
        )

    def load_enemy(self, enemy_id: str, size: QtCore.QSize = QtCore.QSize(256, 256)) -> QtGui.QPixmap:
        return self._load_with_candidates(
            category="enemies",
            ids=self._candidate_ids(enemy_id or "enemy_default"),
            fallback_text=enemy_id or "enemy",
            size=size,
        )

    def load_background(self, name: str, size: QtCore.QSize) -> QtGui.QPixmap:
        ids = self._candidate_ids(name or "background")
        # default 배경도 후보에 추가
        ids.append("default")
        return self._load_with_candidates("backgrounds", ids, fallback_text=name or "background", size=size)

    def load_icon(self, effect_id: str, size: QtCore.QSize = QtCore.QSize(64, 64)) -> QtGui.QPixmap:
        icon_id = effect_id or "icon"
        ids = self._candidate_ids(icon_id)
        # alias 적용 후 재시도
        alias = self._icon_alias.get(icon_id)
        if alias and alias not in ids:
            ids.extend(self._candidate_ids(alias))
        ids.append("default")
        return self._load_with_candidates("icons", ids, fallback_text=icon_id, size=size)

    def load_skill_effect(self, skill_id: str) -> Optional[QtGui.QPixmap]:
        """스킬 오버레이 전용 이펙트 이미지를 로드한다.

        - 탐색 경로: assets/effects/{skill_id}.{png/webp/jpg/jpeg}
        - skill_id와 normalize된 id 둘 다 시도
        - 없으면 None 반환 (기본 플레이스홀더 사용)
        """
        if not skill_id:
            return None
        ids: list[str] = []
        # 1) 원본 id 우선
        ids.extend(self._candidate_ids(skill_id))
        # 2) 접두어 추가 버전도 시도 (이미 skill_가 붙어 있어도 한 번 더 붙은 파일을 대비)
        ids.extend(self._candidate_ids(f"skill_{skill_id}"))
        # 3) skill_ 접두어가 있으면 제거한 버전도 시도 (에셋이 접두어 없이 저장된 경우)
        if skill_id.startswith("skill_"):
            trimmed = skill_id[len("skill_") :]
            ids.extend(self._candidate_ids(trimmed))
        # 중복 제거, 순서 유지
        seen = set()
        ids = [x for x in ids if not (x in seen or seen.add(x))]
        base = self.asset_dir / "effects"
        for cid in ids:
            for ext in self._exts:
                path = base / f"{cid}{ext}"
                if not path.exists():
                    continue
                pix = QtGui.QPixmap(str(path))
                if pix.isNull():
                    print(f"[경고] 스킬 이펙트 로드 실패: {path}")
                    continue
                return pix
        print(f"[안내] 스킬 이펙트 미발견: {skill_id} -> 후보 {ids}")
        return None

    # -------------------------------------------------------------
    # 내부 헬퍼
    # -------------------------------------------------------------
    def _normalize(self, raw: str) -> str:
        text = (raw or "").strip()
        text = text.lower()
        text = re.sub(r"\s+", "_", text)
        text = re.sub(r"[^a-z0-9_]+", "_", text)
        text = re.sub(r"_+", "_", text)
        return text.strip("_") or raw

    def _candidate_ids(self, raw: str) -> list[str]:
        primary = raw or ""
        normalized = self._normalize(primary)
        ids = [primary]
        if normalized and normalized != primary:
            ids.append(normalized)
        return ids

    def _load_with_candidates(self, category: str, ids: list[str], fallback_text: str, size: QtCore.QSize) -> QtGui.QPixmap:
        key_base = (category, fallback_text, size.width(), size.height())
        for cid in ids:
            cache_key = (category, cid, size.width(), size.height())
            if cache_key in self._cache:
                return self._cache[cache_key]
            pix = self._try_load(category, cid, size)
            if pix:
                self._cache[cache_key] = pix
                return pix
        # 플레이스홀더 캐싱
        if key_base in self._cache:
            return self._cache[key_base]
        placeholder = self._placeholder(size=size, text=fallback_text)
        self._cache[key_base] = placeholder
        return placeholder

    def _try_load(self, category: str, cid: str, size: QtCore.QSize) -> Optional[QtGui.QPixmap]:
        base = self.asset_dir / category
        for ext in self._exts:
            path = base / f"{cid}{ext}"
            if not path.exists():
                continue
            pix = QtGui.QPixmap(str(path))
            if pix.isNull():
                print(f"[경고] 에셋 로드 실패: {path}")
                continue
            return pix
        return None

    def _placeholder(self, size: QtCore.QSize, text: str) -> QtGui.QPixmap:
        """회색 박스 플레이스홀더 생성."""
        w = max(size.width(), 1)
        h = max(size.height(), 1)
        pix = QtGui.QPixmap(w, h)
        pix.fill(QtGui.QColor("#3a3f4b"))
        painter = QtGui.QPainter(pix)
        painter.setPen(QtGui.QPen(QtGui.QColor("#cdd3e1")))
        painter.setFont(QtGui.QFont("Segoe UI", 14, QtGui.QFont.Weight.Bold))
        rect = QtCore.QRect(0, 0, w, h)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return pix
