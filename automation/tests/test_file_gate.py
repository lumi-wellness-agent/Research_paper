"""파일 게이트(automation/bin/file_gate.py)를 스크래치 리포에서 실제로 실행해 확인한다.

열린 Office 문서·용량 한도·중복 PDF·쓰레기 파일 규칙과 fail-closed 성질을 본다. 용량 사례는
truncate로 크기만 늘린 파일을 써서 큰 내용을 실제로 쓰지 않는다.
"""

import unittest

from automation.tests.helpers import ScratchRepo

MIB = 1024 * 1024
OPEN = "열려 있는 Office 문서 (잠금 파일 존재). 저장·닫기 후 재실행"
WARN = "50MB (50MB 이상은 GitHub가 경고한다)"
BLOCK = "100MB (100MB 이상은 GitHub가 push를 거부한다)"
SAME = "같은 PDF는 한 번만 저장한다"


class LimitTest(unittest.TestCase):
    def test_passes_without_changes(self):
        repo = ScratchRepo(self)

        self.assertEqual(repo.run("file_gate.py"), (0, ["FILE_GATE result=PASS"]))

    def test_passes_small_file_with_korean_path(self):
        repo = ScratchRepo(self)
        repo.write("자료/하위/P99_한글 경로 논문.pdf", "논문\n")

        self.assertEqual(repo.run("file_gate.py"), (0, ["FILE_GATE result=PASS"]))

    def test_warns_at_github_warning_limit(self):
        repo = ScratchRepo(self)
        repo.sized("자료/큰파일.bin", 50 * MIB)

        self.assertEqual(
            repo.run("file_gate.py"),
            (0, ["용량 경고:", f"  자료/큰파일.bin: {WARN}", "FILE_GATE result=WARN"]),
        )

    def test_blocks_at_github_push_limit(self):
        repo = ScratchRepo(self)
        repo.sized("자료/너무큰파일.bin", 100 * MIB)

        self.assertEqual(
            repo.run("file_gate.py"),
            (1, ["차단된 파일:", f"  자료/너무큰파일.bin: {BLOCK}", "FILE_GATE result=BLOCKED"]),
        )

    # 막힐 때도 용량 경고를 함께 보여 준다 — 한 번에 고칠 수 있게
    def test_reports_warnings_with_blocked_files(self):
        repo = ScratchRepo(self)
        repo.sized("자료/큰파일.bin", 50 * MIB)
        repo.write("자료/Thumbs.db", "x")

        self.assertEqual(
            repo.run("file_gate.py"),
            (
                1,
                [
                    "차단된 파일:",
                    "  자료/Thumbs.db: 쓰레기 파일",
                    "용량 경고:",
                    f"  자료/큰파일.bin: {WARN}",
                    "FILE_GATE result=BLOCKED",
                ],
            ),
        )

    # ls-files는 현재 디렉터리 기준 경로를 낸다 — 루트 기준으로 맞추지 않으면 하위 폴더에서 돌 때
    # 큰 파일을 못 찾고 통과시킨다
    def test_same_result_from_subdirectory(self):
        repo = ScratchRepo(self)
        repo.sized("자료/너무큰파일.bin", 100 * MIB)

        code, out = repo.run("file_gate.py", cwd=repo.dir / "자료")

        self.assertEqual(code, 1)
        self.assertIn(f"  자료/너무큰파일.bin: {BLOCK}", out)

    # 한국어 Windows에서 리다이렉트한 출력은 cp949로 나간다 — 사유 문구에 cp949에 없는 문자가 있으면
    # '?'로 찍힌다
    def test_reasons_survive_cp949_output(self):
        repo = ScratchRepo(self)
        repo.sized("자료/큰파일.bin", 50 * MIB)
        repo.sized("자료/너무큰파일.bin", 100 * MIB)
        repo.write("자료/Thumbs.db", "x")
        repo.write("자료/목록.xlsx", "x")
        repo.write("자료/~$목록.xlsx", "lock")
        repo.write("a/P.pdf", "%PDF same")
        repo.write("b/P.pdf", "%PDF same")

        code, out = repo.run("file_gate.py", encoding="cp949")

        self.assertEqual((code, out[-1]), (1, "FILE_GATE result=BLOCKED"))
        self.assertEqual([line for line in out if "?" in line], [])

    def test_fails_closed_when_git_fails(self):
        repo = ScratchRepo(self)

        self.assertEqual(
            repo.run("file_gate.py", env={"GIT_DIR": str(repo.dir / "missing")}),
            (1, ["FILE_GATE result=ERROR"]),
        )


