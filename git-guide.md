---

# 📖 Git & GitHub Actions 협업 가이드라인

본 문서는 **Rescue AMR Project**의 소스코드 품질 관리와 원활한 협업을 위한 공식 Git 및 CI(지속적 통합) 가이드라인입니다. 모든 팀원은 작업 시작 전 본 문서를 반드시 숙지하고 규정을 준수해야 합니다.

---

## 1. Git & CI 시스템 개요

### 💡 Git이란 무엇이며 왜 사용하나요?

Git은 소스코드의 변경 이력을 유연하게 기록하고 관리하는 분산 버전 관리 시스템(DVCS)입니다.

* **이력 추적**: 코드가 언제, 누구에 의해, 왜 수정되었는지 정확히 추적하여 버그 발생 시 원인을 빠르게 규명합니다.
* **안전한 병렬 개발**: 하나의 코드 베이스에서 여러 팀원이 서로의 코드를 덮어쓰는 사고 없이 각자의 기능을 동시에 개발할 수 있습니다.

### 💻 로컬(Local) vs 원격(Remote) 브랜치 개념

* **로컬 브랜치 (Local Branch)**: 개발자 개인의 컴퓨터(우분투 환경 등)에만 존재하는 격리된 작업 공간입니다. 실험적인 코드를 마음껏 짜고 실패하면 언제든 되돌릴 수 있습니다.
* **원격 브랜치 (Remote Branch)**: GitHub 서버에 올라가 있는 공용 작업 공간입니다. 팀원들이 서로의 진행 상황을 공유하고 코드를 통합하는 기준점이 됩니다.

### 🤖 CI(지속적 통합) 시스템 vs 로컬 검증

* **로컬 검증**: 개발자가 push 전 개인 컴퓨터 환경에서 빌드와 테스트를 수행하는 단계입니다. 개인의 OS 환경 설정이나 누적된 파이썬 패키지 상태에 따라 '오염된 결과'가 나올 수 있습니다.
* **CI 시스템 (GitHub Actions)**: 코드가 원격 레포지토리에 반영되거나 PR이 열릴 때마다, 아무것도 없는 순수한 가상 컴퓨터(Clean Room)를 실행하여 처음부터 빌드 및 테스트를 자동 수행하는 시스템입니다. "내 컴퓨터에서는 잘 되는데요?" 문제를 원천 차단하고 서버 환경에서의 100% 구동을 보장합니다.

---

## 2. Git 핵심 명령어 및 옵션 대백과

### 📥 1. 정보 가져오기 및 동기화 (`fetch`, `pull`)

* **`git fetch origin`**
* **개념**: 원격 저장소(GitHub)의 최신 변경 이력 정보만 로컬로 땡겨옵니다. 실제 로컬 소스코드가 바뀌거나 병합되지는 않으므로, 안전하게 원격의 상태를 염탐할 때 씁니다.


* **`git pull origin <브랜치명>`**
* **개념**: 원격 저장소의 최신 커밋을 가져옴과 동시에 현재 내 로컬 브랜치와 병합(`Merge`)합니다.
* **⚡ 필수 옵션**: `--rebase` (`git pull origin develop --rebase`)
* 그냥 pull을 하면 지저분한 머지 커밋(Merge branch...)이 양산됩니다. `--rebase` 옵션을 쓰면 원격의 최신 커밋들 위에 내 커밋을 한 줄로 예쁘게 다시 쌓아 히스토리를 직선으로 유지해 줍니다.





### 🔄 2. 이동 및 상태 확인 (`switch`, `status`, `log`)

* **`git switch <브랜치명>`**
* **개념**: 작업할 브랜치로 공간을 이동합니다. (과거 `checkout` 명령어에서 이동 기능만 독립된 최신 표준 명령어)
* **⚡ 필수 옵션**: `-c` (`git switch -c feature/login`)
* 해당 이름의 브랜치를 새로 생성(Create)함과 동시에 그 브랜치로 즉시 이동합니다.




* **`git status`**
* **개념**: 현재 수정된 파일, 추적되지 않는 파일(`.gitignore`에 걸리지 않은 파일), 스테이징된 파일의 상태를 실시간으로 보여주는 터미널의 나침반입니다.


* **`git log`**
* **개념**: 지금까지 쌓인 커밋 히스토리를 확인합니다.
* **⚡ 추천 옵션**: `--oneline --graph` (`git log --oneline --graph`)
* 커밋 로그를 한 줄씩 그래프 형태로 시각화하여 전체 브랜치의 흐름을 직관적으로 보여줍니다.





### 💾 3. 기록하고 내보내기 (`add`, `commit`, `push`)

* **`git add <파일명>`**
* **개념**: 수정된 파일을 다음 커밋 리스트(Staging Area)에 올립니다. `git add .`을 사용하면 현재 디렉토리의 모든 변경 사항을 한 번에 올립니다.


* **`git commit -m "메시지"`**
* **개념**: 스테이징된 파일들을 하나의 의미 있는 버전(커밋)으로 로컬 저장소에 영구 기록합니다. 메시지는 명확하게 작성해야 합니다.


