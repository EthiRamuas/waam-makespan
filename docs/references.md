# 오요셉 교수 논문 19편 선별 — IC-PBL 활용 관점

> **rev.3 · 2026-10-06** (rev.2 2026-10-06 · 초판 2026-09-13) · 레포 경로 `docs/references.md`
>
> 결론: **전부도 아니고 전무도 아니다. 필수 2편 + 유용 2편 + 조건부 1편 = 5편.** 나머지 13편(+참고 1편)은 불필요.
>
> 📌 **rev.3 변경 요약 — 프로젝트의 PDF 3편(Oh 2020 · Oh & Cho 2022 · Li 2024)을 전문 정독하고 반영**
> 1. **정정 3건** (초판·rev.2의 틀린 서술)
>    - Li 2024의 "swap area"를 "공유 영역"으로 풀어 썼으나, 본문 정의는 **swept area(SA) = 작업 구간(WP)에서 로봇이 차지하는 영역을 직사각형으로 근사한 것**이다 (초록·논의부는 'swap areas'로 표기하지만 약어표·정의는 swept area).
>    - Poudel et al. (2021, *J. Mech. Des.*)을 "MILP 계열"이라 적었으나 Li 2024는 이를 **chunk 분해 + 증착 순서 관리를 하는 수정 GA**로 서술한다 (Poudel 원문은 미열람).
>    - Oh 2020의 "스케줄링 계열도 GA가 압도적"은 과장이다. **GA 최빈은 nesting 계열(표 5)** 이고, 스케줄링 계열(표 6~9)은 휴리스틱·수리모형·GA가 섞여 있다. makespan은 스케줄링 계열에서 가장 자주 쓰이는 목적함수다.
> 2. **새로 확인된 것** — taxonomy는 micro-level(기계 내부) 스케줄링을 scope 밖으로 두고(§2.1), §4.2가 multi-laser·multi-extruder를 확장 방향으로 언급하며, **표 5~9의 53편 어디에도 AM process = DED 행이 없다** → 우리 문제의 포지셔닝 근거가 원문에 있다 (§1 ① 정독 결과)
> 3. **지표 환산표(§7 신설)** — Li의 SEM = 우리 `ratio`의 역수, Oh & Cho의 MIP gap = `1 − 1/ratio`
> 4. rev.2에서: 편수 정정(불필요 13편), PDF 확보 표시, §5 포지셔닝 보강, §6 매핑표
>
> ⚠️ **미열람**: ③ IJPR 2020, ④ IDETC 2018, ⑤ JCDE 2021, Poudel 2021, McPherson & Zhou 2018, Jin et al. 2019 — 요약은 초판 시점 확인 범위 또는 **다른 논문의 서술**에 의존한다. **미열람 논문은 보고서에 인용하기 전에 원문을 확인한다.**
> ⚠️ PDF 텍스트 추출에서 taxonomy의 기호 첨자(S 아래첨자)가 소실돼 `Sα~Sδ` 표기를 원문과 대조하지 못했다. 순서(생성방식 → 스케줄링 모델 → 주문 속성 → 비동일기계 속성)만 확인됨. **보고서에 기호를 쓰기 전 원문 Table 2에서 확인.**

---

## 먼저, 목록 전체를 보고 알게 된 것

교수님의 연구 궤적은 크게 두 갈래다.

1. **DfAM / 파트 분해·조립 설계** — 가장 많고 가장 많이 인용됨 (138회 리뷰 포함)
2. **AM 생산계획 / nesting·scheduling** — 우리 문제와 닿는 쪽

그런데 중요한 관찰이 하나 있다.

> **19편 중 멀티로봇 협업 적층을 다룬 논문은 없다.**
> 교수님의 스케줄링 연구는 전부 **"여러 파트를 빌드에 배치하고, 빌드를 여러 대의 AM 장비에 배정"** 하는 *machine-level* 문제다. 이번 IC-PBL은 **장비 한 대 안에서 로봇 3대가 하나의 파트를 나눠 쌓는** *intra-cell* 문제다.

