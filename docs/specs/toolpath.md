# toolpath.py 명세 (v0)

상태: **확정 (C-37~C-39, 2026-10-10).** 근거: `docs/drafts/toolpath_v0_spec_draft.md`(작업 13 초안, 기록으로 보존·미수정), DECISIONS C-23~C-39, Validator 소스(읽기만). 이 파일과 `docs/spec.md`가 어긋나면 `docs/spec.md`가 맞다.
표기: **확정**(소스·실측·산술) / **가설** / **미측정**. 가설값은 확정 후에도 가설로 표기한다.
변수 번호는 이 파일의 V1~V22만 쓴다(작업 13 지시의 "기본값 n" 번호는 쓰지 않는다).

## 0. 핵심 사실 (실측, 작업 13)

- 모델 01·02·03은 거의 전부가 **두께 = w(8 mm)** 벽이다. opening 반경 3.99 mm에서 잃는 면적 ≤ 0.01%, 4.0 mm(= w/2)에서 01 75.9% / 02 58.4% / 03 85.9%. 04·05는 0%, 06은 0.22%.
- 그래서 윤곽 오프셋 o = w/2는 이 벽에서 중심선으로 퇴화한다 → 두께 ≈ w 벽은 medial 패스로 처리한다(C-38).
- 프로토타입(medial 없음)에서 04·05·06의 완전 채움 총 길이는 하한과 0.02% 안에서 일치했다. 도달 교집합이 빈 패스는 04 40개, 05 700개(05의 윤곽 고리 전부)였다. 상세: 초안 §8.
- 03에서 opening 반경 3.9 mm일 때 면적이 원래보다 커지는 이상치가 나왔다(R1의 자기접촉 홀 근처). shapely 견고성 문제로 추정(가설) → 테스트 14.

## 1. 범위와 모듈 경계

| 하는 것 | 하지 않는 것 | 다음 모듈로 넘기는 것 |
|---|---|---|
| `LayerStack` + config + 파라미터 → 층별 **패스 리스트** | 로봇 할당(assign, H8), 로봇 간 순서·충돌(schedule) | 패스 리스트(정준 순서 포함) |
| 패스 종류: `contour`·`hole`·`hatch`·`medial` | 이동(T)·리프트·대기·아크 W 생성 → **궤적 조립 단계**(탐침 스크립트, 이후 scheduler + `timing.build_chain`) | 리프트 Δz 값(기록만) |
| 패스별 도달 로봇 집합, 발자국, 길이 | 패스 분할(도달 교집합이 빈 패스) → H8 | 도달 교집합이 빈 패스 수 |
| 얇은 영역 손실 면적 측정, workspace 검사, medial 폴백 | 시간 계산(속도는 C-33 공칭, timing 몫) | 층별 손실 면적, 폴백 사실 |
| 결정적 출력 + 캐시 | Validator 호출 | — |

## 2. 고정 조건

| 조건 | 출처 |
|---|---|
| s·o·n_c는 파라미터, 기본값 = 완전 채움(s = w). 기본값 밖의 값은 C-24 결정 전 사용 금지 | C-29 |
| 윤곽 1개 + 내부 평행 해칭, 단면 안에 머무는 연결만, 층간 0°/90° 교대, 출력 = 패스 리스트 | C-32 |
| **o 정의 = I1:** 윤곽 중심선 = P ⊖ o (round join). o = w/2면 비드 외곽이 경계와 일치, o = w/4면 w/4 돌출 | **C-37** |
| **두께 ≈ w 벽 = medial 단일 패스, 자동 폴백 = 같은 선 2회(b)** — §3 V11·V12, §6 | **C-38** (C-32 보정) |
| chord ≤ 0.1 mm, 리프트 Δz = 2h (**가설값**) | C-32 |
| D 비드 외곽 workspace 안: `max(r0, r1) + w/2 ≤ R_ws + ε` (끝점 기준) | C-32, Validator `trajectory/validator.py:76-79`, `geometry.deposition_in_workspace` |
| z는 config에서: center → build + (k+0.5)h, top → build + (k+1)h | C-32, Validator `layer_index.py` |
| 적층 속도 공칭 | C-33 |
| 발자국 = 선분 buffer(w/2), round cap·join, `quad_segs = shape_validation.polygon_buffer_resolution` | Validator `shape/deposition.py:50-57` |
| D 선분: XY 길이 > 0, 구간 Δz ≤ 0.25 | spec §3 |
| 도달 = 모든 꼭짓점의 XY 거리 ≤ `xy_reach_radius_mm` (원판이 볼록이라 꼭짓점 검사로 선분 전체 보장 — 확정) | C-26, spec §4 |
| 입력 단면 = `slicing.slice_stl` | C-18, C-27, C-30 |
| 모델별 상수·분기 금지. 판정은 기하 규칙으로만 | CLAUDE.md, C-28, C-38 |
| 아크는 패스마다 1회(timing이 반영), toolpath는 패스 경계만 정함 | CLAUDE.md 자체 제약 |

