TCToPyRebuild
=================

목표
----
PyQt6 기반 QStackedWidget 전환식 턴제 RPG 프로토타입. core/ui/data 분리로 규칙과 UI 의존성을 최소화했습니다.

실행 방법
--------
1) Python 3.10+ 설치
2) 가상환경 생성(선택): `python -m venv .venv` 후 활성화
3) 의존성 설치: `pip install -r requirements.txt`
4) 실행: `python app.py`

보스/특수보스 기믹 스키마
-----------------------
- trigger: `every_n_turns`(n턴마다), `hp_below`(HP/max_hp <= ratio, once로 1회 제한)
- action: 현재 단계는 `type: apply_effect`만 사용 (target: player/enemy, effect: bleed/stun, duration, power)
- gimmicks 배열은 bosses.json의 dungeon_bosses/special_bosses에 정의하며 발동해도 보스는 공격을 계속 수행함

장신구 special(on_hit) 스키마
---------------------------
- equipment의 special에 `{ "type": "on_hit", "chance": 0.3, "effect": "stun", "duration": 1 }` 형식으로 정의
- 플레이어가 적을 타격할 때 확률로 effect를 적용

스킬 효과 시스템(apply_effect)
-----------------------------
- skills.json의 apply_effect는 단일 객체 또는 배열로 정의
- 공통 필드: type, target(self|enemy), chance(0~1), duration, power, stats, scope(기본 battle), note(선택)
- 지원 타입: buff_stats(스탯 증가), debuff_stats(스탯 감소), bleed(턴 종료 피해), stun(행동 불가), heal(즉시 회복), lifesteal(가한 피해 비율 즉시 회복)
- 예시: `{"type":"buff_stats","target":"self","duration":3,"stats":{"attack":8},"scope":"battle"}`
- 복수 효과: `[ {...}, {...} ]`로 나열 (예: 은신은 공격/방어 두 버프를 배열로 등록)
- scope가 battle인 효과는 전투 종료 시 모두 제거되어 저장되지 않음 (집중/구르기 등 전투 한정 버프 포함)

캐릭터별 저장/변경 방법
---------------------
- progress.json 구조: `selected_player_id`와 `players[<id>]`에 player_state(level/exp/stat_points/allocated_stats/hp), inventory, equipment, dungeon_progress를 분리 보관
- 구버전 저장파일은 실행 시 자동 마이그레이션됨
- 메인 화면의 "캐릭터 변경" 버튼을 눌러 리스트에서 선택하면 해당 캐릭터 상태를 로드

실행 오류(Exit code 1) 디버깅
----------------------------
1) players.json의 default_player_id가 players 블록에 없는 경우
2) skills.json에서 scale.attack 또는 scale.magic 키가 빠지거나 문자열 등 숫자가 아닌 경우
3) players/monsters가 존재하지 않는 skill_id를 참조하는 경우(정리 시 __basic__으로 대체됨)

JSON 수정 후 체크리스트
----------------------
- players.base_stats에 attack/magic/defense/magic_resist/max_hp 모두 있는지 확인
- skills.scale.attack, skills.scale.magic 값이 숫자인지 확인
- skill_id 참조가 skills.json에 실제 존재하는지 확인
- default_player_id가 players 블록에 포함되어 있는지 확인
- JSON 편집 후 앱을 재실행해 경고/에러 로그를 확인

프로젝트 구조
------------
- app.py : QApplication 부트스트랩 및 GameController 연결
- core/ : 규칙 로직 (전투, 상태이상, 던전 진행, 경험치, 드랍, 저장)
- ui/ : PyQt6 위젯 (메인/던전/전투/인벤/스탯/특수보스)
- data/ : JSON 스키마 (플레이어/스킬/몬스터/보스/아이템/던전)
- save/progress.json : 진행도 저장 파일 (없으면 자동 생성)

