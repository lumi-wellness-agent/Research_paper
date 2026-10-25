"""PR 게이트(automation/bin/pr_gate.py)를 gh 없이 확인한다.

판정은 fixture JSON으로, 폴링은 gh 대역으로 본다. 이 레포는 CI가 없어 앵커 없이 부르는 것이
기본이고(pr_gate.py <PR번호> 180), 앵커 모드는 워크플로우가 생길 때를 위해 BE와 같은 사례로 둔다.
"""

import json
import subprocess
import unittest

from automation.bin import pr_gate
from automation.tests.helpers import capture, fake_gh

ANCHORS = ["check", "gitleaks"]
API_ERROR = subprocess.CalledProcessError(1, ["gh"])
VIEW_CALL = ("pr", "view", "31", "--json", "mergeable,statusCheckRollup")


def run(name: str, conclusion="SUCCESS", status: str = "COMPLETED") -> dict:
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion}


def commit_status(context: str, state: str) -> dict:
    return {"__typename": "StatusContext", "context": context, "state": state}


def view(*checks: dict, mergeable: str = "MERGEABLE") -> dict:
    return {"mergeable": mergeable, "statusCheckRollup": list(checks)}


class JudgeTest(unittest.TestCase):
    CASES = [
        # 앵커 없음 모드 (CI 없는 레포 — 이 레포의 기본) — 체크 존재를 요구하지 않는다
        ("no-anchor-no-checks", view(), [], "PASS"),
        (
            "no-anchor-unknown",
            {"mergeable": "UNKNOWN", "statusCheckRollup": None},
            [],
            "PENDING anchors_absent= pending= mergeable=UNKNOWN",
        ),
        (
            "no-anchor-conflicting",
            view(mergeable="CONFLICTING"),
            [],
            "FAIL failed= mergeable=CONFLICTING",
        ),
        # 앵커가 없어도 붙어 있는 체크가 실패하면 막는다
        ("no-anchor-failed", view(run("x", "FAILURE")), [], "FAIL failed=x mergeable=MERGEABLE"),
        # 앵커 모드 (워크플로우가 생기면)
        ("all-pass", view(run("check"), run("gitleaks")), ANCHORS, "PASS"),
        (
            "anchor-failed",
            view(run("check", "FAILURE"), run("gitleaks")),
            ANCHORS,
            "FAIL failed=check mergeable=MERGEABLE",
        ),
        # 앵커가 아닌 체크도 게이트 대상이다 (전수 검사)
        (
            "non-anchor-failed",
            view(run("check"), run("gitleaks"), run("e2e", "FAILURE")),
            ANCHORS,
            "FAIL failed=e2e mergeable=MERGEABLE",
        ),
        # 앵커가 아직 등록되지 않았으면 통과가 아니다 (vacuous pass 방지)
        (
            "anchor-absent",
            view(run("check")),
            ANCHORS,
            "PENDING anchors_absent=gitleaks pending= mergeable=MERGEABLE",
        ),
        (
            "in-progress",
            view(run("check"), run("gitleaks", None, "IN_PROGRESS")),
            ANCHORS,
            "PENDING anchors_absent= pending=gitleaks mergeable=MERGEABLE",
        ),
        (
            "conflicting",
            view(run("check"), run("gitleaks"), mergeable="CONFLICTING"),
            ANCHORS,
            "FAIL failed= mergeable=CONFLICTING",
        ),
        (
            "no-checks-with-anchor",
            view(),
            ["check"],
            "PENDING anchors_absent=check pending= mergeable=MERGEABLE",
        ),
        # commit status(StatusContext)와 NEUTRAL·SKIPPED도 같은 규칙으로 정규화한다
        (
            "skipped-and-status-pass",
            view(run("check"), run("gitleaks", "SKIPPED"), commit_status("deploy", "SUCCESS")),
            ANCHORS,
            "PASS",
        ),
        (
            "status-pending",
            view(run("check"), run("gitleaks"), commit_status("deploy", "EXPECTED")),
            ANCHORS,
            "PENDING anchors_absent= pending=deploy mergeable=MERGEABLE",
        ),
        (
            "status-error",
            view(run("check"), run("gitleaks"), commit_status("deploy", "ERROR")),
            ANCHORS,
            "FAIL failed=deploy mergeable=MERGEABLE",
        ),
    ]

    def test_judge(self):
        for name, pr, anchors, want in self.CASES:
            with self.subTest(name):
                self.assertEqual(pr_gate.judge(pr, anchors), want)


