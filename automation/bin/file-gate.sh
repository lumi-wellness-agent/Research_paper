#!/usr/bin/env bash
# 파일 게이트 — 반영 대상 파일(스테이징 + 수정 + untracked)에 Office 잠금 파일·GitHub 용량 한도 초과·OS 쓰레기
# 파일이 없는지 검사한다. 자료 레포라 CI가 없으므로 이 게이트가 ship Phase 2의 기계 점검이다.
# 스테이징 전에 돌려도 된다 — 워킹 트리의 반영 후보 전체를 본다 (삭제는 대상이 아니다).
#
# BLOCKED (종료코드 1):
#   - Office 잠금 파일 `~$…` 자체가 대상에 있음, 또는 대상 Office 문서(xlsx/xlsm/docx/pptx) 옆에 잠금 파일이 존재
#     → 그 문서가 열려 있다는 신호. 디스크 내용이 저장 전 상태일 수 있으니 저장·닫기 후 재실행한다.
#   - 100MB 이상 파일 — GitHub가 push를 거부한다
#   - `.DS_Store`, `*.tmp` — 쓰레기 파일 (.gitignore 대상이라 -f 없이는 들어오지 않는다)
# WARN (종료코드 0): 50MB 이상 파일 — GitHub 경고 한도. 진행은 가능, 보고에 남긴다.
# 게이트는 fail-closed다 — git 조회가 실패하면 통과가 아니라 ERROR로 종료한다.
# 한국어 경로가 많아 -z(NUL 구분)로 읽는다 — core.quotepath 이스케이프 문제를 피한다.
# 임계값은 테스트용으로 FILE_GATE_WARN_BYTES / FILE_GATE_BLOCK_BYTES 환경변수로 바꿀 수 있다.
# 종료 마커: FILE_GATE result=PASS|WARN|BLOCKED|ERROR
set -u
set -o pipefail

WARN_BYTES=${FILE_GATE_WARN_BYTES:-$((50 * 1024 * 1024))}
BLOCK_BYTES=${FILE_GATE_BLOCK_BYTES:-$((100 * 1024 * 1024))}

list_targets() {
  git diff --cached --name-only -z --diff-filter=ACMR \
    && git diff --name-only -z --diff-filter=ACMR \
    && git ls-files --others --exclude-standard -z
}
RAW=$(list_targets | tr '\0' '\n' | sort -u) \
  || { echo "FILE_GATE result=ERROR"; exit 1; }

BLOCKED=()
WARNED=()
while IFS= read -r f; do
  [ -n "$f" ] || continue
  base=$(basename "$f")
  dir=$(dirname "$f")
  case "$base" in
    '~$'*)            BLOCKED+=("$f — Office 잠금 파일 (문서가 열려 있다)"); continue ;;
    .DS_Store|*.tmp)  BLOCKED+=("$f — 쓰레기 파일"); continue ;;
  esac
  case "$base" in
    *.xlsx|*.xlsm|*.docx|*.pptx)
      # Excel·Word 잠금 파일: 이름이 짧으면 `~$<이름>`, 길면 앞 두 글자를 `~$`로 바꾼다 — 두 형태를 모두 본다
      if [ -e "$dir/~\$$base" ] || [ -e "$dir/~\$${base:2}" ]; then
        BLOCKED+=("$f — 열려 있는 Office 문서 (잠금 파일 존재). 저장·닫기 후 재실행")
        continue
      fi ;;
  esac
  if [ -f "$f" ]; then
    size=$(wc -c < "$f" | tr -d ' ')
    mb=$((size / 1024 / 1024))
    if [ "$size" -ge "$BLOCK_BYTES" ]; then
      BLOCKED+=("$f — ${mb}MB ≥ 100MB (GitHub가 push를 거부한다)")
    elif [ "$size" -ge "$WARN_BYTES" ]; then
      WARNED+=("$f — ${mb}MB ≥ 50MB (GitHub 경고 한도)")
    fi
  fi
done <<< "$RAW"

if [ ${#BLOCKED[@]} -gt 0 ]; then
  echo "차단된 파일:"
  printf '  %s\n' "${BLOCKED[@]}"
  echo "FILE_GATE result=BLOCKED"
  exit 1
fi
if [ ${#WARNED[@]} -gt 0 ]; then
  echo "용량 경고:"
  printf '  %s\n' "${WARNED[@]}"
  echo "FILE_GATE result=WARN"
  exit 0
fi
echo "FILE_GATE result=PASS"
