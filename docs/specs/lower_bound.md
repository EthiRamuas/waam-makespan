# lower_bound.py 명세 (확정, 2026-10-10)

상태: **명세 확정** (DECISIONS.md C-22). 사람의 ★4 승인(야간 큐 올리기 전 마지막 승인)은 아직 받지 않았다 — 프롬프트 4에서 받는다. 구현하지 않았다.
이 파일과 `docs/spec.md`가 어긋나면 `docs/spec.md`가 맞다.
근거: `docs/spec.md` §6(하한 정의와 표), `CLAUDE.md`(성능 지표), 이번에 한 읽기 전용 측정(§5).

## 1. 역할

`ratio = makespan / 이론 하한`의 분모를 만든다. `results.csv`의 `lower_bound_s`(초 단위)로 들어간다.
**`slicing.py`의 층 단면적에만 의존한다. toolpath(3단계)와 무관하다.** 따라서 slicing 다음에 만들 수 있고, 그때부터 ratio를 측정할 수 있다. 순수 함수 부분은 slicing 없이도 만들 수 있다 (L-2).

## 2. 정의 (docs/spec.md §6)

```
중심선 길이 Σ  ≈ Σ_k 단면적_k ÷ 비드폭          (완전 채움 가정의 근사)
총 적층시간    = 중심선 길이 Σ ÷ 적층속도
이론 하한      = 총 적층시간 ÷ 로봇 수           (완벽한 부하균형 + 이동 0 + 대기 0)
```

- 비드폭, 적층속도는 config에서 읽는다 (`process.bead_width_mm`, `process.deposition_speed_mm_s`). **로봇 수는 `len(config.robots)`에서 읽는다 (L-3).** 숫자를 코드에 박지 않는다.
- **단위는 초.** spec.md 표는 시간(h)이다. 변환은 이 모듈 안에서 한다.
- 아크 시간은 하한에 **포함하지 않는다**(spec 표와 같다). 우리 makespan에는 아크가 들어 있으므로 ratio에는 아크 오버헤드가 포함된다. 이 점은 보고서에서 밝힌다. 아크 하한(스트라이크 수 기준)은 toolpath 이후로 미룬다 (L-4).
- **CLAUDE.md의 6개 하한값(01 0.08 …)을 `src/`에 상수로 넣지 않는다** (모델 하드코딩). 그 값은 테스트의 오라클 데이터일 뿐이다.

## 3. 인터페이스 (확정)

```python
@dataclass(frozen=True)
class LowerBound:
    total_area_mm2: float
    centerline_mm: float
    deposition_s: float          # 총 적층시간
    n_robots: int
    lower_bound_s: float         # = deposition_s / n_robots

lower_bound_from_areas(areas_mm2: Sequence[float], *, bead_width_mm, deposition_speed_mm_s,
                       n_robots) -> LowerBound            # 순수 함수, slicing 불필요 (L-2)
lower_bound(stack: LayerStack, config) -> LowerBound      # slicing 이후의 얇은 래퍼, n_robots = len(config.robots) (L-3)
```

- 래퍼의 `config`는 Validator config **또는** `.robots`(길이를 가진 시퀀스)와 `.process.bead_width_mm`, `.process.deposition_speed_mm_s`를 가진 객체이다 (L-5). 근거: Validator `config/models.py`의 `robots`는 정확히 3대만 받으므로 2대/4대 경로는 Validator config로 만들 수 없다(작업 6 확인).
- 입력 검증: 면적은 유한하고 0 이상, 비드폭·속도·로봇 수는 양수. 위반은 `ValueError`. 면적 합이 0이면 하한이 0이 되어 ratio를 만들 수 없으므로 `ValueError`.
- 반환의 `lower_bound_s`가 `results.make_row(lower_bound_s=...)`에 그대로 들어간다.
- 위치: `src/waam/lower_bound.py` (CLAUDE.md 아키텍처에 이미 있음).

## 4. 한계 (명세와 보고서에 명시한다, L-1)

이 하한은 **완전 채움 가정의 근사 정의**이고 Validator가 증명하는 값이 아니다.

