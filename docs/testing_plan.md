# Тест-план EyeGate Mantrap (учебный СКУД-шлюз)

## Уровни и области
1. FSM (GateFSM) - переходы, контекст, действия.
2. GateController + Dummy HW/Vision - интеграция, таймеры.
3. Auth/регистрация/логин - bcrypt, валидация, блокировки.
4. DB - CRUD/миграции/события/отказоустойчивость.
5. Vision - dummy + OpenCV (интерфейс), сценарии people_count/face_match.
6. API - status/users/events/auth.
7. Web/E2E - UI сценарии (ручные проверки).
8. GPIO/железо - моки sysfs, сценарии концевиков.
9. Безопасность - пароли, rate limiting, пороги FaceMatch; liveness-детекция рассматривается как перспективное расширение (допущение).
10. Производительность - нагрузка на FSM/API/DB (smoke/описательно).

## Покрытые автотесты (pytest)
- `tests/test_fsm_policy_bridge.py` - переходы FSM при решениях policy (`open_door2`, `alarm`).
- `tests/test_controller_policy_integration.py` - интеграция GateController, анализа помещения и policy.
- `tests/test_db_persistence.py`, `tests/test_db_init_retries_locked.py`, `tests/test_db_wsl_unc_path_error.py` - постоянство и устойчивость БД.
- `tests/test_demo_api.py`, `tests/test_api_enroll.py`, `tests/test_api_sim.py` - API логина, enroll и симулятора.
- `tests/test_dummy_vision_v2.py`, `tests/test_face_matcher.py`, `tests/test_people_counter.py`, `tests/test_vision_labels.py`, `tests/test_vision_config_env.py` - стендовый и реальный контуры vision.
- `tests/test_video_mjpeg.py`, `tests/test_spa_fallback.py`, `web/e2e/tests/monitor.spec.ts` - выдача MJPEG, SPA fallback и базовый UI smoke.

Команда запуска:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest tests
```

## Описательные тесты (ручные проверки и E2E)
Раздел содержит сценарии ручной проверки, которые дополняют покрытие автотестами. Они используются при приемке учебной версии и при демонстрации, когда требуется камера/потоки или UI.

### Web/E2E (Playwright/Cypress, ручная проверка)
- Регистрация с камерой → логин → успешный проход (MATCH).
- Заблокированный пользователь не проходит логин.
- Неверный пароль → отказ, проверка сообщения об ошибке.
- Tailgating: в стендовом режиме vision `people_count=2` → ALARM; UI подсветка.
- NO_FACE/NO_MATCH → ACCESS_DENIED/ALARM; UI отображает статус и причину.
- Проверка автообновления таблиц пользователей/событий, индикаторы состояния.

### Vision real (OpenCV)
- Кадр без лиц → people_count=0 → FaceMatch.NO_FACE.
- Один ROI лица (эталонный embedding совпадает) → MATCH.
- Один ROI лица (embedding не совпадает) → NO_MATCH.
- Несколько лиц → people_count>1 → ALARM.
- Набор тестовых изображений: хорошее освещение, очки/маски/частичное закрытие, разные ракурсы; проверка устойчивости порога.
- Подробнее: см. `docs/vision_tests.md` и `docs/e2e_checklist.md`.

### Безопасность
- Rate limiting: повторные неуспешные логины не должны приводить к подбору пароля; проверка по времени/количеству запросов.
- Для механизма ограничения частоты входа выделенного автотеста в текущем комплекте нет; контроль выполняется ручной проверкой сценариев входа и общими API-тестами.
- Проверка ошибок Auth/Vision (исключения) → FSM не падает, события пишутся, пользователь получает корректный статус.
- Проверка сообщений об ошибках: без утечек деталей (единое сообщение для неверных логина/пароля).
- Порог FaceMatch как настройка: тесты для разных порогов (ручная проверка).
- Liveness (перспективное расширение): тесты с фото/видео/маской; ожидаем отказ (NO_MATCH/NO_FACE) или отдельный флаг "подозрение" при введении liveness.

### Производительность/устойчивость (smoke/описательно)
- Бурст событий в FSM (AuthResult/door events) - не блокирует event-loop, таймеры срабатывают.
- Нагрузка API: параллельные логины/status/events (httpx/async) - ответы в допустимых пределах.
- Рост таблицы events - проверка времени выборки (лимиты/пагинация работают).

### GPIO/железо
- Моки sysfs: запись в value/direction, проверка полярности active_high/low.
- Сценарий "дверь не закрывается" - FSM остаётся в WAIT_ENTER до таймаута.
- Power cycle (описание): после рестарта контроллера двери должны быть заблокированы, сирена выключена.

## Предложения по улучшениям (для тестируемости и "почти промышленного" уровня)
- Lockout после N неудачных логинов (конфиг, тесты на блокировку после N ошибок).
- Роли (admin/user): ограничения на CRUD users/events; тесты авторизации.
- Экспорт логов (CSV/JSON) и фильтры по типу/пользователю/датам.
- Настраиваемые пороги Vision (match_threshold) и конфиг через ENV; тесты с разными порогами.
- Liveness модуль (перспективное расширение): тесты с фото/видео.
- Улучшенный UI: индикаторы дверей (locked/closed), подсветка ALARM/ACCESS_GRANTED, карточки событий с деталями.
- UserRepository слой над db.models: облегчает моки/тесты, единые исключения.
- Enum типов событий/причин: упорядоченные коды для логов и тестов.
