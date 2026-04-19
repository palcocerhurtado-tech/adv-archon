import subprocess

from adv_archon.voice.tts import MacTextToSpeech


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return None if not self.terminated and not self.killed else 0

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


def test_tts_builds_say_command(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_popen(args: list[str], **_kwargs: object) -> FakeProcess:
        calls.append(args)
        return FakeProcess()

    monkeypatch.setattr("adv_archon.voice.tts.shutil.which", lambda name: "/usr/bin/say")
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    tts = MacTextToSpeech(enabled=True, voice_name="Monica", rate_wpm=210)

    result = tts.speak_async("Hola  mundo")

    assert result.started is True
    assert calls == [["say", "-v", "Monica", "-r", "210", "Hola mundo"]]
    assert tts.is_speaking() is True


def test_tts_stop_terminates_running_process(monkeypatch) -> None:
    process = FakeProcess()

    monkeypatch.setattr("adv_archon.voice.tts.shutil.which", lambda name: "/usr/bin/say")
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)

    tts = MacTextToSpeech(enabled=True)
    tts.speak_async("Hola")

    stopped = tts.stop()

    assert stopped is True
    assert process.terminated is True
    assert tts.is_speaking() is False