이게 "이거 내 연구 주제야, 정답(갑)이 없어"라는 9/8 발언과 정확히 맞물린다. 그리고 **보고서 포지셔닝의 가장 강력한 재료**다. (→ §5)

---

## 1. 필수 — 이 둘은 반드시 읽고 인용

### ① Nesting and scheduling problems for additive manufacturing: A taxonomy and review
`Y Oh, P Witherell, Y Lu, T Sprock` · *Additive Manufacturing* 36, 101492 (2020) · 125 cites
📎 **프로젝트에 PDF 있음** (`Nesting and scheduling problems for additive manufacturing.pdf`) · 🔗 NIST 무료 PDF — https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=930053

53편을 **Part / Build / AM Machine 3계층**으로 분류하고 **6개 문제 클래스**를 제시한다:

`[M/S/S]` `[M/M/S]` `[M/M/iM]` `[M/M/nM]` `[−/M/iM]` `[−/M/nM]`
(M=multi-part, S=single, iM=identical machines, nM=non-identical machines)

여기에 **보조 기준 8개**가 붙는다. 스케줄링 쪽 4개가 우리와 직결:

- `Sα` 빌드 생성 방식 (nested / grouped / created / **given**)
- `Sβ` 스케줄링 모델 (**단일기계 SM / 병렬기계 PM / 흐름공정 FS**)
- `Sγ` 주문 속성 (납기, 재료, 품질)
- `Sδ` 비동일 기계 속성 (위치, 크기, 공정 파라미터)

또한 목적함수로 **makespan 최소화**가 스케줄링 계열의 주 목적함수임을, 해법으로는 **GA가 압도적으로 많이 쓰였고 TS·SA·Hill Climbing이 뒤를 잇는다**고 정리한다.

**왜 필수인가**
- 우리 문제를 교수님 본인의 분류체계 안에 위치시킬 수 있다 → 문제정의 절이 즉시 단단해진다
- 해법 선택(GA·SA)의 근거를 교수님 논문에서 끌어올 수 있다 → 10~11주차 커리큘럼과도 일치
- 무료 PDF라 접근 비용 0

**정독 결과 (2026-10-06, 프로젝트 PDF 전문)**

- **"Scheduling"의 정의가 machine-level이다.** Table 1: Scheduling = *"Assigning builds to AM machines for build cycles"*. §2.1은 micro-level(예: 특수 AM 기계 안에서 다중재료 교체 횟수 최소화)을 제외하고 **"production planning at the shop-floor level"** 로 범위를 좁힌다고 밝힌다.
  → 우리 문제(한 셀 안에서 로봇 3대가 한 파트를 분담)는 **원문 기준으로 scope 밖**이다. "빈칸" 주장의 직접 근거.
- **§4.2 Future research — 확장 방향 4개**: ① taxonomy 확장(Enterprise 레벨) ② flow-shop·job-shop 모델 ③ **특수 AM 기계(multi-material · multi-laser · multi-extruder · multi-axis)** ④ cloud 주문 처리. ③이 우리와 닿는다. 원문은 multi-extruder 예로 Jin et al. (2019, *IISE Trans.*, "Toolpath allocation and scheduling for concurrent fused filament fabrication with multiple extruders"), multi-axis 예로 Plakhotnik et al. (2019, *CIRP Ann.*)을 든다.
  → **Jin et al. 2019는 가장 가까운 비-WAAM 선행연구 후보다.** (원문 미열람 — 정독 후 §5에 반영)