- Validator의 전체 형상 기준 중 구속 조건은 전체 IoU ≥ 0.9다(C-24 확인). 덜 채우고 넘치지 않으면 IoU = coverage이므로 최소 채움 비율은 0.90이고, coverage ≥ 0.80은 구속하지 않는다. 따라서 형상을 덜 채우면 makespan이 이 하한 아래로 내려가 ratio < 1이 가능하다(면적 기준 이론상 약 0.9배, 이동·아크는 줄지 않으므로 실제 폭은 더 작다 — 가설, C-24). CLAUDE.md의 "1.0은 물리적으로 불가능하다"는 *완전 채움*일 때만 참이다.
- 이 한계는 구현에서 숨기지 않는다: `ratio`는 정의 그대로 계산하고, 값이 1 미만이어도 clamp하거나 거부하지 않는다.
- coverage를 낮추는 전략을 쓸지는 열린 전략 안건(C-24)이며 데드라인은 3단계 toolpath 설계 시작 전이다. 이 명세와 구현은 그 결정과 무관하다(ratio 정의 고정).

**보고서에 쓸 항목 (문구 초안)**
> ratio = makespan ÷ 이론 하한. 하한은 완전 채움을 가정한 근사(Σ단면적 ÷ 비드폭 ÷ 적층속도 ÷ 로봇 수)이며 아크 시간을 포함하지 않는다. Validator의 형상 기준(coverage·overfill·IoU)을 만족하는 범위에서 덜 채우면 makespan이 이 하한보다 작아질 수 있으므로 이 하한은 증명된 하한이 아니다. ratio가 1 미만이면 형상 충실도(coverage)를 먼저 확인한다.

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

- 층수, 중심선 합, 총 적층시간, 하한이 spec.md §6 표의 모든 열과 반올림 범위 안에서 일치한다. 로봇 수는 6개 config 모두 3, 비드폭 8.0, 적층속도 8.0.
- 부피 상대오차 (Σ면적×h vs `mesh.volume`): 01·02·03·04·06은 0.0000%, 05는 +0.0007%. 기록용이며 판정에 쓰지 않는다 (slicing C-18 결정 5).

**모델 05 (두 번 측정: 표 작성 때와 이 갱신 때, 같은 결과)** — Validator 함수 결과, 우리 구현 아님
- 면 108,288개, z 범위 0.0 ~ 700.0 mm, 350층, 빈 층 0개, 층 단면적 최소/최대 = 35,895.0 / 55,005.6 mm².
- Σ단면적 15,543,072.6076 mm² → 중심선 1,942,884.08 mm → 총 적층 242,860.51 s (67.461 h) → **하한 80,953.5032 s (22.4871 h)**. spec 표의 22.5 h와 반올림 범위 안에서 일치.
- 소요 시간: 메시 로드 0.68 s + 350층 슬라이싱 4.16 s (Validator 함수, 이 머신, 1회 측정). 우리 구현의 시간이 아니다 (미측정).

## 6. 테스트 오라클

1. **합성**: 면적 `[800, 800]`, 비드폭 8, 속도 8, 로봇 3 → 중심선 200 mm, 적층 25 s, 하한 8.333… s. 로봇 수 2로 바꾸면 12.5 s (로봇 수가 상수 3이 아님을 확인).
2. **측정값 대조**: slicing 구현 후 모델 01~06의 `lower_bound_s`가 §5 표의 초 값과 일치 (상대오차 1e-9: 같은 면적에 같은 식을 적용하므로 slicing이 Validator와 일치하면 사실상 정확히 같다). 동시에 spec 표 값(h)과는 표의 유효숫자 반올림 범위로 일치. 모델 05는 80,953.5032 s.
3. **입력 검증**: 음수·NaN·inf 면적, 0 이하의 비드폭·속도·로봇 수, 면적 합 0 → 모두 `ValueError`.
4. **단위**: 반환값이 초이고 1 h = 3600 s 변환이 모델 05에서 맞음 (80,953.5 s ≠ 22.487 s).
5. **하드코딩 금지 확인**: `src/waam/lower_bound.py`에 모델별 상수(0.08, 0.18 …)가 없음을 테스트가 grep으로 단언.
6. **`results.make_row`와 연결**: ratio = makespan / lower_bound_s가 `ResultRow` 불변식을 만족. ratio < 1인 입력(예: makespan이 하한보다 작은 합성 값)도 거부 없이 기록된다 (L-1).
7. **로봇 수 출처**: 테스트에서 위 속성만 가진 대체 객체(예: `SimpleNamespace`)로 로봇 2대/4대를 만들어 래퍼가 `len(config.robots)`를 쓰는지 확인한다. 실제 Validator config(3대)로 한 번 더 확인한다.

