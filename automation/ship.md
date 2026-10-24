# ship — 자료 변경 반영 자동화 (하네스 중립 명세)

워킹 트리의 자료 변경(PDF·엑셀·README·스크립트)을 점검하고 이슈 → `chore/#N` 브랜치 → PR → `main` 머지까지 자동화한다.
변경 작업이 이미 완료된 상태에서 사용한다 — 논문 수집·엑셀 편집 등 자료 작업 자체는 수행하지 않는다.
브랜치명에 `#`이 포함되고(`chore/#27`) **경로에 한국어가 많다** — 모든 git/gh 명령에서 브랜치명은 따옴표로 감싸고, 경로를 세거나 grep할 때는 `git -c core.quotepath=false …`를 쓴다 (안 그러면 한국어 경로가 따옴표·이스케이프로 출력돼 `grep '\.pdf$'` 류 집계에서 조용히 빠진다).

> **이 파일은 하네스 중립 「진실의 원천」이다.** 직접 실행 대상이 아니라, 사용하는 LLM 하네스의 진입 어댑터를 통해 실행된다:
> - Claude Code → `.claude/commands/ship.md` (`/ship`)
> - Codex → `.agents/skills/ship/SKILL.md` (`$ship`)
>
> 각 어댑터는 **폴링 모드**, **Co-Author 트레일러**, **안전 규칙 적용 방식**(훅 유무)을 지정한다. Phase 4의 PR 폴링은 `automation/pipeline.md`의 「폴링 실행 규칙」에 정의된 **하네스별 모드**를 따른다.

## 워크플로우 전제 (Research_paper)