- **표 5~9에 DED(= WAAM 계열) 행이 없다.** 분류표에 등장하는 AM process는 BJ · ME · PBF · VP · N/A뿐이다 (AM process 분류 정의에는 DED가 있지만 53편 중 해당 논문이 없다).
- **분류 코드**: 6개 클래스 `[M/S/S] [M/M/S] [M/M/iM] [M/M/nM] [−/M/iM] [−/M/nM]`. 보조 기준 8개 = nesting 4(차원 2D/3D · 회전 ABC/C · 빌드볼륨 Bounded/Unbounded · 대상 Full/Subset) + scheduling 4(빌드 생성 Nested/Grouped/Created/Given · 모델 SM/PM/FS · 주문 속성 Du/Ma/Qu · 비동일기계 속성 Lo/Si/Pr). **공통 3기준**은 AM process · objective · methodology.
  → 우리는 `PM`에 가장 가깝지만 *기계끼리 간섭하지 않는다*는 가정이 깨진다.
- **목적함수·해법 (표 6~9 직접 확인)**: makespan이 가장 빈번한 목적함수다 (일부 논문은 여러 표에 중복 등재). 해법은 nesting 계열(표 5)에서 **GA 최빈**, 스케줄링 계열은 **휴리스틱 · 수리모형 · GA 혼재**. §3.3은 load balancing을 위해 "makespan, the longest processing time in scheduling"을 쓴다고 명시한다.

### ② Scheduling of build and post processes for decomposed parts in additive manufacturing
`Y Oh, Y Cho` · *Additive Manufacturing* 59, 103164 (2022) · 16 cites
📎 **프로젝트에 PDF 있음** (`Scheduling of build and post processes for decomposed parts in AM.pdf`)

**교수님 본인의, 가장 최근의, 가장 순수한 스케줄링 논문.** 분해된 파트들의 build 공정과 post 공정을 함께 스케줄링한다.

**왜 필수인가** — 내용보다 **형식** 때문이다. 교수님이 스케줄링 문제를 어떻게 정식화하고(표기·결정변수·제약), 어떤 지표로 평가하고, 결과를 어떻게 제시하는지가 들어 있다. **우리 보고서를 이 논문의 문법에 맞추면 평가자가 읽기 편하다.** 평가자가 저자 본인이라는 점을 생각하면 이건 작은 이점이 아니다.

**정독 결과 (2026-10-06)**

- **문제**: 분해된 파트의 build + post(trimming · coloring · assembly) 통합 스케줄링. **flow shop**, 분류상 `M/M/iM`. 세 정책 — all-for-one-job / one-for-one-job / hybrid — 에 대응하는 **MIP1~3**으로 makespan 최소화. 결과: 10개 파트에서 hybrid(MIP1)가 all-for-one(MIP2)보다 makespan 27.68% 작다.
- **정식화 형식 (우리가 빌릴 것)**: ① **Table 1 표기표** (Index / Parameter / Decision variable / Auxiliary variable 구분) ② 목적함수·제약을 **번호 붙은 그룹**(1.1~1.31)으로 나열하고 그룹마다 소제목 ③ 조건부 제약을 `{LHS} ⟹ {RHS}` **indicator constraint**로 표기 ④ 같은 자원 위 작업의 겹침 금지를 **이진 보조변수 쌍 u/v**로 표현 (식 1.18~1.27) ⑤ MIP2·MIP3는 MIP1에 **제약 한두 개를 추가**하는 방식으로 정의 → 전략 비교가 깔끔하다.
- **평가·제시 형식**: **MIP gap** `|Z_LOW − Z_CUR| / Z_CUR × 100` (식 6)을 해의 품질 지표로 쓰고, 정책 간 비교는 최악 정책 대비 **reduction rate**(식 8·9), 병렬 처리 효율은 **overlapping time** `OT = BT + PT − MS`(식 7). 결과표(Table 4)는 모델 × 파트 수 × (Obj, Gap) + (Build, Post, Makespan). 정책별 **Gantt chart**(Fig. 5~7).
- **계산시간 보고 방식**: 문제 크기 표(Table 3: 변수·제약 수), **10개 파트 · 50,400 시퀀스 → 43.7 h** 를 CPU·RAM(i9-10900, 32 GB)과 함께 제시하고 "실용적이지 않다"고 결론. 탐색 한도로 시퀀스 상한 N=1000(30분 기준)을 두되 **"최적을 보장하지 않는다"고 명시**. 결론부는 대규모 문제에 GA·TS·SA 같은 메타휴리스틱을 쓸 수 있다고 언급.
- **우리 문제와의 거리**: 자원(AM machine) 간 **공간 간섭이 없다** (machine-level). formulation을 그대로 가져오진 못하고, **표기·제시 방식과 "MIP는 규모에 한계 → 메타휴리스틱" 논거**를 빌린다.