class JunkAndOfficeTest(unittest.TestCase):
    def test_blocks_junk_files(self):
        for path in [".DS_Store", "자료/Thumbs.db", "자료/desktop.ini", "자료/임시.tmp"]:
            with self.subTest(path=path):
                repo = ScratchRepo(self)
                repo.write(path, "x")

                self.assertEqual(
                    repo.run("file_gate.py"),
                    (1, ["차단된 파일:", f"  {path}: 쓰레기 파일", "FILE_GATE result=BLOCKED"]),
                )

    def test_blocks_office_lock_file(self):
        repo = ScratchRepo(self)
        repo.write("자료/목록.xlsx", "x")
        repo.write("자료/~$목록.xlsx", "lock")

        self.assertEqual(
            repo.run("file_gate.py"),
            (
                1,
                [
                    "차단된 파일:",
                    "  자료/~$목록.xlsx: Office 잠금 파일 (문서가 열려 있다)",
                    f"  자료/목록.xlsx: {OPEN}",
                    "FILE_GATE result=BLOCKED",
                ],
            ),
        )

    # 잠금 파일이 .gitignore로 빠져도 옆의 문서가 대상이면 열려 있는 문서로 막는다.
    # 잠금 파일 이름은 `~$<이름>`이거나 앞 한두 글자를 `~$`로 바꾼 형태다.
    def test_blocks_open_office_document(self):
        for document, lock in [
            ("자료/목록.xlsx", "자료/~$목록.xlsx"),
            ("자료/reports.docx", "자료/~$eports.docx"),
            ("자료/LUMI_R_C_논문목록_2026.xlsx", "자료/~$MI_R_C_논문목록_2026.xlsx"),
        ]:
            with self.subTest(document=document):
                repo = ScratchRepo(self)
                repo.write(".gitignore", "~$*\n")
                repo.write(document, "x")
                repo.write(lock, "lock")

                self.assertEqual(
                    repo.run("file_gate.py"),
                    (1, ["차단된 파일:", f"  {document}: {OPEN}", "FILE_GATE result=BLOCKED"]),
                )

    def test_passes_after_document_closed(self):
        repo = ScratchRepo(self)
        repo.write(".gitignore", "~$*\n")
        repo.write("자료/목록.xlsx", "x")
        lock = repo.write("자료/~$목록.xlsx", "lock")
        self.assertEqual(repo.run("file_gate.py")[0], 1)

        lock.unlink()

        self.assertEqual(repo.run("file_gate.py"), (0, ["FILE_GATE result=PASS"]))

    # 스테이징된 파일(diff --cached)과 수정된 추적 파일(diff)도 대상이다
    def test_inspects_staged_and_modified_files(self):
        repo = ScratchRepo(self)
        repo.write(".gitignore", ".DS_Store\n~$*\n")
        repo.write("목록.xlsx", "v1")
        repo.commit(".gitignore", "목록.xlsx")
        repo.stage(".DS_Store", "x")  # ignored라 untracked 목록에는 없고 스테이징으로만 보인다
        repo.write("목록.xlsx", "v2")
        repo.write("~$목록.xlsx", "lock")

        self.assertEqual(
            repo.run("file_gate.py"),
            (
                1,
                [
                    "차단된 파일:",
                    "  .DS_Store: 쓰레기 파일",
                    f"  목록.xlsx: {OPEN}",
                    "FILE_GATE result=BLOCKED",
                ],
            ),
        )


class DuplicatePdfTest(unittest.TestCase):
    def test_blocks_copy_of_tracked_pdf(self):
        repo = ScratchRepo(self)
        repo.write("원본/P01.pdf", "%PDF-1.7 같은 논문")
        repo.commit("원본/P01.pdf")
        repo.write("분류/R1/P01 사본.PDF", "%PDF-1.7 같은 논문")

        self.assertEqual(
            repo.run("file_gate.py"),
            (
                1,
                [
                    "차단된 파일:",
                    f"  분류/R1/P01 사본.PDF: 내용이 같은 PDF가 있다 (원본/P01.pdf). {SAME}",
                    "FILE_GATE result=BLOCKED",
                ],
            ),
        )

    def test_blocks_same_pdf_added_twice(self):
        repo = ScratchRepo(self)
        repo.write("a/P02.pdf", "%PDF same")
        repo.write("b/P02.pdf", "%PDF same")

        code, out = repo.run("file_gate.py")

        self.assertEqual(code, 1)
        self.assertIn(f"  a/P02.pdf: 내용이 같은 PDF가 있다 (b/P02.pdf). {SAME}", out)
        self.assertIn(f"  b/P02.pdf: 내용이 같은 PDF가 있다 (a/P02.pdf). {SAME}", out)

    # 옮긴 PDF(원래 자리는 지워짐), 같은 자리의 판본 교체, 크기만 같은 다른 PDF는 중복이 아니다
    def test_passes_moved_replaced_and_same_size_pdfs(self):
        repo = ScratchRepo(self)
        repo.write("P03.pdf", "%PDF v1")
        repo.write("P04.pdf", "%PDF aa")
        repo.commit("P03.pdf", "P04.pdf")
        (repo.dir / "옮김").mkdir()
        (repo.dir / "P03.pdf").rename(repo.dir / "옮김" / "P03.pdf")
        repo.write("P04.pdf", "%PDF bb")
        repo.write("새/P05.pdf", "%PDF cc")

        self.assertEqual(repo.run("file_gate.py"), (0, ["FILE_GATE result=PASS"]))

    # 이번 변경과 상관없는 기존 중복은 막지 않는다
    def test_ignores_existing_duplicates_outside_change(self):
        repo = ScratchRepo(self)
        repo.write("x/P06.pdf", "%PDF old")
        repo.write("y/P06.pdf", "%PDF old")
        repo.commit("x/P06.pdf", "y/P06.pdf")
        repo.write("README.md", "갱신\n")

        self.assertEqual(repo.run("file_gate.py"), (0, ["FILE_GATE result=PASS"]))
