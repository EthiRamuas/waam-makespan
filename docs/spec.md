# WAAM Validator — 확정 명세 & 작업환경

> 레포: https://github.com/Ha-An/WAAM_Validator (Apache-2.0, v1.0.1, © 2026 Yosep Oh, AIIS Lab, HYU ERICA)
> **이 문서는 레포 문서·소스·실행 결과를 직접 확인해 작성한 것**이며, 추측이 아니다.
> 다음 세션부터는 이 한 장만 읽으면 되므로 원본 문서(378줄 인터페이스 + 232줄 config 참조)를 다시 읽지 않는다.
> 작성 2026-09-13 · **개정 2026-10-06 (rev.2)** · 레포 경로 `docs/spec.md`
>
> 📌 **rev.2 변경 범위** — **§1(작업환경)과 §9(다음 액션)** 를 현재 상태에 맞게 고쳤고, **§8-2의 Li 2024 서술 한 문장**을 PDF 정독(2026-10-06) 결과에 맞게 정정했다. 로컬 구축이 끝나면서 "클라우드에서 프로토타이핑" 체제가 "로컬 Claude Code" 체제로 바뀌었기 때문이다. **그 외 §2~§8의 사양·계약·실측·실험 결과는 한 글자도 바꾸지 않았다.**
> 이 문서가 **수치·계약의 단일 출처**다. 다른 문서(CLAUDE.md, playbook.md 등)와 어긋나면 이 문서가 맞다.

---

## 1. 작업환경 — 결론

### 1-1. 지금 상태 (2026-10-06)

**로컬 PC에 구축 완료.** 작업은 `C:\Github\waam-makespan`에서 Claude Code로 한다.

```
C:\Github\
├─ WAAM_Validator\        # 교수님 레포 (읽기 전용). Validator 원본
└─ waam-makespan\         # 우리 레포. Claude Code 실행 위치
   ├─ .venv\              # Python 3.11, Validator를 -e 로 참조
   └─ tests\fixtures\sample_job\   # 샘플 job 복사본 — waam-validator run → exit code 0 확인
```

즉 **trajectory.csv를 만들어 → 검증하고 → makespan을 재는 루프 전체를 로컬에서 돌린다.** 첫 커밋(`b241800`), `.claude` 설정, `CLAUDE.md`까지 배치됐다. 상세한 구축 순서와 함정은 `playbook.md` §3, 설정은 `operations.md` §2.

> 참고: 2026-09-13에 이 문서를 쓸 때 사용한 클라우드 세션의 clone(`/home/claude/WAAM_Validator`)은 **분석·실험 재현용으로만** 남는다. 새 코드는 로컬 레포에서 쓴다.

### 1-2. 역할 분담 (rev.2)

| 하는 일 | 어디서 | 이유 |
|---|---|---|
| **코드 작성·실행·실험 반복** | **로컬 PC + Claude Code** | 워크스페이스 맥락을 직접 보고, 로컬 파일을 바로 고친다. 야간 배치도 여기 |
| **Validator 실행·makespan 측정** | **로컬** | exit code·summary.json을 같은 머신에서 |
| **공식 계산시간 측정** | **로컬 고정 머신 1대** | 평가 2축. 하드웨어가 매번 다르면 비교 불가 |
| 설계 논의·문서 갱신·보고서·발표 | 이 Claude 프로젝트 | 프로젝트 문서와 같이 관리 |
| 결과 대시보드(아티팩트) 발행 | 이 Claude 프로젝트 | `results.csv`를 올려 같은 URL로 재발행 |

두 환경 사이의 동기화는 **본인 GitHub 레포 하나**로. (제출물도 어차피 GitHub)

> ⚠️ **계산시간은 반드시 로컬에서 측정.** 클라우드에서 잰 숫자는 설계 판단용 참고치일 뿐, 보고서에 넣을 수 없다.