---

## 2. 유용 — 읽으면 보고서가 좋아짐

### ③ The impact of build orientation policies on the completion time in two-dimensional irregular packing for AM
`Y Oh, C Zhou, S Behdad` · *IJPR* 58(21), 6601-6615 (2020) · 26 cites

**completion time(완료시간)을 목적함수로 놓고 "정책"들을 비교 실험한다.** 우리가 해야 할 일(할당 정책 여러 개를 6개 모델에서 비교)과 **실험 설계가 같은 모양**이다. 정책 비교표를 어떻게 만들고 어떤 통계를 보여주는지 참고. → 우리 `results.csv`의 `algo` 컬럼 비교표(sector vs topk vs GA …)가 정확히 이 형태다.

### ④ Production planning for mass customization in AM: build orientation determination, 2D packing and scheduling
`Y Oh, C Zhou, S Behdad` · IDETC 2018 · 46 cites

하나의 큰 생산계획 문제를 **방향결정 → 패킹 → 스케줄링** 세 단계로 분해해 푼다. 우리 파이프라인(슬라이싱 → 경로생성 → **할당 → 순서**)도 같은 분해 전략이다. **"왜 통합 최적화 대신 단계 분해를 택했는가"** 를 방어할 때 근거로 쓸 수 있다 — 평가 2축(계산시간)을 의식한 선택이라는 논리와 연결된다.

---

## 3. 조건부 — 학습 기반으로 갈 때만

### ⑤ Neural network-based build time estimation for additive manufacturing: a performance comparison
`Y Oh, M Sharp, T Sprock, S Kwon` · *JCDE* 8(5), 1243-1256 (2021) · 41 cites · 오픈액세스

신경망으로 **build time을 추정**하고 여러 모델을 성능 비교한다.

**쓸 곳이 정확히 하나 있다.** 할당·순서 후보를 평가하려면 매번 전체 시뮬레이션을 돌려야 하는데, 이게 탐색 속도의 병목이 된다. 여기서 **makespan을 빠르게 추정하는 surrogate model**을 학습시켜 탐색 안쪽에 넣으면 계산시간(평가 2축)을 크게 줄일 수 있다. 그 아이디어의 직접적 근거가 이 논문이다.

> 📝 **rev.2 메모** — 우리 구조에서는 `prevalidate.py`(ms 단위 사전검증)와 segment 리스트 기반 시각 계산이 이미 "전체 시뮬레이션"을 대체한다. surrogate는 **그것으로도 느릴 때의 2차 수단**이다. 순수 휴리스틱으로만 간다면 **읽을 필요 없다.**

### (참고) Optimal process planning for hybrid additive–subtractive manufacturing using recursive volume decomposition
`S Kwon, Y Oh` · *JMS* 71, 360-376 (2023) · 19 cites

**재귀적 볼륨 분해**로 형상을 나눈다. 우리가 형상을 3대에 나누는 발상의 방법론적 사촌이다. 인용까지는 필요 없고, **막혔을 때 분해 아이디어를 얻는 용도**.

---

## 4. 불필요 — 13편

