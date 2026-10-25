"""파일 게이트 — 반영 대상에 열린 Office 문서·용량 초과 파일·중복 PDF·쓰레기 파일이 없는지 검사한다.

자료 레포라 CI가 없으므로 이 게이트가 ship Phase 2의 기계 점검이다. 반영 대상은 스테이징 + 수정 +
untracked 파일이다(삭제는 대상이 아니다). 워킹 트리의 반영 후보 전체를 보므로 스테이징 전에 돌려도
된다.

BLOCKED (종료코드 1):
  - Office 잠금 파일 `~$…` 자체가 대상에 있음, 또는 대상 Office 문서(xlsx/xlsm/docx/pptx) 옆에 잠금
    파일이 있음 → 그 문서가 열려 있다는 신호다. 디스크 내용이 저장 전 상태일 수 있으니 저장·닫기 후
    재실행한다.
  - 100MB 이상 파일 — GitHub가 push를 거부한다.
  - 대상 PDF와 내용이 같은 PDF가 반영 뒤의 레포에 또 있음 — 같은 PDF는 한 번만 저장한다(하위 README
    「분류 방식」). 같은 논문의 다른 판본(이미지 PDF → 텍스트 PDF 등)은 내용이 달라 걸리지 않는다.
  - `.DS_Store`·`Thumbs.db`·`desktop.ini`·`*.tmp` — OS·앱이 만드는 쓰레기 파일(.gitignore 대상이라
    -f 없이는 들어오지 않는다).
WARN (종료코드 0): 50MB 이상 파일 — GitHub 경고 한도. 진행은 가능하고 보고에 남긴다.
게이트는 fail-closed다 — git 조회가 실패하면 통과가 아니라 ERROR로 종료한다.

표준 라이브러리와 git만 쓴다 — bash가 없는 Windows(PowerShell)에서도 같은 명령으로 돈다.

사용법: python3 automation/bin/file_gate.py  (Windows는 python3 대신 py)
종료 마커: FILE_GATE result=PASS|WARN|BLOCKED|ERROR
  ERROR = git 조회 실패·파일 읽기 실패·예상 못 한 예외 (fail-closed)
"""

import hashlib
import subprocess
import sys
import traceback
from pathlib import Path

MIB = 1024 * 1024
WARN_BYTES = 50 * MIB
BLOCK_BYTES = 100 * MIB
JUNK = frozenset({".ds_store", "thumbs.db", "desktop.ini"})
OFFICE = (".xlsx", ".xlsm", ".docx", ".pptx")


def git(cwd: Path, *args: str) -> str:
    # stderr는 가로채지 않는다 — git이 실패하면 원인이 그대로 보인다.
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def paths(root: Path, *args: str) -> set[str]:
    # -z로 받는다 — 기본 출력은 한글 경로를 "\353\271…"처럼 따옴표로 감싸 비교·집계를 빠져나간다.
    return {p for p in git(root, *args, "-z").split("\0") if p}


def collect() -> tuple[Path, set[str], set[str]]:
    """(레포 루트, 반영 대상, 추적·untracked 파일 전체)를 돌려준다. 경로는 모두 루트 기준이다."""
    # ls-files는 현재 디렉터리 기준 경로를 내므로 모든 조회를 루트에서 돌려 기준을 맞춘다.
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").rstrip("\n"))
    untracked = paths(root, "ls-files", "--others", "--exclude-standard")
    targets = (
        paths(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
        | paths(root, "diff", "--name-only", "--diff-filter=ACMR")
        | untracked
    )
    return root, targets, paths(root, "ls-files") | untracked


def sha256(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(MIB), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicates(root: Path, targets: set[str], files: set[str]) -> dict[str, str]:
    """대상 PDF마다 내용이 같은 다른 PDF 하나를 찾는다. 크기가 같은 파일끼리만 해시한다."""
    by_size: dict[int, list[str]] = {}
    for path in sorted(files):
        file = root / path
        # 워킹 트리에서 지운 추적 파일(옮긴 PDF의 원래 자리 등)은 반영 뒤 사라지므로 비교에서 뺀다
        if path.lower().endswith(".pdf") and file.is_file():
            by_size.setdefault(file.stat().st_size, []).append(path)
    found = {}
    for group in by_size.values():
        # 이번 변경과 상관없는 기존 중복은 막지 않는다
        if len(group) < 2 or targets.isdisjoint(group):
            continue
        by_hash: dict[str, list[str]] = {}
        for path in group:
            by_hash.setdefault(sha256(root / path), []).append(path)
        for same in by_hash.values():
            for path in same:
                if len(same) > 1 and path in targets:
                    found[path] = next(other for other in same if other != path)
    return found


def judge(root: Path, targets: set[str], files: set[str]) -> tuple[list[str], list[str]]:
    """반영 대상을 판정해 (차단 사유, 경고 사유) 목록을 돌려준다.

    사유 문구에는 cp949에 있는 문자만 쓴다 — 한국어 Windows에서 리다이렉트한 출력은 cp949로 나가서,
    없는 문자(— 등)는 '?'로 찍힌다.
    """
    blocked, warned = [], []
    for path in sorted(targets):
        file = root / path
        name = file.name.lower()
        if name.startswith("~$"):
            blocked.append(f"{path}: Office 잠금 파일 (문서가 열려 있다)")
        elif name in JUNK or name.endswith(".tmp"):
            blocked.append(f"{path}: 쓰레기 파일")
        elif name.endswith(OFFICE) and any(
            # 잠금 파일은 앱·이름 길이에 따라 `~$<이름>`이거나 앞 한두 글자를 `~$`로 바꾼 이름이다
            file.with_name("~$" + file.name[cut:]).exists()
            for cut in (0, 1, 2)
        ):
            blocked.append(f"{path}: 열려 있는 Office 문서 (잠금 파일 존재). 저장·닫기 후 재실행")
        elif file.is_file():
            size = file.stat().st_size
            if size >= BLOCK_BYTES:
                blocked.append(
                    f"{path}: {size // MIB}MB "
                    f"({BLOCK_BYTES // MIB}MB 이상은 GitHub가 push를 거부한다)"
                )
            elif size >= WARN_BYTES:
                warned.append(
                    f"{path}: {size // MIB}MB ({WARN_BYTES // MIB}MB 이상은 GitHub가 경고한다)"
                )
    for path, same in duplicates(root, targets, files).items():
        blocked.append(f"{path}: 내용이 같은 PDF가 있다 ({same}). 같은 PDF는 한 번만 저장한다")
    return blocked, warned


def main() -> int:
    try:
        root, targets, files = collect()
    except (OSError, subprocess.CalledProcessError):
        print("FILE_GATE result=ERROR")
        return 1
    blocked, warned = judge(root, targets, files)
    for title, lines in (("차단된 파일:", blocked), ("용량 경고:", warned)):
        if lines:
            print(title)
            for line in lines:
                print(f"  {line}")
    if blocked:
        print("FILE_GATE result=BLOCKED")
        return 1
    print(f"FILE_GATE result={'WARN' if warned else 'PASS'}")
    return 0


if __name__ == "__main__":
    # 콘솔 코드 페이지에 없는 문자(경로)에서 죽지 않는다.
    sys.stdout.reconfigure(line_buffering=True, errors="replace")
    try:
        sys.exit(main())
    except Exception:
        # 파일 읽기 실패·예상 못 한 예외도 마커 없이 끝나지 않는다 (fail-closed).
        traceback.print_exc()
        print("FILE_GATE result=ERROR")
        sys.exit(1)
