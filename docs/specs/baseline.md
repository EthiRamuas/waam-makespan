# baseline 명세 (v0 초안)

상태: **확정(C-46, 2026-10-11 20:08, 작업 25 전송 = ★4 승인).** 구현은 작업 26. 근거: DECISIONS C-09·C-15·C-21·C-23·C-32·C-33·C-34·C-42~C-46, `docs/measurements/design_inputs_3stage.md`(M1~M8, M7′), `docs/specs/{probe_driver,toolpath}.md`, `src/waam/{timing,prevalidate,segment,writer,geometry,toolpath,results}.py`(읽기). 이 파일과 `docs/spec.md`가 어긋나면 `docs/spec.md`가 맞다. 작업 25에서 6건 수정(§11)과 미결 항목 정리(§10)를 반영했다.
표기: **확정**(코드·소스·실측·산술·기존 결정) / **가설** / **미측정** / **미확인**. 규칙 번호는 B1~B25, 미결 항목 번호는 U-1~U-28, 분류 R1~R6은 §10.
목적: 3단계 비교군 baseline = **포트폴리오**(C-42). 전략 S(직렬 인계)와 전략 P(섹터 병렬)를 모두 구현하고, 모델마다 prevalidate를 통과한 체인의 makespan이 작은 쪽을 자동 선택한다. 새 탐색 알고리즘이 아니라 toolpath v0 패스 → 조각 → 로봇 배정 → 시간 진행 → `timing.build_chain` → `prevalidate` → `writer`를 잇는 구성이다. 4단계(층 동기화 제거·메타휴리스틱)의 비교군이다.

**일반화 원칙(모든 항목에 적용).** 로봇 수·base 위치·reach·간격 각도는 config에서 읽는다. "3대", "120°", "60°", 모델 번호를 상수로 쓰지 않는다. 공개 config(3대, 120° 간격)는 이 일반 규칙의 한 경우로만 서술한다. 단 현재 코드에는 3대를 가정하는 곳이 있다(§5-3).

## 0. 핵심 사실

- 6개 모델 `config.yaml`은 md5가 모두 같다(확정, probe_driver §0). 이 명세의 숫자는 그 config의 값이지만 규칙은 config에서 읽는다.
- **직렬 하한의 산술 (C-42):** 팔 간 요구 거리 = 2 × `arm_envelope_radius_mm` + `arm_clearance_mm`(config 값 100 + 100 + 50 = 250 mm, 확정). 팔 간 Base→TCP 선분 거리 ≤ TCP 간 거리. D 꼭짓점 집합 지름이 250 mm보다 작으면(M5: 01 222.2, 06 216.9) 두 로봇이 동시에 부품 위 D·아크 W 위치에 있을 수 없다. 따라서 prevalidate를 통과한 체인의 makespan ≥ ΣD + Σ아크 = M8의 W (01: 1872.25 s, 06: 6149.0 s). 02·03(지름 343.6 / 350.0)은 이 산술이 적용되지 않고, M3 삼중 동시 통과 표본이 20000개 중 20 / 127이다(실측).
- **섹터 도달 보장의 산술 (C-43):** 공개 config에서 섹터 안의 점은 자기 base 방향과 60° 이내, base 거리 1400 mm, 원점 반경 r ≤ 700 mm이므로 base까지 거리 ≤ sqrt(1400² + r² − 1400·r) ≤ 1212.4 mm < 1500. 소유 로봇이 항상 도달한다.
- **M6 요약 (실측, 01~06, δ=0):** 섹터 경계에서 잘리는 패스 01 34 / 02 57 / 03 46 / 04 194 / 05 1404 / 06 58개, 추가 조각 34 / 57 / 49 / 744 / 3112 / 298개. 폴백 발동 조각 6개 모델 모두 0(δ 격자 전체에서도 0). 최대/최소 부하비 01 1.03 / 02 1.12 / 03 1.27 / 04 1.20 / 05 1.01 / 06 3.45. 숫자 전체는 `design_inputs_3stage.md` §10.
- **M7 요약 (실측):** 꼭짓점 방식(M7)의 자기 base 방향 반직선 위 최소 대기 반경 ρ는 모델·로봇마다 **305~559 mm**, hull 방식(M7′, B7이 쓰는 값)은 **307~559 mm**이며 모든 로봇에서 M7′ ≥ M7이다(차이 0~2 mm). config home 좌표는 M7 검사를 6개 모델 모두 통과했다(충돌 꼭짓점 0; hull 방식으로는 미검사). 전체 숫자는 `design_inputs_3stage.md` §11(M7)·§13(M7′), 직렬 하한은 §12.
- **미측정:** 두 전략의 prevalidate 통과 makespan, S·P의 compute 시간, 06에서 S와 탐침(6174.838943466003 s)의 차이, 대기 위치 z의 영향, 교착 발생 빈도.

## 1. 범위와 모듈 경계

| 하는 것 | 하지 않는 것 | 넘기는 곳 |
|---|---|---|
| toolpath 패스 → 조각(도달 경계 분할, P는 섹터 분할) | 패스 생성·해칭 간격 변경 | toolpath v0.1(C-45) |
| 전략 S·P의 배정·순서·시간 진행, 대기 위치 계산 | 층 동기화 제거·파이프라이닝·선후관계 검사 | 4단계, C-15 |
| `build_chain` + `prevalidate.try_append`/`close_timeline` + `require_submittable` | prevalidate 규칙 변경 | — |
| 포트폴리오 선택(makespan 비교), 선택된 체인을 `write_trajectory`로 기록 | Validator 실행·결과표 기록 | run_all(C-21), 탐침 구동 방식 |
| 결정적 출력(같은 입력 → 바이트 동일 CSV) | 무작위 탐색·시드 | 4단계 |

## 2. 고정 조건

