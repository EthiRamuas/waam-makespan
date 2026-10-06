CLAUDE.md — 멀티로봇 WAAM Makespan 최소화



\[INE4107] 인공지능과알고리즘 IC-PBL · 담당 오요셉 교수 · 의뢰 생기원 KAMIC 이 파일은 매 세션 로드된다. 여기엔 규칙과 사실만 두고, 긴 설명·근거·실험 기록은 레포의 docs/에 둔다 (구성은 아래 아키텍처 참조).



문제



로봇 3대가 하나의 형상을 나눠 적층한다. 첫 작업 시작 \~ 마지막 작업 종료까지의 시간(makespan)을 최소화한다.



시뮬레이터는 6축 관절을 다루지 않고 TCP 위치만 다루고, 제출물은 trajectory.csv 하나다. → 이건 로봇 모션플래닝이 아니라 기하 제약이 붙은 "할당 + 스케줄링" 문제다. 역기구학·동역학은 범위 밖. 우리가 정하는 것은 누가 · 무엇을 · 언제 · 어디로 이동하며 뿐이다.



절대 금지

config.yaml과 target.stl을 수정하지 않는다. 어떤 이유로도. 유리하게 바꾸는 것은 부정행위다.

Validator 결과를 가공·추정·보간하지 않는다. summary.json에 적힌 값만 기록한다. 돌리지 않은 것을 돌렸다고 쓰지 않는다.

특정 모델(tests/NN)에 맞춘 하드코딩·분기·상수 튜닝을 넣지 않는다. 평가 3축에 일반화가 있다.

WAAM\_Validator/ 레포를 수정하지 않는다. 읽기 전용 참조다. 우리 코드는 src/에만 쓴다.

측정값을 보고할 때 추측과 실측을 섞지 않는다. 실측이 아니면 "추정"이라고 쓴다.

확정 사양 (6개 테스트 모델 전부 동일 · md5 검증됨)

로봇 3대 base: (-1400, 0) / (700, +1212.4) / (700, -1212.4)   # 반경 1400mm, 120° 간격

&#x20; xy\_reach 1500mm (XY 투영만, Z 미사용) | tcp\_radius 100 | arm\_envelope\_radius 100

적층 8 mm/s · 이동 150 mm/s (18.75배) | 층두께 2.0 | 비드폭 8.0

tcp\_z\_reference: center → 층 k의 D 구간 z = (k + 0.5) × 2.0   (1.0, 3.0, 5.0 …)

workspace: 원점 중심 반경 700mm 원 (D 구간 비드 외곽이 이 안. T/W는 밖 허용)

충돌: Base→TCP XY 2D 캡슐. 중심선 ≥250mm, TCP 간 ≥200mm, Z 무시

속도 검사 ±10%, fail\_on\_speed\_violation: true

형상: Coverage ≥80% · Overfill ≤30% · 전체 IoU ≥90% · layer IoU ≥80% · 실패 layer ≤5%

arc\_on/off 1.0s (참조값 — Validator가 요구하지 않는다)



makespan = 로봇별 마지막 waypoint 시각의 최댓값. 그게 전부다 (schedule/metrics.py 확인).



trajectory.csv 계약

csv

robot\_id,time\_s,x\_mm,y\_mm,z\_mm,mode

waypoint 목록이다. 고정 타임스텝이 아니다. 샘플 job 전체가 9행.

행의 mode는 \*\*"이 행부터 다음 행 직전까지"\*\*의 구간 동작. 구간 안은 선형보간. → A→B를 적층하려면 A 행이 D.

로봇 1·2·3 모두 존재 · 각 로봇 첫 time\_s=0.0 · 시간 엄격 증가 · 마지막 행 mode=W

정렬: robot\_id → time\_s 오름차순

D: XY 길이>0, 구간 내 Z 변화 ≤0.25mm, 수직·층간 연결 D 금지

W: 시작·끝 위치 동일(≤0.001mm)

시간 공백 금지. 모드별 시간 합 ≠ 완료시각이면 ArithmeticError로 죽는다. 빈 시간은 W로.

충돌 모델의 함정 — 설계할 때 반드시 기억

Z를 무시하는 보수적 탑뷰. 높이가 달라도 XY로 겹치면 충돌.

대기 중인 로봇도 공간을 차지한다. W 중에도 Base–TCP 선분이 존재한다.

먼저 끝난 로봇의 주차 위치도 전체 makespan까지 검사 대상이다. → "안전한 주차 위치" 선택 자체가 최적화 변수. home 좌표가 안전하다는 보장은 없다.

우리가 스스로 부과한 제약 (Validator는 강제하지 않는다)



실험으로 확인했다 — Validator는 층 선후관계를 강제하지 않고(층 순서를 완전히 뒤집어도 PASS), 아크 시간도 요구하지 않는다. 둘 다 생략하면 makespan이 이득이다. 그래도 생략하지 않는다.



국소 선후관계: 어떤 구간을 층 k에 적층하려면, 그 구간 바로 아래(층 k−1, 같은 XY)가 그 시각 이전에 이미 적층되어 있어야 한다. 전역 barrier는 걸지 않는다(파이프라이닝 허용).

아크 시간: 연속 적층 패스(아크 스트라이크)마다 arc\_on + arc\_off를 W로 반영한다.



이유: 생기원 박사님이 상용 SW로 교차검증한다. Validator만 통과하는 물리적으로 불가능한 해는 거기서 드러난다. 그리고 아크 비용을 목적함수에 넣으면 최적화가 적고 긴 연속 패스를 선호하게 된다 — 실제 WAAM 품질과 같은 방향이다.



