# Матрица трассируемости требований EyeGate Mantrap

| Req ID | Требование | Реализация (файл/модуль) | Проверка (тест/шаг) | Статус |
| --- | --- | --- | --- | --- |
| A | /monitor использует backend MJPEG, без getUserMedia | `web/app/src/components/MjpegStream.tsx`, `MonitorPage.tsx`, backend `/api/video/mjpeg` | `tests/test_spa_fallback.py`, R-1 | Выполнено |
| B | Overlay боксы + подписи имя/UNKNOWN | `MonitorPage.tsx` canvas; WS `vision.faces` с `label/is_known` (`vision/service.py`) | `tests/test_dummy_vision_v2.py`, R-2 | Выполнено |
| C | Пользователи сохраняются после перезапуска | `db/base.py` путь `data/eyegate_scud.db`, `db/init_db.py`; API `server/api/users.py` | `tests/test_db_persistence.py` | Выполнено |
| D | Автодоводчики Door1/2 в сим | `hw/simulated.py`, ENV `DOOR_AUTO_CLOSE_SEC`, API `/api/sim/auto_close` | `tests/test_api_sim.py`, R-3 | Выполнено |
| E | Вкладка /sim — схема FOV | Базовая UI `SimPage.tsx`, описание в RPZ/Прил. E; визуализация FOV как план развития | Ручной осмотр /sim | Частично (описание) |
| F | Proteus-ready SerialBridge | `hw/serial_bridge.py`, ENV `SENSOR_MODE`, `SENSOR_SERIAL_PORT`, `SENSOR_SERIAL_BAUD`; интеграция `server/deps.py` | `tests/test_serial_bridge.py`, R-4 | Выполнено |
| G | Silhouette + face recognition, убрать "Face 1" | PeopleCounter (`vision/people_count.py`), labels из БД (`vision/service.py`), overlay в Monitor | `tests/test_dummy_vision_v2.py`, policy tests | Выполнено |
| H | Документация (README + docs) | `README.md`, `docs/RPZ_EyeGate_Mantrap.md`, `docs/USER_GUIDE.md`, `docs/PROTEUS.md`, `docs/INSTALL_RUNBOOK.md`, `docs/TEST_PLAN.md` | Ручная проверка | Выполнено |
| Policy | Отдельно тестируемая логика | `policy/access.py`, `tests/test_policy.py`, `tests/test_controller_policy_integration.py` | Автотесты | Выполнено |
| Fail-safe | Door2 не открывать при vision error | `gate/controller.snapshot`, `vision/service.py` (stale -> NO_FACE), UI CAMERA DOWN | R-1, policy tests | Выполнено |