* **`git push origin <브랜치명>`**
* **개념**: 로컬 저장소에 기록된 커밋들을 GitHub 원격 저장소로 쏘아 올립니다.
* **⚡ 필수 옵션**: `-u` (`git push -u origin feature/db`)
* 최초 1회만 사용하면 로컬 브랜치와 원격 브랜치를 동기화(Upstream 연동)시켜 줍니다. 이후에는 `git push`만 쳐도 알아서 제자리를 찾아 올라갑니다.





### 🛠️ 4. 강력한 제어 명령어 (`rebase`, `reset`)

* **`git rebase <브랜치명>`**
* **개념**: 내 브랜치의 출발점을 다른 브랜치의 최신 커밋 지점으로 통째로 옮겨 붙여, 히스토리를 갈래길 없이 일직선형 구조로 재정렬합니다.


* **`git reset`**
* **개념**: 과거의 특정 커밋 시점으로 내 로컬 시계를 강제로 되돌립니다.
* **⚡ 파괴적 옵션**: `--hard` (`git reset --hard origin/develop`)
* 지정한 시점 이후의 **모든 로컬 수정 사항과 커밋을 가차 없이 영구 삭제**하고 워킹 디렉토리를 깨끗하게 포맷합니다. 원격 상태와 똑같이 맞추고 싶을 때 최후의 수단으로 씁니다.





---

## 3. Rescue AMR 프로젝트 브랜치 전략 및 규칙

우리 팀은 안정적인 AMR 시스템 구축을 위해 **`main`**, **`develop`**, 그리고 기능별 **작업 브랜치** 구조로 저장소를 운영합니다.

```text
  main (최종 릴리즈 / 실장 테스트용 방어선)
   ▲
   │ (Pull Request 및 팀장 최종 승인)
  develop (팀원들의 1차 통합 및 부분 CI 검증 공간)
   ▲
   ├── feature/database (새로운 기능 추가)
   ├── refact/ui-bridge (기존 코드 구조 개선)
   └── debug/mqtt-fix   (버그 수정)

```

### 📋 1. 브랜치 명명 규칙 (Branch Naming Convention)

팀원들은 목적에 따라 반드시 아래의 접두사를 사용하여 로컬 브랜치를 파고 작업해야 합니다.

* **`feature/기능이름`**: 새로운 기능 개발 (예: `feature/yolo-detection`, `feature/db-api`)
* **`refact/개선이름`**: 기능 변경 없이 폴더 구조 변경, 성능 최적화, UI 브릿지 개편 등 코드 가독성 및 아키텍처 향상 (예: `refact/ui-bridge`)
* **`debug/버그이름`**: 에러 로그 해결 및 오작동 대처 (예: `debug/mqtt-handler`)

### 🔒 2. Push 및 Merge 관련 3대 팀 규칙 (Repository Ruleset)

GitHub 레포지토리에 강력한 보안 규칙이 걸려 있습니다. 이를 위반하면 push가 거절됩니다.

1. **`main` 및 `develop` 직접 push 원천 금지 (`Restrict updates`)**
* 그 누구도 `main`과 `develop` 브랜치에 `git push`로 코드를 직접 꽂을 수 없습니다. 무조건 본인의 기능 브랜치(`feature/*`)를 push한 후 Pull Request(PR)를 통해서만 합칠 수 있습니다.


2. **강제 Push 금지 (`Block force pushes`)**
* 로컬 히스토리를 리셋했다고 해서 원격 저장소에 `git push -f`를 날리는 행위는 금지됩니다. 팀원들의 히스토리가 통째로 날아가는 것을 방지합니다.


3. **CI 검사관 통과 필수 (`Require status checks to pass`)**
* `develop`이나 `main` 브랜치로 합쳐지기 위한 모든 PR은 GitHub Actions 서버에서 수행하는 `pytest-backend` 테스트를 반드시 통과(초록불 `✔`)해야 합니다. 빨간불(`✖`) 상태에서는 머지 버튼이 원천 봉쇄됩니다.



---

## 4. 실전 시나리오별 터미널 명령어 가이드

### 🎬 시나리오 A: 새 프로젝트 원격에 최초 연동 (팀장 초기 세팅용)

```bash
# 1. README 작성 및 깃 초기화
echo "# rescue_amr_project" >> README.md
git init

# 2. 첫 커밋 쌓기
git add README.md
git commit -m "chore: 레포지토리 초기화 및 가이드라인 등록"

# 3. 메인 브랜치 설정 및 원격 연결 후 푸시
git branch -M main
git remote add origin https://github.com/dev-kibeom/rescue_amr_backend.git
git push -u origin main

```

### 🎬 시나리오 B: 팀원이 원격 저장소 복제 후 환경 설정 (팀원 최초 연동)