### 1-3. 로컬 세팅 (본인 PC, Windows) — 우리 레포 기준

**Python 3.11 필수** (README 명시, lock 파일도 3.11 기준). 새 셸을 열어야 PATH가 잡힌다.

```powershell
winget install Python.Python.3.11
cd C:\Github
git clone https://github.com/Ha-An/WAAM_Validator.git
mkdir waam-makespan; cd waam-makespan; git init

py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned      # 1회. Activate.ps1 차단 해제
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.prefix)"                # 반드시 .venv 경로
python -m pip install -U pip
python -m pip install -r C:\Github\WAAM_Validator\requirements.lock
python -m pip install -e C:\Github\WAAM_Validator --no-deps
waam-validator run .\tests\fixtures\sample_job            # exit code 0 나오면 성공
```

솔버 쪽 추가 패키지 — `requirements.lock`에 **없다.** 별도 설치 필요:

```powershell
python -m pip install scipy rtree networkx               # trimesh 슬라이싱에 scipy+rtree 필수
python -m pip install ortools pymoo matplotlib pandas pytest
```

> `trimesh.section_multiplane`의 `.area` / `.polygons_full`은 **scipy와 rtree가 없으면 런타임에 죽는다.** 실제로 겪고 확인했다.

> (원본 방식: Validator 레포 안에서 직접 `python -m pip install -e . --no-deps` 후 `waam-validator run .\examples\sample_job`. 우리는 레포를 분리했으므로 위 방식을 쓴다.)

### 1-4. 토큰·시간을 아끼는 규칙

1. **파일을 붙여넣지 말 것.** 공개 레포는 직접 받는다. 본인 코드도 GitHub에 올린 뒤 URL만.
2. **로그·CSV 전문을 붙여넣지 말 것.** `summary.json`의 판정과 makespan, exit code만. 전체가 필요하면 "어느 파일 몇 번째 줄" 형태로.
3. **작은 모델로 반복.** `tests/01·02·03`은 6~8층이라 순식간. `04`(50층)·`05`(350층)는 최종 검증에만.
4. **이 문서(`docs/spec.md`)를 계속 갱신.** 새 세션은 원본 문서 대신 이것만 읽는다.
5. **레포 루트의 `CLAUDE.md`** 가 규칙(파이썬 버전, 좌표 단위, 금지사항, 실행 명령)을 고정한다 — ✅ 배치 완료. 이 문서와 어긋나면 이 문서가 맞다.
6. 질문을 묶어서 한 번에. 한 줄씩 왕복하면 매번 전체 맥락이 다시 실린다.

---

## 2. 확정된 셀 사양 (`config.yaml` — 6개 테스트 모델 전부 동일, md5 검증 완료)

```yaml
robots:                          # 반경 1400mm 원주 위 120° 간격
  1: base (-1400,     0,    0)   home (-1000,      0, 1000)
  2: base (  700, +1212.4, 0)    home (  500, +866.0, 1000)
  3: base (  700, -1212.4, 0)    home (  500, -866.0, 1000)
  공통: tcp_radius 100mm | arm_envelope_radius 100mm | xy_reach_radius 1500mm

process:
  deposition_speed  8 mm/s       ← 느림
  travel_speed    150 mm/s       ← 적층의 18.75배
  layer_height      2.0 mm
  bead_width        8.0 mm
  build_plane_z     0.0 mm
  tcp_z_reference   center       → layer k의 D 구간 z = (k + 0.5) × 2.0  (1.0, 3.0, 5.0, …)
  safe_travel_z  1000 mm
  arc_on_time     1.0 s          ┐ D 구간 하나당 고정 오버헤드 2초
  arc_off_time    1.0 s          ┘

workspace: 원점 중심 반경 700mm 원 (D 구간의 비드 외곽이 이 안에 있어야 함. T/W는 밖 허용)

collision:
  arm_clearance 50mm | touching_is_collision true
  → 두 로봇 Base–TCP 중심선 간 최소거리 요구 = 100 + 100 + 50 = 250 mm
  → TCP 간 최소거리 요구 = 100 + 100 = 200 mm  (샘플 job은 20+20=40)

validation:
  layer_z_tolerance 0.25mm | speed_relative_tolerance 0.1
  fail_on_speed_violation: true   ← 속도 위반이 FAIL (샘플 job은 false, 착각 주의)

shape_validation:
  minimum_overall_coverage 0.80 | maximum_overall_overfill_ratio 0.30
  minimum_overall_iou 0.9 | minimum_layer_iou 0.8 | maximum_failed_layer_ratio 0.05
```