| 묶음 | 편수 | 제외 이유 |
|---|---:|---|
| DfAM·파트 분해·조립 설계 계열<br><small>(Part decomposition review 138회 / 2D batch placement / design guidelines 평가 / Part separation methods / Axiomatic design 프레임워크 / Assembly based part design / Part consolidation RfAM 2025)</small> | 7 | **우리는 설계를 바꾸지 않는다.** `target.stl` 수정 금지가 명시 제약이다. 이름의 "decomposition"은 *설계 분해*라서 우리의 *작업 분해*와 다른 개념 |
| Simultaneous reassembly and procurement planning (재제조) | 1 | 도메인 무관 |
| Spatial-temporal deep learning for real-time monitoring | 1 | 공정 **모니터링**. 우리는 실행 전 **계획** 단계 |
| An optimal quantity of scheduling model for mass customization | 1 | 스케줄링이지만 로트 **수량** 결정이 핵심. 연결 약함 |
| 박사학위논문 (SUNY Buffalo, 2019) | 1 | 위 논문들의 집합. 개별 논문으로 충분 |
| 중복 항목 (Addit Manuf 22 재등록, DRAFT 버전) | 2 | Google Scholar 중복 |
| **소계** | **13** | |

*(검산: 19 − 필수 2 − 유용 2 − 조건부 1 − 참고 1 = 13)*

---

## 5. 이걸로 보고서에서 뭘 할 것인가

### 5-1. 가장 값나가는 한 수: 교수님 taxonomy의 빈칸을 우리 문제로 채우는 것

교수님의 2020 taxonomy는 `Sβ`에서 스케줄링 모델을 **SM / PM / FS** 로 나눈다. 우리 문제를 여기에 대보면:

- 겉보기엔 **병렬기계(PM)** 다 — 동일한 3개 자원이 작업들을 나눠 처리
- 그런데 **고전 PM 스케줄링은 기계끼리 물리적으로 간섭하지 않는다고 가정한다.** 우리는 **로봇끼리 충돌한다.** 심지어 대기 중이거나 작업을 끝낸 로봇도 계속 공간을 점유한다 (Validator 실측 — 주차 위치도 makespan 끝까지 검사 대상)
- 게다가 자원마다 **접근 가능한 작업 집합이 기하학적으로 제한된다** (실측: 41%는 한 대만 도달 가능, 56%는 두 대 공유 → "3자 자유 배분"이 아니라 **3개의 2자 교환 문제**)

> 즉 이 문제는 **"공간 간섭이 있는 제약된 병렬기계 스케줄링"**이고, 교수님 taxonomy의 machine-level 축에는 자리가 없는 **intra-cell(장비 내부) 병렬성**이라는 새 축이다.

이 문장 하나면 문제정의 절이 선다. 억지가 아니라 사실이다 — 목록 19편 어디에도 멀티로봇 협업 적층이 없다는 것이 근거다.

### 5-2. (rev.2 신설) "Validator가 검사하지 않는 물리 제약을 식별하고 부과했다"

환경 구축 이후 확정된 사실 두 가지가 방법 절의 재료가 된다. **둘 다 코드 grep → 반증 실험 → 대조군의 3단계로 확인**했다 (상세는 `docs/spec.md` §8-2·8-3).

| 확인한 것 | 결과 | 우리의 입장 |
|---|---|---|
| 층간 선후관계 | **강제하지 않는다.** 층 순서를 완전히 뒤집은 tB도 tA와 소수점까지 동일하게 PASS | **국소 선후관계**를 스스로 부과 (층 `k` 구간은 그 바로 아래 `k−1`이 먼저 적층돼 있어야 함). 전역 barrier는 걸지 않음 → 파이프라이닝 허용 |
| `arc_on` / `arc_off` | **요구도 금지도 하지 않는다** (참조값). 넣으면 makespan이 정확히 그만큼 늘 뿐 | **넣는다.** 연속 패스(아크 스트라이크)마다 1+1초를 `W`로 반영. 윤곽 기준 비용 1~11% |

보고서에서는 두 가지를 같이 제시하면 강하다:
- **"넣은 경우 / 안 넣은 경우" makespan 둘 다** — 자발적으로 부과한 제약의 비용을 정량화
- **상용 SW 교차검증**(생기원 박사님)에서 살아남는 해라는 논거 — Validator만 통과하는 비물리 해와의 차별점

