# Django + Docker 기반 6/45 로또 웹사이트 개발 보고서

> 과목: Docker Tutorial 실습 과제  
> 제출일: 2026년 5월  
> GitHub 링크: `https://github.com/YOUR_USERNAME/lucky645-lotto` *(제출 전 실제 URL로 교체)*

---

## 1. 시스템 설계

### 1.1 요구사항 분석

| 구분 | 기능 |
|------|------|
| 일반 사용자 | 회원가입/로그인, 복권 구매(수동/자동), 당첨 확인 |
| 관리자 | 판매 내역 확인, 추첨 실행, 당첨 내역 확인, 회차 관리 |
| 시스템 | Docker multi-container 환경 |

### 1.2 아키텍처 설계

```
[사용자 브라우저]
       ↓ HTTP :80
  [Nginx 컨테이너]  ← static 파일 직접 서빙
       ↓ proxy_pass
  [Django 컨테이너]  (Gunicorn WSGI)
       ↓ psycopg2
  [PostgreSQL 컨테이너]
       ↓
  [Named Volume: postgres_data]
```

**Multi-container 구성 (docker-compose.yml):**

| 컨테이너 | 이미지 | 역할 |
|---------|--------|------|
| `lotto_db` | postgres:15-alpine | 데이터베이스 |
| `lotto_web` | 커스텀 빌드 (python:3.11-slim) | Django 애플리케이션 |
| `lotto_nginx` | nginx:1.25-alpine | 리버스 프록시, Static 서빙 |

### 1.3 데이터 모델

**LottoRound (회차)**
```
- round_number: 회차 번호 (고유)
- draw_date: 추첨일
- num1~num6: 당첨 번호
- bonus: 보너스 번호
- is_drawn: 추첨 완료 여부
```

**LottoTicket (복권 티켓)**
```
- user: 구매자 (FK → User)
- round: 회차 (FK → LottoRound)
- num1~num6: 선택 번호
- purchase_type: 수동/자동
- rank: 당첨 등수 (0=낙첨, null=미확인)
- prize: 당첨금
- is_checked: 당첨 확인 여부
```

### 1.4 당첨 규칙

| 등수 | 조건 | 당첨금 |
|------|------|--------|
| 1등 | 6개 일치 | 20억 원 |
| 2등 | 5개 + 보너스 | 6,000만 원 |
| 3등 | 5개 일치 | 150만 원 |
| 4등 | 4개 일치 | 5만 원 |
| 5등 | 3개 일치 | 5,000원 |

---

## 2. 디렉토리 구조

```
lotto_project/
├── docker-compose.yml       ← 멀티 컨테이너 정의
├── Dockerfile               ← Django 앱 이미지 빌드
├── entrypoint.sh            ← 컨테이너 시작 시 실행 (migrate, superuser 생성 등)
├── requirements.txt         ← Python 의존성
├── manage.py
├── nginx/
│   └── nginx.conf           ← Nginx 설정 (리버스 프록시)
├── lotto_app/               ← Django 프로젝트 설정
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── lotto/                   ← Django 앱
    ├── models.py            ← LottoRound, LottoTicket
    ├── views.py             ← 사용자/관리자 뷰
    ├── urls.py
    ├── admin.py
    └── templates/lotto/
        ├── base.html
        ├── index.html
        ├── buy_ticket.html
        ├── my_tickets.html
        ├── draw_history.html
        ├── login.html
        ├── register.html
        ├── admin_dashboard.html
        ├── admin_draw.html
        ├── admin_sales.html
        └── admin_winners.html
```

---

## 3. 구현 과정

### 3.1 Docker 이미지 구성