## 3. 변수

판정: **고정**(C-xx) / **자동**(R3: 내부 구현, 지표 영향 없음) / **자동·측정 후 재검토**(R4: 기본값 + 파라미터 노출)

| ID | 변수 | 값 | 영향 지표 | 판정 | 재검토 조건 |
|---|---|---|---|---|---|
| V1 | o 정의 | I1 | coverage·overfill·IoU | 고정(C-37) | — |
| V2 | o 값 | **w/2** | overfill·IoU | 자동·측정 후 재검토 | C-31 스윕(w/4) 결과 → C-24 |
| V3 | s | **w** | coverage·IoU·makespan | 고정(C-29) | C-24 |
| V4 | n_c | **1** (바깥 고리 + 구멍 고리 각각) | coverage·스트라이크 | 고정(C-32) | — |
| V5 | n_c > 1일 때 i번째 고리 위치 | o + i·s | coverage | 자동·측정 후 재검토 | — |
| V6 | **해칭 연결** | 연결선 발자국이 단면 P 안에 있으면 직선 연결, 아니면 패스 분할 | overfill·스트라이크·makespan | 자동·측정 후 재검토 | — |
| V7 | 해칭 각 | 짝수 k 0°(+x), 홀수 k 90° | 스트라이크·makespan | 고정(C-32) | 각도 최적화는 4단계 |
| V8 | 해칭 선 위치 | 해칭 영역 H = P ⊖ (o + (n_c−1)·s + w/2). 회전 좌표에서 y_min(H) + s/2 + i·s | coverage·overfill | 자동·측정 후 재검토 | — |
| V9 | 층 안 정준 순서·시작점 | 윤곽(바깥→구멍) → medial → 해칭. 각 단계에서 직전 끝점에 가장 가까운 패스(닫힌 고리는 가장 가까운 꼭짓점에서 시작). 층 0의 첫 시작 기준점 = 사전식 최소 (x, y) 꼭짓점. 다음 층은 직전 층 마지막 끝점 | makespan(T) | 자동·측정 후 재검토 | 순서 최적화는 4단계 |
| V10 | 얇은 영역(두께 < w) | thin = P − opening(P, w/2 − ε_w), **ε_w = 0.01 mm**. 패스 없음, 손실 면적만 기록 | 측정값 | 자동 | 모델별 손실 / 단면 면적 > 0.5%면 사람 |
| V11 | **두께 ≈ w 벽 판정** | W = opening(P, w/2 − ε_w) − opening(P, w/2). W에 닿는 부분은 medial 패스(V12). 모드 `wall_mode ∈ {"medial", "double"}`, 기본 `"medial"` | coverage·IoU·makespan | 고정(C-38) | §6 폴백 |
| V12 | medial 추출 | 경계를 조밀화 → `shapely.voronoi_polygons`의 가장자리 중 P 안이고 경계까지 거리 ≈ w/2인 것 → `line_merge`로 사슬 → 패스. 세부(조밀화 간격, 거리 허용오차, 가지 제거)는 구현자가 R3로 정하고 `ToolpathParams` 필드(기본값, 가설값)로 노출한다. 모듈 상수로 박지 않는다 | coverage(분기점) | 자동 | 테스트 5·13 |
| V13 | 짧은 조각 | 길이 0만 제거. 둘레 고리 중 면적 ≤ `area_epsilon_mm2`인 퇴화 고리도 제거 | 스트라이크 | 자동 | — |
| V14 | 오프셋 모서리 | round join, quad_segs는 chord ≤ 0.1 mm에서 유도 (mitre는 오목 꼭짓점에서 돌출 → overfill, R6로 배제) | overfill | 자동 | — |
| V15 | chord | ≤ 0.1 mm (**가설값**) | 형상(미미, 가설) | 고정(C-32) | 탐침 1회 후 재확인 |
| V16 | 리프트 Δz | 2h (**가설값**), 기록만 | makespan(미미) | 고정(C-32) | — |
| V17 | 도달 로봇 집합 | 꼭짓점 전체 교집합 | 할당 가능성 | 자동(Validator 규칙) | 분할은 H8 |
| V18 | workspace 위반 | `ToolpathError("WORKSPACE_VIOLATION")` raise | PASS | 자동(Validator 규칙) | 발생 시 사람 |
| V19 | 윤곽 방향 | 바깥 CCW, 구멍 CW | 없음 | 자동 | — |
| V20 | 발자국 보관 | Pass 필드로 저장 | 메모리 | 자동 | 05 메모리 문제 시 |
| V21 | 캐시 | 키 = STL sha256 + slicing 파라미터 + `ToolpathParams` 전체 + 로봇 base·reach + workspace + w + h + build_plane + tcp_z_reference + buffer_resolution + `TOOLPATH_VERSION` + 라이브러리 버전 + 소스 sha (C-27c 방식). 위치 `.cache/waam/toolpath/`, 쓰기 실패는 삼킴 | 계산 시간 | 자동 | — |
| V22 | wall_mode 폴백 | §6 | PASS | 고정(C-38) | 전환 시 보고 |

