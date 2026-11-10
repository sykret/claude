# sfit

TCAD 입자 충돌 시뮬레이션 결과를 SPICE 전류원 모델로 변환하고 SPICE 파일을 생성하는 도구.
TFIT 같은 도구의 TCAD → SPICE 변환 방식을 블랙박스로 분석·재현(역공학)하는 데 씁니다.
방법론은 [docs/reverse_engineering.md](docs/reverse_engineering.md) 참고.

## 설치
```bash
cd sfit
pip install -e ".[dev]"
```

## 사용법
```bash
# 1) TCAD 전류 과도응답 → 이중지수 파라미터 (Q, tau_r, tau_f, t0)
sfit fit examples/transient.csv -o params.json

# 2) netlist의 노드에 충돌 전류 주입 → SPICE 파일
sfit gen examples/rc2.sp --node n8 --params params.json -o strike.sp
sfit gen examples/rc2.sp --node n8 --let 10 --depth 2 --tau-r 3e-12 --tau-f 40e-12 --style pwl

# 3) LET → 전하
sfit charge --let 10 --depth 2

# 4) 레퍼런스 도구가 만든 SPICE 파일 분석/비교
sfit inspect ref.sp
sfit diff ref.sp strike.sp
```

## 모듈
| 파일 | 역할 |
|---|---|
| `src/sfit/tcad.py` | 과도응답 로드, 전하 적분, 이중지수 피팅, LET→Q |
| `src/sfit/spice.py` | 전류원 생성(EXP 2개로 정확한 이중지수 / PWL), 주입, SPICE 파서 |
| `src/sfit/cli.py` | 명령줄 인터페이스 |

## 테스트
```bash
pytest
```
