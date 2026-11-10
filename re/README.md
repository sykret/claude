# 역공학 작업 공간 (REA 기반)

TFIT 같은 도구의 TCAD → SPICE 모델 변환과 SPICE 파일 생성 방식을 분석해 `sfit`에서 재구현하기 위한 작업 공간입니다.

## 폴더

| 경로 | 내용 | 커밋 |
|---|---|---|
| `inbox/` | 분석 대상 바이너리, 설정, 샘플 입출력 | ✗ |
| `evidence/` | 분석 근거 노트 (`raw/`에는 디컴파일 덤프) | 노트만 커밋 (`raw/` 제외) |
| `specs/` | 동작 명세. 개발자가 보는 유일한 분석 결과 | ✓ |
| `plans/` | 구현 계획과 수용 기준 | ✓ |
| `qa/` | 검증 보고서 | ✓ |

## 에이전트 (`.claude/agents/`)

```
 바이너리 ──▶ rea-analyst ──specs──▶ rea-planner ──plans──▶ rea-developer ──코드──▶ rea-qa
 (inbox)      분석 (REA)              기획                   개발 (클린룸)            QA
                  ▲                       ▲                                           │
                  └───── 명세 보완 요청 ───┴──────────── 실패 항목 / 질문 ──────────────┘
```

| 에이전트 | 역할 | 볼 수 있는 것 |
|---|---|---|
| `rea-analyst` | REA로 바이너리를 분석해 근거와 명세를 작성 | 바이너리, REA 도구 |
| `rea-planner` | 명세를 작업 단위와 수용 기준으로 정리 | specs, sfit 코드 |
| `rea-developer` | 명세와 계획만 보고 sfit에 구현 | specs, plans, sfit 코드 |
| `rea-qa` | 레퍼런스 출력과 비교해 검증 | plans, sfit, 레퍼런스 출력 |

분석과 개발을 분리하는 **클린룸 구조**입니다. 개발 에이전트는 디컴파일 코드를 보지 않고 명세만 보고 구현합니다. 그래서 원본 코드가 결과물에 그대로 옮겨지는 일을 막을 수 있습니다.

## 사용 예 (Claude Code)

```
re/inbox/에 tfit 바이너리 넣었어. rea-analyst로 SPICE 파일 생성 로직 분석해줘
rea-planner로 re/specs/spice-writer.md 기준 구현 계획 세워줘
rea-developer로 re/plans/01-spice-writer.md 구현해줘
rea-qa로 01번 계획 검증해줘
```

## REA 설치 (사용자가 직접 실행)

REA는 [morluto/rea](https://github.com/morluto/rea) (npm `rea-agents`, MIT 라이선스)입니다. 이름이 비슷한 가짜 저장소가 보고된 적이 있으니 공식 경로로만 설치하세요.

요구 사항: Node.js `^22.23.4 || ^24.22.1 || >=26.12.1`. 네이티브 바이너리 분석에는 Ghidra(Linux), Hopper, IDA 중 하나가 필요합니다.

```bash
# 1) 변경 계획만 미리 보기 (아무것도 쓰지 않음)
npx -y rea-agents@6.8.0 setup --client claude_code --dry-run --json

# 2) 적용: MCP 서버 등록과 reverse-engineer-anything 스킬 설치
npx -y rea-agents@6.8.0 setup --client claude_code --yes

# 3) Claude Code를 재시작한 뒤 확인
npx -y rea-agents@6.8.0 doctor --client claude_code --json
```

프로젝트 단위로 수동 등록하려면 저장소 루트에 `.mcp.json`을 만듭니다. Claude Code가 처음 불러올 때 승인을 요청합니다.

```json
{
  "mcpServers": {
    "rea": { "type": "stdio", "command": "npx", "args": ["-y", "rea-agents@6.8.0", "--mcp"] }
  }
}
```

## 원칙

- 합법적으로 사용 권한이 있는 바이너리만 분석합니다. 사용 계약의 역공학 조항을 먼저 확인하세요.
- 라이선스 검사 우회, 키 생성, 복제 방지 해제는 하지 않습니다.
- 바이너리와 디컴파일 원본은 저장소에 커밋하지 않습니다 (`re/.gitignore`).