| 조건 | 출처 |
|---|---|
| **층 동기화(C-23):** 층 k의 모든 D·아크 W가 끝난 뒤 층 k+1의 D 시작. 국소 선후관계는 이 구조로 보장되고 writer 게이트에는 없다 | C-23, C-15 |
| **아크(C-09):** 조각마다 `arc_on` W + `arc_off` W. 생략 금지. 조각 = 연속 적층 패스(아크 스트라이크) | C-09, `timing.build_chain` |
| **리프트(C-32):** 조각 사이 이동 = 수직 상승 → 수평 → 수직 하강, z_lift = max(z_cur, z_next) + Δz, Δz = `ToolpathParams.lift_dz_mm`(**가설값** 2h = 4 mm) | C-32, probe_driver P6 |
| **속도(C-33):** 적층·이동 공칭 속도, 시각은 float32 양자화 끝점 3D 거리 ÷ 속도 | C-33, `timing.build_chain` |
| **포트폴리오(C-42)** 선택 규칙·결정성·모델별 분기 금지 | C-42 |
| **섹터(C-43)** base 각도 기준, 폴백, δ 자동(R4) | C-43 |
| **경계 충돌(C-44)** 대기 안전망 + 바깥→안 순서 | C-44 |
| **범위·순서(C-45)** baseline(S+P) → run_all → toolpath v0.1, 중간발표 10/20 전 | C-45 |
| toolpath v0 기본값(s = w, o = w/2, n_c = 1, 기본 `wall_mode`)만 사용 | C-29 |
| Validator는 제출 후보에만, 탐색 중에는 prevalidate만 | CLAUDE.md, C-34 |
| 모든 로봇이 CSV에 있고 첫 시각 0.0, 시각 엄격 증가, 마지막 모드 W, 빈 시간은 W | CLAUDE.md 계약, `writer.lint_csv` |
| 쓰기 전 `require_submittable`, 스케줄러는 로봇마다 일을 끝내면 `close_timeline` | CLAUDE.md, C-04 |
| `config.yaml`·`target.stl`·Validator 레포 수정 금지, 모델 번호·상수 분기 금지, 일반화 원칙 | CLAUDE.md |

## 3. 규칙 (검증 가능)

### 3-1. 공통

| ID | 규칙 | 검증(§8) |
|---|---|---|
| **B1** 입력 | 입력은 `LayerStack`·config. `toolpath.generate(stack, cfg, use_cache=False)` 결과 `Toolpath.passes`를 쓴다(기본 파라미터). 로봇 수 n, base, reach, home, 원점(`workspace.center_xy_mm`), 속도·아크는 config에서 읽는다 | T-B01, T-B15 |
| **B2** 조각 | 조각 = 패스 또는 패스를 나눈 부분 polyline. 속성: 층, z, 꼭짓점(XY), 길이, 원 패스 번호, 조각 번호, 종류, 도달 로봇 집합. 조각의 도달 집합 = 모든 꼭짓점이 닿는 로봇들(원판이 볼록해 꼭짓점 검사로 충분, 확정) | T-B02 |
| **B3** 도달 경계 분할 | 도달 집합이 빈 패스는 도달 경계(각 로봇 reach 원)에서 분할한다. 패스를 앞에서부터 훑으며 "공통 도달 로봇이 하나 이상 남는 최대 구간"을 탐욕적으로 늘리고, 구간이 끝나는 곳은 선분과 reach 원의 교점으로 자른다(교점 계산은 `d ≤ R + ε`과 일치해야 함). 도달 집합이 비지 않은 패스는 나누지 않는다(S에서) | T-B03 |
| **B4** 이동 | 조각 사이·대기 위치로의 이동은 probe_driver P6과 같다: 같은 점(float32)이면 이동 없음, 아니면 ① 수직 ② 수평(z_lift) ③ 수직. 닫힌 고리 조각은 꼭짓점 순서 그대로 쓰고, 열린 조각은 현재 위치에 가까운 끝점부터 쓸지 R4(U-19) | T-B04 |
| **B5** 시작 | 모든 로봇은 config `home_xyz_mm`에서 시작한다(probe A2·D6 선례). 첫 동작은 B4 규칙으로 첫 작업 또는 대기 위치까지 이동 | T-B05 |
| **B6** 층 동기화 | 층 k의 모든 조각의 D·아크 W가 끝난 시각 t_k = max(로봇별 층 k 끝 시각). 층 k+1의 어떤 로봇의 첫 이동도 t_k 이후에 시작한다(그 전까지 대기 위치 W). 로봇이 층 k에 조각이 없어도 같다 | T-B06 |
| **B7** 대기 위치 | 로봇 i의 대기 위치 = 원점에서 자기 base 방향 반직선 위, 원점 거리 ρ_i. K_j = 로봇 j가 닿는 D 꼭짓점 집합(전 층, 소수 셋째 자리 반올림 중복 제거), H_j = conv(K_j), **A_j = conv({base_j} ∪ H_j)**(base_j에서 H_j 안 점으로 그은 팔 선분들의 합집합 — 볼록성에 의해 확정). 조건: 모든 j ≠ i에 대해 dist(선분 [base_i, 대기점_i], A_j) ≥ arm_i + arm_j + `arm_clearance_mm` + `prevalidate.float32_buffer_mm(geom)`(공개 config: 100 + 100 + 50 + 0.001 mm). TCP 조건은 팔 조건에 포함된다(팔 간 선분 거리 ≤ TCP 간 거리, 팔 요구 거리 ≥ TCP 요구 거리). **ρ_i = 이 조건을 만족하는 최소 정수 mm**(선분이 ρ가 클수록 짧아져 조건은 ρ에 대해 단조: M7′에서 6모델 18로봇 모두 확인). 이 방식은 j의 꼭짓점 사이 선분 위 TCP와 j의 부품 안 이동까지 포함하므로 꼭짓점 방식(M7)보다 보수적이다. 없으면 base 위치(ρ = base 거리). z = R4(U-13). 근거: 볼록 껍질 안의 TCP 위치는 모두 A_j 안의 팔 선분이다. 이 검사는 설계 조건이며 최종 판정은 prevalidate | T-B07 |
| **B8** 비작업 로봇 | 층 안에서 일이 없거나 끝낸 로봇은 제자리 W가 `check_hold`(다른 로봇들의 확정 구간 기준)를 통과하면 **제자리**에서 기다리고, 통과하지 못하면 B7 대기 위치로 후퇴해 W로 기다린다(R4, 후퇴 횟수는 측정 항목). 층 경계(B6·B21)·교착 후퇴(B20)도 같다. 근거: 불필요한 이동 T를 없애되 충돌 여유는 prevalidate가 보증 | T-B08 |
| **B9** 종료 주차 | (a) **한 번도 작업하지 않은 로봇**(예: S에서 일이 없는 로봇): probe A2 그대로 — home에서 시작해 `park_candidates`(λ ∈ (0, .25, .5, .75, 1.0), **가설값**) 중 `check_hold`가 통과하는 첫 후보에 W 하나, 마지막 시각 = T_end. (b) **일을 끝낸 로봇**: 일을 끝낸 직후 B7 대기 위치로 이동해 W로 유지하고 `close_timeline`. 단 **마지막으로 끝나는 로봇**은 이동하지 않고 마지막 위치에서 끝낸다(makespan에 주차 T를 넣지 않는다). (b)는 지시문의 "probe A2 규칙"의 해석 확장이므로 §10 U-27(R5) | T-B09 |
| **B10** 닫기·쓰기 | 모든 로봇의 타임라인을 `close_timeline`하고 `check_all`이 ok여야 한다. 포트폴리오가 고른 체인만 `write_trajectory`(내부에서 `require_submittable`)로 쓴다 | T-B10 |
| **B11** 결정성 | 모든 순회는 정렬된 키(층, 패스 번호, 조각 번호, 로봇 id)로 한다. 동률은 로봇 id가 작은 쪽, 조각 번호가 작은 쪽. 해시 순서·실행 시간·무작위 사용 금지. 같은 입력 두 번 → 바이트 동일 CSV | T-B11 |
| **B12** 일반화 | 섹터·도달·대기 위치 함수는 n과 base를 `CellGeometry`/config에서 읽는다. 로봇 id는 1..n(config 정렬). 모델 번호·로봇 수 상수 분기 없음 | T-B15, T-B16 |