---

## 3. `trajectory.csv` 계약 — 확정

```csv
robot_id,time_s,x_mm,y_mm,z_mm,mode
1,0.0,-1000.0,-600.0,100.0,T
1,4.0,-40.0,0.0,2.0,D
1,14.0,40.0,0.0,2.0,T
1,18.0,-1000.0,-600.0,100.0,W
```

> ✅ **중요 정정:** 이건 고정 타임스텝이 아니라 **waypoint(꼭짓점) 목록**이다. 샘플 job 전체가 **9행**. 앞선 착수가이드에서 "수십만 행" 걱정을 적었는데 **틀렸다** — 행 수는 경로 꼭짓점 수만큼이지 시간 해상도와 무관하다. `max_time_step_s: 0.1` / `max_tcp_step_mm: 5.0`은 Validator가 **내부 충돌검사용으로 샘플링할 때** 쓰는 값이지 우리 출력 형식이 아니다.

핵심 규칙:

- **행의 mode는 "이 행부터 다음 행 직전까지"의 구간 동작.** 구간 안은 두 waypoint 선형보간.
  → `A→B`를 적층하려면 **A 행**이 `D`.
- 컬럼 6개 정확히, 이 순서. 빈 셀·NaN·Inf·소문자 mode·`R1` 같은 ID 전부 불가.
- 로봇 1·2·3 모두 존재. 각 로봇 **첫 `time_s` = 0.0**, 시간 엄격 증가, **마지막 행 mode = `W`**.
- 정렬: `robot_id` 오름차순 → 그 안에서 `time_s` 오름차순.
- `W`: 시작·끝 위치 동일(허용오차 0.001mm). arc on/off·냉각·동기화 대기는 전부 `W` 구간으로 시간 반영.
- `D`: XY 길이 > 0, 한 구간 내 Z 변화 ≤ 0.25mm, **수직 적층·층간 연결 D 금지**. 층 이동은 `T`.
- `T`: XYZ 자유 이동. 적층 형상에 기여하지 않음.
- **시간은 우리가 다 채워야 한다.** Validator는 속도로 timestamp를 재생성하지 않고, 우리가 쓴 `time_s`를 그대로 믿은 뒤 속도가 설정값과 맞는지 **검사만** 한다 (10% 허용, 위반 시 FAIL).
- 곡선은 chord 오차가 작도록 여러 개의 직선 `D`로 분할.

**Exporter 권장 중간표현** (문서 §9.1이 직접 제시):

```python
Segment(robot_id=1, mode="D", start_time_s=4.0, end_time_s=14.0,
        start_xyz_mm=(0,0,2), end_xyz_mm=(80,0,2))
```
로봇별로 segment가 시간·위치 모두 끊김 없이 연결되어야 하고, 빈 시간은 생략이 아니라 `W`로 채운다. → segment 리스트를 만든 뒤 시작점만 행으로 뽑고 마지막에 `W` 한 줄 붙이면 CSV 완성.

---

## 4. 검증 항목과 판정

