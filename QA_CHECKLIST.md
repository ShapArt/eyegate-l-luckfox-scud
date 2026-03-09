# QA Checklist

- [x] `README.md` соответствует фактической структуре `repo/`.
- [x] Актуальные руководства доступны в `docs/INSTALL_RUNBOOK.md`, `docs/USER_GUIDE.md`, `docs/OPERATOR_GUIDE.md`.
- [x] Матрица трассируемости присутствует в комплекте: `../../05_АСУД_ГОСТ34/TRACEABILITY_MATRIX.csv` и `../../05_АСУД_ГОСТ34/TRACEABILITY_MATRIX.xlsx`.
- [x] Реальный лог автотестов сохранён в `../../02_Моделирование/logs/pytest.txt`.
- [x] Основные markdown- и DOCX-документы очищены от битых ссылок на `QA_CHECKLIST.md`, `docs/.md`, `controller.log` и несуществующие тесты.
- [ ] Перед отправкой преподавателю проверить состав финального ZIP и исключить временные каталоги `_release_build/` и `_teacher_release/`.