### 3-2. 전략 S (직렬 인계)

| ID | 규칙 | 검증 |
|---|---|---|
| **B13** 배정 | 층마다 **현재 로봇이 닿는 조각을 정준 순서(V9)대로 먼저 모두 처리**한다. 남은 조각이 있으면 "남은 조각 중 그 로봇이 닿는 길이"가 가장 큰 로봇(동률은 id가 작은 쪽)에게 인계하고, 그 로봇이 닿는 남은 조각을 모두 처리하는 것을 반복한다. 인계 횟수 ≤ 그 층 필요 로봇 수 − 1(한 로봇은 자기가 닿는 조각을 모두 처리한 뒤 넘기므로 남은 조각은 그 로봇이 닿지 않는 것뿐이고, 한 번 쓴 로봇은 그 층에 다시 오지 않는다. 모든 조각은 B3 분할 뒤 닿는 로봇이 있다). 층 사이에는 직전 층의 마지막 로봇이 다음 층을 이어받는다(닿는 조각부터 처리, 유지). R4. 근거: 층당 인계를 최소화(인계마다 후퇴·진입 이동 T와 대기 도착 대기가 든다) | T-B13 |
| **B14** 한 번에 1대 | 같은 시각에 부품 영역(조각 위·리프트 구간)에 있는 로봇은 하나뿐이다. 로봇이 바뀔 때: 이전 로봇이 B7 대기 위치에 **도착한 뒤** 다음 로봇이 대기 위치에서 출발한다. 모든 구간을 B20의 `append_checked`(`try_append` + 다른 로봇의 마지막 위치 유지 검사)로 확인한다 | T-B14 |
| **B15** 실패 | S에서 `try_append`가 실패하면 그 구간은 대기 후 재시도하지 않고 S를 **실패**로 표시한다(포트폴리오가 P를 쓴다). 이유(`Verdict`)를 기록 | T-B17 |

### 3-3. 전략 P (섹터 병렬)