| 검사 | 기준 |
|---|---|
| XY Reach | `sqrt((TCPx−Basex)² + (TCPy−Basey)²) ≤ 1500mm`. **Z는 안 씀.** T/D/W 모든 절점에 적용 |
| Arm 충돌 | 각 로봇을 **Base→TCP를 잇는 XY 2D 캡슐**로 단순화. 두 중심선 최단거리 ≥ 250mm |
| TCP 충돌 | TCP 간 XY 거리 ≥ 200mm |
| 형상 | `D` 선분을 bead_width로 buffer → layer 단면과 비교. Coverage ≥ 80%, Overfill ≤ 30%, 전체 IoU ≥ 90%, layer IoU ≥ 80%, 실패 layer ≤ 5% |
| 속도 | D는 8mm/s, T는 150mm/s 상한 대비 ±10% |

> 🔴 **충돌 모델의 함정 3가지**
> 1. **Z를 무시하는 보수적 탑뷰 판정**이다. 높이가 달라도 XY로 겹치면 충돌.
> 2. **대기 중인 로봇도 공간을 차지한다.** `W` 중에도 Base–TCP 선분이 존재한다.
> 3. **먼저 끝난 로봇의 주차 위치도 전체 makespan까지 계속 충돌 검사 대상이다.**
> → 그래서 "안전한 주차 위치"를 고르는 것 자체가 최적화 변수다. home 좌표가 안전하다는 보장은 없다.

**CLI / 종료 코드**

```bash
waam-validator check <job>   # 형식만  : 0 통과
waam-validator run   <job>   # 전체 검증: 0 PASS / 1 FAIL(충돌·형상) / 2 config·csv오류 / 3 STL / 4 계산 / 5 출력
waam-validator ui    <job>   # 로컬 대시보드 127.0.0.1:8050 (간트차트·3D 리플레이)
```

job 폴더는 `config.yaml` + `trajectory.csv` + `target.stl` **정확히 이 세 파일명**. 로그·체크포인트는 이 폴더 밖에 둘 것.

결과: `<job>/output/YYYY-MM-DD_HHMMSS/` 에 `summary.json`(schema 4.0), `validation_report.md`, `robot_metrics.csv`, `collision_events.csv`, `layer_metrics.csv`, `run.log`.

---

## 5. makespan 정의 — 소스 확인 완료

`src/waam_validator/schedule/metrics.py`:

```python
completion  = trajectory.time_s[-1]          # 로봇별 마지막 행 시각
makespan    = max(completions)               # 세 로봇 중 최댓값
imbalance   = max(completions) - min(completions)
normalized_imbalance = imbalance / makespan
```

- **makespan = 세 로봇의 마지막 waypoint 시각 중 최댓값.** 그게 전부다.
- 원본 interval로 계산하며, 충돌검사용 샘플 시각은 쓰지 않는다.
- `deposition_time + travel_time + wait_time == completion` 이 안 맞으면 `ArithmeticError`로 죽는다 → **시간 공백을 남기면 안 된다.**
- Validator가 `workload_imbalance_s`를 함께 뱉는다 → **불균형이 공식 지표로 노출된다.** 보고서에 그대로 쓸 것.

---

## 6. 공개 모델 6개 — 실측 워크로드

`tests/01~06`을 직접 슬라이싱해 계산 (층 두께 2mm, 중심선 길이 ≈ 단면적 ÷ 비드폭 8mm — 완전 채움 가정의 **근사치**):

| 폴더 | 형상 | X×Y×Z (mm) | 층수 | Σ중심선 | 총 적층시간 | **이론 하한 makespan** |
|---|---|---:|---:|---:|---:|---:|
| 01 | Honeycomb | 226×218×12 | 6 | 7.3 m | 0.25 h | **0.08 h** |
| 02 | Spiral | 351×325×16 | 8 | 15.9 m | 0.55 h | **0.18 h** |
| 03 | Triangular truss | 358×303×12 | 6 | 12.3 m | 0.43 h | **0.14 h** |
| 04 | Motor inner | 458×458×100 | 50 | 416 m | 14.5 h | **4.8 h** |
| 05 | Twisted tri. shell | 766×800×700 | **350** | 1,943 m | 67.5 h | **22.5 h** |
| 06 | Angle frame bracket | 126×190×102 | 51 | 39.8 m | 1.38 h | **0.46 h** |