도달범위 구조 — 할당 설계의 골격 (실측)

&#x09;비율

1대만 닿는 영역 (전용, 선택 여지 없는 고정 부하)	41.2%

정확히 2대가 닿는 영역 (유일한 조절 손잡이)	55.6%

3대 모두 / 아무도 못 닿음	3.2% / 0%



→ 3자 자유 배분이 아니라 3개의 2자 교환 문제다. → 전용 부하를 먼저 계산하고 공유 영역 배분으로 불균형을 상쇄한다. → 단순 120° 3등분은 이 구조를 무시해 비대칭 형상에서 바로 깨진다. 비교군으로만 쓴다.



아키텍처

src/waam/

&#x20; config.py      # config.yaml 로더

&#x20; geometry.py    # reach·캡슐 최단거리·workspace 판정 (Validator 수식 재구현)

&#x20; prevalidate.py # 탐색 중 ms 단위 사전검증 ← Validator 대신 이걸 부른다

&#x20; slicing.py     # ① STL → 층 단면 (trimesh, 캐싱)

&#x20; toolpath.py    # ② 단면 → segment 집합 (윤곽 오프셋 + 해칭)

&#x20; segment.py     # Segment dataclass + 불변식 검사

&#x20; assign.py      # ③ 할당 전략 (Assigner 프로토콜)

&#x20; schedule.py    # ④ 순서·타이밍·충돌 회피 (Scheduler 프로토콜)

&#x20; precedence.py  # 국소 선후관계 검사

&#x20; timing.py      # ⑤ 거리/속도 → 시각 채우기 + 아크시간

&#x20; writer.py      # ⑥ segment → trajectory.csv + 자체 린터

&#x20; lower\_bound.py # 이론 하한

experiments/

&#x20; run\_all.py     # 6모델 일괄 → results.csv

&#x20; sweep.py       # 하이퍼파라미터 스윕 (야간 배치용)

docs/            # 긴 문서는 전부 여기. Claude 프로젝트 "인공지능과 알고리즘"에서 받아 채운다

&#x20; spec.md        #   WAAM Validator 확정명세 + 작업환경

&#x20;                #   ← 수치·계약의 단일 출처. 이 파일과 어긋나면 spec.md가 맞다

&#x20; playbook.md    #   IC-PBL 착수 가이드 — 전략, 단계 순서, 실패 모드

&#x20; references.md  #   선행연구 + 오요셉 교수 논문 선별 (보고서 인용 계획)

&#x20; operations.md  #   Claude Code 운영 설계 — 모델 배분·루틴·작업 분배

&#x20; experiments.md #   실험 로그. 사람이 쓴다. 왜 그 결정을 했는지가 여기 남는다

out/             # trajectory.csv 6개 (제출물)



레버리지는 assign.py·schedule.py에 100% 있다. 나머지는 배관이다. 배관에 시간을 쓰지 않는다.



성능 지표



절대 makespan이 아니라 \*\*ratio = makespan / 이론하한\*\*으로 본다. 6개 모델을 한 눈금으로 비교할 수 있다. 1.0은 물리적으로 불가능하다.



적층 총량은 형상이 정하므로 우리가 줄이는 것은 (불균형 + 이동 + 대기) 뿐이다.



이론 하한 (h): 01 0.08 · 02 0.18 · 03 0.14 · 04 4.8 · 05 22.5 · 06 0.46



실행

powershell

.\\.venv\\Scripts\\Activate.ps1

python -m experiments.run\_all --models 01 02 03      # 개발 루프 (6\~8층, 빠름)

python -m experiments.run\_all --all                 # 전체 회귀 (05는 350층, 느림)

waam-validator run .\\out\\01                         # 단일 job 전체 검증

waam-validator ui  .\\out\\01                         # 간트·3D 리플레이

pytest -q                                           # 골든 테스트



개발은 01·02·03으로. 04(50층)·05(350층)는 회귀·최종 검증에만.



작업 규칙

탐색 루프 안에서 waam-validator를 부르지 않는다. prevalidate.py로 거르고, Validator는 제출 후보에만.

내부 표현은 segment 리스트. 타임스텝 루프를 만들지 않는다.

모든 실험은 results.csv에 makespan · 계산시간 · PASS/FAIL · ratio를 함께 적는다. 하나만 보면 다른 데서 손해 본다.

시드 고정(numpy, random). python -m experiments.run\_all --all 한 줄로 6모델 전부 재현되어야 한다.

새 전략을 추가할 때 기존 전략을 지우지 않는다. results.csv의 비교군이다.

구간 충돌 같은 연속시간 판정은 샘플링 밀도로 보수성을 주장하지 않는다(Validator 샘플 시각과 일치 보장 없음). Lipschitz 하한으로 보수성을 보장하고, 반례는 Validator를 직접 돌린 골든 테스트로 고정한다.

보고 형식



작업을 마치면 이 세 줄로 보고한다. 장문 설명은 요청받을 때만.



변경: <무엇을 바꿨는지 한 줄>

측정: 모델별 ratio = 01:x.xx 02:x.xx 03:x.xx | 계산시간 xx s | PASS n/3

판단: <다음에 무엇을 결정해야 하는지 한 줄>



측정하지 않았으면 \*\*"미측정"\*\*이라고 쓴다. 숫자를 만들지 않는다.