> ⚠️ 이 서술의 **출처는 우리 실험**이다. 교수님 논문의 주장으로 인용하지 말 것. 논문은 "왜 선후관계·준비시간이 스케줄링 모델의 보조 기준(`Sγ`·`Sδ` 계열)으로 다뤄지는가"를 받쳐주는 배경으로만 쓴다 — **원문에서 해당 절을 확인한 뒤에.**

### 5-3. 선행연구 Li et al. (2024)와의 관계 (rev.3 — 정독 반영)

📎 PDF: `Yongzhe Li et al_ Allocation and scheduling of deposition paths in a layer for multi-robot coordinated wire and arc additive manufacturing of large-scale parts.pdf` · *Virtual and Physical Prototyping* 19(1), e2300680 (2024), 오픈액세스. 오요셉 논문은 아니지만 **가장 가까운 선행연구**라 같이 관리한다.

**그들이 푼 문제 (정독 결과)**
- **한 층(flat layer) 안**의 raster 경로 m개를 로봇 n대에 할당 + 순서 + 충돌 회피. 목적 `min max(Tⱼ)`. 실험은 3대(Yaskawa AR1730), 경로 137~327개.
- **work time = 경로 길이 ÷ 속도만** (식 3·5). **로봇의 경로 간 이동시간은 "적층시간보다 훨씬 짧다"며 무시**한다 (실험 설정: 적층 6 mm/s, 경로 간 이동 12 mm/s).
- **top k%**: 로봇마다 *도달 가능한 경로 창고(PW)* 를 만들고 로봇–경로 중심 거리로 정렬 → 매 반복 **작업량이 가장 적은 로봇**에게 `t_a = k·T_pw/100`(T_pw = 그 로봇 PW에 남은 경로의 총 작업시간)만큼 **가까운 순서로** 할당 → 할당된 경로를 모든 PW에서 제거 → 반복. 복잡도는 경로 수에 대해 로그 수준 (원문 §4.3, 밑은 k에 의존).
- **지표**: EWL(작업량 균등도), GOA(인접 경로가 같은 로봇에 가는 비율), `Ω = w·EWL + (1−w)·GOA`, **SEM = t_avg / t_act = Σtᵢ / (n·max Tⱼ)**. **k는 하이퍼파라미터**: 작을수록 EWL↑·GOA↓, 클수록 반대. 실험은 `k=35, w=0.5`.
- **스케줄링**: 인접 경로를 이어 **deposition task(DT)** 로 묶어 대상 수를 줄이고 (예: 경로 137개 → DT 10개), 로봇이 동시에 일하는 구간을 **work period(WP)** 로 나눈 뒤, **swept area(SA) = 경로 bounding box + 안전반경(RoS 50 mm)의 직사각형**끼리 **겹침 검사**. DT 순서의 **모든 순열을 열거**해 SA 간 최소거리를 최대화하는 순서를 고른다. 해가 없으면 가장 긴 DT를 반으로 쪼개 반복.
- **결과**: SEM **92.1%** (단일 로봇 4083 s → 3대 1478 s), turns 127회 · 아크 시작점 10개 — 비교 방법은 Bhatt 183 turns, Shen 293 turns · SEM 80.9%. top k% 할당 계산시간 0.011~0.027 s (MATLAB, Ryzen 7 5800H).
- **저자들이 밝힌 한계**: raster 경로만 검증 / 한 층만 / **SA가 겹치면 충돌 없는 스케줄링 알고리즘이 무효** / 모든 로봇의 적층 파라미터 동일 / closed-loop 경로(contour · MAT)는 중심이 겹쳐 정렬 기준이 불명.

**우리 문제와 다른 점 — 그대로 못 가져오는 이유**

