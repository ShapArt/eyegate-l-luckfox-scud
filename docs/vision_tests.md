# Тесты Vision (dummy/real)

## Dummy
- Проверить, что `default_people_count` и `default_face_match` возвращаются как есть.
- Сценарии для FSM (через Dummy):
  - people_count=2 → ALARM (tailgating).
  - people_count=0/NO_FACE → ACCESS_DENIED.
  - people_count=1/NO_MATCH → ALARM.
  - people_count=1/MATCH → ACCESS_GRANTED.

## Real (OpenCV)
Раздел описывает ручные и скриптовые проверки для реализации vision на OpenCV. В учебной версии допускается использование подготовленного набора изображений/видео для воспроизводимости результатов.

### Цели
- Корректно определять: нет лица (NO_FACE), одно лицо (MATCH/NO_MATCH), несколько лиц (>1 → ALARM).
- Генерировать embedding по ROI лица и сравнивать с embedding пользователя из БД.

### Минимальный набор тестовых данных (PNG/JPG)
- `noface/*.png` - пустой фон, предметы без людей.
- `single_match/*.png` - одно лицо, зарегистрированное (embedding совпадает).
- `single_nomatch/*.png` - одно лицо, не совпадающее с embedding пользователя.
- `multi/*.png` - два и более лиц.
- `edge_cases/*.png` - очки, маска, частичное закрытие, сильный угол, плохой свет.

### Тест-кейсы (ручные/скрипты)
- **NO_FACE:** кадр из `noface/` → people_count=0, face_match=NO_FACE.
- **MATCH:** кадр из `single_match/` с embedding из БД → people_count=1, face_match=MATCH.
- **NO_MATCH:** кадр из `single_nomatch/` → people_count=1, face_match=NO_MATCH.
- **TAILGATING:** кадр из `multi/` → people_count>1 → ALARM в FSM.
- **Порог match_threshold:** использовать пару почти совпадающих и пару разных лиц; варьировать threshold (например, 0.05 / 0.1 / 0.2) и фиксировать результат. ENV: `VISION_MATCH_THRESHOLD` (по умолчанию 0.1).
- **Сложные условия:** `edge_cases/` - ожидать чаще NO_MATCH/NO_FACE; фиксировать частоту ошибок.

### Скриптовая проверка (пример концепции)
- Загружать изображения из папок, вызывать `VisionServiceOpenCV.analyze_room` с mock user_id/embedding.
- Сравнивать результаты с ожидаемыми people_count/face_match (матрица соответствий).
- Логировать отклонения, строить сводку ошибок.

### Liveness (перспективное расширение)
- Подготовить тесты с фото/видео/маской → ожидать NO_MATCH/NO_FACE или отдельный флаг "подозрение".
- При добавлении liveness-интерфейса в Vision (отдельный метод или расширенный ответ) фиксировать критерии: FAR/FRR, пороги, условия освещения, устойчивость к повторному воспроизведению.
