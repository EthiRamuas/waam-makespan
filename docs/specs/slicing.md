# slicing.py 명세 (C-18 반영, 2026-10-10)

상태: **명세 확정 대기 — 야간 큐 후보 심사용. 구현하지 않았다.** 결정 근거는 `DECISIONS.md` C-18.
기준: Validator 소스(`shape/target.py`, `shape/layer_index.py`, `shape/polygon_utils.py`)를 읽고 확인한 사실. 이 파일과 `docs/spec.md`가 어긋나면 `docs/spec.md`가 맞다.

## 1. 역할

STL → 층 단면(shapely 객체). 3단계 `toolpath.py`의 입력이고, `lower_bound.py`(Σ단면적 ÷ 비드폭 ÷ 속도 ÷ 3)의 입력이다. `lower_bound`는 toolpath가 아니라 slicing에 의존한다.

## 2. 입출력

입력
- `target.stl` 경로. 수정하지 않는다(읽기 전용).
- config에서: `process.layer_height_mm`, `process.build_plane_z_mm`, `shape_validation.polygon_snap_tolerance_mm`, `collision.geometry_epsilon_mm`, `shape_validation.area_epsilon_mm2`. 코드에 숫자를 박지 않는다.

출력 `LayerStack`
- `layer_count`
- 층별: `index`, `z_bottom`, `z_top`, `z_slice`, `geometry`(shapely Polygon/MultiPolygon, 홀 보존, **C-18 결정 2**), `area_mm2`
- 비어 있는 층도 층으로 존재한다(`geometry`만 비어 있음).

## 3. 규칙 (Validator와 같아야 한다)

- 층 k의 단면 높이: `z_slice = build_plane_z + (k + 0.5) × layer_height`. `tcp_z_reference`와 무관하다(그것은 TCP z에만 영향).
- 층 수: `max(0, ceil((zmax − build_plane_z) / layer_height))`.
- 메시 전처리(Validator `load_target_mesh`와 같은 순서): 정점 병합 → 퇴화 면 제거 → 중복 면 제거 → 미참조 정점 제거 → 법선 정리.
  - **`fill_holes` 등 repair는 하지 않는다. 전처리 뒤에도 watertight가 아니면 `TARGET_NOT_WATERTIGHT`로 raise한다 (C-18 결정 3).**
  - 읽기 전용 확인(2026-10-10): 모델 01~06의 STL은 원본 그대로는 `is_watertight`가 False이고(STL이 면마다 정점을 따로 저장하기 때문), trimesh 기본 처리(`process=True`, 정점 병합)를 거치면 6개 모두 watertight이고 winding이 일치한다. 이 확인은 Validator의 전처리 순서와 완전히 같지 않다. 구현이 오라클 2·3으로 일치를 증명한다.
- 단면 선분: `trimesh.intersections.mesh_plane`으로 구하고 shapely로 루프를 만든다(scipy 불필요).
- 스냅: `snap_tolerance`가 0보다 크면 `set_precision`. 닫힘 허용오차: `max(snap, geometry_epsilon)`. 열린 루프는 버린다.
- 홀·다중 윤곽: 루프를 `(−면적, bounds)`로 정렬해 even-odd(대칭차)로 합친다. 홀, 분리된 섬, 홀 안의 섬이 결정적으로 처리된다.
- 정규화: `make_valid` → 스냅 → `area_epsilon` 이하 조각 제거 → union.
- 빈 단면 fallback: 단면이 비었고 `z_slice`가 메시 범위 안이면 `±min(1e-4, h × 1e-6)`로 한 번씩 더 시도한다.

## 4. 캐싱 (C-18 결정 4)

- 위치: `.cache/waam/slicing/` (`.gitignore`에 `.cache/` 추가 완료, dc76f73).
- 키: `sha256(STL 바이트)` + layer_height + build_plane_z + snap + geometry_epsilon + area_epsilon + 알고리즘 버전 상수.
- 값: 층별 WKB. 같은 키에서는 바이트가 같은 결과를 돌려준다. STL이 한 바이트라도 다르면 미스.

## 5. 테스트 오라클 (통과/실패는 1~4와 6으로만 판정)

1. 층 수가 spec 표와 같다: 01=6, 02=8, 03=6, 04=50, 05=350, 06=51. (표의 숫자는 테스트 데이터이고 `src/`에는 넣지 않는다.)
2. sample_job: Validator가 실제로 낸 `layer_metrics.csv`의 층 0 `target_area_mm2` = 332.48569089999995와 일치.
3. 모델 01~03(회귀에서 04·06)의 모든 층에서 단면 면적이 `waam_validator.shape.target.slice_target_layers` 결과와 일치. Validator import는 **오라클 테스트에만** 쓴다 (C-18 결정 1).
4. 합성 메시: 홀 하나, 분리된 섬 둘, 홀 안의 섬. 합성 입력은 테스트가 만든다.
5. 부피: Σ(면적 × h)와 `mesh.volume`의 상대오차를 **측정해서 기록만 한다. 통과/실패 판정에 쓰지 않는다 (C-18 결정 5).** 야간에는 단언하지 않는다.
6. 캐시: 두 번째 호출은 재슬라이싱 없이 같은 WKB를 돌려주고, STL 바이트가 바뀌면 미스.

## 6. 완료 기준 (자동 판정)

- 새 테스트 전부 통과, skip 0
- 기존 pytest 전부 통과, 기존 테스트·fixture 변경 없음
- 모델 01~03의 층 수와 면적이 오라클 2·3과 일치
- `waam-reviewer` 통과 (무작위 탐색 3분 이내, 샘플 상한)

## 7. 중단 조건

- 같은 오류가 2회 연속
- 모델 01~06 중 하나라도 오라클 3과 면적이 다르고 한 번의 수정으로 원인을 못 찾을 때
- `target.stl` 또는 `config.yaml` 수정이 필요해 보일 때 (금지)
- 새 바이너리 의존성 설치가 필요할 때 (스마트 앱 컨트롤 차단 가능성: 사용자 확인 후)
- 모델 05(350층) 슬라이싱 시간이 회귀에 쓰기 어려울 만큼 길 때 (현재 시간 미측정)
- 전처리 뒤 watertight가 아닌 모델이 나올 때 (repair 결정이 필요 → 보류하고 B등급 메모)

## 8. 야간 큐 자격 (J-1 4조건) — 2026-10-10 재판정

| # | 조건 | 판정 | 근거 |
|---|---|---|---|
| ① | 명세 확정 + 사람의 ★4 승인 | ✓ 명세는 C-18로 확정 / **★4 승인은 아직 아님** | 이 파일이 승인 대상 |
| ② | 설계 결정 없음 (A등급) | ✓ | C-18 결정 1~5로 후보 소진. 남은 항목은 Validator 규칙을 따르는 구현 선택뿐 |
| ③ | 자동 판정 가능 | ✓ | 오라클 1·2·3·4·6, 부피(5)는 판정에서 제외 |
| ④ | 되돌릴 수 있음 | ✓ | `nightly/<날짜>` 로컬 커밋, `.cache/`는 ignore |

- 구현 시간은 **미측정**이다 (가설: 40~70분 + 리뷰). 1단계 속도를 환산하지 않는다.
- 다만 중단 조건 7번째(전처리 뒤 비 watertight)는 모델 01~06에서는 발생하지 않을 것으로 보이나(위 읽기 전용 확인), Validator 전처리와 순서가 완전히 같지는 않아서 오라클 3이 최종 증명이다.
