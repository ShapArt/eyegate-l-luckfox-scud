# Сценарий демо (offline/dummy)

Цель: показать сквозной проход без камеры, проверить оверлеи/имена/UNKNOWN, работу политики и датчиков.

## Подготовка
```bash
cp .env.example .env
python -m db.init_db
EYEGATE_DEMO_MODE=1 EYEGATE_DUMMY_HW=1 VISION_MODE=dummy uvicorn server.main:app --reload
```
- Путь БД по умолчанию: `data/eyegate_scud.db` (пользователи сохраняются между перезапусками).
- Автозакрытие в симуляторе можно задать через `DOOR_AUTO_CLOSE_SEC` или по дверям `DOOR1/2_AUTO_CLOSE_SEC`.

## Шаги
1) `/admin`: добавить пользователя (login+PIN). Нажать **Capture face** (в dummy-режиме принимается заглушка-дескриптор). Убедиться, что пользователь появился в списке.
2) `/kiosk`: ввести PIN -> Door1 разблокируется/откроется (demo mode). Статус обновляется через WS.
3) `/monitor`:
   - В сети виден поток `/api/video/mjpeg`; браузер не запрашивает камеру напрямую.
   - Overlay: bbox + label содержит имя/логин пользователя; неизвестные показываются как `UNKNOWN` (красным). Счетчик людей отображается вверху слева.
   - Правая колонка: состояние FSM, двери (актуатор + сенсор), `people_count`, список лиц с score.
   - Переключатель "Debug overlay" скрывает/показывает canvas.
   - Если остановить поток (остановить backend), появляется `CAMERA DOWN`, Door2 остается заблокированной.
4) `/sim`:
    - Нажимать open/close Door1/Door2; сенсоры зеркалируются автоматически, если включено авто-закрытие.
    - Layout-диаграмма показывает Door1/Door2 и камеру у Door2 с упрощенной визуализацией FOV.
    - Проверка auto-close: задать задержку (ms), открыть Door1/Door2; по таймеру состояние/сенсор вернется в closed.
    - Эндпоинты сенсоров: `POST /api/sim/sensor/1/open` и т.п.; наблюдать обновления в `/monitor`.

## Вариации
- Политика multi-known: задать `ALLOW_MULTI_KNOWN=1`, `MAX_PEOPLE_ALLOWED=2` и использовать `VISION_DUMMY_PEOPLE=2`, `VISION_DUMMY_RECOGNIZED=1,2`, чтобы показать "разрешено группе" vs тревога.
- Реальная камера: задать `VISION_MODE=real`, скачать ONNX через `python scripts/download_models.py` и сохранить тот же сценарий; `/monitor` продолжит получать `/api/video/mjpeg`.
