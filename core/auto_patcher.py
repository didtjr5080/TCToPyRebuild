from __future__ import annotations

"""원격 GitHub Raw에서 JSON/에셋을 받아오는 자동 패처.

- requests 기반으로 GitHub Raw URL을 사용해 최신 데이터를 내려받습니다.
- 오프라인/에러 시 게임이 크래시하지 않도록 항상 실패를 감싸고 False를 반환합니다.
- 임시 파일로 먼저 저장 후 교체하여 다운로드 중 파손을 방지합니다.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests

log = logging.getLogger(__name__)


class AutoPatcher:
    def __init__(self, base_url: str, local_root: Path, timeout: float = 10.0) -> None:
        """GitHub Raw 베이스 URL과 로컬 루트 경로를 지정합니다.

        Args:
            base_url: 예) "https://raw.githubusercontent.com/user/repo/main/" (끝에 / 있으면 그대로 사용)
            local_root: 데이터/에셋이 저장될 로컬 기본 폴더(Path 객체 권장)
            timeout: 요청 타임아웃(초)
        """
        if not base_url.endswith("/"):
            base_url += "/"
        self.base_url = base_url
        self.local_root = Path(local_root)
        self.timeout = timeout
        self.manifest_name = "manifest.json"
        self.session = requests.Session()

    def check_for_updates(self) -> Union[List[str], bool]:
        """서버 manifest와 로컬 manifest를 비교해 업데이트 대상 파일 목록을 반환합니다.

        Returns:
            업데이트가 필요한 상대 경로 리스트. 네트워크 오류 시 False.

        Note:
            - URL 캐싱을 피하려고 타임스탬프 쿼리를 붙여 매번 강제 최신을 받습니다.
            - 예외 발생 시 "오프라인 모드로 실행합니다"를 로그에 남기고 False를 반환합니다.
        """
        try:
            server_manifest = self._fetch_manifest()
            if server_manifest is None:
                return False
            local_manifest = self._load_local_manifest()
            server_files: Dict[str, str] = server_manifest.get("files", {}) if isinstance(server_manifest, dict) else {}
            local_files: Dict[str, str] = local_manifest.get("files", {}) if isinstance(local_manifest, dict) else {}

            to_update: List[str] = []
            for rel_path, ver in server_files.items():
                if local_files.get(rel_path) != ver:
                    to_update.append(rel_path)
            return to_update
        except Exception as exc:  # 방어적: 어떤 예외라도 앱이 죽지 않게 잡는다
            log.warning("오프라인 모드로 실행합니다 (manifest 확인 실패: %s)", exc)
            return False

    def download_updates(self, file_list: List[str]) -> bool:
        """서버에서 파일을 받아 로컬에 덮어씁니다.

        Args:
            file_list: 업데이트가 필요한 상대 경로 목록 (예: "data/items.json")

        Returns:
            True: 모두 성공, False: 네트워크/저장 실패로 일부라도 내려받지 못함.

        구현 메모 (초보자용):
            - 다운로드 중 전원이 꺼지거나 네트워크가 끊기면 파일이 깨질 수 있어, 같은 위치에 .tmp로 먼저 저장합니다.
            - .tmp 저장이 끝까지 성공하면 그때 최종 파일로 교체합니다(원자적 교체에 가까움).
            - GitHub CDN 캐시를 우회하기 위해 매 요청에 현재 시각을 쿼리로 붙입니다.
        """
        if not file_list:
            return True
        try:
            for rel_path in file_list:
                url = self._build_url(rel_path)
                target_path = self.local_root / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")

                resp = self.session.get(url, timeout=self.timeout, stream=True)
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {url}")

                # 임시 파일로 먼저 저장
                with tmp_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        f.write(chunk)

                # 다운로드 완료 후 원본 교체
                tmp_path.replace(target_path)
            return True
        except Exception as exc:
            log.warning("오프라인 모드로 실행합니다 (다운로드 실패: %s)", exc)
            # 실패 시 tmp 파일이 남더라도 다음 실행에서 덮어쓰게 둔다
            return False

    # --------------------
    # 내부 헬퍼
    # --------------------
    def _fetch_manifest(self) -> Optional[Dict[str, object]]:
        """서버 manifest를 가져옵니다. 실패 시 None."""
        url = self._build_url(self.manifest_name)
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            log.warning("manifest 요청 실패: %s (status=%s)", url, resp.status_code)
            return None
        return resp.json()

    def _load_local_manifest(self) -> Dict[str, object]:
        """로컬 manifest.json을 읽습니다. 없으면 기본 구조 반환."""
        path = self.local_root / self.manifest_name
        if not path.exists():
            return {"version": "0.0.0", "files": {}}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _build_url(self, rel_path: str) -> str:
        """캐시 무시용 타임스탬프 쿼리를 포함한 완전한 Raw URL 구성."""
        timestamp = int(time.time())
        # GitHub Raw는 단순 경로 연결로 접근 가능. 끝에 ?t= 로 캐시를 무시한다.
        return f"{self.base_url}{rel_path}?t={timestamp}"


__all__ = ["AutoPatcher"]
