# Архитектура EyeGate Mantrap

Цель: учебный двухдверный шлюз (mantrap) с полной цепочкой аутентификации, проверки лица и управления дверями/тревогой.

## Слои
1) **HW (hw/)** — управление GPIO замков/концевиков/сирены (sysfs) и заглушка Dummy.
2) **FSM (gate/)** — конечный автомат состояний шлюза + GateController, который исполняет действия (двери, таймеры, Vision, лог).
3) **Vision (vision/)** — сервисы анализа комнаты: `VisionServiceDummy` и `VisionServiceOpenCV` (Haar + embedding-заглушка).
4) **Auth (auth/)** — проверка карт (DB) и паролей (bcrypt), валидатор сложности паролей.
5) **DB (db/)** — SQLite, таблицы users/events/settings, миграции, логер событий.
6) **Server/Web (server/, web/)** — FastAPI API + Jinja2 шаблоны, статика HTML/CSS/JS.
7) **Deploy (deploy/)** — скрипт установки на Luckfox Pico Ultra + systemd unit.

## Потоки данных
- **Регистрация** (`/register`):
  веб-форма → снимок камеры (canvas dataURL) → `POST /api/auth/register` → bcrypt hash + embedding-заглушка → запись в `users` → событие в `events`.
- **Логин** (`/login`):
  логин/пароль → `POST /api/auth/login` → проверка bcrypt/is_blocked → `GateController.login_success(user_id)` → FSM `AuthResult(allow=True)` → UNLOCK_DOOR1.
- **Карта**:
  внешнее событие card_id → `AuthServiceDB.check_card` → `AuthResult` → FSM (аналог логина).
- **Анализ комнаты**:
  FSM генерирует `START_ROOM_ANALYSIS` после закрытия двери 1 → GateController вызывает Vision (dummy/real) → `RoomAnalyzed(people_count, face_match)` → решение FSM.
- **Логи**:
  все действия FSM + auth записываются через `SQLiteEventLogger` в таблицу events и stdout.

## Конфигурация
- `EYEGATE_DUMMY_HW=1|0` — выбор DummyDoors/DummyAlarm или GPIO.
- `VISION_MODE=dummy|real` — выбор Vision; при ошибке OpenCV откат на dummy.
- Таймауты (enter/check/exit/alarm) через `EYEGATE_*_TIMEOUT`.
- Путь к БД: `EYEGATE_DB_PATH`.

## Каталоги (кратко)
- `gate/fsm.py` — состояния/события/действия + логика переходов.
- `gate/controller.py` — очередь событий, исполнение действий, таймеры, вызовы Vision/Auth/Alarm.
- `vision/service.py` — dummy и OpenCV реализация VisionService.
- `vision/embeddings.py` — embedding-заглушка (SHA-256 по снимку) + сравнение.
- `auth/service.py` — проверка карт из БД; `auth/passwords.py` — bcrypt; `auth/validation.py` — сложность пароля.
- `db/models.py` — CRUD по users/events + миграции; `db/init_db.py` — создание схемы и демо-пользователя.
- `server/api/*` — REST API: статус, CRUD пользователей, события, аутентификация (register/login).
- `web/templates/*.html`, `web/static/*` — UI для дашборда, регистрации и логина.
- `deploy/install_luckfox.sh` — копирование проекта, venv, зависимости, init_db, systemd.

## Варианты работы
- **Лаптоп (demo)**: `EYEGATE_DUMMY_HW=1`, `VISION_MODE=real` (если есть камера+OpenCV) или `dummy` по умолчанию.
- **Luckfox Pico Ultra (RV1106)**: `EYEGATE_DUMMY_HW=0`, `VISION_MODE=dummy`; GPIO пины заданы в `server/deps.py` (DoorsConfig/AlarmConfig). При желании заменить Vision на RKNN — реализовать класс с тем же интерфейсом.

## Расширение/замена Vision
Интерфейс `analyze_room(card_id, user_id) -> (people_count, FaceMatch)` единый. Можно подменить реализацию (например, RKNN на RV1106) без изменений FSM/контроллера. Embedding-заглушка легко заменяется на настоящие в `vision/embeddings.py`.