## 7. 결정 (DECISIONS.md C-22)

- **L-1** 정의 그대로 구현한다. 한계(완전 채움 가정, coverage 80%면 PASS하므로 ratio<1 가능)를 명세(§4)와 보고서 항목에 명시한다. coverage 활용은 별도 전략 결정(C-24)으로 남긴다.
- **L-2** 순수 함수(`lower_bound_from_areas`)와 래퍼(`lower_bound`)로 분할한다.
- **L-3** 로봇 수는 `len(config.robots)`에서 읽는다.
- **L-4** 아크 하한은 toolpath 이후로 미룬다.
- **L-5** (등급 A, 시그니처 불변·테스트 한정) 래퍼의 `config`는 Validator config 또는 `.robots`(길이를 가진 시퀀스)와 `.process.bead_width_mm`, `.process.deposition_speed_mm_s`를 가진 객체다. 오라클 7은 대체 객체(2대/4대) + 실제 Validator config(3대)로 한다. 근거: Validator `config/models.py`의 `robots`가 정확히 3대만 받는다 (작업 6 확인).
- C-21(config·target sha 대조)은 run_all 설계 때 결정한다.

## 8. 완료 기준 / 중단 조건

완료 (자동 판정)
- §6의 1·3·4·5는 slicing 없이 통과 (순수 함수), 2·6·7은 slicing 이후 통과 (6의 합성 부분은 순수 함수만으로 가능)
- 새 테스트 skip 0, 기존 테스트·fixture 변경 없음, `waam-reviewer` 통과 (탐색 3분 상한)

중단
- 같은 오류 2회 연속
- 오라클 2가 반올림 범위를 넘어 어긋남 (slicing 또는 정의가 틀렸다는 신호: 구현을 맞추려 상수를 만지지 말고 보고)
- `src/`에 모델별 상수가 필요해 보일 때 (금지)

## 9. 야간 큐 자격 (J-1 4조건) — 2026-10-10 재판정

| # | 조건 | lower_bound 순수 함수 | lower_bound 래퍼 | (참고) slicing |
|---|---|---|---|---|
| ① 명세 확정 + 사람의 ★4 승인 | 명세 ✓ / **★4 승인 대기** | 명세 ✓ / ★4 승인 대기 | 명세 ✓ / ★4 승인 대기 | 명세 ✓ (C-18) / ★4 승인 대기 |
| ② 설계 결정 없음 | ✓ (L-1~L-4 소진) | ✓ | ✓ | ✓ (C-18 소진) |
| ③ 자동 판정 가능 | ✓ (오라클 1·3·4·5) | ✓ (오라클 2·6·7은 slicing 필요) | ✓ | ✓ (오라클 1·2·3·4·6) |
| ④ 되돌릴 수 있음 | ✓ | ✓ | ✓ | ✓ |
| **의존** | 없음 | **slicing 구현에 의존** | — | 없음 |

- 판정: ①의 "명세 확정"은 충족했고, **사람의 ★4 승인만 남았다.** 승인 후에는 4조건 모두 ✓이다.
- ② 재판정(L-5 반영 후): **여전히 ✓.** 오라클 7은 이전에 Validator config로는 만들 수 없는 입력(2대/4대)을 요구하는 오류였고, L-5로 구현 선택이 아닌 명세가 되어 남은 설계 결정이 없다.
- 순서: 순수 함수는 의존이 없어 slicing보다 먼저 올릴 수 있다. 래퍼는 slicing 뒤에만 올릴 수 있다 (같은 야간 큐에 둘 다 올리면 slicing → 래퍼 순서).
- 구현 시간은 **미측정**이다 (1단계 속도를 환산하지 않는다).
