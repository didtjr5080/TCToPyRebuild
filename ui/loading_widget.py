from __future__ import annotations

"""패치/로딩 화면.

- AutoPatcher를 별도의 QThread에서 실행해 메인(UI) 스레드를 블로킹하지 않습니다.
- 진행률과 상태를 간단히 표시하고, 완료 시 patch_complete 시그널을 방출합니다.
"""

from typing import List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from core.auto_patcher import AutoPatcher


class _PatchWorker(QThread):
    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(bool)

    def __init__(self, patcher: AutoPatcher, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.patcher = patcher

    def run(self) -> None:
        """백그라운드에서 패치 실행.

        QThread를 사용하여 메인 스레드를 막지 않음. (UI 프리징 방지)
        """
        # 0% 시작
        self.progress.emit(0)
        targets = self.patcher.check_for_updates()
        if targets is False:
            # 네트워크 실패 등: 그대로 종료 (오프라인 모드)
            self.progress.emit(100)
            self.finished_ok.emit(False)
            return
        if not targets:
            # 업데이트 필요 없음
            self.progress.emit(100)
            self.finished_ok.emit(True)
            return

        # 간단한 분배: 파일 개수 기준으로 퍼센트 증가
        total = len(targets)
        step = max(1, int(90 / total))
        current = 10
        self.progress.emit(current)

        # 파일마다 다운로드가 끝날 때마다 조금씩 증가시켜 사용자에게 피드백 제공
        success_all = True
        for idx, rel_path in enumerate(targets, start=1):
            # download_updates는 내부에서 안전 쓰기를 하지만, 여기서는 파일 단위 진행률 표시를 위해 하나씩 호출
            result = self.patcher.download_updates([rel_path])
            success_all = success_all and result
            current = min(100, current + step)
            self.progress.emit(current)

        self.progress.emit(100)
        self.finished_ok.emit(success_all)


class LoadingWidget(QWidget):
    patch_complete = pyqtSignal(bool)

    def __init__(self, patcher: AutoPatcher, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.patcher = patcher
        self.worker: Optional[_PatchWorker] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(12)

        self.label = QLabel("업데이트 확인 중...")
        self.label.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

    def start_patch(self) -> None:
        """패치 시작 (외부에서 호출)."""
        if self.worker and self.worker.isRunning():
            return
        self.worker = _PatchWorker(self.patcher, self)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished_ok.connect(self._on_patch_finished)
        self.worker.start()

    def _on_patch_finished(self, ok: bool) -> None:
        self.patch_complete.emit(ok)


__all__ = ["LoadingWidget"]