| ID | 규칙 | 검증 |
|---|---|---|
| **B16** 섹터 | C-43. 원점 = `workspace.center_xy_mm`. 로봇 각도 θ_i = atan2(base_i − 원점). 각도 순으로 정렬해 이웃 θ 사이 이등분선이 경계, 로봇 i의 섹터는 두 경계 사이. n = 1이면 경계 없음. 회전 δ(전 층 공통)는 경계를 같은 각도만큼 돌린다. 점의 소유 로봇은 중점 각도로 정한다 | T-B16, T-B18 |
| **B17** 분할 | 패스를 섹터 경계 반직선(원점에서 각도 β_k + δ)에서 자른다. 연속한 같은 섹터 부분이 한 조각. 닫힌 고리는 첫 조각과 마지막 조각이 같은 섹터이면 합친다(스트라이크 감소). M6의 "추가 조각"이 이 규칙의 값이다 | T-B19 |
| **B18** 폴백 | 조각마다 소유 로봇이 모든 꼭짓점에 닿는지 검사한다. 못 닿으면 그 조각을 닿는 이웃 로봇(섹터 경계가 더 가까운 쪽)에게 넘기고, 그래도 안 닿는 부분은 B3 규칙으로 분할한다. 공개 config에서 발동은 **0이어야 한다**(M6 실측 0, 테스트로 고정) | T-B20 |
| **B19** 순서 | 섹터 안 조각 순서 = 부품 중심(전 층 D 꼭짓점의 경계상자 중심)에서 조각 중점까지 거리가 먼 것부터(바깥→안, C-44), 동률은 조각 번호. 열린 조각은 B4(R4)에 따라 방향 선택 | T-B21 |
| **B20** 시간 진행 | 이벤트 기반(타임스텝 루프 아님). 층 안에서 **가장 이른 가용 로봇**(체인 끝 시각 최소, 동률은 id)이 자기 큐의 다음 조각 체인(이동 + 조각, 아크 포함)을 제안 → 구간마다 **`append_checked`**: ① `try_append` ② 성공하면 끝 시각이 이 구간 끝보다 이른 열린 타임라인(다른 로봇)마다 `check_pair(rules, 내 타임라인, 그 타임라인, seg.start, seg.end, hold_open=True)`로 "그 로봇이 마지막 위치를 유지"한다고 보고 검사, 실패하면 `pop_last`로 되돌려 실패. 근거: `try_append`는 `hold_open` 없이 `check_pair`를 부르므로 다른 열린 타임라인은 확정한 끝 시각까지만 알려진 것으로 본다(§5-4 인용). 구간 전체가 성공하면 확정. 실패하면(C-44) 이 조각에서 확정한 구간을 `pop_last`로 되돌리고 그 로봇은 B8 규칙(제자리 `check_hold` 통과면 제자리, 아니면 B7 대기 위치)으로 W한다. W 길이 = 다른 미완료 로봇 중 자기 끝 시각보다 큰 최소 끝 시각까지. 그 시각에 다시 제안 | T-B22 |
| **B21** 층 경계 | 한 층의 모든 큐가 비면 t_k를 정하고(B6) 각 로봇이 B8 규칙(제자리 `check_hold` 통과면 제자리, 아니면 B7 대기 위치)으로 t_k까지 W한 뒤 다음 층으로 | T-B06 |
| **B22** 교착 | 후퇴 W의 끝에서 더 큰 끝 시각을 가진 다른 로봇이 없으면(모두 같은 시각에 대기 중이거나 완료) 교착이다. **초안 선택지:** (a) P를 실패로 표시하고 포트폴리오가 S를 쓴다, (b) 조각 큐에서 다음 조각을 먼저 시도한다(재배열), (c) 한 로봇만 부품 영역에 들이는 직렬 모드로 그 조각만 전환. 기본값 후보 (a). 재시도 횟수는 조각당 최대 n−1회로 둔다(근거 없음, 가설) | T-B23 |

### 3-4. 포트폴리오

| ID | 규칙 | 검증 |
|---|---|---|
| **B23** 선택 | S와 P를 모두 실행한다. 각각 `check_all` ok인 체인만 후보. 후보 makespan = 로봇별 마지막 `end_time_s`의 최댓값. 작은 쪽을 고르고 동률이면 S. 후보가 하나뿐이면 그것, 없으면 예외(결과를 만들지 않는다). 모든 모델에 같은 규칙이며 모델별 분기가 없다 | T-B24 |
| **B24** 기록 | 선택된 전략 이름("S"/"P"), 두 후보의 makespan(실패 이유 포함), 전략별 계산 시간을 `notes` 또는 반환 객체에 남긴다. `algo` 문자열은 R3(§10 U-22) | T-B25 |
| **B25** compute_s | probe D7과 같은 범위(`toolpath.generate` 캐시 없음 + 조각 + 배정 + 시간 진행 + prevalidate + write)에서 **두 전략 모두** 포함한다. 슬라이싱·Validator는 제외, 전략별 시간은 따로 기록 | T-B26 |

## 4. 경우의 수와 엣지 케이스

| 경우 | 처리 |
|---|---|
| 로봇 1대만 도달하는 패스가 많은 층 | S: 그 로봇 유지. P: 섹터 폴백(B18) 또는 경계 분할 |
| 섹터 경계가 패스 꼭짓점 위를 지남 | 경계는 반개구간 [lo, hi)로 정한다. 길이 0인 부분 조각은 버린다(B2) |
| 01·06처럼 부품이 작음(D 지름 < 250 mm) | P도 prevalidate가 동시 작업을 거부하므로 후퇴 W가 잦다. 포트폴리오가 S를 고를 가능성이 크다(**가설**, 미측정) |
| 04·05처럼 도달 집합이 빈 패스(04 60개, 05 1286개) | B3 분할 또는 P의 섹터 분할. 섹터 분할 조각은 소유 로봇이 닿는다(M6 폴백 0) |
| 로봇이 한 층에서 조각이 없음 | B8 대기 위치에서 W, 층 경계까지 |
| 대기 위치가 없음(어떤 ρ도 B7 조건 불통과) | base 위치를 쓴다. 그것도 충돌이면 그 전략 실패 |
| n = 1 | 경계 없음, S·P 동일. 포트폴리오는 S |
| n = 2·4 | 섹터 계산(B16~B18)은 동작해야 한다. 체인·prevalidate는 3대 고정(§5-3), Validator도 3대만 받는다(U-25) |

## 5. 인터페이스 (제안)

### 5-1. 모듈

```
src/waam/strategy.py     # Task(조각)·Cell 값 객체, Assigner/Scheduler 프로토콜 (operations.md §6-2)
src/waam/pieces.py       # 조각 분할: split_at_reach(), split_at_sectors()
src/waam/sector.py       # 섹터 경계·소유 로봇·δ 후보·phi_max (순수 함수, n·base는 인자)
src/waam/standby.py      # 대기 위치 ρ 계산(B7), 종료 주차 후보(B9)
src/waam/assign.py       # HandoverAssigner(S, B13), SectorAssigner(P, B16~B19)
src/waam/schedule.py     # SerialHandoverScheduler(S), EventScheduler(P) — 층 동기화·try_append 루프
src/waam/baseline.py     # run_baseline(stack, cfg) -> BaselineResult (포트폴리오 B23)
```

