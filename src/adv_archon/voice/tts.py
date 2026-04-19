from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass

from adv_archon.core.logging import AppLogger


@dataclass(slots=True)
class SpeechResult:
    started: bool
    reason: str


class MacTextToSpeech:
    def __init__(
        self,
        *,
        enabled: bool = False,
        voice_name: str = "Jorge",
        rate_wpm: int = 190,
        logger: AppLogger | None = None,
    ) -> None:
        self._enabled = enabled
        self._voice_name = voice_name
        self._rate_wpm = rate_wpm
        self._logger = logger
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.stop()

    def enable(self) -> None:
        self.set_enabled(True)

    def disable(self) -> None:
        self.set_enabled(False)

    def status(self) -> str:
        return "on" if self._enabled else "off"

    def describe(self) -> str:
        return f"{self.status()} | voz={self._voice_name} | ritmo={self._rate_wpm} wpm"

    def is_enabled(self) -> bool:
        return self._enabled

    def is_speaking(self) -> bool:
        with self._lock:
            process = self._process
        if process is None:
            return False
        if process.poll() is None:
            return True
        with self._lock:
            if self._process is process:
                self._process = None
        return False

    def speak_async(self, text: str) -> SpeechResult:
        message = " ".join(text.split())
        if not self._enabled:
            return SpeechResult(started=False, reason="voice_disabled")
        if not message:
            return SpeechResult(started=False, reason="empty_text")
        if shutil.which("say") is None:
            raise RuntimeError("No encuentro `say` en este Mac.")

        self.stop()
        process = subprocess.Popen(
            ["say", "-v", self._voice_name, "-r", str(self._rate_wpm), message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        with self._lock:
            self._process = process
        if self._logger is not None:
            self._logger.log(
                "tts_started",
                voice=self._voice_name,
                rate_wpm=self._rate_wpm,
                chars=len(message),
            )
        return SpeechResult(started=True, reason="started")

    def stop(self) -> bool:
        with self._lock:
            process = self._process
            self._process = None
        if process is None:
            return False
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        if self._logger is not None:
            self._logger.log("tts_stopped")
        return True

