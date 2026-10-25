---
name: ship
description: Research_paper(LUMI 논문·자료 레포)의 워킹 트리 변경(PDF·엑셀·README)을 점검(file_gate)하고 이슈 생성 → chore/#<이슈> 브랜치 → main PR → mergeable 확인 → merge commit 머지까지 자동화한다 (하네스 중립 워크플로우 automation/ship.md의 Codex 어댑터). 사용자가 "ship", "$ship", "반영해줘", "PR 올려서 머지까지 해줘" 등 자료 작업이 끝난 변경을 main에 올리라고 하면 사용한다. 논문 수집·엑셀 편집 등 자료 작업 자체에는 쓰지 않는다. Codex에는 사용자 정의 슬래시 커맨드가 없어 "/ship"은 동작하지 않는다 — $ship 멘션이나 평문으로 부른다.
---

# ship (Codex 어댑터)

하네스 중립 반영 워크플로우의 **Codex 진입점**이다. 절차 원본은 리포의 `automation/ship.md`(+ `automation/pipeline.md`)에 있다. 그 파일들을 읽고 그대로 실행하되, 아래 Codex 전용 오버라이드를 적용한다.

## 실행 절차

1. `automation/ship.md`를 읽고 Preflight → Phase 1~4를 순서대로 수행한다. Phase 4에서 `automation/pipeline.md`를 읽어 반영한다.
2. 사용자 인자(타입+설명, 예: `$ship chore 미확보 논문 2편 추가`)는 `automation/ship.md`의 Phase 1 규칙대로 처리한다.
3. 전 과정을 이 세션이 직접 순차 수행한다 — 서브에이전트(`spawn_agent`)에 폴링을 위임하지 않는다.
4. 경로를 세거나 grep하는 git 명령에는 `-c core.quotepath=false`를 붙인다 — 한국어 경로가 많다.
5. Windows 네이티브(PowerShell)에서 돌고 있으면 아래 「Windows 네이티브」를 함께 적용한다.

## Codex Co-Author 트레일러 · PR 서명 (`automation/pipeline.md` 하네스별 값)

- 커밋 메시지 끝: **`Co-Authored-By: Codex <noreply@openai.com>`** (다른 하네스의 트레일러를 쓰지 않는다)
- PR 본문 서명: **없음**

## Codex 폴링 모드 (`automation/pipeline.md` 「폴링 실행 규칙」의 Codex 모드)

- 배경 재호출 프리미티브가 없으므로 PR 머지 가능 폴링(`automation/bin/pr_gate.py`)은 `python3`로 **포그라운드 블로킹 호출**로 **한 번의 셸 호출**로 완료까지 실행한다 — 스크립트가 종료 마커를 출력하고 반환할 때까지 그 호출이 블로킹된다.
- 스크립트 출력은 파일로 리다이렉트(`> "$LOG" 2>&1`)하고 마커를 `tail`로 읽는다. **셸 명령 타임아웃은 스크립트 내부 타임아웃보다 넉넉히** 설정한다 (게이트 3분 → 셸 5분+).
- 폴링 스크립트는 `gh`를 반복 호출하므로 **샌드박스에 네트워크가 열려 있어야 한다** — `~/.codex/config.toml`(Windows는 `%USERPROFILE%\.codex\config.toml`)의 `[sandbox_workspace_write] network_access = true`. 닫혀 있으면 첫 호출이 `result=API_ERROR`로 끝난다: 이를 GitHub 장애로 추측하거나 `TIMEOUT`으로 바꾸지 말고, 설정을 안내하고 중단한다 (`approval_policy = "never"`에서는 승인 상승을 요청할 수 없다).

## `.git` 쓰기 (workspace-write 샌드박스)

workspace-write 샌드박스는 `.git/` 쓰기를 기본 차단해 커밋·체크아웃·pull이 막힌다(원격은 정상인데 로컬 `main`만 뒤처진다). 프로젝트 로컬 설정 `.codex/config.toml`의 `writable_roots`에 **이 체크아웃의 `.git` 절대경로**가 있어야 한다 — 파일이 없으면 `.codex/config.toml.example`을 복사해 경로를 맞춘다(머신마다 달라 `.gitignore` 대상). Windows 경로는 작은따옴표 TOML 리터럴로 적는다 — `writable_roots = ['C:\Users\<사용자>\…\Research_paper\.git']`(큰따옴표면 백슬래시를 `\\`로 이스케이프해야 한다). `.git` 쓰기 거부 에러가 보이면 이 설정을 안내하고 중단한다.

## 안전 규칙 (훅 + 직접 준수)

- `.codex/hooks.json`의 PreToolUse(`Bash`) 훅이 `automation/hooks/validate-git-sensitive.sh`로 `git add/commit/push`의 민감 파일을 자동 차단한다 — Claude Code와 같은 스크립트, 이중 방어다. 단 **프로젝트를 신뢰하고 `/hooks`에서 훅을 승인한 뒤에만** 동작한다(시작 시 "hooks need review" 경고가 보이면 미승인 상태). 훅 스크립트는 bash·jq로 돌아 Windows 네이티브(PowerShell)에서는 실행되지 않으므로 Windows에서는 승인하지 않는다(「Windows 네이티브」).
- 훅이 승인되지 않았거나 동작을 확신할 수 없으면 `automation/pipeline.md` 「민감 파일 커밋 금지」 규칙을 **직접** 준수한다 (Step 1의 `sensitive_gate.py` 기계 검사와 병행): `git add/commit/push` 전에 대상에 `.env`(및 `.env.*`, `.env.example` 제외), `.claude/settings.local.json`, `.mcp.json`, `*.pem`·`*.p12`·`*.p8`·`*.key`, `firebase-adminsdk*.json`, `id_rsa*`가 없는지 확인하고, 있으면 커밋하지 말고 사용자에게 보고한다 (스테이징돼 있으면 `git reset HEAD <file>`).
- `git add -f`를 쓰지 않는다 — `~$*` Office 잠금 파일·`.DS_Store`·`Thumbs.db`는 `.gitignore`가 막고 있고, 뚫고 들어오면 `file_gate.py`가 차단한다.

## Windows 네이티브 (PowerShell)

Windows용 Codex는 명령을 PowerShell로 실행한다. WSL 없이 쓸 때는 `automation/ship.md` 「실행 환경」(인터프리터 `py`·PowerShell 문법)에 더해 아래를 따른다.

- 필요한 도구는 Windows용 git, gh(`gh auth login` 완료), Python 3.9 이상(`py` 런처)이다. bash·jq는 없어도 된다 — 없는 도구가 있으면 진행하지 말고 사용자에게 알린다.
- 게이트·폴링 스크립트는 같은 인자로 부른다: `py automation/bin/file_gate.py`, `py automation/bin/pr_gate.py <PR번호> 180`. 로그 마커는 `Get-Content $LOG -Tail 5`로 읽는다.
- 훅(`.codex/hooks.json`)은 승인하지 않는다 — bash 스크립트라 PowerShell에서 실행되지 않는다. 민감 파일은 `sensitive_gate.py`와 「안전 규칙」의 직접 준수로 지킨다.
- `.codex/config.toml`의 `writable_roots`는 Windows 경로로 적는다 (「`.git` 쓰기」).