`strategy.py` 프로토콜은 `docs/operations.md` §6-2의 `Assigner.assign(tasks, cell) -> dict[int, list[Task]]`를 따른다. **차이:** `Scheduler.schedule`은 operations의 `list[Segment]` 대신 `ScheduleResult(chains: dict[int, list[Segment]], timelines, makespan_s, notes)`를 돌려준다(writer가 `timelines`를 요구하기 때문, 확정: `write_trajectory(path, chains, rules, timelines)`).

### 5-2. 주요 시그니처 (제안)

```
Cell.from_config(cfg) -> Cell                      # n, base_xy, reach, home, origin, TimingParams, ToolpathParams, geometry
split_at_reach(passes, cell) -> list[Task]         # B3
sector_bounds(cell, delta_rad=0.0) -> SectorSpec   # B16 (경계 각도, 로봇 순서, 반폭)
split_at_sectors(passes, cell, spec) -> list[Task] # B17~B18 (task.owner 포함)
phi_max(cell, r_max) -> list[float]                # C-43 식
standby_positions(cell, passes) -> dict[int, tuple[float, float]]   # B7
HandoverAssigner(cell).assign(tasks, cell) -> dict[int, list[Task]]
SectorAssigner(cell, delta_rad=0.0 | "auto").assign(tasks, cell) -> dict[int, list[Task]]
SerialHandoverScheduler().schedule(assignment, cell) -> ScheduleResult
EventScheduler().schedule(assignment, cell) -> ScheduleResult
run_baseline(stack, cfg, *, params=None) -> BaselineResult   # 선택된 chains, timelines, 후보 정보
```

### 5-3. 재사용과 3대 고정 처리 (확정: 소스 확인)

| 재사용 | 비고 |
|---|---|
| `timing.TimingParams.from_config`, `Step`, `build_chain` | 조각 = `Step("pass")`, 이동 = `Step("travel")`, 대기 = `Step("wait")`. 변경 없음 |
| `prevalidate.PrevalidateRules.from_config`, `new_timelines`, `try_append`, `close_timeline`, `check_hold`, `check_all`, `require_submittable`, `Timeline.pop_last` | 후퇴 시 `pop_last`로 되돌린다(확정: `Timeline.pop_last` 존재). 변경 없음 |
| `writer.write_trajectory` | 변경 없음 |
| `geometry.in_reach`, `pair_collides`, `CellGeometry` | n을 `len(g.base_xy)`로 읽는다 |
| `toolpath.generate`, `lower_bound` | 변경 없음 |

3대를 가정하는 곳(확정, 소스):

| 위치 | 내용 | 처리 방안 |
|---|---|---|
| `geometry.reachable_mask` | `for rid in (1, 2, 3)` | **방안 1(기본값 후보):** `range(1, len(g.base_xy) + 1)`로 일반화(3대에서 결과 동일, 기존 테스트 불변, 2·4대 테스트 추가). **방안 2:** 변경 없이 baseline에서 `in_reach`를 로봇 수만큼 직접 호출(toolpath가 이미 그렇게 함). R3 |
| `prevalidate.new_timelines`·`try_append`·`close_timeline` 등 | 튜플 3개, `for other in (1, 2, 3)` | 이 명세는 바꾸지 않는다. 체인 조립은 3대 cell에서만 동작. 2·4대 cell은 섹터·도달·대기 위치(순수 함수)까지만 지원하고 테스트한다. 체인 일반화는 별도 결정 |
| `segment.Segment`·`check_chain` | `robot_id ∈ {1, 2, 3}` | 위와 같음 |
| `toolpath` 캐시 | 로봇 수 상한 8 | 근거 없는 상한(PROGRESS 열린 항목). 영향 없음 |

### 5-4. prevalidate의 "다른 로봇이 먼저 끝난 타임라인" 처리 (소스 확인, 작업 25)

| 위치 | 확인 결과 |
|---|---|
| `src/waam/prevalidate.py:374-376` `_known_until` | 열린 타임라인(`closed` 아님, `hold_open` 거짓)은 확정한 끝 시각 `end_time`까지만 위치가 알려진 것으로 본다. 닫혔거나 `hold_open`이면 무한히(마지막 위치 유지) |
| `prevalidate.py:379-393` `check_pair(..., hold_open=False)` | `t_to = min(t_to, _known_until(a), _known_until(b))`(388행), `t_to < t_from`이면 검사 없이 OK(389행) → **한 타임라인이 제안 구간보다 먼저 끝났으면 그 구간은 검사하지 않는다** |
| `prevalidate.py:421-448` `try_append` | 다른 로봇과의 검사는 `check_pair(rules, tl, timelines[other - 1], seg.start_time_s, seg.end_time_s)`(444행)로 **`hold_open` 없음** → 다른 열린 타임라인의 마지막 위치 유지는 검사하지 않는다. 닫힌 타임라인(`close_timeline` 후)만 유지로 검사된다 |
| `prevalidate.py:396-418` `check_hold` | "robot_id가 xy에 t_from부터 영원히 머무는 것이 안전한가"를 다른 로봇의 확정 구간(열린 것은 `end_time`까지, 닫힌 것은 무한) 기준으로 검사한다. 대기 후보·종료 주차 후보 검사용 |
| `prevalidate.py:496-507` `check_all` | 마지막에 모든 쌍을 `hold_open=True`로 검사(506행) → try_append가 통과시킨 유지 충돌이 **최종 `check_all`·`require_submittable`에서 뒤늦게 실패**할 수 있다 |

결론(확정): `try_append`만으로는 부족하다. B20·B14의 `append_checked`는 `try_append` 성공 뒤에 끝 시각이 이 구간 끝보다 이른 열린 타임라인마다 `check_pair(rules, 내 타임라인, 그 타임라인, seg.start_time_s, seg.end_time_s, hold_open=True)`를 추가로 부른다(`prevalidate` 변경 없음, 공개 함수만 사용). 실패하면 `Timeline.pop_last()`로 되돌린다. `close_timeline`된 타임라인은 `try_append`가 이미 유지로 검사하므로 중복이지만 무해하다.

