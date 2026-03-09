# EyeGate Mantrap — Программа и методика испытаний

## 1. Цели испытаний
- Проверить соответствие функциональным требованиям A–H (MJPEG, overlay, persistence, автодоводчики, serial).
- Подтвердить стабильность БД и FSM таймаутов.

## 2. Окружение
- Backend: `uvicorn server.main:app --reload`
- ENV: по `.env` (dummy vision для быстрых тестов).
- БД: `data/eyegate_scud.db` (или временный файл в тестах).

## 3. Автоматические тесты (pytest)
| ID | Тест | Назначение | Статус |
| --- | --- | --- | --- |
| T-A1 | `tests/test_spa_fallback.py` | SPA отдаёт index на /monitor и др. | автомат |
| T-A2 | `tests/test_db_persistence.py` | Пользователь сохраняется после “рестарта” | автомат |
| T-A3 | `tests/test_api_sim.py` | Сенсоры + автодоводчик | автомат |
| T-A4 | `tests/test_serial_bridge.py` | Парсер и сим SerialBridge | автомат |
| T-A5 | `tests/test_dummy_vision_v2.py` | Dummy vision snapshot с faces/labels | автомат |
| T-A6 | `tests/test_policy.py`, `test_controller_policy_integration.py` | Policy/ALARM/ACCESS_GRANTED | автомат |

## 4. Ручные тесты
| ID | Шаги | Ожидаемый результат | Критерий “OK” |
| --- | --- | --- | --- |
| R-1 MJPEG monitor | Открыть `/monitor`, убедиться в запросе `/api/video/mjpeg`, отключить камеру → CAMERA DOWN | Видео из backend, нет запроса getUserMedia | Да/Нет |
| R-2 Overlay labels | Создать пользователя, enroll (можно dummy), показать лицо на камеру/dummy → подпись имени | Подпись имя/логин, неизвестные красный UNKNOWN | Да/Нет |
| R-3 Autoclose | `/api/sim/auto_close` delay 0.1s, `/api/sim/door/1/open`, подождать 0.2s | door1_closed=true, sensor1_open=false | Да/Нет |
| R-4 Serial | SENSOR_MODE=serial, отправить `D1:OPEN` в порт | sensor1_open=true в /monitor | Да/Нет |
| R-5 Policy multi-people | В dummy vision выставить people_count=2 (env VISION_DUMMY_PEOPLE=2), PIN вход | FSM в ALARM, Door2 закрыт | Да/Нет |

## 5. Критерии приемки
- Все автотесты проходят.
- Ручные проверки R-1…R-5 = “Да”.
- БД сохраняет пользователей между запусками.
- overlay в /monitor показывает имя/UNKNOWN, нет “Face 1”.
- Door2 не открывается при vision_error/people_count>max.

## 6. План регрессии
- При изменении vision/WS/monitor — rerun T-A1, T-A5, R-1, R-2.
- При изменении симулятора/датчиков — rerun T-A3, T-A4, R-3, R-4.
- При изменении БД/инициализации — rerun T-A2.