데이터 교체 가이드 (TCToPyTest 호환)
-----------------------------------
- data/*.json 스키마는 요구사항에 맞춰 고정. 기존 레포 수치를 그대로 옮기려면 같은 key 에 값을 덮어쓰면 됩니다.
- players.json : base_stats는 attack/magic/defense/magic_resist/max_hp 를 사용하며 skills 배열에 사용 스킬 ID를 나열합니다.
- skills.json : base_physical/base_magic(또는 base), scale.attack / scale.magic 값으로 데미지/방어감소 계수를 지정, apply_effect 로 상태(chance/duration/power) 부여 정의
- monsters.json : stats는 defense/magic_resist 포함, ai=="basic"이면 skills 배열에서 랜덤 스킬 사용
- bosses.json : dungeon_bosses, special_bosses 아래 gimmicks 배열(예: every_n_turns) 사용
- items.json : equipment/consumable/material 구분, drop_tables 는 확률(chance)과 수량(min/max) 지원
- dungeons.json : zones -> stages -> monster_pool 또는 boss_id, exp 필수

아이템/드랍 스키마 요약
---------------------
- items.json 루트: { "items": {...}, "drop_tables": {...} }
- item 공통 필드: name, type(equipment|consumable|material), rarity(common|rare|epic|legendary), desc, icon, stats(attack/magic/defense/magic_resist/max_hp), special, use_effect
- equipment: slot(weapon|armor|accessory) 필수, stats 합산, special은 on_hit 등 옵션
- special 예시: on_hit(기절 등 상태 부여), stat_multiplier(특정 스탯을 % 단위로 곱연산, 예: {"type":"stat_multiplier","stat":"magic","mult":1.2})
- consumable: use_effect 필수 (type: heal/cleanse/buff_stats, target self, power/duration/stats/remove/scope)
- material: 보관용, use_effect 없음
- drop_tables: [ {"item": "id", "chance": 0.25, "min": 1, "max": 2} ] 형태로 수량 범위 지원

소모품 사용 규칙
---------------
- 전투 화면의 아이템 버튼으로만 사용 가능하며 행동 1회를 소비
- heal: power 만큼 즉시 회복(최대 체력까지), cleanse: remove 목록의 상태이상 제거, buff_stats: duration 동안 전투 한정 스탯 버프
- 스턴 등 행동 불가 상태일 때는 사용 불가

인벤토리 저장 형식
-----------------
- progress.json에 inventory 는 {"item_id": count} 딕셔너리 형태로 저장되며 구버전 리스트는 자동 마이그레이션
- 장비는 equipment: {"weapon": id|None, "armor": id|None, "accessory": id|None}로 저장

자동 저장 트리거
--------------
- 앱 시작 시 progress.json 없으면 기본값 생성
- 전투 승리, 장비 변경, 스탯 분배 시 save/progress.json 갱신

이미지/에셋 로딩
----------------
- 자동 매칭 규칙: characters/{player_id}.* , enemies/{enemy_id}.* , backgrounds/{name or default}.* , icons/{effect_id}.* (png/webp/jpg/jpeg)
- alias: buff_stats->buff, debuff_stats->debuff (icons에 buff/debuff만 있어도 매핑)
- 파일이 없거나 손상돼도 회색 박스 플레이스홀더로 폴백하여 크래시 없음

전투 연출(풀패키지)
------------------
- TURN 배너: 턴 시작마다 중앙 상단에 "TURN N" 배너가 잠깐 떠서 템포를 알림
- 피해 숫자: 피격/회복 시 데미지 텍스트가 위로 떠오르며 사라짐, 크리티컬이면 글자가 커지고 강조됨
- HP바: HP 변화는 점프하지 않고 부드럽게 보간(animate_hpbar)
- 흔들림/플래시: 피격 시 대상 패널이 살짝 흔들리고 색상이 번쩍이며 타격감을 제공
- 크리티컬: 일정 확률 또는 큰 피해 시 CRIT 표시, 흔들림/플래시 강도가 상승
- 스킬 오버레이: 스킬 사용 시 대상 위에 오버레이 이미지를 잠깐 투영. 에셋이 없으면 기본 라이트/번쩍 효과 사용
- 입력 보호: 연출이 재생되는 0.4초 동안 공격/스킬/아이템 버튼이 잠시 비활성화되어 꼬임을 방지
- 쿨타임 안내: 각 캐릭터의 4번째 스킬은 5턴마다 1회 사용 가능하며, 쿨타임 중 버튼이 비활성화되고 "(n턴 뒤)"로 남은 턴을 표시

스킬 오버레이 에셋 규칙
-----------------------
- 경로: assets/effects/
- 파일명: {skill_id}.png 또는 {normalized_skill_id}.png (png/webp/jpg/jpeg 순서 탐색)
- 예: assets/effects/skill_독살.png, assets/effects/피의사슬.png
- 없으면 기본 오버레이(라이트 원/번쩍)가 표시됨

에셋 검수 도구
--------------
- python tools/assets_check.py: 캐릭터/몬스터/보스/아이콘/배경뿐 아니라 스킬 이펙트 에셋까지 자동 확인해 누락을 보고함
- 스킬 이펙트는 접두어 유무(skill_/미포함)와 정규화된 이름까지 모두 탐색해 실제 파일명을 최대한 자동 매칭

기본 동작 시나리오
-----------------
1) 앱 실행 → 메인 화면
2) 던전: zone1 stage1 입장 → 전투 → 승리 시 EXP/드랍, 다음 스테이지 해금
3) 스탯 화면에서 포인트 분배 → 전투 능력에 반영
4) 인벤토리에서 장비 장착/해제 → 스탯 합산 반영
5) 특수 보스(심연의 군주) 전투 → 3턴마다 출혈 기믹 → 승리 시 장신구 드랍 테이블 롤

추가 참고
--------
- UI 텍스트는 모두 한국어.
- 상태이상: bleed(턴 종료 피해), stun(해당 턴 행동 불가).
- 데미지 공식: 기본데미지 + (스탯*계수) - (방어*0.5) 최소 1.
