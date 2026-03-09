# EyeGate Mantrap — Руководство оператора/охранника/админа

## 1. Роли и доступ
- Оператор наблюдает /monitor, управляет симулятором /sim.
- Администратор создаёт пользователей, настраивает ENV, следит за БД и журналами.

## 2. Подготовка системы
1. Настроить `.env` (см. INSTALL_RUNBOOK) — путь к БД, режим vision, автодоводчики, serial mode.
2. Запустить backend `uvicorn server.main:app --reload`.
3. Собрать фронтенд `cd web/app && npm install && npm run build` (или использовать dev Vite).

## 3. Мониторинг и реагирование (/monitor)
- Видео: MJPEG `/api/video/mjpeg` (не browser camera).
- Оверлей: бокс + подпись имени или `UNKNOWN`. Красный фон для CAMERA DOWN/ALARM.
- В правой панели: FSM state, двери, замки, сенсоры, people_count, список распознанных лиц/score.
- Кнопки:
  - Reload stream — перезапуск MJPEG при обрыве.
  - Debug overlay — отключение рисования боксов (для диагностики).
- Реакция на события:
  - ALARM: убедиться, что двери закрыты, устранить нарушение (лишний человек/unknown).
  - CAMERA DOWN: проверить камеру/vision, не открывать Door2 вручную.

## 4. Работа с симулятором (/sim)
- Управление дверями: кнопки Open/Close вызывают `/api/sim/door/{id}/open|close`.
- Сенсоры обновляются автоматически (автодоводчик) или через `/api/sim/sensor/{id}/open|closed`.
- Автодоводчик: `/api/sim/auto_close` с `delay_ms` и опционально `door_id` (1 или 2). Значения конфигурируются через ENV `DOOR_AUTO_CLOSE_SEC`, `DOOR1_AUTO_CLOSE_SEC`, `DOOR2_AUTO_CLOSE_SEC`.
- Визуализация поля зрения камеры рядом с Door2 — план/описание в RPZ, UI базовый.

## 5. Администрирование (/admin, /enroll)
- Создание пользователя: форма отправляет на `/api/users/` (QuickUserPayload: login, pin, name, access_level, is_blocked). PIN хешируется на сервере.
- Enroll лица: `/api/users/{id}/enroll` — backend берёт embedding из VisionService (или dummy), сохраняет в `users.face_embedding`.
- Проверка: на /monitor при появлении пользователя должен отображаться его `name`/`login`; неизвестные — `UNKNOWN` красным.

## 6. Датчики и SerialBridge
- Режимы: `SENSOR_MODE=sim` (по умолчанию) или `serial`.
- При `serial` указать `SENSOR_SERIAL_PORT`, `SENSOR_SERIAL_BAUD`. Backend стартует SerialBridge (`hw/serial_bridge.py`) и принимает строки:
  - `D1:OPEN`, `D1:CLOSED`, `D2:OPEN`, `D2:CLOSED`
  - или JSON `{"door":1,"closed":false}`
- Для Proteus COMPIM: см. `docs/PROTEUS.md` (использовать связку com0com CNCA0/CNCB0).

## 7. Журналы и БД
- БД: `data/eyegate_scud.db` (таблицы users/events/settings). WAL включён.
- Логи событий: таблица `events` заполняется через `db/logger.py`; для анализа используются записи в БД и журнал приложения, если он включён в среде запуска.
- При блокировке файла БД fallback создаётся в `data/eyegate_scud_fallback_<pid>.db` (init_db), in-memory не используется.

## 8. Диагностика
- Тесты: `pytest` (автодоводчики, DB persistence, serial, SPA fallback, policy).
- Проверить WS: `wscat -c ws://localhost:8000/ws/status`.
- Проверить MJPEG: `curl -I http://localhost:8000/api/video/mjpeg`.

## 9. Плановые работы
- Резервное копирование `data/eyegate_scud.db`.
- Проверка ENV на соответствие стенду (камера, serial).
- Очистка временных fallback-баз (если появлялись).