레포에 적혀 있지 않고 GitHub 이력(PR #2~#28)으로만 보이는 팀 관행을 그대로 따른다:

- **자료 레포다.** 코드가 없어 CI·테스트·빌드가 없다. 검증은 Phase 2의 **파일 게이트**(Office 잠금 파일·용량 한도·쓰레기 파일)와 사람의 눈이다.
- **이슈 → `chore/#N` 브랜치 → PR → merge commit.** 이슈 제목·본문은 한국어로 짧게(`## 배경`·`## 작업`), PR 제목은 `[chore/#N] 설명`, 본문은 `## 변경 내용` 불릿 + `Closes #N`. 머지는 **merge commit**(`--merge`)이다 — 기존 12건이 모두 `Merge pull request #N from lumi-wellness-agent/chore/#M` 형식이고, CI가 없어 squash로 런 제목을 맞출 이유도 없다.
- **`main`은 보호되지 않는다** (private 레포, Free 플랜은 브랜치 보호 불가). 서버 관문이 없으므로 "PR을 거치고 mergeable을 확인한 뒤 머지한다"는 이 명세가 지키는 규범이다.
- **라벨·담당자 자동화는 없다.** 레포에 타입 라벨이 없고 이슈 템플릿도 없다 — 붙이지 않는다.
- **큰 바이너리가 많다** (PDF 76편, xlsx). GitHub는 100MB 이상 파일의 push를 거부하고 50MB 이상에 경고한다. 같은 PDF는 한 번만 저장한다(하위 README 「분류 방식」) — 중복 바이너리를 다른 폴더에 복사해 넣지 않는다.
- **PDF 재배포 조건은 각 문서의 라이선스를 따른다.** 출판사 구독본을 공개 레포로 옮기지 않는다 — 이 레포는 private이다.

## Preflight

1. `gh auth status` — 인증 실패 시 **중단**.
2. `git fetch origin main` — 이후 모든 main 대비 비교는 **`origin/main` 기준**이다. 로컬 `main`은 뒤처져 있을 수 있으므로 비교 기준으로 쓰지 않는다.
3. 현재 브랜치 판별:
   - **이슈 브랜치** (`<타입>/#<번호>` 형식, 보통 `chore/#N`):
     - 브랜치명에서 타입과 이슈번호를 파싱한다. `gh issue view <번호> --json state,title`로 이슈가 열려 있는지 확인한다 — 없거나 닫혀 있으면 보고하고 **중단**.
     - `git log origin/main..HEAD --oneline`과 `git -c core.quotepath=false status --porcelain`으로 변경사항 확인 — 커밋도 변경도 없으면 **중단** ("반영할 변경사항이 없습니다"). 변경 유무 판정에 `git diff`(무인자)를 쓰지 않는다 — staged 변경이 보이지 않는다.
     - 최신 동기화: `git pull --rebase --autostash origin main` — **충돌 시 자동 해결하지 않는다**: rebase 충돌은 `git rebase --abort`로 원상복구 후 보고하고 중단, autostash 재적용 충돌은 변경이 stash에 보존된 상태이므로(`git stash list`로 확인) 그대로 두고 보고하고 중단한다. 바이너리(xlsx·PDF) 충돌은 git이 합칠 수 없으니 특히 사람이 정한다.
     - **Phase 3(이슈·브랜치 생성)을 스킵**한다.
   - **`main`**:
     - `git log origin/main..HEAD --oneline` — **push 안 된 로컬 커밋이 있으면 중단**하고 커밋 목록과 함께 보고한다. `main` 직접 커밋은 ship이 반영하지 않는다 — 사용자가 브랜치로 옮기는 등 직접 처리해야 한다.
     - `git -c core.quotepath=false status --porcelain` — 변경사항이 없으면 **중단**.
     - 최신 동기화: `git pull --rebase --autostash origin main` — 충돌 처리는 위와 동일(**자동 해결 금지**).
     - Phase 1로 진행한다. 이슈·브랜치는 Phase 3에서 만든다.

## Phase 1: 변경사항 분석

> 사용자가 인자로 타입과 설명을 직접 제공한 경우 (예: `/ship chore 미확보 논문 2편 추가`), 해당 값을 사용하고 사용자 확인 없이 Phase 2로 직행한다.

1. `git -c core.quotepath=false diff origin/main --stat`과 `git -c core.quotepath=false status --porcelain`(untracked 신규 파일 확인)으로 변경된 파일을 분석한다. 바이너리는 내용 diff가 없으니 **파일 단위**(추가·교체·삭제·이름 변경)로 요약하고, xlsx는 어느 시트·열이 바뀌었는지 사용자 설명이나 README 변경에서 읽는다. 무인자 `git diff`를 쓰지 않는다 — staged·커밋된 변경이 보이지 않는다.
2. 변경 성격에 맞는 타입을 결정한다 (기존 관행: 거의 전부 `chore`):

   | 타입 | 쓰는 경우 | 브랜치 | PR 제목 | 커밋 제목 |
   |------|-----------|--------|---------|-----------|
   | `chore` (기본) | 논문 PDF 추가·교체·정리, 엑셀 갱신, 스크립트·설정 | `chore/#N` | `[chore/#N] 설명` | `chore: …` 또는 `docs: …` |
   | `docs` | README·설명 문서만 바뀐 경우 | `docs/#N` | `[docs/#N] 설명` | `docs: …` |
   | `fix` | 잘못 들어간 자료·메타데이터 정정 | `fix/#N` | `[fix/#N] 설명` | `fix: …` |

   브랜치·PR 제목은 한국어 설명, 커밋 제목은 기존 이력(`docs: add six previously missing papers (E20, …)`)에 맞춰 **영문 소문자 명령형**으로 쓴다. 헷갈리면 `chore`다.
3. 변경 내용을 한 줄(한국어)로 요약한다 — 이슈·PR 제목에 그대로 쓰인다. 기존 제목(`미확보 논문 6편 추가 및 N15 출판본으로 교체`, `README 워크북 설명 중복 정리`)과 같은 문체(명사형 종결)로 쓴다.
4. **사용자 확인 대기**:
   ```
   변경사항 요약:
   - 타입: chore
   - 설명: ...
   - 변경 파일: N개 (추가 a · 교체 b · 삭제 c)
   - 용량 경고: 없음 | <파일> (NN MB)

   이대로 진행할까요? (타입이나 설명을 변경하려면 알려주세요)
   ```

## Phase 2: 점검

CI가 없으므로 로컬 점검이 전부다. 스크립트가 판정하고, 판정 조건은 **스크립트 상단 주석이 원천**이다(`smoke-test.sh`가 회귀 검증).

1. **파일 게이트**: `automation/bin/file-gate.sh` 실행 — 반영 대상(스테이징·수정·untracked) 파일을 본다 → `FILE_GATE` 마커.
   - `result=PASS` → 3으로.
   - `result=WARN` → 50MB 이상 파일이 있다. 진행은 가능하지만 사용자 확인 문구와 PR 본문에 남긴다.
   - `result=BLOCKED` → 보고하고 **중단**. 사유별 조치: Office 잠금 파일(`~$*.xlsx`)이 있으면 **그 엑셀이 열려 있다** — 저장·닫기 후 재실행. 100MB 이상 파일은 GitHub가 push를 거부한다 — 분할·압축·외부 링크로 바꾼다. `.DS_Store`·`*.tmp`는 삭제한다(이미 `.gitignore` 대상이라 `-f` 없이는 들어오지 않는다).
   - `result=ERROR` → git 조회 실패(fail-closed). 통과로 취급하지 않고 보고 후 중단.
2. **중복 바이너리 점검**: 추가된 PDF와 같은 내용(해시)의 파일이 이미 레포에 있으면 보고하고 중단한다 — `git -c core.quotepath=false ls-files -z '*.pdf' | xargs -0 shasum -a 256`과 신규 파일 해시를 비교한다. 같은 논문의 **다른 판본으로 교체**(이미지 PDF → 텍스트 PDF 등)는 교체이므로 해당하지 않는다.
3. **목록 정합성**: PDF를 추가·교체·삭제·개명했으면 마스터 목록(`LUMI_R_C_Research_2026-10-22/LUMI_R_C_논문목록_2026-10-22.xlsx`)·루트 `LUMI_RAW데이터 링크.xlsx`·하위 `README.md`의 「현재 상태」 수치가 같은 변경에 들어 있는지 확인한다. 빠져 있으면 **코드를 고치지 않고** 사용자에게 보고한다 — 자료 작업은 ship의 몫이 아니다.
4. `automation/`을 고친 변경이면 `automation/bin/smoke-test.sh`를 돌린다 (`SMOKE result=PASS`).
5. 실패·누락 시 → 사용자에게 보고하고 **중단**한다 (자동 수정하지 않는다).

## Phase 3: 이슈 & 브랜치

> Preflight에서 이슈 브랜치로 진입한 경우 이 Phase를 스킵한다.

1. **이슈 생성**: `gh issue create --title "<설명>" --body "<본문>"` — 제목은 Phase 1의 한국어 요약 그대로(접두사 없음 — 기존 이슈 #5~#27과 같은 형식). 본문은 짧게:
   ```
   ## 배경
   <왜 이 변경이 필요한지 1~2문장>

   ## 작업
   - <파일 단위 변경 1>
   - <파일 단위 변경 2>
   ```
   라벨·담당자는 붙이지 않는다. 출력 URL 끝 숫자가 `<이슈번호>`.
2. **브랜치 생성**: `git checkout -b "<타입>/#<이슈번호>"` (변경사항은 워킹 트리에 그대로 유지된다).

## Phase 4: 반영

`automation/pipeline.md`를 읽고 Step 1부터 실행한다.
PR 폴링은 `automation/pipeline.md`의 「폴링 실행 규칙」에 정의된 **현재 하네스의 폴링 모드**를 따른다 (진입 어댑터가 지정).

전달할 컨텍스트:
- 브랜치명, 타입, 이슈번호
- 변경사항 요약 (한국어 한 줄) + 파일 단위 변경 목록
- Phase 2 결과 (용량 경고 등 — PR 본문에 남긴다)

## 규칙

- Phase 1~3에서는 자료·문서를 수정하지 않는다 — 이미 완료된 변경을 점검하는 것이 목적이다.
- 점검 실패 시 (Phase 2) 자동 수정하지 않고 사용자에게 보고한다.
- Phase 4의 파이프라인 실패 처리는 `automation/pipeline.md`의 규칙을 따른다.
- 모든 `gh`/`git` 명령 실패 시 에러 내용을 사용자에게 보고한다.
- **라벨·담당자를 부여하지 않는다.**
- **민감 파일 커밋 금지**: `git add/commit/push`는 `automation/pipeline.md`의 「민감 파일 커밋 금지」 규칙을 따른다 (훅이 있는 하네스는 자동 차단이 추가되는 이중 방어).
