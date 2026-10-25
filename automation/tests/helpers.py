"""automation/ 테스트 공용 — 스크래치 git 리포, gh 대역, 출력 캡처."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

AUTOMATION = Path(__file__).resolve().parents[1]
# 사용자의 전역·시스템 git 설정(autocrlf·훅 등)이 결과를 바꾸지 않게 한다.
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class ScratchRepo:
    """임시 git 리포 — 사용자 리포의 인덱스·워킹트리와 전역 git 설정을 건드리지 않는다."""

    def __init__(self, test: unittest.TestCase) -> None:
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.git("init", "-q")
        self.write("note.txt", "hi\n")
        self.commit("note.txt")

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.dir, env=ENV, check=True, capture_output=True)

    def write(self, path: str, text: str = "secret\n") -> Path:
        file = self.dir / path
        file.parent.mkdir(parents=True, exist_ok=True)
        # 바이트로 쓴다 — 텍스트 모드는 Windows에서 줄바꿈을 바꿔 크기·내용이 OS마다 달라진다.
        file.write_bytes(text.encode("utf-8"))
        return file

    def sized(self, path: str, size: int) -> None:
        """truncate로 크기만 늘린 파일을 만든다 — 큰 내용을 실제로 쓰지 않는다."""
        with self.write(path, "").open("r+b") as stream:
            stream.truncate(size)

    def stage(self, path: str, text: str = "secret\n") -> None:
        self.write(path, text)
        self.git("add", "-f", path)

    def commit(self, *paths: str) -> None:
        self.git("add", "-f", *paths)
        self.git("-c", "user.email=smoke@test", "-c", "user.name=smoke", "commit", "-qm", "commit")

    def run(
        self,
        script: str,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        encoding: str = "utf-8",
    ) -> tuple[int, list[str]]:
        """automation/bin/<script>를 이 리포에서 실행해 (종료코드, stdout 줄 목록)을 돌려준다.

        encoding은 스크립트의 출력 인코딩이다 — 한국어 Windows에서 리다이렉트한 출력(cp949)을
        흉내 낼 때 바꾼다.
        """
        done = subprocess.run(
            [sys.executable, str(AUTOMATION / "bin" / script)],
            cwd=cwd or self.dir,
            env={**ENV, "PYTHONIOENCODING": encoding, **(env or {})},
            capture_output=True,
            text=True,
            encoding=encoding,
        )
        return done.returncode, done.stdout.splitlines()


def fake_gh(test: unittest.TestCase, module, *responses) -> list:
    """module의 gh 호출을 대역으로 바꾼다. 응답을 차례로 돌려주고, 예외면 던지고, 대기는 건너뛴다.

    받은 인자 목록을 돌려준다.
    """
    queue = list(responses)
    calls = []

    def gh(*args):
        calls.append(args)
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    for patcher in (
        mock.patch.object(module, "gh", gh),
        mock.patch.object(time, "sleep", lambda seconds: None),
    ):
        patcher.start()
        test.addCleanup(patcher.stop)
    return calls


def capture(main, *args) -> tuple[int, list[str], str]:
    """main(*args)를 돌려 (종료코드, stdout 줄 목록, stderr)를 돌려준다."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(*args)
    return code, out.getvalue().splitlines(), err.getvalue()
