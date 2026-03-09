# Демонстрационные сценарии

## 1. Регистрация нового пользователя
1. Открыть `/register`.
2. Заполнить имя, логин, card_id, пароль (≥6, буквы+цифры).
3. Нажать Start camera → Capture кадр → Create user.
4. В events появится `USER_REGISTERED`, в users — новая запись с embedding (если был кадр).

## 2. Успешный проход (логин/пароль + лицо)
1. `/login`: ввести логин/пароль → OK → FSM в WAIT_ENTER, дверь 1 разблокирована.
2. Закрыть дверь 1 → CHECK_ROOM → Vision:
   - 1 человек, MATCH по embedding пользователя → ACCESS_GRANTED.
3. Дверь 2 открыта, выйти → закрыть дверь 2 → RESET/IDLE.
4. В events: LOGIN_OK, UNLOCK_DOOR1, ROOM_ANALYZED, ACCESS_GRANTED, EXIT_TIMEOUT/RESET.

## 3. Tailgating (два человека)
1. Аналогично логину.
2. В CHECK_ROOM Vision возвращает `people_count=2`.
3. FSM → ALARM: обе двери блокированы, сирена ON, START_ALARM_TIMEOUT.
4. По таймауту ALARM или ручному RESET → LOCK_BOTH, сирена OFF, RESET/IDLE.

## 4. Чужое лицо
1. Логин валидный.
2. CHECK_ROOM: `people_count=1`, но embedding не совпал (NO_MATCH).
3. FSM → ALARM (как выше).

## 5. Нет лица / пусто
1. Логин валидный.
2. CHECK_ROOM: `people_count=0` или `NO_FACE`.
3. FSM → ACCESS_DENIED, двери блокированы, контекст очищен.

## 6. Таймауты
- ENTER_TIMEOUT: в WAIT_ENTER дверь 1 так и не закрыли → LOCK_DOOR1, RESET.
- CHECK_TIMEOUT: в CHECK_ROOM нет ответа Vision → ACCESS_DENIED.
- EXIT_TIMEOUT: в ACCESS_GRANTED дверь 2 не закрылась вовремя → ACCESS_DENIED.

## 7. Карта вместо логина
- Поднести карту с card_id, известным БД → AuthServiceDB → AuthResult(allow=True) → сценарий идентичен логину.

## 8. API-тесты (FastAPI + TestClient)
- Регистрация: успех, дубликат логина/карты, слабый пароль, несовпадение password/password_confirm, отсутствие face_image_b64.
- Логин: успех, неверный пароль, заблокированный пользователь.
- Users CRUD: create/list/update/delete, валидация логина/карты на уникальность.
- Events: выдача последних событий, проверка лимита.

## Настройки для демонстрации
- Dummy Vision: `VISION_MODE=dummy` (по умолчанию) — параметры `default_people_count`, `default_face_match` в `server/deps.py`.
- Real Vision: `VISION_MODE=real` — нужна камера и установленный opencv-python; при ошибке откатится в dummy.
- Железо: `EYEGATE_DUMMY_HW=1` (ноутбук) или `0` (Luckfox, GPIO).
