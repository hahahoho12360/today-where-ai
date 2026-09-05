# 초등학생도 따라 하는 완성·배포·증빙 가이드

이 문서는 “무엇을 누르고, 왜 하는지”를 작은 단계로 나눕니다. 한 단계가 끝날 때마다 체크 상자를 표시하세요.

## 0단계. 웹서비스를 가게로 생각하기

- HTML은 가게의 **벽과 진열대**입니다.
- CSS는 가게의 **색과 가구 배치**입니다.
- JavaScript는 버튼을 누르면 움직이는 **직원**입니다.
- Python API는 손님에게 안 보이는 **주방**입니다.
- 환경 변수는 주방 금고에 넣는 **비밀 열쇠**입니다.
- Vercel은 가게를 인터넷에 올려 주는 **건물**입니다.

이 프로젝트에서는 브라우저가 키를 알지 못합니다. 브라우저는 `/api/generate`에 주문만 보내고, Python이 금고의 키를 꺼내 외부 API와 이야기합니다.

## 1단계. 준비물 설치

- [ ] Python 3.12 설치
- [ ] Node.js LTS 설치
- [ ] Git 설치
- [ ] VS Code 설치
- [ ] GitHub 계정 만들기
- [ ] Vercel 계정 만들고 GitHub로 연결

터미널에서 아래 명령을 한 줄씩 입력합니다.

```bash
python --version
node --version
git --version
```

세 명령이 모두 버전 번호를 보여 주면 성공입니다. 오류가 나면 다음 단계로 가지 말고 설치부터 고칩니다.

## 2단계. 프로젝트 열기와 가상환경

1. 압축을 풉니다.
2. VS Code에서 **File → Open Folder**로 `today-where-ai` 폴더를 엽니다.
3. **Terminal → New Terminal**을 누릅니다.
4. 아래 명령을 실행합니다.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

- [ ] 터미널 앞에 `(.venv)`가 보임
- [ ] 필요한 Python 꾸러미 설치가 끝남
- [ ] `.env` 파일이 생김

가상환경은 이 프로젝트만 쓰는 별도 장난감 상자입니다. 다른 Python 프로젝트와 부품이 섞이지 않게 합니다.

## 3단계. API 키 준비와 안전하게 넣기

### OpenAI

