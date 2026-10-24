# pipeline — 반영 파이프라인 (하네스 중립 명세)

이슈 브랜치의 변경을 커밋 → `main` PR → mergeable 확인 → merge commit 머지 → 정리까지 자동화한다. `ship`의 Phase 4에서 사용한다.
브랜치명에 `#`이 포함되므로 모든 git/gh 명령에서 브랜치명은 따옴표로 감싼다. 경로를 다루는 git 명령에는 `-c core.quotepath=false`를 붙인다.

> **이 파일은 하네스 중립 「진실의 원천」이다.** 진입 어댑터(`ship`)를 통해 실행되며, 어댑터가 「폴링 실행 규칙」의 모드와 아래 하네스별 값을 지정한다:
>
> | 하네스 | 커밋 Co-Author 트레일러 (Step 1-1 커밋 메시지 끝 한 줄) | PR 본문 서명 (Step 1-4 본문 끝) |
> |--------|---------------------------------------------------------|---------------------------------|
> | Claude Code | 세션 시스템 규칙이 지정하는 `Co-Authored-By:` 트레일러 | `🤖 Generated with [Claude Code](https://claude.com/claude-code)` |
> | Codex | `Co-Authored-By: Codex <noreply@openai.com>` | 없음 |

**실행 주체**: 전 과정(Step 1~2)을 하나의 실행 흐름이 직접 수행한다. 폴링을 서브에이전트에 위임하면 완료 후 재개가 안 돼 대기 지점에서 멈춘다.
- **Claude Code**: 메인 세션이 직접 수행하고 서브에이전트에 위임하지 않는다. 메인 세션의 `run_in_background` Bash는 완료 시 세션을 확실히 재호출한다.
- **Codex**: 단일 호출 흐름에서 순차 수행한다. 서브에이전트(`spawn_agent`)에 폴링을 맡기지 않는다.

## 폴링 실행 규칙

PR 머지 가능 대기는 `automation/bin/pr-gate.sh`로 실행한다 — 루프를 즉석에서 작성하지 않는다. 이 레포는 CI가 없어 보통 1분 안에 끝나지만(GitHub가 `mergeable`을 계산하는 몇 초), 규약은 다른 레포와 같다. 스크립트의 *실행 모드*는 진입 어댑터가 지정한 **하네스별 폴링 모드**를 따른다:

| 하네스 | 폴링 모드 |
|--------|-----------|
| **Claude Code** | 스크립트를 **`run_in_background: true` Bash**로 실행. 포그라운드 `sleep` 차단·Monitor 도구 금지. 스크립트 완료 시 세션이 자동 재호출된다. |
| **Codex** | 스크립트를 포그라운드 **블로킹** 호출로 완료까지 대기. 출력은 파일로 리다이렉트(`> "$LOG" 2>&1`)하고, **셸 명령 타임아웃을 스크립트 내부 타임아웃보다 넉넉히** 둔다(게이트 3분 → 셸 5분+). 샌드박스에 네트워크가 열려 있어야 한다(어댑터 참조). |

- 스크립트는 성공·실패·타임아웃 **모든 종료 상태에서 exit**하고, 종료 직전 결과 마커 1줄(`... result=...`)을 출력한다. 출력의 마커·종료코드로 분기한다. 게이트 정의·간격·타임아웃·마커 규약은 **스크립트 상단 주석이 원천**이다.
- GitHub 조회 실패는 pending으로 삼키지 않는다 — 3회 연속 실패 시 `result=API_ERROR` 마커로 종료된다(스크립트에 구현됨). `API_ERROR`는 `TIMEOUT`과 구분해 실제 stderr를 요약하고 중단한다. 하네스의 네트워크 권한·DNS·인증 상태를 함께 확인한다.
- `result=ERROR`는 jq 부재·판정 출력 이상 등 **실행 환경 문제**다(fail-closed) — 통과로 취급하지 않고 환경을 확인해 보고 후 중단한다.
- **알림이 애매하거나 오래 소식이 없으면 추측·무한 대기 말고 즉시 `gh pr view`로 실제 상태를 확인**한 뒤 분기한다.

## 제목·머지 규범 (팀 관행)

| 대상 | 형식 | 예 |
|------|------|----|
| 커밋 제목 (Step 1-1) | `<type>: <영문 명령형 요약>` | `docs: add six previously missing papers (E20, N11, N13, N19, N22, N25)` |
| PR 제목 (Step 1-4) | `[<타입>/#<이슈번호>] <한국어 설명>` | `[chore/#15] 미확보 논문 6편 추가 및 N15 출판본으로 교체` |
| 머지 커밋 (Step 1-5) | GitHub 기본값 `Merge pull request #<PR> from lumi-wellness-agent/<브랜치>` (본문 = PR 제목) | `Merge pull request #16 from lumi-wellness-agent/chore/#15` |