## 6. 실패 처리

| 분류 | 판별 | 처리 |
|---|---|---|
| 한 전략의 `try_append` 실패(S) | B15 | S 실패, 이유 기록, P 후보만 |
| P 교착 | B22 | 기본값 후보 (a): P 실패 |
| 두 전략 모두 실패 | B23 | 예외, 결과 없음(출력 만들지 않음) |
| `check_all`·`require_submittable` 실패 | B10 | 그 전략 실패 |
| 대기 위치 없음 | §4 | base 위치 시도, 실패면 전략 실패 |
| 도달 불가 조각(어떤 로봇도 못 닿음) | B3 분할 후에도 비어 있음 | 예외(toolpath가 이미 workspace 검사를 함) |

## 7. 의사코드

### 7-1. 전략 S

```
run_S(passes, cell):
  tasks ← split_at_reach(passes, cell)                       # B3
  stand ← standby_positions(cell, passes)                    # B7 (hull)
  tl ← new_timelines(); pos ← {r: home(r)}; cur ← None       # cur: 현재 작업 로봇
  for layer in layers(tasks):
    todo ← tasks_of(layer) in toolpath canonical order
    while todo nonempty:
      if cur is None or no task in todo is reachable by cur:
        cur' ← argmax over r of reach_len(r, todo)           # 동률: id 작은 쪽, B13
        if cur is not None: retreat(cur → stand[cur])        # B14: 대기 도착 뒤 다음 로봇 출발
        cur ← cur'
      for task in [t in todo if cur in t.reach] (canonical order):
        steps ← transit(pos[cur] → task.start, B4) + [Step("pass", task)]
        for seg in build_chain(cur, pos[cur], steps):
          if not append_checked(seg).ok: return FAIL(verdict)  # B15, B20 ①②
        pos[cur] ← task.end; todo.remove(task)
    # 층 끝: 한 로봇만 일하므로 층 동기화 자동 충족 (B6). 다음 층도 cur로 시작
  finish(): 마지막 작업 로봇은 제자리 종료, 나머지는 B9 (a)/(b), close_timeline 전부
  return ScheduleResult(chains, tl)
```

### 7-2. 전략 P

```
run_P(passes, cell, delta):
  spec ← sector_bounds(cell, delta)                           # B16
  tasks ← split_at_sectors(split_at_reach_if_needed(passes), cell, spec)   # B17, B18
  queues ← {r: sort(tasks of r, 바깥→안, B19)}
  stand ← standby_positions(cell, passes)
  tl ← new_timelines(); pos ← {r: home(r)}; end ← {r: 0}
  for layer in layers:
    todo ← {r: queue[r] ∩ layer}
    while any(todo[r] nonempty):
      r ← argmin over robots with todo[r] nonempty of (end[r], id)       # 가장 이른 가용 로봇
      task ← todo[r][0]
      segs ← build_chain(r, pos[r], transit + pass)
      ok ← append_all(segs)                                     # try_append, 실패 시 pop_last로 되돌림
      if ok: todo[r].pop(0); update pos[r], end[r]
      else:                                                     # C-44
        retreat(r → stand[r]) ; t_next ← min{end[q] : q != r unfinished, end[q] > end[r]}
        if t_next 없음: return FAIL(deadlock)                   # B22 (a)
        wait(r until t_next)
    t_layer ← max(end[r])                                       # B6
    for r in robots: retreat(r → stand[r]); wait(r until t_layer)
  finish() ; return ScheduleResult(chains, tl)
```

### 7-3. 포트폴리오

```
run_baseline(stack, cfg):
  cell ← Cell.from_config(cfg); tp ← toolpath.generate(stack, cfg, use_cache=False)
  cand ← []
  for name, runner in (("S", run_S), ("P", run_P)):            # 순서 고정
    res ← runner(tp.passes, cell)
    if res is OK and check_all(res.timelines).ok: cand.append((makespan(res), name, res))
  if cand empty: raise BaselineError(실패 이유들)
  best ← min(cand, key = (makespan, name != "S"))             # 동률이면 S
  require_submittable(best.timelines)                          # 쓰기 전 게이트 (write_trajectory 내부)
  return BaselineResult(best.name, best.chains, best.timelines, candidates=cand)
```

## 8. 테스트 목록

공통: Validator 없이 prevalidate까지. 느린 테스트(04·05)는 `slow` 표시하고 회귀·최종에만. 이름은 제안이다.

