# Proteus / COMPIM: SerialBridge (режим датчиков `serial`)

Проект умеет принимать события дверных датчиков из последовательной линии, чтобы можно было "кормить" FSM из Proteus (COMPIM) или любого другого эмулятора RS-232.

## Протокол сообщений
- Только текстовые строки: `D1:OPEN`, `D1:CLOSED`, `D2:OPEN`, `D2:CLOSED`

Каждая строка заканчивается `\n`. Остальные сообщения считаются некорректными и игнорируются.

## Настройка backend
1) Задать параметры в `.env`:
```
SENSOR_MODE=serial
SENSOR_SERIAL_PORT=COM7      # на Linux: /dev/ttyS5 или аналог; для com0com: \\.\CNCB0
SENSOR_SERIAL_BAUD=115200
```
2) Убедиться, что `pyserial` установлен (входит в `requirements.txt`).
3) Запустить backend обычным образом (`uvicorn server.main:app --reload`). При `SENSOR_MODE=serial` и заданном `SENSOR_SERIAL_PORT` поднимается `SerialBridge`, который передает события в симулятор дверей + FSM (изменения будут видны в WS `/ws/status`).

## Виртуальная COM-пара (Windows, com0com)
1) Установить com0com: https://sourceforge.net/projects/com0com/
2) Создать пару портов, например: `CNCA0 <-> CNCB0`.
3) Направить backend на одну сторону: `SENSOR_SERIAL_PORT=\\.\CNCB0`.
4) В Proteus COMPIM выбрать вторую сторону: `\\.\CNCA0`.

## Подключение Proteus (COMPIM)
1) Добавить COMPIM на схему и открыть его свойства.
2) Задать:
   - Port: `\\.\CNCA0` (сторона com0com, противоположная backend)
   - Baud: `115200`, Data bits: 8, Parity: None, Stop bits: 1
3) Передавать в линию текстовые строки (например, из UART TX модели микроконтроллера):
   - `D1:OPEN` -> датчик Door1 открыт
   - `D1:CLOSED` -> датчик Door1 закрыт
   - аналогично для Door2

## Быстрая локальная симуляция (без Proteus)
Можно воспроизвести несколько строк через bridge без Proteus:
```
python - <<'PY'
from hw.serial_bridge import SerialBridge
bridge = SerialBridge(port="ignored", simulate_lines=["D1:OPEN","D2:CLOSED"])
bridge.start(); bridge.join()
print("done")
PY
```
При `SENSOR_MODE=serial` + реальном `SENSOR_SERIAL_PORT` backend будет потреблять эти же события и обновлять `/ws/status` и `/api/status/`.
