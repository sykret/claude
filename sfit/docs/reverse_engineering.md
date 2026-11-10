# TFIT 방식 TCAD → SPICE 변환 역공학 가이드

목표: TFIT 같은 도구가 (1) TCAD 결과를 어떤 소형(compact) 모델로 바꾸고, (2) 그 모델을 어떤
SPICE 모델로 표현하며, (3) 최종 SPICE 파일을 어떻게 만드는지 재현 가능한 수준으로 밝혀내는 것.

접근 원칙: **블랙박스 분석**. 정상적으로 라이선스를 가진 도구에 입력을 넣고, 나오는 출력
(SPICE 파일, 로그, 리포트)을 관찰해 변환 규칙을 추론합니다. 바이너리 디컴파일이나
라이선스 우회는 범위 밖입니다(사용 계약서의 역공학 조항을 먼저 확인하세요).

## 1. 전체 흐름 (공개 문헌 기준 가설)

```
 TCAD 소자 시뮬레이션                  소형 모델                  SPICE
 ─────────────────────               ───────────               ──────────────────────
 입자 충돌(LET, 위치, 각도)  ──fit──▶  Q, τr, τf, t0   ──gen──▶  셀 netlist + 전류원 주입
 → 드레인 전류 과도응답 I(t)          (+ 바이어스 의존성)          + .tran / .meas
                                                                → 반전(upset) 판정 → Qcrit → FIT
```

| 단계 | 일반적인 구현 | sfit 대응 |
|---|---|---|
| TCAD 결과 표현 | 접합별 전류 과도응답 I(t), 바이어스·LET·충돌 위치별 테이블 | `sfit fit` (CSV 입력) |
| 소형 모델 | 이중지수 펄스 `I(t) = Q/(τf-τr)·(e^{-t/τf} − e^{-t/τr})` | `tcad.DoubleExp` |
| 전하 계산 | `Q[pC] = 0.01036 · LET[MeV·cm²/mg] · 깊이[µm]` (Si) | `sfit charge` |
| SPICE 표현 | `EXP` 전류원, `PWL` 전류원, 또는 바이어스 의존 B-source/Verilog-A | `sfit gen --style exp|pwl` |
| 판정·집계 | 출력 노드 전압이 VDD/2를 넘는지 → 최소 Q = Qcrit → 면적×플럭스로 FIT | (다음 단계) |

## 2. 역공학 절차

### 2.1 출력 SPICE 파일 수집
같은 셀에 대해 **변수 하나만 바꿔가며** 레퍼런스 도구로 SPICE 파일을 생성합니다.

| 실험 | 고정 | 변화 | 알아낼 것 |
|---|---|---|---|
| A | 셀, 노드, 바이어스 | LET (1, 2, 5, 10, 20…) | Q가 LET에 선형인지, 비례상수(=유효 깊이) |
| B | 셀, LET | 충돌 노드/트랜지스터 | 주입 노드 선택 규칙, 극성(n/p 확산) |
| C | 셀, LET | VDD, 온도 | τr/τf·Q의 바이어스 의존성 |
| D | LET | 공정 코너, 셀 크기 | 모델 테이블 인덱싱 방식 |

### 2.2 구조 분석
```bash
sfit inspect ref_let10.sp            # 소자 수, 노드, 전류원, .model, 해석 명령
sfit inspect ref_let10.sp --json     # 스크립트로 비교할 때
sfit diff ref_let10.sp ref_let20.sp  # 무엇이 바뀌었는지(대개 전류원 인자만)
```
확인 포인트:
- 주입 전류원의 **형태**: `EXP(...)`, `PWL(...)`, `B`-source 수식, 서브서킷(`X…`) 호출 중 무엇인지
- 전류원 **노드 쌍과 방향** (드레인→벌크/웰인지, 드레인→0인지)
- 추가된 `.param`, `.meas`, `.tran` 스텝/종료 시간, `.include`/`.lib` 경로
- 원본 netlist 대비 **바뀐 부분** (`sfit diff 원본.sp 생성본.sp`)

### 2.3 파라미터 추출
- `EXP`면 인자에서 바로 진폭·τ 추출. `PWL`이면 점들을 CSV로 뽑아 `sfit fit`으로 Q/τr/τf 역산.
- 실험 A 결과로 Q-LET 그래프 → 기울기/0.01036 = 유효 수집 깊이(µm).
- 실험 C 결과로 τ, Q의 VDD 의존 함수형(선형/거듭제곱/테이블)을 추정.

### 2.4 재현 및 검증
1. 추론한 규칙으로 `sfit gen`이 같은 SPICE 파일을 만들도록 확장
2. `sfit diff ref.sp ours.sp`로 구조 일치 확인
3. 같은 시뮬레이터로 두 파일을 돌려 출력 파형 비교 (오차 지표: 피크 전압, 펄스 폭, Qcrit)

## 3. 정보가 필요한 부분
다음 자료가 있으면 sfit을 해당 형식에 맞춰 바로 확장할 수 있습니다.
- 레퍼런스 도구가 생성한 SPICE 파일 샘플 (가능하면 실험 A~C처럼 변수만 바꾼 묶음)
- TCAD 전류 과도응답 내보내기 파일 (Sentaurus `.plt`, Silvaco `.log` 등) 샘플
- 사용 중인 SPICE 시뮬레이터 (HSPICE / Spectre / ngspice) — 문법 차이 반영용

## 참고 문헌
- G. C. Messenger, "Collection of Charge on Junction Nodes from Ion Tracks," IEEE TNS, 1982 — 이중지수 모델
- P. E. Dodd, L. W. Massengill, "Basic Mechanisms and Modeling of Single-Event Upset in Digital Microelectronics," IEEE TNS, 2003
- T. Merelle et al., "Criterion for SEU Occurrence in SRAM Deduced from Circuit and Device Simulations," IEEE TNS, 2005