| ID | 이름 | 한 줄 기준 |
|---|---|---|
| T-B01 | `test_baseline_reads_everything_from_config` | 로봇 수·base·속도·아크 값이 config에서만 오고, 같은 코드가 값을 바꾼 가짜 config에서 달라진 결과를 낸다 |
| T-B02 | `test_piece_reachable_set_is_vertex_intersection` | 조각의 도달 집합이 꼭짓점별 도달의 교집합이다 |
| T-B03 | `test_empty_reach_pass_is_split_at_reach_boundary` | 도달 집합이 빈 패스(합성)가 분할되고 각 조각의 도달 집합이 비지 않으며 길이 합이 보존된다 |
| T-B04 | `test_transit_between_pieces_is_lift_horizontal_descend` | 조각 사이 이동이 P6 규칙이고 같은 점이면 이동이 없다 |
| T-B05 | `test_every_robot_starts_at_home_at_time_zero` | 세 로봇 모두 첫 시각 0.0, 위치 home |
| T-B06 | `test_layer_synchronization_invariant` | 층 k+1의 어떤 D·T 시작도 층 k의 마지막 D·아크 종료 이후다(C-15 메모의 불변식) |
| T-B07 | `test_standby_position_is_collision_free_against_reachable_vertices` | 대기 위치가 B7 조건을 만족하고 ρ−1은 만족하지 않거나 ρ = 0이다 |
| T-B08 | `test_idle_robot_waits_at_standby` | 일 없는 로봇의 W 위치가 대기 위치다 |
| T-B09 | `test_parking_rules_after_finish` | (a) 작업 없는 로봇은 home 후보에 W 하나, (b) 마지막 로봇은 이동 없이 종료 |
| T-B10 | `test_all_timelines_closed_and_submittable` | 선택된 체인이 `close_timeline`·`check_all`·`require_submittable`을 통과한다 |
| T-B11 | `test_same_input_twice_gives_byte_identical_csv` | 같은 입력 두 번 → 바이트 동일 CSV |
| T-B13 | `test_handover_processes_current_robot_pieces_first_then_hands_over` | S에서 현재 로봇이 닿는 층 조각을 정준 순서로 모두 처리한 뒤에만 인계하고, 층당 인계 ≤ 필요 로봇 수 − 1이며 인계 대상은 남은 닿는 길이 최대(동률 id 작은 쪽)다 |
| T-B14 | `test_serial_strategy_never_has_two_robots_on_part` | S에서 두 로봇의 부품 위 구간이 시간상 겹치지 않는다 |
| T-B15 | `test_sector_functions_read_robot_count_from_config` | 2대·4대 가짜 config(`SimpleNamespace`)에서 섹터 수·경계가 로봇 수를 따른다 |
| T-B16 | `test_no_robot_count_or_angle_constants_in_strategy_modules` | 전략 모듈 AST에서 로봇 id·`len(robots)`·각도 변수와의 비교, `range(1, 4)`·`(1, 2, 3)` 같은 로봇 수·각도 맥락의 상수 리터럴(3·60·120·180 등)이 없다. 일반 숫자(길이·시간·tol)와 문자열은 검사하지 않는다 |
| T-B17 | `test_serial_strategy_failure_is_reported_not_hidden` | `try_append` 실패를 주입하면 S가 실패로 표시되고 이유가 남는다 |
| T-B18 | `test_sector_bounds_are_bisectors_of_neighbor_directions` | 공개 config에서 경계가 0°·120°·240° 근처(δ=0)이고 비대칭 base에서 이등분선이다 |
| T-B19 | `test_sector_split_counts_and_length_conservation` | 분할 뒤 길이 합이 보존되고 조각 수가 M6 산술(합성 직선·고리)과 같다 |
| T-B20 | `test_public_config_sector_fallback_is_never_triggered` | 공개 config 6모델에서 폴백 발동 0(δ=0과 δ 격자 전체) |
| T-B21 | `test_sector_piece_order_is_outer_to_inner` | 섹터 안 조각 순서가 중심 거리 내림차순이다 |
| T-B22 | `test_event_scheduler_retreats_to_standby_on_collision` | 충돌을 유발하는 합성 입력에서 후퇴 W가 들어가고 최종 `check_all`이 ok다 |
| T-B23 | `test_event_scheduler_reports_deadlock` | 교착 합성 입력에서 P가 실패로 표시된다 |
| T-B24 | `test_portfolio_selects_smaller_makespan_ties_to_serial` | 합성 후보 두 개로 작은 쪽, 동률 S를 고른다. 선택이 입력 외 요소에 의존하지 않는다 |
| T-B25 | `test_portfolio_records_both_candidates_and_choice` | 선택 이름·두 makespan·실패 이유가 결과에 있다 |
| T-B26 | `test_compute_time_covers_both_strategies` | compute_s ≥ 두 전략 시간의 합(슬라이싱 제외) |
| T-B27 | `test_six_models_pass_require_submittable` (slow) | 6모델 모두 포트폴리오 결과가 `require_submittable`을 통과한다 |
| T-B28 | `test_models_01_06_makespan_not_below_serial_work_bound` | 01·06에서 makespan ≥ M8의 W(산술: ΣD/v + 아크 × 패스 수) |
| T-B29 | `test_geometry_reachable_mask_generalized_to_n_robots` | 방안 1 채택 시: 2·4대 geometry에서 `(N, n)` 마스크, 3대는 기존 결과와 동일 |

측정·보고 항목(테스트 아님, R4): 06에서 S의 prevalidate 통과 makespan과 탐침 6174.838943466003 s의 차이, 6모델 S·P 각각의 makespan·compute 시간·교착 발생 횟수·후퇴 횟수.

## 9. 가설과 검증

| 가설 | 검증 |
|---|---|
| 01·06에서는 S가 P 이상이다(동시 작업 불가 산술) | 6모델 포트폴리오 결과(측정 항목) |
| 04·05에서는 P가 S보다 짧다(전용 영역·섹터 부하 균형) | 같음 |
| 섹터 폴백은 공개 config에서 발동하지 않는다 | T-B20, M6 실측 0 |
| M7 대기 위치는 부품 위 D 위치만 고려하므로 이동 중 충돌은 prevalidate가 잡아야 한다 | 후퇴 횟수 측정 |
| 대기 위치 z = 층 z + Δz가 home z(1000)보다 T 시간이 짧다(산술상) | 측정 항목 |

## 10. 미결 항목 (분류 R1~R6)

R1 기존 결정 고정 / R2 Validator 식 / R3 점수 무관 자동 / R4 기본값 자동 + 측정 후 재검토 / R5 사람 / R6 PASS 여유 큰 쪽.