| | Li et al. (2024) | 우리 (Validator) |
|---|---|---|
| 범위 | **한 층** | 전체 형상 (층 선후관계 미강제 → 한 문제로) |
| 이동·대기 | 무시 | **T·W가 makespan에 포함** — 이동속도(150 mm/s)가 적층의 18.75배라도 횟수가 많아 무시할 수 없다 |
| 아크 시간 | 아크 시작점 *개수*를 품질 지표로만 | `arc_on + arc_off` 2 s를 **시간으로 반영** |
| 충돌 모델 | TCP 중심 원(RoS 50 mm) → SA 사각형 겹침 | **Base→TCP XY 캡슐** 중심선 ≥250 mm, TCP ≥200 mm, 대기·주차 로봇 포함 |
| 도달 범위 | PW로 표현 (경로 전체를 한 로봇이 수행) | 같은 개념. **전용 41% / 2대 공유 56%** 구조 |
| 경로 | raster 직선 | contour + infill (해칭 방식이 아크 스트라이크 수를 좌우) |
| 순서 탐색 | DT 순열 전수 열거 (DT 수가 작아 가능) | 층 수 6~350 → 전수 불가, 휴리스틱·메타휴리스틱 필요 |

**그래서 베이스라인으로 쓰는 법**: PW(= 도달 가능 집합)와 "가장 한가한 로봇에게 가까운 순서로 k%"라는 **할당 규칙**만 가져온다. 이 규칙은 우리의 전용/공유 구조(PW가 겹치는 56%)에 자연스럽게 대응한다. 대신 (a) 층 단위가 아니라 전체 또는 층 묶음으로 확장하고 (b) 부하 계산에 **이동·아크 시간을 포함**하고 (c) 충돌은 우리 캡슐 모델로 `prevalidate`가 판정하고 (d) 순서는 순열 열거 대신 별도 탐색으로 바꾼다. **k를 하이퍼파라미터로 스윕**하는 것이 곧 `waam-sweep`의 첫 대상이다.

**왜 선행연구의 층 내 구조를 따르지 않았는가** — 그쪽은 **한 층만 다루는 범위 설정**이다 (논문 스스로 "primary research"라며 flat layer만 고려한다). 층 순서 자체는 물리적 전제이고, 우리 Validator는 층 순서를 보지 않는다. 그래서 전체를 한 문제로 두고 국소 선후관계를 스스로 부과한다 (§5-2).

⚠️ **억지 인용은 역효과.** 평가자가 저자 본인이라 어디서 끌어다 붙였는지 바로 보인다. **실제로 방법이나 근거로 쓴 것만 인용할 것.** 위 5편은 전부 실제로 쓸 자리가 있는 것들이다.

### 5-4. 참고문헌 구성 제안

| 절 | 인용 |
|---|---|
| 배경·동기 | Arbogast et al. 2024 (ORNL MedUSA, 슬라이드 29) |
| 선행연구 — AM 스케줄링 | **Oh et al. 2020 taxonomy** ①, **Oh & Cho 2022** ② |
| 선행연구 — 멀티로봇 WAAM | Li et al. 2024 (top k% 층 내 할당), He et al. 2024 (오픈소스 아키텍처) |
| 문제정의·포지셔닝 | ①의 분류축으로 우리 문제 위치짓기 + 빈칸 지적 (§5-1) |
| 방법 — 단계 분해 근거 | Oh et al. 2018 ④ |
| 방법 — 자체 부과 제약 | 우리 실험 (§5-2) — **논문 인용 아님** |
| 측정 지표 정의 | Li 2024의 SEM · Oh & Cho 2022의 MIP gap — 우리 `ratio`와의 환산은 §7 |
| 실험 설계 | Oh et al. 2020 IJPR ③ |
| (학습 기반일 때) surrogate | Oh et al. 2021 JCDE ⑤ |

---

## 6. 논문 ↔ 레포 ↔ 보고서 매핑과 읽기 상태 (rev.3 갱신)

