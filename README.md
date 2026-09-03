# EyeGate-L

**Two-door access-control / mantrap prototype for Luckfox-class edge hardware.**

EyeGate-L is a university engineering project built around a real access-control flow rather than a standalone computer-vision notebook. The repository combines camera ingest, face/people analysis, gate state logic, authentication, a FastAPI backend, a web UI and hardware-facing integration.

> **Status:** prototype / educational system. It is not presented as production-ready physical security equipment.

## System shape

```text
camera(s)
   │
   ▼
camera ingest ──► vision service ──► recognition / people count
                                      │
                                      ▼
                                policy / decision
                                      │
                                      ▼
                               gate controller + FSM
                                      │
                                      ▼
                              serial / hardware layer

                 FastAPI API + WebSocket status
                           │
                           ▼
                      React web UI
```

The important part for me was the boundary between **recognising a person** and **allowing a physical transition**. Those are separate stages in the code: the vision layer produces information; the gate controller and finite-state machine own the door sequence and state transitions.

## What is in the repository

### Backend

`server/` contains the FastAPI application, API routes, configuration/dependencies, WebSocket status updates and stream handling. `server/main.py` serves the API and the built frontend and starts the gate controller on application startup.

### Gate logic

`gate/` contains the controller and a dedicated finite-state machine. This is where the two-door gateway behaviour lives instead of being mixed directly into camera or UI code.

### Vision

`vision/` contains the recognition-side services:

- embeddings;
- matching;
- people counting;
- the main vision service and shared result types.

The project uses OpenCV on the Python side. The frontend also contains browser-side face/TensorFlow dependencies for UI-side experiments and interaction.

### Camera ingest

`camera_ingest/` handles camera input separately from the recognition and gate layers. That separation makes it possible to test the rest of the system without coupling every component to one capture path.

### Authentication

`auth/` includes password handling, tokens, validation and rate limiting. The web application is therefore not treated as an unauthenticated hardware control panel.

### UI

`web/app/` is a React + TypeScript + Vite frontend. It uses React Query, React Router, Zustand and Tailwind-based UI tooling and is served by FastAPI after a production build.

### Hardware / deployment

The repository also keeps hardware- and device-specific pieces separate in `hw/`, `luckfox/` and `deploy/`, plus configuration through `.env.example`.

## Stack

**Backend:** Python · FastAPI · Uvicorn · Pydantic  
**Vision:** OpenCV · embedding/matching pipeline · people counting  
**Frontend:** React · TypeScript · Vite · React Query · Zustand · Tailwind  
**Hardware:** serial integration / `pyserial` · Luckfox-oriented deployment  
**Security:** bcrypt · token auth · rate limiting · explicit gate state machine

## Run locally

Create a Python environment and install the backend dependencies:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn server.main:app --reload
```

For frontend development:

```bash
cd web/app
npm install
npm run dev
```

For a production-style frontend build:

```bash
cd web/app
npm run build
cd ../..
uvicorn server.main:app
```

The backend has a development fallback when the SPA build is missing, so API work does not require a prebuilt frontend.

## Repository map

```text
auth/           authentication, tokens, rate limiting
camera_ingest/  camera capture / ingest
db/             persistence layer
gate/           controller + finite-state machine
hw/             hardware-facing code
luckfox/        Luckfox-specific pieces
policy/         access decision policy
server/         FastAPI application / API / WebSocket
vision/         embeddings, matching, people count, vision service
web/app/        React + TypeScript frontend
tests/          automated tests
deploy/         deployment files
```

## Design constraints

- **Recognition is not the lock controller.** Vision results do not directly become GPIO/door actions.
- **Two-door behaviour is stateful.** The gateway sequence is represented as an FSM rather than scattered booleans in request handlers.
- **The UI is not trusted by itself.** Authentication and control logic live on the backend side.
- **Edge conditions matter.** Camera input, hardware I/O and deployment are first-class parts of the project, not a final “TODO: deploy later”.

## Tests

The repository contains pytest-based tests and a QA checklist. Development dependencies are separated in `requirements-dev.txt`.

```bash
pip install -r requirements-dev.txt
pytest
```

## По-русски

EyeGate-L — учебный прототип двухдверного шлюза СКУД на Luckfox. Здесь есть не только CV: отдельные слои для камер, распознавания, подсчёта людей, политики доступа, конечного автомата дверей, backend API, авторизации и web-интерфейса.

Главная инженерная идея — не давать распознаванию напрямую управлять физическим доступом. Результат vision-пайплайна проходит через отдельную логику решения и контроллер состояния шлюза.

## License

See [LICENSE](LICENSE).