반론 기록(값은 유지): V7은 06 벽 층(x폭 18 mm)에서 0° 해칭이 약 2 mm 조각으로 쪼개진다(프로토타입 614패스, V6 연결 후 수는 미측정). V16은 config의 `safe_travel_z_mm: 1000`이 Validator에서 쓰이지 않는 참조값이고, 1000 mm 리프트는 전환마다 약 13 s(산술)라 2h를 유지한다.

## 4. 경우의 수와 엣지 케이스

| 경우 | 실측 근거 | 처리 |
|---|---|---|
| 섬 여러 개 | 04 최대 4개/층 | 폴리곤별로 같은 절차, 정준 순서(V9)는 층 전체에 적용. 섬 사이 연결 없음 |
| 구멍 | 01 7 · 03 9 · 04 4 · 05 1 (층 최대) | 구멍 고리마다 윤곽 n_c개. 03 자기접촉 홀은 slicing이 홀 2개로 나뉜 유효 폴리곤으로 준다 |
| 두께 < w | ε_w = 0.01에서 최대 06 0.220% | 패스 없음, 손실 기록(V10) |
| **두께 ≈ w 벽** | 01~03 면적의 58~86% | medial(V11·V12), 폴백 b(§6) |
| 두께 > w 영역과 벽이 만나는 곳(01 육각 꼭짓점, Y자 분기) | — | 윤곽·해칭은 P ⊖ o에서, medial은 W에서. 겹침은 P 안이라 overfill이 아니다 |
| 오목 단면 | 06 L자, 01 육각 구멍 | round join(V14), 연결 검사(V6) |
| 해칭 영역 H가 빔 | 좁은 영역 | 윤곽(과 medial)만 |
| 층 간 단면 급변 | 06: 23,940 → 3,420 mm² | 층별 독립. 돌출부 처리는 precedence(4단계) |
| 도달 교집합이 빈 패스 | 04 40, 05 700 | 보고만(V17), 분할은 H8 |
| 빈 층 | 6개 모델 0층 | 패스 없음 |
| `tcp_z_reference: top` | sample_job | Validator 식(§2) |

## 5. 인터페이스