하한 = (총 적층시간 ÷ 3), 즉 **완벽한 부하균형 + 이동 0 + 대기 0**인 이상적 경우.

> 💡 **이게 문제의 본질을 말해준다.**
> 적층 총량은 형상이 정하므로 **우리가 줄일 수 없다.** 우리가 줄이는 건 *(불균형 + 이동 + 대기)* 뿐이다.
> → 팀 내부 성능 지표를 절대값이 아니라 **`ratio = makespan / 이론하한`** 으로 잡으면 6개 모델을 한 눈금으로 비교할 수 있고, 보고서에도 강력하다. 1.0에 가까울수록 좋고, 1.0은 물리적으로 불가능하다.

실용 메모: **01·02·03으로 개발하고 04·06으로 확인, 05는 최종 검증에만.** 05는 350층 × 1.9km라 한 번 돌리는 것도 부담이다.

---

## 7. 도달범위 구조 — 이게 할당 문제의 골격

로봇 베이스가 원점에서 1400mm, 도달반경 1500mm, 작업영역 반경 700mm. 작업영역을 1.1M개 점으로 샘플링해 계산:

| | 비율 |
|---|---:|
| 로봇 1대당 도달 가능 면적 | 각 **54.0%** |
| **아무도 못 닿는 영역** | **0.00%** ✅ 실현 가능 |
| **1대만 닿는 영역 (전용)** | **41.2%** |
| **2대가 닿는 영역 (공유)** | **55.6%** |
| 3대 모두 닿는 영역 | 3.2% |

> 💡 **핵심 구조:**
> - 작업영역의 **41%는 할당이 이미 결정되어 있다.** 그 로봇 말고는 닿지 않는다 → 최적화 여지 없음, 고정 부하.
> - **56%는 정확히 2대가 공유한다.** 여기가 부하를 옮길 수 있는 **유일한 조절 손잡이**이고, 동시에 충돌이 나는 곳이다.
> - 3대 모두 닿는 영역은 3%뿐(중심부에서도 17%). 즉 **3자 자유 배분이 아니라, 3개의 2자 교환 문제**로 보는 게 맞다.
> - 따라서 알고리즘 1순위 과제: 각 형상에서 **전용 부하를 먼저 계산**하고, 그 불균형을 **공유 영역 배분으로 상쇄**하는 것. 단순 120° 3등분은 이 구조를 무시하므로 비대칭 형상에서 바로 깨진다.

---

## 8. 앞선 착수가이드에서 정정할 내용

| 앞 문서 | 실제 |
|---|---|
| "CSV가 타임스텝마다 한 줄 → 수십만 행 우려" | **틀림.** waypoint 목록이며 샘플 job은 9행 |
| "dt·파일 크기 확인 필요" | 해당 없음. `max_time_step_s`는 Validator 내부 샘플링 값 |
| "충돌 판정 기하 확인 필요" | **확정.** Base–TCP XY 2D 캡슐, 중심선 ≥250mm, TCP ≥200mm |
| "도달거리 3D인지 XY인지 확인 필요" | **확정.** XY 투영만, Z 미사용 |
| "makespan 정의 확인 필요" | **확정.** 로봇별 마지막 waypoint 시각의 최댓값 |
| "레포에 샘플 해가 있는지 확인" | **있음.** `examples/sample_job/` 3종 완비 |

여전히 미확정:

- [x] ~~층간 선후관계를 Validator가 강제하는가?~~ → **§8-2에서 확정: 강제하지 않는다**
- [x] ~~arc_on/off 2초를 Validator가 요구하는가~~ → **§8-3에서 확정: 요구하지 않는다 (참조값일 뿐)**
- [ ] 보고서 템플릿 (미배포)

