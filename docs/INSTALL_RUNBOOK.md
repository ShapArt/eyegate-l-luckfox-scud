# EyeGate Mantrap — Установка и запуск

## 1. Предварительные требования
- Python 3.11+ (виртуальное окружение `.venv` рекомендуется).
- Node.js 18+ для сборки фронтенда.
- Git, pip, npm.
- (Опционально) com0com для виртуальных COM (Proteus).

## 2. Клонирование и окружение
```bash
git clone <repo> eyegate-mantrap
cd eyegate-mantrap
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 3. Конфигурация ENV
Скопировать `.env.example` → `.env` и отредактировать:
- База данных: по умолчанию `data/eyegate_scud.db`.
- Vision: `VISION_MODE=dummy|real`, `VISION_MATCH_THRESHOLD`, `VISION_TTL_SEC`.
- Автодоводчики: `DOOR_AUTO_CLOSE_SEC` или `DOOR1_AUTO_CLOSE_SEC`, `DOOR2_AUTO_CLOSE_SEC`.
- Датчики: `SENSOR_MODE=sim|serial`, `SENSOR_SERIAL_PORT`, `SENSOR_SERIAL_BAUD`.
- Стендовый режим: `EYEGATE_DUMMY_HW=1`, `EYEGATE_DEMO_MODE=1`.

## 4. Сборка фронтенда
```bash
cd web/app
npm install
npm run build   # билд попадет в web/app/dist
cd ../..
```

## 5. Запуск backend
```bash
uvicorn server.main:app --reload
# или без reload для стенда:
uvicorn server.main:app --host 0.0.0.0 --port 8000
```
SPA отдаётся из `web/app/dist` (assets) с fallback на Vite index, если dist отсутствует.

## 6. Быстрый старт (стендовый режим)
```bash
export EYEGATE_DUMMY_HW=1
export VISION_MODE=dummy
uvicorn server.main:app --reload
```
Открыть `http://localhost:8000/monitor`, убедиться, что MJPEG грузится с `/api/video/mjpeg`.

## 7. Проверка автодоводчика
```bash
curl -X POST http://localhost:8000/api/sim/auto_close -H "Content-Type: application/json" -d '{"delay_ms":100}'
curl -X POST http://localhost:8000/api/sim/door/1/open"
sleep 0.2
curl http://localhost:8000/api/sim/
```
Дверь должна закрыться (door1_closed=true, sensor1_open=false).

## 8. Проверка SerialBridge (опционально)
- Настроить `.env`: `SENSOR_MODE=serial`, `SENSOR_SERIAL_PORT=\\.\CNCB0`.
- Отправить строку в порт: `echo "D1:OPEN" > \\.\CNCA0` (через com0com пару).
- В `/monitor` сенсор Door1 станет open.

## 9. Тесты
```bash
pytest
```
Ключевые тесты: `test_db_persistence`, `test_api_sim`, `test_serial_bridge`, `test_spa_fallback`, policy tests.

## 10. Остановка
`CTRL+C` в терминале uvicorn. Файлы БД и логи остаются в `data/`.