- **머지는 `--merge`(merge commit)다.** 기존 12건의 PR이 모두 이 방식이라 `main` 이력이 「머지 커밋 + 작업 커밋들」로 읽힌다. CI가 없어 squash로 런 제목을 맞출 이유가 없고, 바이너리 교체 이력은 커밋 단위로 남는 쪽이 추적에 유리하다. `--squash`·`--rebase`로 바꾸지 않는다. 제목·본문은 기본값을 쓴다(`--subject`·`--body` 생략).
- 저장소는 세 방식을 모두 허용한다 — 이 규범을 지키는 장치는 이 문서뿐이므로 명령을 그대로 따른다.

## Step 1: 커밋 & PR & 머지 (main)

1. `git -c core.quotepath=false status --short`를 확인해 커밋 안 된 변경이 있으면 `git add -A` → **민감 파일 게이트 통과 후** 커밋한다. 제목은 「제목·머지 규범」의 커밋 제목, 본문은 파일 단위 변경을 `-` 불릿(한국어 가능)으로, 끝에 **현재 하네스의 Co-Author 트레일러** 한 줄. 변경이 성격이 다른 두 묶음(예: PDF 교체 + README 갱신)이면 커밋을 둘로 나눠도 된다 — merge commit이라 `main`에 그대로 남는다. 게이트는 반드시 스테이징 **후**에 돌린다 — add 이전 검사로는 untracked였던 민감 파일이 잡히지 않는다:
   - 게이트: `automation/bin/sensitive-gate.sh` 실행. `SENSITIVE_GATE result=PASS` → 커밋 진행. `result=BLOCKED`(종료코드 1) → 출력된 파일을 `git reset HEAD <파일>`로 해제하고 보고 후 중단. `result=ERROR` → git 조회 실패(fail-closed) — 통과로 취급하지 않고 보고 후 중단.
   - `~$*` Office 잠금 파일·`.DS_Store`는 `.gitignore`가 막는다 — `git add -f`를 쓰지 않는다.
