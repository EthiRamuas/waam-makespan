# lower_bound.py 명세 (2026-10-10, 구현하지 않음)

상태: **명세 초안 — 결정 대기 항목(§7)이 있다.** 이 파일과 `docs/spec.md`가 어긋나면 `docs/spec.md`가 맞다.
근거: `docs/spec.md` §6(하한 정의와 표), `CLAUDE.md`(성능 지표), 이번에 한 읽기 전용 측정(§5).

## 1. 역할

`ratio = makespan / 이론 하한`의 분모를 만든다. `results.csv`의 `lower_bound_s`(초 단위)로 들어간다.
**`slicing.py`의 층 단면적에만 의존한다. toolpath(3단계)와 무관하다.** 따라서 slicing 다음에 만들 수 있고, 그때부터 ratio를 측정할 수 있다.

## 2. 정의 (docs/spec.md §6)

```
중심선 길이 Σ  ≈ Σ_k 단면적_k ÷ 비드폭          (완전 채움 가정의 근사)
총 적층시간    = 중심선 길이 Σ ÷ 적층속도
이론 하한      = 총 적층시간 ÷ 로봇 수           (완벽한 부하균형 + 이동 0 + 대기 0)
```

- 비드폭, 적층속도, 로봇 수는 config에서 읽는다 (`process.bead_width_mm`, `process.deposition_speed_mm_s`, `len(robots)`). 숫자를 코드에 박지 않는다.
- **단위는 초.** spec.md 표는 시간(h)이다. 변환은 이 모듈 안에서 한다.
- 아크 시간은 하한에 **포함하지 않는다**(spec 표와 같다). 우리 makespan에는 아크가 들어 있으므로 ratio에는 아크 오버헤드가 포함된다. 이 점은 보고서에서 밝힌다.
- **CLAUDE.md의 6개 하한값(01 0.08 …)을 `src/`에 상수로 넣지 않는다** (모델 하드코딩). 그 값은 테스트의 오라클 데이터일 뿐이다.

## 3. 인터페이스 (제안)

```python
@dataclass(frozen=True)
class LowerBound:
    total_area_mm2: float
    centerline_mm: float
    deposition_s: float          # 총 적층시간
    n_robots: int
    lower_bound_s: float         # = deposition_s / n_robots

lower_bound_from_areas(areas_mm2: Sequence[float], *, bead_width_mm, deposition_speed_mm_s,
                       n_robots) -> LowerBound            # 순수 함수, slicing 불필요
lower_bound(stack: LayerStack, config) -> LowerBound      # slicing 이후의 얇은 래퍼
```

- 입력 검증: 면적은 유한하고 0 이상, 비드폭·속도·로봇 수는 양수. 위반은 `ValueError`. 면적 합이 0이면 하한이 0이 되어 ratio를 만들 수 없으므로 `ValueError`.
- 반환의 `lower_bound_s`가 `results.make_row(lower_bound_s=...)`에 그대로 들어간다.

## 4. 파일/모듈 위치

`src/waam/lower_bound.py` (CLAUDE.md 아키텍처에 이미 있음).

## 5. 측정 (2026-10-10, 읽기 전용 · 실측)

Validator의 `load_target_mesh` + `slice_target_layers`를 scratch 스크립트에서 호출해 층 단면적 합을 구하고 위 정의를 적용했다. 두 레포 모두 수정하지 않았다(Validator `git status` 깨끗). **우리 slicing 구현이 아니라 Validator 함수의 결과다.**

| 모델 | 층수 | Σ단면적 (mm²) | 중심선 Σ (m) | 총 적층 (h) | **하한 (s)** | **하한 (h)** | spec 표 하한 (h) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01 | 6 | 58,420.2 | 7.30 | 0.254 | **304.3** | 0.0845 | 0.08 |
| 02 | 8 | 127,003.8 | 15.88 | 0.551 | **661.5** | 0.1837 | 0.18 |
| 03 | 6 | 98,637.5 | 12.33 | 0.428 | **513.7** | 0.1427 | 0.14 |
| 04 | 50 | 3,330,508.4 | 416.31 | 14.455 | **17,346.4** | 4.8184 | 4.8 |
| 05 | 350 | 15,543,072.6 | 1,942.88 | 67.461 | **80,953.5** | 22.4871 | 22.5 |
| 06 | 51 | 318,060.0 | 39.76 | 1.380 | **1,656.6** | 0.4602 | 0.46 |

- 층수, 중심선 합, 총 적층시간, 하한이 spec.md §6 표의 모든 열과 반올림 범위 안에서 일치한다. 표는 근사 정의이므로 **하한은 Validator가 증명하는 값이 아니다.**
- 로봇 수는 6개 config 모두 3, 비드폭 8.0, 적층속도 8.0.
- 부피 상대오차 (Σ면적×h vs `mesh.volume`): 01·02·03·04·06은 0.0000%, 05는 +0.0007%. (05는 비틀린 형상.) 기록용이며 판정에 쓰지 않는다 (slicing C-18 결정 5).
- 소요 시간 (Validator 함수, 메시 로드 포함): 01 0.07 s, 02 0.24 s, 03 0.05 s, 04 0.54 s, **05 4.74 s**, 06 0.04 s. 우리 구현의 시간은 아니다.

