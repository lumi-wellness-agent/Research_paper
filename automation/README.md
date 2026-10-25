# ship 준비

ship은 자료 작업을 끝낸 변경(PDF·엑셀·README·스크립트)을 점검하고 이슈 → `chore/#N` 브랜치 → PR →
`main` 머지까지 올리는 자동화입니다. 이 문서는 ship을 처음 쓰는 PC에서 한 번 해 둘 준비를 정리합니다.
절차는 LLM 하네스가 읽는 명세 [`ship.md`](ship.md)·[`pipeline.md`](pipeline.md)에 있고, 하네스별 진입점은
Claude Code [`.claude/commands/ship.md`](../.claude/commands/ship.md), Codex
[`.agents/skills/ship/SKILL.md`](../.agents/skills/ship/SKILL.md)입니다.

## 1. 공통

| 도구 | macOS · Linux · WSL | Windows (PowerShell) |
| --- | --- | --- |
| git | 대부분 기본 설치 | `winget install Git.Git` |
| GitHub CLI | `brew install gh` · [Linux 설치 안내](https://github.com/cli/cli/blob/trunk/docs/install_linux.md) | `winget install GitHub.cli` |
| Python 3.9 이상 | macOS는 git과 함께 설치되는 `python3`(Xcode Command Line Tools)로 충분 · `sudo apt install python3` | `winget install Python.Python.3.12` (BE 준비 때 설치했으면 그대로 씁니다) |
| jq (훅용) | `jq --version`으로 확인, 없으면 `brew install jq` · `sudo apt install jq` | Codex는 필요 없음 · Claude Code는 `winget install jqlang.jq` |

WSL에서는 WSL 안에 설치한 git·gh·Python을 씁니다. Windows 쪽 설치·로그인과는 별개입니다. 게이트·폴링
스크립트는 표준 라이브러리만 쓰므로 가상환경이나 패키지 설치는 필요 없습니다. Windows에서는 명령의
`python3`를 `py`로 바꿔 씁니다(`py`가 없으면 `python`).

1. **GitHub 로그인**: `gh auth login`을 실행해 GitHub.com → HTTPS를 고르고, "Authenticate Git with your
   GitHub credentials?"에 Yes로 답합니다. 그래야 ship의 `git push`가 통과합니다. `gh auth status`로 확인합니다.
2. **커밋 작성자**: `git config --global user.name "이름"`, `git config --global user.email "GitHub 계정 이메일"`
3. **레포 권한**: ship이 브랜치 push·이슈 생성·PR 머지를 하므로 이 레포에 write 권한이 있어야 합니다.
4. **점검 스크립트 확인**: 레포 루트에서 아래를 실행해 마지막 줄에 `FILE_GATE result=PASS`가 나오면 됩니다.
   작업 중인 변경이 있으면 `WARN`·`BLOCKED`와 사유가 함께 나올 수 있습니다.

   ```bash
   # macOS · Linux · WSL
   python3 automation/bin/file_gate.py
   ```

   ```powershell
   # Windows (PowerShell)
   py automation/bin/file_gate.py
   ```

## 2. Claude Code로 쓸 때

- 레포를 처음 열 때 폴더를 신뢰하면 `.claude/settings.json`의 민감 파일 차단 훅이 함께 적용됩니다.
  훅은 bash·jq로 돌아서 jq가 있어야 합니다.
- Windows 네이티브 Claude Code는 Git for Windows(Git Bash)가 있어야 합니다.
- 자료 작업을 끝내고 **엑셀·워드를 저장하고 닫은 뒤** `/ship`으로 부릅니다. `/ship chore 미확보 논문 2편 추가`처럼
  타입과 설명을 주면 확인 단계를 건너뜁니다.

## 3. Codex로 쓸 때

Codex에는 사용자 정의 슬래시 커맨드가 없어 `/ship`은 동작하지 않습니다. 레포 루트에서 Codex를 띄우고
`$ship`으로 부릅니다.

1. **네트워크 열기**: 사용자 설정 파일(macOS·Linux·WSL은 `~/.codex/config.toml`, Windows는
   `%USERPROFILE%\.codex\config.toml`)에 아래를 넣습니다. 이미 `[sandbox_workspace_write]`가 있으면 그 아래에
   키만 추가합니다. ship은 PR 머지 가능 여부를 기다리는 동안 `gh`를 계속 부르므로, 이게 없으면 대기 단계가
   바로 `result=API_ERROR`로 끝납니다.

   ```toml
   [sandbox_workspace_write]
   network_access = true
   ```

2. **`.git` 쓰기 열기**: `.codex/config.toml.example`을 `.codex/config.toml`로 복사하고(PowerShell은
   `Copy-Item`), `writable_roots`를 이 체크아웃의 `.git` 절대경로로 바꿉니다. 경로는 레포 루트에서 `pwd`
   (PowerShell은 `(Get-Location).Path`)로 확인합니다. 이게 없으면 ship의 커밋·브랜치 전환·pull이 샌드박스에
   막힙니다. 이 파일은 머신마다 달라 커밋하지 않습니다(`.gitignore` 대상).

   ```toml
   # macOS · Linux · WSL
   writable_roots = ["/절대/경로/Research_paper/.git"]
   # Windows — 작은따옴표로 씁니다. 큰따옴표면 백슬래시를 \\로 적어야 합니다.
   writable_roots = ['C:\Users\<사용자>\…\Research_paper\.git']
   ```

3. **처음 실행**: 레포 루트에서 `codex`를 띄우면 프로젝트를 신뢰할지 묻습니다. 신뢰해야 `.codex/`의 설정과
   훅을 읽습니다.
   - macOS · Linux · WSL: 시작할 때 "hooks need review"가 보이면 `/hooks`에서 `validate-git-sensitive.sh`
     훅을 승인합니다.
   - Windows: 훅을 **승인하지 않습니다.** bash 스크립트라 PowerShell에서 돌지 않습니다. 민감 파일은 ship 안의
     게이트(`automation/bin/sensitive_gate.py`)가 검사합니다.
4. **확인**: `$`를 입력했을 때 목록에 `ship`이 보이면 준비가 끝났습니다. `source-command-ship`이 보이면
   고르지 않습니다. Codex가 `.claude/commands/ship.md`를 변환해 만든 사본이라 경로가 깨져 있습니다.

Codex 데스크톱 앱에서 에이전트를 WSL로 돌리면(앱 설정에서 전환 후 재시작) macOS · Linux · WSL 기준을 따릅니다.

## 4. 처음 한 번 시험하기

README 오타 수정 같은 작은 문서 변경을 만들고 `$ship docs <설명>`(Claude Code는 `/ship docs <설명>`)으로
끝까지 올려 봅니다. 실제로 이슈·PR이 만들어지고 `main`에 머지되므로 의미 있는 변경으로 합니다.

- 이 레포는 CI가 없어 PR을 기다리는 단계가 보통 1분 안에 끝납니다(GitHub가 머지 가능 여부를 계산하는
  시간). 최대 3분까지 응답 없이 기다리는 것은 정상입니다. 중간에 끊지 않습니다.
- Codex가 명령 승인을 물으면 내용을 확인하고 승인합니다.
- 이 문서대로 했는데 동작이 다르면, 확인한 내용으로 이 파일을 고쳐 둡니다.

## 막힐 때

| 증상 | 원인과 해결 |
| --- | --- |
| 시작하자마자 `gh auth status` 실패로 멈춤 | gh에 로그인하지 않았습니다 → `gh auth login` |
| `FILE_GATE result=BLOCKED`와 "열려 있는 Office 문서" | 그 엑셀·워드가 열려 있습니다 → 저장하고 닫은 뒤 다시 부릅니다 |
| `FILE_GATE result=BLOCKED`와 "내용이 같은 PDF가 있다" | 레포에 이미 있는 PDF를 다른 이름·폴더로 또 넣었습니다 → 새 사본을 지웁니다 |
| 커밋·브랜치 전환에서 `.git` 쓰기 거부 (Codex) | 3-2의 `writable_roots`가 없거나 경로가 다릅니다 |
| PR 대기가 바로 `result=API_ERROR`로 끝남 | Codex는 3-1의 `network_access`를, 그 밖에는 gh 인증·네트워크를 확인합니다 |
| `result=ERROR`와 "gh를 찾을 수 없다" | gh가 설치되지 않았거나 PATH에 없습니다 |
| `python3`가 Microsoft Store를 열거나 "Python was not found" (Windows) | `python3` 대신 `py`로 부릅니다. `py`도 없으면 1의 표대로 Python을 설치합니다 |
| clone·pull이 `Filename too long`으로 실패 (Windows) | 논문 PDF 파일명이 길어 Windows 경로 한도에 걸렸습니다 → `git config --global core.longpaths true` 후 다시 받습니다 |
| `$` 목록에 `ship`이 없음 (Codex) | 레포 밖에서 띄웠거나 프로젝트를 신뢰하지 않았습니다 |
| 훅이 `bash\r: No such file or directory`로 실패 (WSL·Git Bash) | Windows git으로 받아 CRLF가 된 사본입니다 → 파일을 지우고 `git checkout -- <파일>`로 다시 받습니다 |
