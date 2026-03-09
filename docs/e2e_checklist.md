# E2E чек-лист (UI/API/Vision)

## Базовый успешный проход (login + MATCH)
1. `/register`: создать пользователя с face_image_b64 (камера).
2. `/login`: валидный логин/пароль → FSM = WAIT_ENTER (дверь 1 unlocked).
3. Имитация закрытия двери 1 → CHECK_ROOM.
4. Vision dummy/real: people_count=1, MATCH.
5. FSM → ACCESS_GRANTED (дверь 2 unlocked) → закрыть дверь 2 → RESET/IDLE.
6. Проверка UI: схема дверей отражает unlocked/locked, в таблице events есть LOGIN_OK, ROOM_ANALYZED (MATCH), ACCESS_GRANTED.

## Неверный пароль
1. `/login` с неправильным паролем → HTTP 401.
2. После max_failures (rate limit) → HTTP 429.
3. Проверка events: INVALID_CREDENTIALS, LOGIN_RATE_LIMIT.

## Заблокированный пользователь
1. Пользователь is_blocked=True.
2. `/login` → HTTP 403, events: USER_BLOCKED.

## Tailgating
1. Успешный логин.
2. Door1 closed → Vision: people_count=2.
3. FSM → ALARM: обе двери locked, сирена ON, UI room=ALARM, events: TAILGATING.
4. По ALARM timeout → RESET/IDLE, alarm OFF.

## Нет лица / пусто
1. Успешный логин.
2. Vision: people_count=0 или NO_FACE.
3. FSM → ACCESS_DENIED, двери locked, events: NO_FACE.

## Чужое лицо
1. Успешный логин, embedding в БД не совпадает.
2. Vision: people_count=1, NO_MATCH.
3. FSM → ALARM, events: FACE_MISMATCH.

## Таймауты
- ENTER_TIMEOUT: дверь 1 не закрыли → RESET, doors locked.
- CHECK_TIMEOUT: нет ответа Vision → ACCESS_DENIED.
- EXIT_TIMEOUT: дверь 2 не закрыли → ACCESS_DENIED.

## Карта вместо логина
- card_presented() → AuthResult → WAIT_ENTER → далее как базовый проход.

## UI обновления
- Автообновление статуса/событий раз в 3–5 сек.
- Фильтр событий по уровню/substring.
- Схема дверей отражает FSM (WAIT_ENTER/ACCESS_GRANTED/ALARM).
- Экспорт событий: `/api/events/export?format=csv|json`.

## Vision real (OpenCV) — ручные проверки
1. Кадр без лиц → people_count=0 → ACCESS_DENIED.
2. Кадр с одним лицом и embedding из БД → MATCH.
3. Кадр с одним лицом, но embedding другой → NO_MATCH → ALARM.
4. Два лица в кадре → people_count>1 → ALARM (tailgating).
5. Разные условия: очки/маска/освещение/ракурсы — оценить стабильность порога match_threshold.