```bash
# 1. 프로젝트 원격 코드 클론 및 디렉토리 진입
git clone https://github.com/dev-kibeom/rescue_amr_backend.git
cd rescue_amr_project

# 2. 개인 깃 사용자 설정 명시 (닉네임/이메일 오염 방지)
git config --global user.name "본인이름"
git config --global user.email "본인이메일"

# 3. 원격의 develop 브랜치가 잘 있는지 확인 후 트래킹
git fetch origin
git switch develop

```

### 🎬 시나리오 C: 기능 구현 시작 (브랜치 따기 및 버전 관리)

```bash
# 1. 무조건 최신 'develop' 상태에서 시작합니다.
git switch develop
git pull origin develop --rebase

# 2. 규칙에 맞춰 내 작업 브랜치를 새로 생성하며 이동합니다.
git switch -c feature/db-api

# 3. [코드 열공 및 구현 진행...] 후 실시간 상태 확인
git status

# 4. 내 로컬에 안전하게 버전 기록 (커밋은 자주, 쪼개서 할수록 좋습니다)
git add .
git commit -m "feat: 데이터베이스 turtlebot4 테이블 엔드포인트 구현"

```

### 🎬 시나리오 D: 내 작업 브랜치 원격에 올리고 PR 날리기 (협업의 핵심)

```bash
# 1. push 전, 내가 일하는 동안 남이 develop에 올려둔 최신 코드가 있는지 확인하고 내 커밋을 그 뒤로 이어 붙입니다.
git fetch origin
git rebase origin/develop

# 2. 뼈대 정리가 끝난 내 브랜치를 GitHub 서버로 쏘아 올립니다.
git push -u origin feature/db-api

# 3. [GitHub 웹사이트 접속] -> [Compare & pull request] 버튼 클릭
# 4. PR 본문에 테스트한 내용 요약 적고 [Create pull request] 발송!

```

### 🎬 시나리오 E: 작업 완료 후 로컬 환경 정리정돈

개발 팀장이 PR을 승인하여 원격 `develop`에 내 코드가 합쳐졌다면, 내 컴퓨터도 깨끗하게 동기화해 줍니다.

```bash
# 1. 내 로컬의 대피소를 최신 개발 기지 상태로 맞춥니다.
git switch develop
git pull origin develop --rebase

# 2. 이제 임무를 다한 로컬 기능 브랜치는 깔끔하게 삭제합니다.
git branch -d feature/db-api

```

### 🎬 시나리오 F: 로컬 작업이 완전히 꼬여서 원격 상태로 강제 포맷하고 싶을 때 (치료제)

*"머지하다가 터졌어요", "이것저것 만지다가 완전 개판 됐어요"* 할 때 뇌를 비우고 원격 상태로 초기화하는 치트키입니다.

```bash
# 1. 원격의 최신 정보를 리프레시하고
git fetch origin

# 2. 내가 현재 있는 브랜치의 소스코드와 이력을 원격의 develop 상태로 100% 강제 밀어버립니다.
git reset --hard origin/develop

# 3. 추적되지 않던 찌꺼기 빌드 파일이나 쓰레기 파일까지 싹 소각합니다.
git clean -fd

```

---

## 5. Pull Request(PR) 개념 및 코드 리뷰 문화

### 🔍 Pull Request(PR)란 무엇인가요?

직역하면 "내가 짠 코드가 완벽하니, 원격의 메인 브랜치(`develop` 또는 `main`)로 당겨서 합쳐달라(Pull)"고 관리자(팀장)에게 보내는 정중한 **합류 요청 서신**입니다.

### 💬 코드 리뷰 및 대화 해결 규칙

* **코드 라인별 댓글**: 팀장님이나 동료 팀원들이 PR의 `Files changed` 탭에서 소스코드 특정 줄에 "여기에 데이터 예외 처리가 누락되면 토픽 발행할 때 AMR 제어 노드가 터질 수 있어요" 같은 피드백을 남길 수 있습니다.
* **`Require conversation resolution sebelum merging`**:
* 리뷰어가 코드에 남긴 모든 의견과 토론이 완료되어 **[Resolve conversation]** 버튼이 눌리기 전까지는 최종 머지가 금지됩니다. 피드백을 대충 무시하고 합치는 행위를 시스템이 차단해 줍니다.



---

## 🚨 [중요] .gitignore 데이터 오염 주의보

프로젝트 루트에 설정된 `.gitignore` 파일에 의해 아래 폴더들은 **절대 Git 추적 대상에 들어오지 않도록 정교하게 필터링**되어 있습니다:

* `admin_dashboard/node_modules/` (웹 라이브러리 파편 폴더)
* `/__pycache__/` / `*.pyc` (파이썬 컴파일 캐시) 
* `turtlebot4_ws/build/, install/, log/` (ROS 2 빌드 아티팩트) 
* `.db_data/` (도커 컴포즈가 사용하는 실제 DB 원본 데이터 저장소)

**절대로 깃이그노어 규칙을 임의로 해제하거나 강제로 위 폴더 안의 파일들을 push하지 마십시오.** 원격 저장소 오염의 주범이 됩니다.

---