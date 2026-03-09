# Repo map

Core runtime
- `server/`: FastAPI app, API routes, deps, config.
- `vision/`: OpenCV pipeline, detectors, people counter, embeddings.
- `gate/`: FSM + controller logic for the mantrap.
- `auth/`: auth services, passwords, tokens.
- `db/`: SQLite models, migrations, event log.
- `policy/`: access policy decisions.
- `hw/`: hardware drivers (doors/alarm/serial).

Frontend
- `web/app/`: React + Vite SPA (Monitor/Kiosk/Sim/Admin/Enroll).
- `web/static/`, `web/templates/`: legacy HTML/JS (kept for fallback).

Scripts
- `scripts/`: dev run/stop, doctor, deploy, docs tools.
- `scripts/windows/`: Windows start/stop launchers (ADB + WSL).
- `luckfox/`: board scripts + init.d templates.

Data / models / tests
- `models/`: YuNet/SFace ONNX files.
- `data/`: SQLite DB (local).
- `tests/`: pytest suite.
- `docs/`: short project docs.

Legacy / archive candidates
- Large zip/7z bundles and old doc dumps in repo root.
- Cyrillic-named legacy docs folders in repo root.
- `eyegate-mantrap-reference-pack/` (reference snapshot).

Note: legacy items are not used by runtime; consider moving to `archive/`.