| 논문 | PDF | 쓰는 곳 (레포 / 보고서) | 읽기 상태 | 얻은 것 / 남은 확인 |
|---|---|---|---|---|
| ① Oh 2020 taxonomy | 프로젝트 ✅ | 보고서 문제정의·포지셔닝 | **정독 완료 (2026-10-06)** | Table 1 scheduling 정의 · §2.1 scope · §4.2 future · 표 5~9에 DED 없음 (§1 ①). **남음**: 기호 첨자 — 원문 Table 2 |
| ② Oh & Cho 2022 | 프로젝트 ✅ | 보고서 정식화 절 · 계산시간 논거 · gap 표기 | **정독 완료** | 표기표 / indicator constraint / MIP gap / RR / 43.7 h 사례 (§1 ②) |
| Li et al. 2024 | 프로젝트 ✅ | 베이스라인 top k% (`assign.py`) · 선행연구 절 | **정독 완료** | §5-3 비교표. 우리가 바꿔야 할 4가지 (a~d) |
| ③ Oh 2020 IJPR | 없음 | 보고서 실험 설계 | 미열람 | 정책 비교표 형식. Oh & Cho 2022가 [26]으로 인용 확인 |
| ④ Oh 2018 IDETC | 없음 | 보고서 방법 — 단계 분해 근거 | 미열람 | Oh 2020이 [16]으로 인용 확인 |
| ⑤ Oh 2021 JCDE | 없음 | (조건부) surrogate 절 | 미열람 | 학습 데이터 구성, 오차 지표 |
| Jin et al. 2019 (IISE Trans.) | 없음 | 선행연구 절 (가장 가까운 비-WAAM 후보) | 미열람 | Oh 2020 §4.2가 multi-extruder 예로 인용 |
| Poudel et al. 2021 (J. Mech. Des.) | 없음 | 멀티로봇 AM 스케줄링 선행연구 | 미열람 | Li가 "수정 GA"로 서술 — 원문으로 확인 |
| McPherson & Zhou 2018 | 없음 | (참고) 충돌 제약의 출처 | 미열람 | Li의 식 15가 이 연구를 수정 |

**다음 읽기 순서**: Jin 2019 → Poudel 2021 → (필요 시) ③. 나머지는 해당 절을 쓸 때. PDF를 프로젝트에 올리면 같은 방식으로 정독해 표를 갱신한다.

---

## 7. (rev.3 신설) 지표 환산표 — 선행연구와 같은 눈금으로 보고하기

| 우리 | Li et al. (2024) | Oh & Cho (2022) | 관계 |
|---|---|---|---|
| `ratio = makespan / LB`, LB = Σ적층시간 ÷ 3 | **SEM** = t_avg / t_act = Σtᵢ / (n·max Tⱼ) | — | **SEM = 1 / ratio** (분자가 같은 "완벽한 균형" 값). 예: SEM 92.1% ↔ ratio 1.086 |
| `gap = (makespan − LB) / makespan` | — | **MIP gap** = \|Z_LOW − Z_CUR\| / Z_CUR × 100 | **gap = 1 − 1/ratio = 1 − SEM** (Z_CUR = makespan, Z_LOW = LB일 때) |
| 정책 B의 개선율 | — | **reduction rate** = (MS(l) − MS_worst) / MS_worst × 100 | 전략 간 비교표에 같은 식 사용 |
| `workload_imbalance_s` (Validator: max − min) | **EWL** = (T̄ − s_T) / T̄ | — | 불균형 지표 |

⚠️ **비교 시 주의**
- Li의 SEM은 *적층시간만*으로 계산한다 (이동·대기·아크 제외, 한 층). 우리 makespan에는 T·W·아크 2 s가 들어간다. 같은 SEM 숫자라도 우리 쪽이 더 어렵다. 보고서에는 **"Li의 정의대로(적층시간만) 환산한 값"** 과 **"Validator 기준 실제 makespan으로 계산한 값"** 을 구분해 적는다.
- 우리 LB는 reach 제약을 무시한 **LB0 = Σ/3** 이다. Oh & Cho의 MIP gap은 솔버가 구한 하한을 쓰므로, 우리도 **reach를 반영한 CP-SAT 완화 하한 LB1** (`docs/playbook.md` §4-2)을 만들면 같은 의미의 gap을 줄 수 있다. LB1 ≥ LB0이므로 gap은 더 작아진다.