1. [OpenAI API dashboard](https://platform.openai.com/)에서 프로젝트와 API 키를 만듭니다.
2. 사용량 한도를 작게 정합니다.
3. `.env`의 `OPENAI_API_KEY=` 오른쪽에 붙여 넣습니다.
4. `OPENAI_MODEL=gpt-5.6-luna`를 둡니다. 계정에서 사용할 수 없다면 사용 가능한 텍스트 모델 ID로 바꿉니다.

### 카카오

1. [Kakao Developers](https://developers.kakao.com/)에서 애플리케이션을 만듭니다.
2. 앱 키에서 **REST API 키**를 복사합니다.
3. `.env`의 `KAKAO_REST_API_KEY=` 오른쪽에 붙여 넣습니다.

### TourAPI - 선택 보너스

1. [공공데이터포털](https://www.data.go.kr/)에서 한국관광공사 국문 관광정보 서비스 활용 신청을 합니다.
2. 발급받은 일반 인증키를 `.env`의 `TOUR_API_KEY=` 오른쪽에 넣습니다.
3. 이 키가 없어도 핵심 기능은 동작하고, 행사 카드가 키 등록 안내를 보여 줍니다.

안전 확인:

- [ ] `.env`는 `.gitignore` 안에 있음
- [ ] 키가 `README.md`, 코드, 캡처 화면에 없음
- [ ] `.env.example`에는 `your_...` 예시만 있음

왜 이렇게 하나요? GitHub는 전 세계가 볼 수 있는 게시판이 될 수 있습니다. 비밀 키가 올라가면 다른 사람이 내 돈으로 API를 사용할 수 있습니다.

## 4단계. 로컬에서 실행

```bash
npm install -g vercel
vercel dev
```

처음 한 번은 로그인과 프로젝트 연결 질문이 나옵니다. 터미널에 표시된 로컬 주소를 브라우저에서 엽니다.

확인 순서:

- [ ] 메뉴 5개가 각 섹션으로 이동
- [ ] 지역을 빈칸으로 두고 “지역 확인” → 친절한 오류 표시
- [ ] 전체 지역명 입력 → 법정동·행정동 표시
- [ ] AI 하루 여행 만들기 → 시간표와 장소 카드 표시
- [ ] 음식점·카페·주차장 “다른 곳” → 카드가 바뀜
- [ ] 새로고침 → 최근 여행이 남아 있음
- [ ] 다크 모드 → 글자가 읽힘

현재 위치는 브라우저가 로컬 주소를 안전한 출처로 인정할 때 동작할 수 있지만, **최종 판정은 반드시 Vercel HTTPS 주소에서** 합니다.

## 5단계. 자동 검사

```bash
python -m unittest discover -s tests -v
node --check js/app.js
```

- [ ] Python 테스트가 모두 `OK`
- [ ] JavaScript 검사에 오류 문장이 없음

자동 검사는 철자와 약속을 빠르게 살피는 로봇 검사관입니다. 하지만 실제 API와 휴대폰 화면은 사람이 한 번 더 확인해야 합니다.

## 6단계. 보너스 과제 2개가 자연스럽게 들어간 곳

### 보너스 1: 데이터 저장·운영 흐름

계획을 만들면 JavaScript가 결과를 localStorage에 자동 저장합니다. 최근 5개만 남겨 저장 공간이 끝없이 커지는 일을 막습니다. 개별 재추천은 서버를 다시 호출하지 않고 이미 받은 후보에서 다음 장소를 꺼내므로 비용과 대기시간도 줄입니다.

검사:

- [ ] 여행 A 생성
- [ ] 새로고침
- [ ] “최근 여행”에서 A가 다시 열림
- [ ] 개별 재추천 때 네트워크를 다시 기다리지 않고 즉시 바뀜

### 보너스 2: UX와 측정

다크 모드, 버튼 움직임, 로딩 화면, 움직임 줄이기 설정, 모바일 레이아웃을 적용했습니다. “내 여행”에는 이 브라우저의 방문 수·계획 수·재추천 수·최근 응답시간이 표시됩니다.

검사:

- [ ] 라이트/다크 모드 각각 캡처
- [ ] 개발자 도구에서 390 × 844 화면 확인
- [ ] AI 생성 전후 계획 수와 응답시간 기록
- [ ] `prefers-reduced-motion` 사용자는 큰 애니메이션 없이 사용 가능

주의: 이 숫자는 전체 사용자 통계가 아니라 **현재 브라우저의 로컬 지표**입니다. 보고서에 전체 방문자 수라고 쓰면 안 됩니다.

## 7단계. Git 저장소 만들기

```bash
git init
git add .
git commit -m "feat: build verified local AI trip planner"
```

GitHub에서 빈 저장소 `today-where-ai`를 만든 뒤 GitHub가 보여 주는 `git remote add origin ...`와 `git push ...` 명령을 실행합니다.

```bash
git status
```

`nothing to commit, working tree clean`이면 저장이 잘 된 것입니다. GitHub 페이지에서 `.env`가 보이면 즉시 키를 폐기하고 기록 정리까지 해야 합니다.

## 8단계. Vercel에 배포

1. Vercel Dashboard에서 **Add New → Project**를 누릅니다.
2. GitHub의 `today-where-ai`를 **Import**합니다.
3. Framework Preset은 **Other**로 둡니다.
4. Environment Variables에 아래를 한 줄씩 넣습니다.
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `KAKAO_REST_API_KEY`
   - `TOUR_API_KEY`(선택)
5. **Deploy**를 누릅니다.
6. 완성 주소의 `/api/health`를 열어 `ok: true`인지 확인합니다.
7. 메인 주소에서 직접 입력·현재 위치·AI 생성·재추천·새로고침을 모두 시험합니다.

배포에서 고쳤다면:

```bash
git add .
git commit -m "fix: handle deployment issue"
git push
```

Vercel이 새 커밋을 자동 재배포합니다. 이것이 과제에서 말하는 “수정 → 재배포” 흐름입니다.

## 9단계. README의 URL 완성

`README.md` 맨 위의 두 줄을 실제 주소로 바꿉니다.

```text
배포 URL: https://실제이름.vercel.app
GitHub URL: https://github.com/실제아이디/today-where-ai
```

바꾼 뒤 커밋하고 push합니다.

## 10단계. 매우 중요 - “최종 결과물 증빙” 만들기

이 단계는 기능 개발과 **별개의 채점 대상**입니다. 웹이 잘 작동해도 증빙이 빠지면 완성 제출물이 아닙니다. 키·정확한 좌표·개인정보가 화면에 보이지 않게 한 뒤 아래 파일을 만드세요.

### A. 서비스 화면 1세트

`evidence/` 폴더에 다음 이름으로 저장하면 헷갈리지 않습니다.

1. `01-desktop-home.png`: 데스크톱 전체 화면과 메뉴 5개
2. `02-mobile-responsive.png`: 개발자 도구 390px 모바일 화면
3. `03-ai-input-result.png`: 입력 조건과 AI 시간표·장소 결과가 함께 보이는 화면
4. `04-error-message.png`: 빈 입력 또는 잘못된 지역의 친절한 오류
5. `05-bonus-dark-history.png`: 다크 모드와 최근 여행/로컬 측정값

데스크톱 캡처:

1. 배포 URL을 엽니다.
2. 브라우저 확대를 100%로 둡니다.
3. 핵심 내용이 보이게 캡처합니다.

모바일 캡처(Chrome/Edge):

1. `F12` → 휴대폰/태블릿 아이콘을 누릅니다.
2. 크기를 `390 × 844`로 맞춥니다.
3. 메뉴, 입력, 결과 카드가 잘리지 않는지 확인하고 캡처합니다.

AI 작동 캡처:

1. 지역·날짜·관심사를 입력한 상태를 남깁니다.
2. “AI 하루 여행 만들기” 후 제목·시간표·세 장소가 보이게 캡처합니다.
3. API 키, 개발자 도구의 요청 헤더, 정확한 위도·경도는 캡처하지 않습니다.

### B. AI 코딩 도구 사용 과정 1세트

AI와 주고받은 대화 또는 코드 생성·오류 수정 과정 중 아래 세 가지가 보이는 화면을 캡처합니다.

- 요청: “순수 HTML/CSS/JS와 Vercel Python API로 구현”
- 문제: 실제로 만난 오류 또는 테스트 실패
- 해결: 원인을 설명하고 수정·재검사한 결과

파일 예시: `06-ai-coding-process.png`

**절대로 채팅이나 터미널에 API 키를 붙여 넣어 캡처하지 마세요.**

### C. 서비스 기획서

- [ ] `docs/SERVICE_PLAN.md`에 목적·타깃·섹션·AI 입력/출력/실패 기준이 있음

### D. 최종 URL 재현 테스트

내 컴퓨터에만 로그인된 상태로 검사하면 안 됩니다. 시크릿 창 또는 다른 휴대폰에서:

- [ ] URL이 로그인 없이 열림
- [ ] 5개 메뉴 이동
- [ ] 직접 입력 → 지역 확인
- [ ] AI 입력 → 결과 출력
- [ ] 모바일에서 가로 잘림 없음
- [ ] 오류 안내 확인

### E. 제출 전 5종 패키지

- [ ] 1. Vercel URL
- [ ] 2. GitHub 저장소
- [ ] 3. README.md
- [ ] 4. 서비스 기획서
- [ ] 5. 데스크톱·모바일·AI 동작·AI 코딩 도구 증빙

`docs/SUBMISSION_TEMPLATE.md`에 주소와 파일명을 적고 그대로 제출 메모로 사용합니다.

## 11단계. “완벽하게 작동”의 현실적인 뜻

외부 API는 사용량 초과나 장애가 생길 수 있으므로 100% 영원히 실패하지 않는 서비스는 없습니다. 좋은 서비스는 정상일 때 정확히 작동하고, 실패했을 때 이유와 다음 행동을 알려 줍니다. 이 프로젝트는 다음을 완성 기준으로 삼습니다.

- 정상 입력: 실제 장소 기반 결과
- AI가 가짜 ID 출력: 서버가 제거 또는 실제 후보로 대체
- 빈 입력: 즉시 안내
- 키·권한 문제: 설정 확인 안내
- 느린 응답: 타임아웃 안내
- 장소·행사 없음: 만들어 내지 않고 없음 표시
- 모바일: 핵심 버튼과 카드가 화면 안에 표시

모든 항목이 `TEST_CHECKLIST.md`에서 통과한 뒤에만 최종 제출하세요.