---

## 8-2. 층 선후관계 — 코드 확인 + 반증 실험으로 확정

### 확인 방법 (다른 항목에도 그대로 쓸 수 있는 절차)

1. **코드에서 해당 검사의 존재를 찾는다.** `shape/` 모듈 전체에서 시간 관련 식별자를 grep → 적층 형상 재구성 함수는 각 `D` 구간을 **Z만 보고 layer index로 매핑한 뒤 layer별로 폴리곤을 union**할 뿐, `time_s`를 전혀 참조하지 않는다. 코드베이스 전체에 `precede / prerequisite / support / overhang / previous_layer` 류의 검사도 없다.
2. **반증 실험을 만든다.** "제약이 있다면 반드시 실패할" 최소 예제를 만들어 돌린다. **통과하면 제약이 없다는 증거**가 되고, 내가 코드를 잘못 읽었을 가능성까지 배제된다.
3. **대조군을 같이 돌린다.** 정상 케이스와 비교해 다른 요인(형상·도달거리·충돌) 때문이 아님을 확인한다.

### 실험 설계와 결과

모든 job은 동일한 `config.yaml`을 쓰고, 궤적만 다르다.

| | 내용 | Makespan | Coverage / IoU | 판정 |
|---|---|---:|---|---|
| **tA** (대조군) | 바 1개, 로봇1이 **층0 → 층1** 순서로 적층 (물리적으로 정상) | 67.68 s | 99.12 % | ✅ **PASS** |
| **tB** (반증) | 동일 형상, **층1 → 층0** 순서 (공중에 뜬 층을 먼저 쌓음 — 물리적으로 불가능) | 67.67 s | 99.12 % | ✅ **PASS** |
| **tC** (동시성) | 분리된 두 바. 로봇1은 층0→층1, 로봇2는 층1→층0 을 **같은 시각에** 진행 | 77.87 s | 99.22 % | ✅ **PASS** |

> **tA와 tB의 결과가 소수점까지 동일하다.** 적층 순서를 완전히 뒤집어도 Validator는 차이를 인식하지 못한다.

### 확정 결론

> **Validator는 층간 선후관계를 전혀 강제하지 않는다. 층 경계 파이프라이닝은 물론, 층 순서의 완전한 임의 배치까지 통과한다.**
> 형상 검증은 "모든 `D` 구간을 Z로 층에 배분해 합집합한 최종 형상"만 보며, **시간은 makespan 계산과 충돌 검사에만 쓰인다.**

### 이게 바꾸는 것

- **층 동기화 barrier가 불필요하다.** 층마다 세 로봇을 맞춰 세울 이유가 없으므로, barrier 때문에 생기던 대기(W)가 통째로 사라진다.
- **문제가 "층별 서브문제 × 층수"로 쪼개지지 않아도 된다.** 착수가이드 §1-2(a)의 분해 가정은 *선택지*이지 *제약*이 아니다. 전체를 하나의 큰 할당·스케줄링 문제로 두면 불균형 손실이 층마다 누적되지 않고 전체에서 한 번만 정산된다 → **이론 하한에 훨씬 가까워질 수 있다.**
- 선행연구 Li et al.(2024)은 **한 층만 다루는 범위 설정**이다 (논문 스스로 "primary research"라며 flat layer만 고려). 층 순서 자체는 물리적 전제이지만 이 Validator는 층 순서를 보지 않으므로 **그 분해를 따를 필요가 없다.**

### ⚠️ 그런데 그대로 악용하면 안 된다

교수님은 **생기원 박사님과 함께 상용 소프트웨어에 넣어 실제로 도는지 검증**하겠다고 했고, "재현했을 때 얼토당토않게 나오면 FAIL"이라고 명시했다. 공중에 층을 먼저 쌓는 해는 Validator는 통과하지만 **실제 WAAM에서는 성립하지 않는다** — 밑에 받칠 재료가 없다.