| # | 항목 | 분류 | 기본값 후보 | 비고 |
|---|---|---|---|---|
| U-1 | 층 동기화 | R1 | 유지 | C-23 |
| U-2 | 아크 W | R1 | 조각마다 arc_on + arc_off | C-09 |
| U-3 | 리프트 Δz | R1 | `lift_dz_mm`(가설값 4 mm) | C-32 |
| U-4 | 속도 | R1 | 공칭 8 / 150 | C-33 |
| U-5 | 포트폴리오 선택 | R1 | 작은 makespan, 동률 S | C-42 |
| U-6 | 섹터 정의 | R1 | base 각도 기준 이등분선 | C-43 |
| U-7 | 경계 충돌 | R1 | 대기 후퇴 + 바깥→안 | C-44 |
| U-8 | `reachable_mask` 일반화 | R3 | 방안 1 | §5-3 |
| U-9 | 도달 경계 분할 교점 | R2 | `d ≤ R + eps`와 일치하는 원-선분 교점 | Validator 식 |
| U-10 | 닫힌 고리 첫·마지막 조각 합침 | R3 | 합침 | 스트라이크 감소, 결과 영향은 M6로 측정 |
| U-11 | 결정적 동률 처리 | R3 | id·조각 번호 작은 쪽 | B11 |
| U-12 | 부품 중심 정의 | R3 | 전 층 D 꼭짓점 경계상자 중심 | B19 |
| U-13 | 대기 위치 z | R4 | 층 z + Δz | home z와 측정 비교 |
| U-14 | 대기 반경 여유 | R4 | `float32_buffer_mm`(공개 config 0.001 mm)만, 1 mm 해상도 ρ_min (B7) | prevalidate 거부율 측정 후 |
| U-15 | 섹터 안 순서 | R4 | 바깥→안, 열린 조각은 가까운 끝점부터 | 최근접 밴드 방식은 측정 후 |
| U-16 | 회전 δ | R4 | 측정 전 0, 이후 C-43 자동(2° 격자) | M6(b) 값 참조 |
| U-17 | P 교착 처리 | R4 | (a) P 실패 | 발생 빈도 측정 후 |
| U-18 | 후퇴 재시도 횟수 | R4 | 조각당 n−1(가설) | 측정 후 |
| U-19 | 열린 조각 방향 선택 | R4 | 가까운 끝점부터 | B4 |
| U-20 | S 인계 진입 시점 | R4 | 이전 로봇 대기 도착 후 | 겹침 허용 변형은 측정 후 |
| U-21 | `ScheduleResult` 반환형(operations.md와 차이) | R3 | `chains + timelines` | §5-1 |
| U-22 | `algo` 문자열 | R3 | `baseline_portfolio` (`notes`에 선택 전략) | |
| U-23 | 시작 위치 | R1 | home | probe A2·D6 |
| U-24 | 종료 주차 (작업 없는 로봇) | R1 | probe A2 후보 | |
| U-25 | 체인 일반화(2·4대 prevalidate) | R2 | **종결: 하지 않음.** Validator `config/models.py:90` `robots: tuple[RobotConfig, RobotConfig, RobotConfig]`, `:99-101` `sorted(ids) != [1, 2, 3]`이면 거부 → Validator가 정확히 3대만 받는다(C-22 L-5, 작업 6). 비공개 모델도 3대이고 일반화 대상은 base 위치뿐이다(섹터 규칙 B16이 처리). 섹터·도달·대기 위치 순수 함수만 n을 config에서 읽고 테스트한다(T-B15) | Validator 식 |
| U-26 | S·P 각각을 Validator에 돌려 results.csv 비교군으로 남길지 | → C-21(run_all 설계)로 이월 | 기본: 비교군 기록(CLAUDE.md "새 전략을 추가할 때 기존 전략을 지우지 않는다"), 비용은 04·05 Validator 시간 측정 후 정한다 | 이 명세에서 결정하지 않음 |
| U-27 | 종료 주차 (일을 끝낸 로봇) | R6 | **자동:** (b) 일을 끝낸 로봇은 B7 대기 위치에서 W 유지(B8 규칙상 제자리 `check_hold`가 통과하면 제자리), 마지막으로 끝나는 로봇은 제자리 종료. 근거: makespan에 주차 T를 넣지 않으므로 makespan 영향 없음, 대기 위치는 충돌 여유가 가장 크다 | 지시문 "probe A2 규칙"은 작업 없는 로봇(B9 (a))에 적용 |
| U-28 | 대기 위치에서 층 사이 z 변화 | R4 | U-13과 같이 | |

R5 잔여: 없음. (작업 25: U-25 → R2 종결, U-26 → C-21 이월, U-27 → R6 자동.)

## 11. 작업 25 수정 6건 (근거 한 줄씩)

| # | 수정 | 근거 |
|---|---|---|
| 1 | B7 대기 위치를 hull 방식(A_j = conv({base_j} ∪ conv(K_j)))으로. M7′ 재측정은 `design_inputs_3stage.md` §13 | 꼭짓점 사이 선분 위 TCP와 j의 부품 안 이동까지 포함(볼록성), 6모델 18로봇 모두 M7′ ≥ M7 |
| 2 | B14·B20: `append_checked`(`try_append` + 마지막 위치 유지 `check_pair(hold_open=True)`) | §5-4: `try_append`는 `hold_open` 없이 호출(444행)해 먼저 끝난 열린 타임라인의 유지를 검사하지 않는다 |
| 3 | B8·B21: 제자리 `check_hold` 통과면 제자리, 아니면 B7 후퇴(R4, 후퇴 횟수 측정) | 불필요한 이동 T 제거, 안전은 prevalidate가 보증 |
| 4 | B13·7-1·T-B13: 현재 로봇이 닿는 조각을 모두 처리한 뒤 인계 반복(인계 ≤ 필요 로봇 수 − 1) | 인계마다 후퇴·진입 이동과 대기 도착 대기가 든다 |
| 5 | T-B16: 로봇 수·각도 맥락 상수만 금지하는 AST 검사 | 리터럴 전면 금지는 길이·시간·tol 같은 무관한 수까지 막는다 |
| 6 | §0: M7 범위를 305~559 mm로 정정, M7′ 범위 307~559 mm 병기 | 이전 문구 "305~468"은 05(558~559)를 빠뜨린 오류였다 |