## 6. 테스트 오라클

1. **합성**: 면적 `[800, 800]`, 비드폭 8, 속도 8, 로봇 3 → 중심선 200 mm, 적층 25 s, 하한 8.333… s. 로봇 수 2로 바꾸면 12.5 s (로봇 수가 상수 3이 아님을 확인).
2. **측정값 대조**: slicing 구현 후 모델 01~06의 `lower_bound_s`가 §5 표의 초 값과 일치 (상대오차 1e-9: 같은 면적에 같은 식을 적용하므로 slicing이 Validator와 일치하면 사실상 정확히 같다). 동시에 spec 표 값(h)과는 표의 유효숫자 반올림 범위로 일치.
3. **입력 검증**: 음수·NaN·inf 면적, 0 이하의 비드폭·속도·로봇 수, 면적 합 0 → 모두 `ValueError`.
4. **단위**: 반환값이 초이고 1 h = 3600 s 변환이 모델 05에서 맞음 (80,953.5 s ≠ 22.487 s).
5. **하드코딩 금지 확인**: `src/waam/lower_bound.py`에 모델별 상수(0.08, 0.18 …)가 없음을 테스트가 grep으로 단언.
6. `results.make_row(lower_bound_s=…)`와 연결: ratio = makespan / lower_bound_s가 `ResultRow` 불변식을 만족.

## 7. 명세 밖 결정(B등급) 후보

- **L-1 하한의 의미.** 이 하한은 *완전 채움* 가정이다. Validator는 coverage 80% 이상, overfill 30% 이하면 PASS하므로, 형상을 일부러 덜 채우면 makespan이 이 "하한" 아래(ratio < 1)로 내려갈 수 있다. CLAUDE.md의 "1.0은 물리적으로 불가능하다"는 완전 채움 한정으로만 참이다.
  - 선택지: a) spec 정의 그대로 쓰고 보고서에 "완전 채움 기준, ratio<1은 coverage를 희생한 결과"라고 명시 b) coverage 하한(80%)을 반영한 별도 하한도 함께 기록 c) ratio를 지표에서 빼고 절대 makespan만 쓴다
  - 권고: a — 아크 시간과 같은 이유로 coverage를 줄이는 것은 물리적으로 의미가 없다. 단 results.csv의 PASS 행에 coverage도 남겨 두면 ratio<1이 나올 때 곧바로 의심할 수 있다 (`notes` 또는 컬럼 추가는 별도 결정).
- **L-2 구현 분할.** `lower_bound_from_areas`(순수 함수)를 slicing 없이 지금 만들고 래퍼는 slicing 이후에 만든다 vs 둘 다 slicing 이후. 권고: 분할. 순수 함수는 의존이 없어 바로 구현·검증된다.
- **L-3 로봇 수의 출처.** `len(config.robots)` vs 고정 3. 권고: config (CLAUDE.md의 "6개 모델 전부 동일"은 사양일 뿐 코드의 가정이 아니다).
- **L-4 아크 하한 병기.** spec.md §8-3의 스트라이크 수 하한(윤곽 기준)을 `lower_bound_arc_s`로 같이 제공할지. 권고: 지금은 하지 않는다 (infill이 정해지는 toolpath 이후에 의미가 있다).

## 8. 완료 기준 / 중단 조건

완료 (자동 판정)
- §6의 1·3·4·5는 slicing 없이 통과 (순수 함수), 2와 6은 slicing 이후 통과
- 새 테스트 skip 0, 기존 테스트·fixture 변경 없음, `waam-reviewer` 통과 (탐색 3분 상한)

중단
- 같은 오류 2회 연속
- 오라클 2가 반올림 범위를 넘어 어긋남 (slicing 또는 정의가 틀렸다는 신호: 구현을 맞추려 상수를 만지지 말고 보고)
- `src/`에 모델별 상수가 필요해 보일 때 (금지)

## 9. 야간 큐 자격 (J-1 4조건) — 순수 함수 부분 기준

| # | 조건 | 판정 |
|---|---|---|
| ① | 명세 확정 + ★4 승인 | ✗ L-1~L-3 미결정, ★4 승인 아직 |
| ② | 설계 결정 없음 | ✗ L-1(의미), L-2(분할), L-3(출처) 결정 필요 |
| ③ | 자동 판정 가능 | ✓ |
| ④ | 되돌릴 수 있음 | ✓ |

- L-1~L-3을 정하면 ②가 ✓가 되고, ★4 승인 후 ①도 ✓가 된다. 구현 시간은 미측정(1단계 속도를 환산하지 않는다).
- 순수 함수는 의존이 없어 slicing보다 먼저 야간 큐에 올릴 수 있다.
