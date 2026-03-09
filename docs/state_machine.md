# FSM шлюза (mantrap)

Состояния:
- `IDLE` — ждём аутентификацию.
- `WAIT_ENTER` — дверь 1 открыта, ждём входа и закрытия.
- `CHECK_ROOM` — обе двери блокированы, идёт анализ комнаты (Vision).
- `ACCESS_GRANTED` — дверь 2 открыта, ждём выхода.
- `ACCESS_DENIED` — отказ, ждём RESET.
- `ALARM` — тревога (tailgating/face mismatch), сирена, ждём таймаут или RESET.
- `RESET` — возврат в IDLE с очисткой контекста.

Источники AuthResult:
- `card_presented(card_id)` → AuthServiceDB → `AuthResult(allow/deny, user_id, reason)`.
- `POST /api/auth/login` (bcrypt) → `GateController.login_success(user_id)` → `AuthResult(allow=True, reason="LOGIN_OK")`.

Переходы (кратко):
1) `IDLE` -> `WAIT_ENTER`: `AuthResult(allow=True)` → UNLOCK_DOOR1 + START_ENTER_TIMEOUT.
2) `WAIT_ENTER` -> `CHECK_ROOM`: `DoorClosedChanged(door=1, is_closed=True)` → LOCK_BOTH + START_ROOM_ANALYSIS + START_CHECK_TIMEOUT.
3) `CHECK_ROOM`:
   - `people_count > 1` → `ALARM` (tailgating) + SET_ALARM_ON + START_ALARM_TIMEOUT.
   - `people_count == 0` или `face_match == NO_FACE` → `ACCESS_DENIED`.
   - `people_count == 1` и `NO_MATCH` → `ALARM`.
   - `people_count == 1` и `MATCH` → `ACCESS_GRANTED` (LOCK_DOOR1, UNLOCK_DOOR2, START_EXIT_TIMEOUT).
   - `TIMEOUT_CHECK` → `ACCESS_DENIED`.
4) `ACCESS_GRANTED`:
   - `DoorClosedChanged(door=2, is_closed=True)` → `RESET` (LOCK_DOOR2, CANCEL timeouts).
   - `TIMEOUT_EXIT` → `ACCESS_DENIED`.
5) `ALARM`:
   - `TIMEOUT_ALARM` или `RESET` → `RESET` (SET_ALARM_OFF, LOCK_BOTH).
6) `RESET` → `IDLE` (лог + очистка контекста).

Таймеры:
- ENTER, CHECK, EXIT, ALARM — создаются контроллером как asyncio-задачи; CANCEL_ALL_TIMEOUTS отменяет все активные.

Логирование:
- Каждое действие/решение пишется в events (SQLiteEventLogger) с уровнем/причиной/состоянием/пользователем/картой.