2. `git pull origin main --rebase` — 충돌 시 `git rebase --abort` 후 보고하고 중단. (ship Preflight에서 이미 rebase했으므로 보통 no-op이다.)
3. `git push --force-with-lease -u origin "<브랜치명>"`
4. PR 확보 — **기존 PR 확인부터** (재시작 시 같은 브랜치에 열린 PR이 이미 있다):
   - `gh pr list --head "<브랜치명>" --base main --state open --json number --jq '.[0].number // empty'` — 번호가 나오면 **생성을 스킵**하고 그 번호를 `<PR번호>`로 재사용한다.
   - 없으면 `gh pr create --base main --head "<브랜치명>" --title "[<타입>/#<이슈번호>] <설명>" --body "<본문>"`. PR 템플릿이 없으므로 본문은 기존 PR(#26·#28)과 같은 형식으로 쓴다:
     ```
     ## 변경 내용
     - <파일 단위 변경 1 — 추가/교체/삭제와 이유>
     - <파일 단위 변경 2>
     - <용량 경고가 있으면: `<파일>` NN MB (GitHub 경고 한도 50MB 초과)>

     Closes #<이슈번호>

     <현재 하네스의 PR 본문 서명 — 있으면>
     ```
     **라벨·담당자를 붙이지 않는다.** 출력 URL 끝 숫자가 `<PR번호>`.
5. 머지 가능 폴링: **`automation/bin/pr-gate.sh <PR번호> 180`** (앵커 없음 — CI 없는 레포 모드, 30초 간격, 최대 3분) → `PR_GATE_DONE` 마커. **게이트 = `mergeable` MERGEABLE + (체크가 있다면) 전부 성공** — 판정 로직은 `automation/bin/pr-gate.jq`가 원천이다. 워크플로우가 생기면 앵커(잡 이름)를 넘기는 쪽으로 이 줄을 고친다.
   - `result=PASS` → `gh pr merge <PR번호> --merge`. **`--merge`를 `--squash`로 바꾸지 않는다** (「제목·머지 규범」). `--auto`·`--admin`은 쓰지 않는다.
   - `result=FAIL* mergeable=CONFLICTING` → `main`이 이 브랜치와 충돌한다(보통 같은 xlsx를 양쪽에서 고친 경우). 바이너리 충돌은 git이 합칠 수 없다 — 어느 쪽을 살릴지 사용자에게 묻고 중단한다 (「실패 시 재시작 규칙」).
   - `TIMEOUT`·`API_ERROR`·`ERROR` → 각각 요약해 중단 (「폴링 실행 규칙」의 구분 참조).
6. `MERGE_SHA=$(gh pr view <PR번호> --json mergeCommit --jq '.mergeCommit.oid')`
7. `git checkout main && git pull origin main`
   - `main`이 기본 브랜치이므로 PR 본문의 `Closes #<이슈번호>`가 머지 시 이슈를 **자동으로 닫는다**. 따로 닫지 않는다.

## Step 2: 정리 & 보고

각 명령이 실패해도 **중단하지 않고 계속 진행**한다(실패 내역만 기록):
1. `git branch -D "<브랜치명>"`
2. `git push origin --delete "<브랜치명>"` — 머지 시 자동 삭제 설정이 꺼져 있어 실제로 지워진다. (ship 도입 전 머지된 `chore/#1`~`chore/#27` 원격 브랜치는 그대로 남아 있다 — 이 파이프라인은 자기 브랜치만 지운다.)
3. 최종 보고:
   - 머지 커밋(`MERGE_SHA`), 닫힌 이슈 번호, 파일 단위 변경 요약
   - 용량 경고(있으면), 정리 실패 내역(있으면). 머지 성공 + 정리 실패는 파이프라인 실패로 취급하지 않는다.
   - 하위 README 「현재 상태」 수치(마스터 목록·원문 확보·미확보)가 바뀌었으면 새 값을 적는다 — 이 레포의 "배포"는 `main` 반영이다.

## 실패 시 재시작 규칙

이슈 브랜치와 PR은 재사용한다 — 수정 커밋을 **같은 브랜치에 push**하면 같은 PR이 업데이트된다.

| 실패 시점 | 원인 | 재시작 |
|-----------|------|--------|
| Step 1-1 | 민감 파일 게이트 BLOCKED | 파일 해제 → **Step 1** |
| Step 1-5 | PR 충돌(`CONFLICTING`) | 사용자가 살릴 쪽을 정하면 `git pull origin main --rebase`로 해결(바이너리는 `git checkout --ours/--theirs`) → **Step 1** |
| Step 1-5 | TIMEOUT (mergeable 계산 지연) | `gh pr view <PR번호> --json mergeable`로 직접 확인 → MERGEABLE이면 **Step 1-5의 머지부터** |

## 민감 파일 커밋 금지

`git add/commit/push` 대상에 아래 민감 파일이 포함되지 않도록 커밋 전 확인한다 (기본 이름 및 `<이름>.*` 확장 변형 포함). 기계적 검사는 Step 1의 **`automation/bin/sensitive-gate.sh`**(스테이징 후 `git diff --cached` 검사)가 수행한다 — **스크립트의 정규식이 패턴의 단일 원천**이고, 아래 목록과 훅(`automation/hooks/validate-git-sensitive.sh`)의 배열은 사람용 요약/이중 방어다(불일치하면 스크립트가 우선). 패턴 변경은 스크립트에서 하고 훅을 같이 갱신한다:

- `.env` (및 `.env.*` — `.env.example` 제외) — 논문 수집 스크립트가 API 키를 쓰게 되면 여기로 온다
- `.claude/settings.local.json` (Claude Code 개인 권한 설정)
- `.mcp.json` (로컬 IDE MCP 연결 — 개인 환경 전용)
- `*.pem`, `*.p12`, `*.p8`, `*.key`
- `firebase-adminsdk*.json`
- `id_rsa*`

발견 시 커밋하지 말고 사용자에게 보고한다 — 스테이징돼 있으면 `git reset HEAD <file>`로 해제하고, 이미 커밋에 포함됐으면 해당 커밋을 정리한 뒤 재시도한다.

> **하네스별 적용**: 모든 하네스가 Step 1에서 `sensitive-gate.sh`를 실행한다. 훅을 지원하는 하네스(Claude Code `.claude/settings.json`, Codex `.codex/hooks.json`)는 같은 스크립트 `automation/hooks/validate-git-sensitive.sh`가 PreToolUse에서 `git add/commit/push`를 추가로 자동 차단한다(이중 방어). Codex 훅은 프로젝트 신뢰 + `/hooks` 승인 뒤에만 동작하므로, 승인 전에는 규칙을 직접 준수한다. 이 레포에는 CI(gitleaks)가 없으므로 `.gitignore` + GitHub push protection만 병행된다.

## 규칙

- 모든 `gh`/`git` 실패 시 에러 내용을 사용자에게 보고한다.
- PR 본문은 「변경 내용 + Closes」 형식을 지키고, **라벨·담당자는 부여하지 않는다**.
- **머지는 항상 `--merge`다** — `--squash`·`--rebase`로 바꾸지 않는다. 이유는 「제목·머지 규범」 참조.
- **PR 없이 `main`에 직접 push하지 않는다.** 보호가 없어 서버가 막지 않으므로 이 규칙이 유일한 관문이다.
- **실패 시 재시작 규칙을 반드시 따른다.**
- **「민감 파일 커밋 금지」 규칙을 준수한다.**