**Dockerfile 핵심 내용:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev gcc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["/entrypoint.sh"]
```
- `python:3.11-slim` 경량 이미지 사용
- requirements 레이어를 먼저 COPY하여 빌드 캐시 최적화
- entrypoint.sh에서 DB 연결 대기 → migrate → superuser 생성 → Gunicorn 실행

**docker-compose.yml 핵심 설계:**
- `db` 서비스에 `healthcheck` 설정 → `web`이 DB 준비 후에만 시작 (`depends_on: condition: service_healthy`)
- `lotto_net` 브릿지 네트워크로 컨테이너 간 통신
- `postgres_data` named volume으로 데이터 영속화
- `static_volume` shared volume으로 Nginx가 static 파일 직접 서빙

### 3.2 Django 애플리케이션 구현

**사용자 기능:**
1. 회원가입/로그인 – Django 내장 `UserCreationForm`, `LoginView` 활용
2. 복권 구매(수동) – 번호판 UI에서 클릭 선택 또는 직접 입력, 유효성 검사
3. 복권 구매(자동) – `random.sample(range(1,46), 6)` 서버 측 생성
4. 당첨 확인 – 당첨 번호와 집합 연산으로 일치 개수 계산, 보너스 확인
5. 내 티켓 목록 – 등수, 당첨금, 상태 표시

**관리자 기능:**
1. 대시보드 – 총 판매 티켓, 매출, 당첨자 수 통계
2. 추첨 실행 – `random.sample(range(1,46), 7)` 후 상위 6개=당첨, 1개=보너스
3. 자동 다음 회차 생성 – 추첨 완료 시 다음 회차 자동 생성
4. 판매 내역 / 당첨 내역 조회

### 3.3 Nginx 리버스 프록시 설정

```nginx
upstream django { server web:8000; }
server {
    location /static/ { alias /app/staticfiles/; }  # 직접 서빙
    location / { proxy_pass http://django; }         # Django 프록시
}
```

---

## 4. 실행 방법

### 4.1 사전 준비
- Docker Desktop 설치 및 실행 확인
- 소스코드 클론: `git clone https://github.com/YOUR_USERNAME/lucky645-lotto`

### 4.2 서비스 시작

```bash
# 1. 프로젝트 디렉토리로 이동
cd lotto_project

# 2. Docker 이미지 빌드 및 컨테이너 시작
docker-compose up --build -d

# 3. 컨테이너 상태 확인
docker-compose ps

# 4. 로그 확인 (web 컨테이너)
docker-compose logs -f web
```

### 4.3 서비스 접속

| URL | 설명 |
|-----|------|
| `http://localhost/` | 메인 페이지 |
| `http://localhost/register/` | 회원가입 |
| `http://localhost/buy/` | 복권 구매 |
| `http://localhost/admin-panel/` | 관리자 패널 |
| `http://localhost/admin/` | Django Admin |

**기본 관리자 계정:** `admin` / `admin1234`

### 4.4 서비스 중지 및 데이터 초기화

```bash
# 서비스 중지 (데이터 보존)
docker-compose down

# 서비스 중지 + 데이터 삭제
docker-compose down -v

# 이미지 재빌드
docker-compose up --build -d
```

---

## 5. 테스트 결과

### 5.1 컨테이너 실행 확인

```
$ docker-compose ps
NAME           IMAGE                  STATUS          PORTS
lotto_db       postgres:15-alpine     Up (healthy)    5432/tcp
lotto_web      lotto_project-web      Up              8000/tcp
lotto_nginx    nginx:1.25-alpine      Up              0.0.0.0:80->80/tcp
```

### 5.2 기능 테스트

| 테스트 항목 | 결과 |
|-------------|------|
| 회원가입 | ✅ 성공 |
| 로그인/로그아웃 | ✅ 성공 |
| 수동 번호 복권 구매 | ✅ 성공 |
| 자동 번호 복권 구매 | ✅ 성공 |
| 중복 번호 입력 방지 | ✅ 유효성 검사 작동 |
| 추첨 전 당첨확인 시도 | ✅ "추첨 전" 메시지 표시 |
| 관리자 추첨 실행 | ✅ 당첨번호 생성 및 저장 |
| 당첨 확인 (1~5등, 낙첨) | ✅ 등수 및 당첨금 정확 계산 |
| 판매 내역 조회 | ✅ 성공 |
| 당첨 내역 조회 | ✅ 등수별 통계 표시 |
| Nginx Static 서빙 | ✅ /static/ 경로 정상 동작 |
| DB 영속성 (재시작 후) | ✅ 데이터 유지 |

### 5.3 당첨 로직 검증

```python
# 테스트: 당첨번호 [1,2,3,4,5,6], 보너스 7
# 티켓 A: [1,2,3,4,5,6] → 1등 (6개 일치)
# 티켓 B: [1,2,3,4,5,7] → 2등 (5개 + 보너스)
# 티켓 C: [1,2,3,4,5,8] → 3등 (5개 일치)
# 티켓 D: [1,2,3,4,8,9] → 4등 (4개 일치)
# 티켓 E: [1,2,3,8,9,10] → 5등 (3개 일치)
# 티켓 F: [1,2,8,9,10,11] → 낙첨 (2개 일치)
```
모든 경우에서 정확한 등수 판정 확인.

---

## 6. 주요 Docker 명령어 정리

강의 자료(Docker-1)에서 학습한 명령어를 이 프로젝트에 적용:

```bash
# 이미지 확인 (docker image ls)
docker-compose images

# 실행 중 컨테이너 확인 (docker ps)
docker-compose ps

# 컨테이너 내부 명령 실행 (docker container exec)
docker-compose exec web python manage.py shell
docker-compose exec db psql -U lottouser lottodb

# 컨테이너 로그 확인 (docker logs)
docker-compose logs web
docker-compose logs db

# 리소스 사용량 확인 (docker stats)
docker stats lotto_web lotto_db lotto_nginx

# 네트워크 확인
docker network ls
docker network inspect lotto_project_lotto_net
```

---

## 7. AI 도구 사용 내역

본 과제에서 **Claude (Anthropic, claude-sonnet-4-6)** AI 도구를 사용하였으며 아래와 같이 활용하였습니다:

| 사용 항목 | 내용 |
|-----------|------|
| 프로젝트 전체 구조 설계 | Django 앱 구조, 파일 분리 방식 제안 |
| Django 모델 설계 | LottoRound, LottoTicket 모델 및 당첨 로직 구현 |
| Dockerfile 작성 | python:3.11-slim 기반 이미지 구성, entrypoint.sh |
| docker-compose.yml 작성 | 3-tier 구성, healthcheck, named volume 설정 |
| HTML 템플릿 구현 | 반응형 CSS, 로또볼 시각화, 번호판 인터랙션 |
| 보고서 작성 | 보고서 구조 및 내용 작성 지원 |

**검토 및 수정 사항:**
- 당첨 등수 계산 로직 직접 검토 및 테스트
- 컨테이너 의존성 순서(DB → Web → Nginx) 직접 확인
- DB 연결 재시도 로직 직접 테스트

---

## 8. 결론

Django와 Docker를 활용하여 6/45 로또 웹사이트를 성공적으로 구현하였습니다.

**핵심 학습 성과:**
- Docker 컨테이너의 격리성(Isolation)과 이식성(Portability) 직접 체험
- docker-compose를 통한 멀티 컨테이너 오케스트레이션
- Nginx-Django-PostgreSQL의 3-tier 웹 아키텍처 구현
- Named Volume을 통한 데이터 영속화
- Bridge 네트워크를 통한 컨테이너 간 통신