```python
TOOLPATH_VERSION = "toolpath-0"

@dataclass(frozen=True, slots=True)
class ToolpathParams:
    s_mm: float          # 기본 w (C-29)
    o_mm: float          # 기본 w/2 (C-37, I1)
    n_c: int             # 기본 1
    chord_mm: float      # 0.1 (가설값)
    lift_dz_mm: float    # 2h (가설값, 기록만)
    eps_w_mm: float      # 0.01 (V10·V11)
    wall_mode: Literal["medial", "double"]   # 기본 "medial" (C-38)
    # + V12 세부 필드(구현자가 R3로 추가, 기본값은 가설값으로 표기)
    @classmethod
    def from_config(cls, config) -> "ToolpathParams": ...   # w, h는 config에서 읽는다

@dataclass(frozen=True, slots=True)
class Pass:
    layer: int
    z: float                                    # §2의 z 식
    kind: Literal["contour", "hole", "hatch", "medial"]
    vertices: tuple[tuple[float, float], ...]   # 순서 있는 XY. 닫힌 고리는 첫 점을 끝에 반복
    length: float
    footprint: BaseGeometry                     # Validator와 같은 buffer
    reachable_robots: frozenset[int]

@dataclass(frozen=True, slots=True)
class Toolpath:
    passes: tuple[Pass, ...]                    # (층, 정준 순서) 순
    params: ToolpathParams
    thin_lost_mm2: tuple[float, ...]            # 층별 (V10)
    empty_reach_count: int
    medial_fallback_regions: int                # 실행 중 medial 예외로 b 처리된 영역 수 (§6-1)

def generate(stack: LayerStack, config, params: ToolpathParams | None = None, *,
             cache_dir=None, use_cache=True) -> Toolpath: ...

class ToolpathError(Exception):   # code: "WORKSPACE_VIOLATION" 등
    code: str
```
- `config`는 slicing·lower_bound와 같은 덕 타이핑. 숫자는 코드에 넣지 않는다.
- 입력 검증: 파라미터는 유한하고 s, o, chord > 0, n_c ≥ 1, eps_w ≥ 0. 위반은 `ValueError`.

## 6. medial 폴백 (C-38)

