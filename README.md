# EyeGate Mantrap

EyeGate Mantrap — учебный программно-аппаратный макет шлюзовой системы контроля доступа с двумя дверями, PIN-аутентификацией, мониторингом состояния дверей и модулем анализа зоны между дверями.

## Состав
- `server/` — backend на FastAPI.
- `web/app/` — SPA-интерфейс оператора, администратора, киоска и симулятора.
- `gate/` — конечный автомат шлюза и контроллер логики.
- `vision/` — сервис анализа кадров, people count, face matching.
- `hw/` — драйверы датчиков, дверей и последовательного интерфейса.
- `tests/` — автоматические тесты `pytest`.
- `docs/` — эксплуатационные и проектные markdown-документы.

## Быстрый старт
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cd web/app
npm install
npm run build
cd ../..
uvicorn server.main:app --reload
```

Для автономной стендовой проверки используйте `EYEGATE_DUMMY_HW=1` и `VISION_MODE=dummy`. Подробные параметры запуска и настройки приведены в [docs/INSTALL_RUNBOOK.md](docs/INSTALL_RUNBOOK.md).

## Проверка
```bash
pytest -q
```

Ключевые документы:
- [docs/INSTALL_RUNBOOK.md](docs/INSTALL_RUNBOOK.md)
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md)
- [docs/TEST_PLAN.md](docs/TEST_PLAN.md)
- [docs/TRACEABILITY_MATRIX.md](docs/TRACEABILITY_MATRIX.md)