**권장 입장**: 파이프라이닝은 쓰되, **Validator가 강제하지 않는 제약을 우리가 스스로 부과한다.**

> **국소 선후관계(local precedence)**: 어떤 구간을 층 `k`에 적층하려면, 그 구간 바로 아래(층 `k−1`, 같은 XY 영역)가 **그 시각 이전에 이미 적층되어 있어야 한다.**

이러면 전역 barrier 없이도 물리적 타당성이 유지된다. 로봇 A가 왼쪽에서 층 `k+1`을 시작할 때 로봇 B가 오른쪽에서 층 `k`를 끝내고 있어도 — 왼쪽 아래가 이미 채워져 있는 한 — 문제가 없다. 이게 실제 멀티로봇 AM에서 쓰는 전략이고, 전역 동기화보다 훨씬 빠르다.

그리고 이 선택 자체가 **보고서에 쓸 재료**다. "Validator가 검사하지 않는 물리 제약을 식별하고 자발적으로 부과했다"는 것은 공정 이해도를 보여주는 서술이고, 상용 SW 교차검증에서도 살아남는다.

---

## 8-3. arc_on / arc_off — 강제되지 않는 참조값

§8-2와 같은 절차(코드 grep → 반증 실험 → 대조군)로 확인했다.

### 코드 확인 — 참조가 딱 4곳뿐

레포 전체에서 `arc_on` / `arc_off`를 참조하는 곳을 전부 찾았다.

| 위치 | 내용 |
|---|---|
| `config/models.py:47-48` | `arc_on_time_s: float \| None = Field(default=None, ge=0)` — **Optional 필드.** 0 이상의 수인지만 본다. 아예 생략해도 되는 값이다 |
| `dashboard/views.py:464` | UI에 문자열로 **표시만** 한다 |
| `docs/config-reference.md:81-82` | 명시: *"외부 경로 생성기가 Deposition 시작 전 아크 점화 대기를 만들 때 사용할 **참조시간**입니다. **기존 trajectory의 시간을 자동 변경하지 않습니다.**"* |

소스의 주석도 단정적이다 — *"Optional NCO scheduling parameters retained in the shared config. They **do not change Validator trajectory semantics by themselves**."*

**검증 로직에서 이 값을 읽는 코드는 단 한 줄도 없다.**

### 실험 — 양방향 모두 확인

| | 내용 | Makespan | 판정 |
|---|---|---:|---|
| **tA** (§8-2의 대조군) | 아크 대기 **0초**. `T` 직후 바로 `D` 시작, `D` 직후 바로 `T` | 67.68 s | ✅ PASS, **경고 0건** |
| **tD** | 동일 형상·경로, 각 `D` **앞뒤에 1초 `W`** 삽입 | 71.68 s | ✅ PASS |

- 아크 대기를 **넣지 않아도** 통과하고 경고조차 뜨지 않는다 → **요구하지 않는다.**
- 아크 대기를 **넣어도** 통과한다 → **금지하지도 않는다.** makespan은 삽입한 4초만큼 정확히 늘었다(67.68 → 71.68).

### 확정 결론

> **arc_on/off는 우리가 넣을지 말지 결정하는 값이다.** Validator는 요구하지도 금지하지도 않고, 우리가 쓴 `time_s`를 그대로 받아 makespan에 반영할 뿐이다. 즉 **넣으면 순수하게 makespan 손해**다.

§8-2의 층 선후관계와 구조가 같은 상황이다 — 생략하면 점수가 좋아지지만 물리적으로는 틀린다. 실제 WAAM에서 아크 점화·소호는 반드시 걸리는 시간이다.

### 그래서 비용이 얼마인가 — 넣기로 결정하기 전에 재봤다