1. **실행 중 (자동, 영역 단위):** `wall_mode="medial"`에서 어떤 벽 영역의 medial 추출이 예외로 실패하면, 그 영역은 b(두께 ≈ w 벽을 o_b = w/2 − ε_w 윤곽으로 처리 = 같은 선 2회)로 처리하고 `medial_fallback_regions`를 1 올린다. 모델 이름으로 분기하지 않는다.
2. **실모델 형상 테스트(§7 #13)에서 (자동, 전역):** 01~03 중 어느 모델이든 `wall_mode="medial"`의 전체 IoU < 0.93 또는 실패층 > 5%이면, `from_config`의 기본 `wall_mode`를 `"double"`로 바꾼다(전역, 모든 모델 동일). 사람 승인 없이 전환할 수 있다. **전환 사실과 a·b 두 모드의 지표를 PROGRESS에 보고**한다.
3. 전환 뒤에도 #13이 실패하면 테스트를 고치지 않는다(xfail 금지). 항목을 미합격으로 멈춘다(야간 프롬프트).

## 7. 의사코드 (보고서용)

```
generate(stack, cfg, p):
  for layer k in stack:                          # 층별 독립
    P ← layer.geometry; out ← []
    thin_k ← area(P − open(P, w/2 − ε_w))         # V10
    W ← open(P, w/2 − ε_w) − open(P, w/2)         # V11 두께 ≈ w 벽
    for poly in parts(P):
      for i in 0..n_c−1:                         # 윤곽(바깥·구멍), I1
        R ← poly ⊖ (o + i·s)   [round join, chord]
        out += rings(R) as contour/hole (V13 퇴화 고리 제거, V19 방향)
      if W ∩ poly ≠ ∅:
        if p.wall_mode = "medial":
          try:   out += medial_chains(poly, W) as medial        # V12
          except: out += rings(poly ⊖ (w/2 − ε_w)) near W as contour; fallback += 1   # §6-1
        else:     out += rings(poly ⊖ (w/2 − ε_w)) near W as contour                   # b
      H ← poly ⊖ (o + (n_c−1)·s + w/2)            # V8 해칭 영역
      L ← θ_k 방향 선들 y_min(H) + s/2 + i·s ∩ H   # V7
      L ← 이웃 선 끝점 연결(연결선 발자국 ⊂ P일 때만) # V6
      out += L as hatch
    drop length-0; workspace 검사(raise, V18); reach = ∩ robots(모든 꼭짓점) (V17)
    order: contour/hole → medial → hatch, 가장 가까운 다음 (V9)
  return Toolpath(...)
```

## 8. 테스트와 합격 기준 (모두 자동 판정)

공통: "발자국 ⊂ P"는 overfill 면적 = area(∪발자국 − P) ≤ 1e-6·area(P). 모서리 손실 상한 c(w) = (1 − π/4)·(w/2)² (볼록 모서리 하나당, 둥근 캡이 못 채우는 면적, 산술).

| # | 테스트 | 합격 기준 |
|---|---|---|
| 1 | 정사각형 100×100 | 발자국 ⊂ P, coverage ≥ 0.99(**가설값**), 0.97 ≤ L·w/A ≤ 1.03(**가설값**) |
| 2 | 고리(정사각형 − 구멍) | hole 패스 존재, 발자국 ⊂ P, coverage ≥ 0.99(가설값) |
| 3 | L자(오목) | 발자국 ⊂ P, 연결선 발자국 ⊂ P |
| 4 | 두께 < w 띠(예: 6 mm) | 패스 0개, thin_lost = 띠 면적(상대 1e-9) |
| 5 | 두께 = w 띠(8 × 100 mm) | **medial 모드:** medial 패스 정확히 1개, contour 0개, 발자국 ⊂ P, 미충전 면적 ≤ 4·c(w) + 1e-3·A. **double 모드(폴백):** 같은 중심선 근처(거리 ≤ ε_w + 1e-6)의 적층이 2회, 총 길이 ≈ medial의 2배(상대 5% 이내, 가설값), 발자국 ⊂ P |
| 6 | 섬 2개 | 두 섬 모두에 패스, 섬 사이 연결 없음 |
| 7 | 결정성 | 두 번 실행 + 캐시 적중의 패스 바이트가 같음 |
| 8 | 파라미터 기본값 | `from_config` = (s=w, o=w/2, n_c=1, chord 0.1, Δz 2h, ε_w 0.01, wall_mode "medial" 또는 §6-2 전환 후 "double") |
| 9 | 해칭 각 | 짝수 층 hatch는 수평, 홀수 층은 수직(연결선 제외, 꼭짓점으로 판정) |
| 10 | z | center/top 두 config에서 z가 Validator 식과 같음 |
| 11 | workspace | 작은 workspace 대체 config → `ToolpathError("WORKSPACE_VIOLATION")` |
| 12 | 도달 | 먼 base 대체 config → reachable_robots 빈 집합, empty_reach_count 일치 |
| 13 | 실모델 형상 | 01·02·03·04·06: 층별 ∪발자국 vs 단면을 Validator 식(체적 가중, C-24 확인 결과 ①)으로 계산 → 전체 IoU ≥ 0.93(C-31 m), 실패층(층 IoU < 0.8) ≤ 5%, overfill ≤ 0.30. 실패 시 §6-2 |
| 14 | 03 견고성 | 03 모든 층에서 발자국 ⊂ P |
| 15 | 생성 시간 | 05 캐시 없음: ≤ 60 s 통과 / 60~300 s 기록 / > 300 s 사람. pytest가 아니라 측정 기록(N3) |

- #13의 지표 = Validator 지표라는 것은 **가설**이다(발자국 합집합 = Validator `build_deposited_layers`). 06 탐침 PASS(C-30)로 검증한다.
- #1·#2·#5의 가설값은 첫 구현에서 실측한 뒤 고정한다(완화는 사람 결정).

## 9. 결정 결과 (작업 13 결정 시트)

| # | 항목 | 결과 | 기록 |
|---|---|---|---|
| P1 | o 정의 | **I1** | C-37 |
| P2 | 두께 ≈ w 벽 | **a(medial) + 자동 폴백 b** | C-38 |
| P3 | 얇은 영역 손실 > 0.5% | 조건 미충족(최대 0.220%, 06) | — |
| P4 | workspace 위반 | 조건 미충족(최소 여유 301 mm, 05) | — |
| P5 | 05 생성 > 300 s | 조건 미충족(프로토타입 7.21 s, 구현 후 재측정) | — |
| P6 | 명세 확정 + 야간 큐 승인 | **확정** | C-39 |

## 10. 야간 큐 (C-39 승인)

`docs/prompts/night-2026-10-10b.md`: N1 toolpath v0 구현 → N2 below-plane 가드 동등성 테스트(C-35) → N3 측정 기록(N1 합격 시에만).

## 11. 가설과 검증 방법

| 가설 | 검증 |
|---|---|
| ∪발자국 = Validator 증착 형상 | 06 탐침 Validator `layer_metrics.csv` 대조(C-30) |
| medial 단일 패스가 Y자 분기점에서도 IoU ≥ 0.93 | #13 (01) |
| chord 0.1 mm·Δz 2h 영향 미미 | 탐침 1회 후 재확인 |
| V6 연결로 스트라이크가 크게 준다 | N3 측정 |
| 03 opening 이상치는 shapely 견고성 문제 | #14 |
| #1·#2·#5 기준값 | 첫 구현 실측 |
