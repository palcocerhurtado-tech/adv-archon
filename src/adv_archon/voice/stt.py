from __future__ import annotations

import tempfile
import time
import wave
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any

import numpy as np

from adv_archon.core.logging import AppLogger


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str
    duration_seconds: float
    used_wake_word: bool = False


class WhisperSpeechToText:
    def __init__(
        self,
        *,
        model_name: str = "small",
        language: str = "es",
        device: str = "cpu",
        compute_type: str = "int8",
        sample_rate: int = 16000,
        max_record_seconds: int = 45,
        silence_seconds: float = 1.2,
        silence_threshold: float = 0.015,
        wake_word_enabled: bool = False,
        wake_word_keyword: str = "jarvis",
        wake_word_timeout_seconds: int = 60,
        porcupine_access_key: str | None = None,
        logger: AppLogger | None = None,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._device = device
        self._compute_type = compute_type
        self._sample_rate = sample_rate
        self._max_record_seconds = max_record_seconds
        self._silence_seconds = silence_seconds
        self._silence_threshold = silence_threshold
        self._wake_word_enabled = wake_word_enabled
        self._wake_word_keyword = wake_word_keyword
        self._wake_word_timeout_seconds = wake_word_timeout_seconds
        self._porcupine_access_key = porcupine_access_key
        self._logger = logger
        self._model: Any | None = None

    def describe(self) -> str:
        wake_word = self._wake_word_keyword if self._wake_word_enabled else "off"
        return (
            f"modelo={self._model_name} | idioma={self._language} | "
            f"wake-word={wake_word}"
        )

    def listen_once(self, *, use_wake_word: bool = False) -> TranscriptionResult:
        used_wake_word = False
        if use_wake_word and self._wake_word_enabled:
            self.wait_for_wake_word()
            used_wake_word = True

        audio, duration_seconds = self._record_until_silence()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            self._write_wav(temp_path, audio)
            text = self.transcribe_file(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

        result = TranscriptionResult(
            text=text,
            language=self._language,
            duration_seconds=duration_seconds,
            used_wake_word=used_wake_word,
        )
        if self._logger is not None:
            self._logger.log(
                "stt_transcribed",
                chars=len(text),
                duration_seconds=round(duration_seconds, 2),
                wake_word=used_wake_word,
                model=self._model_name,
            )
        return result

    def listen_streaming(
        self,
        *,
        use_wake_word: bool = False,
        on_partial: Callable[[str], None] | None = None,
        on_final: Callable[[str], None] | None = None,
        cancel_event: Event | None = None,
        partial_interval_seconds: float = 1.5,
        partial_window_seconds: float = 3.0,
    ) -> TranscriptionResult:
        """Capture one utterance and emit pseudo-partials while recording.

        faster-whisper does not stream partial tokens in this integration. This method
        keeps the existing local backend and transcribes small rolling windows while
        the microphone is still open. The final result always comes from the complete
        recorded buffer.
        """
        used_wake_word = False
        if use_wake_word and self._wake_word_enabled:
            self.wait_for_wake_word()
            used_wake_word = True

        audio, duration_seconds = self._record_until_silence_streaming(
            on_partial=on_partial,
            cancel_event=cancel_event,
            partial_interval_seconds=partial_interval_seconds,
            partial_window_seconds=partial_window_seconds,
        )
        self._raise_if_cancelled(cancel_event)
        text = self._transcribe_audio(audio)
        if on_final is not None:
            on_final(text)

        result = TranscriptionResult(
            text=text,
            language=self._language,
            duration_seconds=duration_seconds,
            used_wake_word=used_wake_word,
        )
        if self._logger is not None:
            self._logger.log(
                "stt_transcribed_streaming",
                chars=len(text),
                duration_seconds=round(duration_seconds, 2),
                wake_word=used_wake_word,
                model=self._model_name,
            )
        return result

    def transcribe_file(self, path: Path) -> str:
        model = self._load_model()
        segments, _info = model.transcribe(
            str(path),
            language=self._language,
            vad_filter=True,
            condition_on_previous_text=False,
            beam_size=1,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise RuntimeError("No he podido transcribir nada útil del audio.")
        return text

    def _transcribe_audio(self, audio: np.ndarray) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            self._write_wav(temp_path, audio)
            return self.transcribe_file(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def wait_for_wake_word(self) -> None:
        if not self._wake_word_enabled:
            raise RuntimeError("La wake-word no está activada en la configuración.")
        if not self._porcupine_access_key:
            raise RuntimeError(
                "Falta `PORCUPINE_ACCESS_KEY` para usar wake-word con pvporcupine."
            )
        try:
            import pvporcupine  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Falta `pvporcupine`. Instálalo para activar la wake-word."
            ) from exc
        try:
            import sounddevice as sd  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "Falta `sounddevice`. Instálalo para capturar audio del micrófono."
            ) from exc

        porcupine = pvporcupine.create(
            access_key=self._porcupine_access_key,
            keywords=[self._wake_word_keyword],
        )
        timeout_at = time.monotonic() + self._wake_word_timeout_seconds
        try:
            with sd.RawInputStream(
                samplerate=porcupine.sample_rate,
                blocksize=porcupine.frame_length,
                channels=1,
                dtype="int16",
            ) as stream:
                while time.monotonic() < timeout_at:
                    frame, _overflowed = stream.read(porcupine.frame_length)
                    pcm = np.frombuffer(frame, dtype=np.int16)
                    if porcupine.process(pcm) >= 0:
                        if self._logger is not None:
                            self._logger.log(
                                "wake_word_detected",
                                keyword=self._wake_word_keyword,
                            )
                        return
        finally:
            porcupine.delete()
        raise RuntimeError("No he detectado la wake-word dentro del tiempo configurado.")

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RuntimeError(
                    "Falta `faster-whisper`. Instálalo para usar `/listen`."
                ) from exc
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )
        return self._model

    def _record_until_silence(self) -> tuple[np.ndarray, float]:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Falta `sounddevice`. Instálalo para capturar audio del micrófono."
            ) from exc

        chunk_seconds = 0.2
        chunk_frames = max(1, int(self._sample_rate * chunk_seconds))
        max_chunks = max(1, int(self._max_record_seconds / chunk_seconds))
        max_pre_roll = max(1, int(0.6 / chunk_seconds))
        pre_roll: deque[np.ndarray] = deque(maxlen=max_pre_roll)
        recorded: list[np.ndarray] = []
        speech_started = False
        silence_for = 0.0
        started_at = time.monotonic()

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
        ) as stream:
            for _ in range(max_chunks):
                chunk, _overflowed = stream.read(chunk_frames)
                mono = np.asarray(chunk[:, 0], dtype=np.float32)
                level = float(np.sqrt(np.mean(np.square(mono))))
                if speech_started:
                    recorded.append(mono.copy())
                else:
                    pre_roll.append(mono.copy())

                if level >= self._silence_threshold:
                    if not speech_started:
                        recorded.extend(list(pre_roll))
                        pre_roll.clear()
                        speech_started = True
                    silence_for = 0.0
                elif speech_started:
                    silence_for += chunk_seconds
                    if silence_for >= self._silence_seconds:
                        break

        if not speech_started or not recorded:
            raise RuntimeError("No he detectado voz en el micrófono.")

        audio = np.concatenate(recorded)
        duration_seconds = time.monotonic() - started_at
        return audio, duration_seconds

    def _record_until_silence_streaming(
        self,
        *,
        on_partial: Callable[[str], None] | None,
        cancel_event: Event | None,
        partial_interval_seconds: float,
        partial_window_seconds: float,
    ) -> tuple[np.ndarray, float]:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Falta `sounddevice`. Instálalo para capturar audio del micrófono."
            ) from exc

        chunk_seconds = 0.2
        chunk_frames = max(1, int(self._sample_rate * chunk_seconds))
        max_chunks = max(1, int(self._max_record_seconds / chunk_seconds))
        max_pre_roll = max(1, int(0.6 / chunk_seconds))
        pre_roll: deque[np.ndarray] = deque(maxlen=max_pre_roll)
        recorded: list[np.ndarray] = []
        speech_started = False
        silence_for = 0.0
        started_at = time.monotonic()
        last_partial_at = started_at
        partial_future: Future[str] | None = None
        last_partial_text = ""
        window_samples = max(1, int(self._sample_rate * partial_window_seconds))

        with ThreadPoolExecutor(max_workers=1) as executor:
            with sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
            ) as stream:
                for _ in range(max_chunks):
                    self._raise_if_cancelled(cancel_event)
                    chunk, _overflowed = stream.read(chunk_frames)
                    mono = np.asarray(chunk[:, 0], dtype=np.float32)
                    level = float(np.sqrt(np.mean(np.square(mono))))
                    if speech_started:
                        recorded.append(mono.copy())
                    else:
                        pre_roll.append(mono.copy())

                    if level >= self._silence_threshold:
                        if not speech_started:
                            recorded.extend(list(pre_roll))
                            pre_roll.clear()
                            speech_started = True
                            last_partial_at = time.monotonic()
                        silence_for = 0.0
                    elif speech_started:
                        silence_for += chunk_seconds
                        if silence_for >= self._silence_seconds:
                            break

                    partial_text = self._consume_partial(partial_future)
                    if partial_text and partial_text != last_partial_text:
                        last_partial_text = partial_text
                        if on_partial is not None:
                            on_partial(partial_text)
                    if partial_future is not None and partial_future.done():
                        partial_future = None

                    now = time.monotonic()
                    ready_for_partial = (
                        speech_started
                        and on_partial is not None
                        and partial_future is None
                        and now - last_partial_at >= max(0.8, partial_interval_seconds)
                        and recorded
                    )
                    if ready_for_partial:
                        audio_so_far = np.concatenate(recorded)
                        window = audio_so_far[-window_samples:].copy()
                        partial_future = executor.submit(self._try_transcribe_partial, window)
                        last_partial_at = now

            partial_text = self._consume_partial(partial_future, wait_seconds=0.05)
            if partial_text and partial_text != last_partial_text and on_partial is not None:
                on_partial(partial_text)

        if not speech_started or not recorded:
            raise RuntimeError("No he detectado voz en el micrófono.")

        audio = np.concatenate(recorded)
        duration_seconds = time.monotonic() - started_at
        return audio, duration_seconds

    def _try_transcribe_partial(self, audio: np.ndarray) -> str:
        try:
            return self._transcribe_audio(audio)
        except Exception:
            return ""

    @staticmethod
    def _consume_partial(
        partial_future: Future[str] | None,
        *,
        wait_seconds: float = 0.0,
    ) -> str:
        if partial_future is None:
            return ""
        if wait_seconds <= 0 and not partial_future.done():
            return ""
        try:
            return partial_future.result(timeout=wait_seconds).strip()
        except Exception:
            return ""

    @staticmethod
    def _raise_if_cancelled(cancel_event: Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Escucha cancelada por el usuario.")

    def _write_wav(self, path: Path, audio: np.ndarray) -> None:
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self._sample_rate)
            handle.writeframes(pcm.tobytes())
