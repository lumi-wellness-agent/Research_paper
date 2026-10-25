"""민감 파일 커밋 차단을 확인한다 — 파이프라인 게이트(sensitive_gate.py)와 하네스 훅.

스크래치 리포에서 돌려 사용자 리포의 인덱스·워킹트리와 전역 git 설정을 건드리지 않는다.
게이트는 실제로 실행해 마커와 종료코드를 본다. 훅(validate-git-sensitive.sh)에는 Claude Code·Codex가
주는 stdin JSON을 그대로 흘린다. 훅은 bash·jq로 도는 macOS·Linux 하네스용이라 Windows와 bash·jq가
없는 환경에서는 건너뛴다.
"""

import json
import shutil
import subprocess
import sys
import unittest

from automation.tests.helpers import AUTOMATION, ENV, ScratchRepo

HOOK = AUTOMATION / "hooks" / "validate-git-sensitive.sh"

needs_bash = unittest.skipIf(
    sys.platform == "win32" or not (shutil.which("bash") and shutil.which("jq")),
    "훅은 bash·jq로 도는 macOS·Linux 하네스용이다",
)


class GateTest(unittest.TestCase):
    def test_passes_without_sensitive_files(self):
        repo = ScratchRepo(self)
        repo.stage("app.py")

        self.assertEqual(repo.run("sensitive_gate.py"), (0, ["SENSITIVE_GATE result=PASS"]))

    def test_blocks_staged_sensitive_file(self):
        for path in [
            ".env",
            "deploy/.env.prod",
            "AuthKey_test.p8",
            ".claude/settings.local.json",
            ".mcp.json",
            "firebase-adminsdk-abc.json",
            "keys/id_rsa",
            # 한글 경로도 그대로 받는다 — git 기본 출력은 경로를 따옴표·8진수로 바꿔
            # 정규식을 빠져나간다
            "비밀/.env",
        ]:
            with self.subTest(path=path):
                repo = ScratchRepo(self)
                repo.stage(path)

                self.assertEqual(
                    repo.run("sensitive_gate.py"),
                    (1, ["차단된 민감 파일:", f"  {path}", "SENSITIVE_GATE result=BLOCKED"]),
                )

    def test_allows_example_template(self):
        repo = ScratchRepo(self)
        repo.stage(".env.example")

        self.assertEqual(repo.run("sensitive_gate.py"), (0, ["SENSITIVE_GATE result=PASS"]))

    def test_fails_closed_when_git_fails(self):
        repo = ScratchRepo(self)

        self.assertEqual(
            repo.run("sensitive_gate.py", env={"GIT_DIR": str(repo.dir / "missing")}),
            (1, ["SENSITIVE_GATE result=ERROR"]),
        )


@needs_bash
class HookTest(unittest.TestCase):
    def decide(self, repo: ScratchRepo, command: str) -> str:
        """훅에 하네스 stdin JSON을 흘려 deny/pass를 받는다.

        훅은 판정과 상관없이 0으로 끝나야 한다.
        """
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        done = subprocess.run(
            ["bash", str(HOOK)],
            input=payload,
            cwd=repo.dir,
            env=ENV,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        if not done.stdout.strip():
            return "pass"
        return json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"]

    def test_with_untracked_env(self):
        repo = ScratchRepo(self)
        repo.write(".env")
        for command, want in [
            ("ls", "pass"),  # git 외 명령
            ("git -c core.quotepath=false status --short", "pass"),
            ("git add .env", "deny"),
            ("git add -A && git commit -m x", "deny"),  # 광역 add가 untracked .env를 끌어들인다
            ("git add note.txt", "pass"),
            ("git commit -m 'x'", "pass"),  # 스테이징된 민감 파일이 없다
        ]:
            with self.subTest(command=command):
                self.assertEqual(self.decide(repo, command), want)

    def test_denies_commit_with_staged_env(self):
        repo = ScratchRepo(self)
        repo.stage(".env")

        self.assertEqual(self.decide(repo, "git commit -m 'x'"), "deny")

    # .gitignore가 막는 민감 파일을 -f로 끌어들이는 경로 — 명시 인자 파싱이 광역 판정으로 새지
    # 않아야 잡힌다 (macOS sed는 \b를 몰라 원본 훅의 파싱이 광역 판정으로 떨어졌다 — 회귀 방지)
    def test_with_ignored_env(self):
        repo = ScratchRepo(self)
        repo.write(".gitignore", ".env*\n")
        repo.write(".env")
        for command, want in [
            ("git add -f .env", "deny"),
            ("git add -A -f", "deny"),  # 광역 + 강제는 ignored 파일까지 스테이징한다
            ("git add .", "pass"),  # git도 ignored 파일은 add하지 않는다
            ("git add -f note.txt", "pass"),  # 강제지만 명시·비민감
            ("git add -- .env", "deny"),
        ]:
            with self.subTest(command=command):
                self.assertEqual(self.decide(repo, command), want)