아크 비용은 CSV 행 수가 아니라 **연속 적층 패스(아크 스트라이크) 개수**에 붙는다. 끊김 없이 이어진 `D` 구간들은 아크를 한 번만 켜므로 한 번의 스트라이크다.

층별 폐곡선(외곽 + 내부 홀) 개수를 세어 **스트라이크 수의 하한**을 구했다:

| 모델 | 층수 | 층당 평균 윤곽 | 최소 스트라이크 | 아크 오버헤드 | 이론하한 대비 |
|---|---:|---:|---:|---:|---:|
| 01 Honeycomb | 6 | 8.0 | 48 | 0.01 h | **11 %** |
| 02 Spiral | 8 | 1.0 | 8 | 0.00 h | 1 % |
| 03 Truss | 6 | 9.0 | 54 | 0.01 h | 7 % |
| 04 Motor inner | 50 | 5.6 | 280 | 0.05 h | 1 % |
| 05 Twisted shell | 350 | 2.0 | 700 | 0.13 h | 1 % |
| 06 Bracket | 51 | 1.0 | 51 | 0.01 h | 2 % |

*(스트라이크당 2초, 로봇 3대 분산 기준)*

> ⚠️ **이건 하한이다.** 윤곽 패스만 셌고 **내부 채움(infill)은 포함하지 않았다.** infill을 지그재그로 이어 한 번에 긋는지, 평행선마다 끊는지에 따라 스트라이크 수가 10~100배까지 늘어난다. 모델 05 기준으로 패스 평균 길이가 500mm면 +0.7h(3%), 100mm면 +3.6h(16%)다.

### 판단

**아크 시간을 넣는다.** 근거:

1. **비용이 작다.** 윤곽 기준 1~11%이고, 대부분의 모델에서 1~2%다. 물리적 타당성을 사는 값으로 싸다.
2. **경로 설계를 옳은 방향으로 민다.** 아크 비용이 목적함수에 들어가면 최적화가 **적고 긴 연속 패스**를 선호하게 된다. 이건 실제 WAAM 품질(시작·정지점이 적을수록 좋음)과도 일치하고, Li et al.(2024)이 "turns and start-arc points를 줄인다"고 내세운 바로 그 지표다.
3. **상용 SW 교차검증에서 드러난다.** 생략한 해는 재현 시 시간이 어긋난다.

보고서에는 **"넣은 경우와 안 넣은 경우의 makespan을 둘 다 제시"** 하는 것을 권한다. 자발적으로 부과한 제약의 비용을 정량화해 보여주는 셈이라 어필이 된다.

---

## 9. 다음 액션 (rev.2, 2026-10-06 기준)

**완료**

1. ✅ 로컬 세팅 + `waam-validator run .\tests\fixtures\sample_job` **exit 0**
2. ✅ 층간 선후관계 강제 여부 확정 (§8-2) — 미강제, 국소 선후관계 자체 부과
3. ✅ arc 시간 요구 여부 확정 (§8-3) — 미요구, 우리가 반영
4. ✅ 레포 뼈대·첫 커밋(`b241800`)·`.claude` 설정·`CLAUDE.md` 배치

**지금**

5. docs 나머지 저장(`playbook` · `references` · `operations`) → `attrib +R C:\Github\WAAM_Validator\* /S` → 설정 커밋 → `claude` 첫 실행 4점검 (`operations.md` §2-7)
6. **1단계 모듈**: `geometry → prevalidate → segment → timing → writer` → **`tests/03` 같은 작은 모델로 1대만 쓰는 최소 통과 해**로 PASS 찍기 (안전망)
7. 2단계 `lower_bound → results.csv → tests` → 3단계 `slicing → toolpath → baseline_sector` → 전용/공유 구조를 반영한 할당 베이스라인(top k%)으로 `ratio = makespan/하한` 측정 시작
8. 열린 질문: **infill 이어 긋기 방식에 따른 아크 스트라이크 수** (§8-3 하한은 윤곽만), 보고서 템플릿