class MainTest(unittest.TestCase):
    def test_waits_until_mergeable(self):
        calls = fake_gh(self, pr_gate, json.dumps(view(mergeable="UNKNOWN")), json.dumps(view()))

        code, out, _ = capture(pr_gate.main, ["31", "180"])

        self.assertEqual((code, out[-1]), (0, "PR_GATE_DONE result=PASS"))
        self.assertEqual(calls, [VIEW_CALL] * 2)

    def test_stops_on_conflict(self):
        fake_gh(self, pr_gate, json.dumps(view(mergeable="CONFLICTING")))

        code, out, _ = capture(pr_gate.main, ["31", "180"])

        self.assertEqual(
            (code, out[-1]), (1, "PR_GATE_DONE result=FAIL failed= mergeable=CONFLICTING")
        )

    def test_times_out_while_unknown(self):
        fake_gh(self, pr_gate, json.dumps(view(mergeable="UNKNOWN")))

        code, out, _ = capture(pr_gate.main, ["31", "0"])

        self.assertEqual(
            (code, out[-1]),
            (1, "PR_GATE_DONE result=TIMEOUT PENDING anchors_absent= pending= mergeable=UNKNOWN"),
        )

    def test_waits_for_anchor_checks(self):
        fake_gh(
            self,
            pr_gate,
            json.dumps(view(run("check", None, "QUEUED"))),
            json.dumps(view(run("check"))),
        )

        code, out, _ = capture(pr_gate.main, ["31", "180", "check"])

        self.assertEqual((code, out[-1]), (0, "PR_GATE_DONE result=PASS"))

    def test_reports_api_error_after_three_failures(self):
        fake_gh(self, pr_gate, API_ERROR, API_ERROR, API_ERROR)

        code, out, _ = capture(pr_gate.main, ["31", "180"])

        self.assertEqual((code, out[-1]), (1, "PR_GATE_DONE result=API_ERROR"))

    def test_counts_only_consecutive_api_errors(self):
        unknown = json.dumps(view(mergeable="UNKNOWN"))
        passed = json.dumps(view())
        fake_gh(self, pr_gate, API_ERROR, API_ERROR, unknown, API_ERROR, API_ERROR, passed)

        code, _, _ = capture(pr_gate.main, ["31", "180"])

        self.assertEqual(code, 0)

    # 판정 입력이 이상하면 TIMEOUT까지 기다리지 않고 바로 ERROR로 끝난다 (fail-closed)
    def test_fails_closed_on_malformed_output(self):
        for response in ["", "not json", "[]", json.dumps({"statusCheckRollup": []})]:
            with self.subTest(response=response):
                fake_gh(self, pr_gate, response)

                code, out, _ = capture(pr_gate.main, ["31", "180"])

                self.assertEqual((code, out[-1]), (1, "PR_GATE_DONE result=ERROR"))

    def test_fails_closed_without_gh(self):
        fake_gh(self, pr_gate, FileNotFoundError("gh"))

        code, out, _ = capture(pr_gate.main, ["31", "180"])

        self.assertEqual((code, out[-1]), (1, "PR_GATE_DONE result=ERROR"))

    def test_rejects_bad_arguments(self):
        for argv in (["31"], ["31", "ten"]):
            with self.subTest(argv=argv):
                code, _, err = capture(pr_gate.main, argv)

                self.assertEqual(code, 2)
                self.assertIn("usage", err)
