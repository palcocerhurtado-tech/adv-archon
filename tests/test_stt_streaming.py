from __future__ import annotations

import numpy as np

from adv_archon.voice.stt import WhisperSpeechToText


def test_listen_streaming_emits_final_without_real_microphone(monkeypatch) -> None:
    stt = WhisperSpeechToText()
    partials: list[str] = []
    finals: list[str] = []
    audio = np.zeros(16000, dtype=np.float32)

    monkeypatch.setattr(
        stt,
        "_record_until_silence_streaming",
        lambda **kwargs: (
            kwargs["on_partial"]("texto parcial"),
            (audio, 1.0),
        )[1],
    )
    monkeypatch.setattr(stt, "_transcribe_audio", lambda _audio: "texto final")

    result = stt.listen_streaming(
        on_partial=partials.append,
        on_final=finals.append,
    )

    assert partials == ["texto parcial"]
    assert finals == ["texto final"]
    assert result.text == "texto final"
    assert result.duration_seconds == 1.0


def test_consume_partial_ignores_pending_future() -> None:
    stt = WhisperSpeechToText()

    assert stt._consume_partial(None) == ""
