#!/bin/sh
set -e

APP_DIR="/opt/eyegate-mantrap"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_BIN="${PIP_BIN:-pip3}"

echo "[*] EyeGate Mantrap installer"
echo "[*] Target directory: ${APP_DIR}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "[!] python3 не найден в PATH."
    echo "    Установите Python3/venv/pip в образ или используйте сборку с Python."
    exit 1
fi

echo "[*] Создаём каталог ${APP_DIR}..."
mkdir -p "${APP_DIR}"

echo "[*] Копируем проект в ${APP_DIR}..."
rm -rf "${APP_DIR:?}/"*

cp -R . "${APP_DIR}/"

cd "${APP_DIR}"

if [ ! -d ".venv" ]; then
    echo "[*] Создаём виртуальное окружение Python..."
    ${PYTHON_BIN} -m venv .venv
fi

echo "[*] Активируем venv и ставим зависимости..."
. .venv/bin/activate

if [ -f "requirements.txt" ]; then
    ${PIP_BIN} install --upgrade pip
    if [ "${SKIP_OPENCV:-0}" = "1" ]; then
        echo "[*] SKIP_OPENCV=1, installing deps without opencv-python (VISION_MODE should stay dummy)..."
        grep -vi "^opencv-python" requirements.txt > /tmp/requirements-no-cv.txt
        ${PIP_BIN} install -r /tmp/requirements-no-cv.txt
    else
        ${PIP_BIN} install -r requirements.txt
    fi
else
    ${PIP_BIN} install fastapi uvicorn[standard] jinja2 "pydantic>=2,<3" bcrypt
fi

echo "[*] Инициализируем SQLite-базу..."
${PYTHON_BIN} -m db.init_db

if command -v systemctl >/dev/null 2>&1; then
    echo "[*] Настраиваем systemd-сервис eyegate-mantrap.service..."

    SERVICE_SRC="deploy/systemd/eyegate-mantrap.service"
    SERVICE_DST="/etc/systemd/system/eyegate-mantrap.service"

    if [ -f "${SERVICE_SRC}" ]; then
        cp "${SERVICE_SRC}" "${SERVICE_DST}"
    else
        echo "[!] Не найден ${SERVICE_SRC}, пропускаем копирование unit-файла."
    fi

    systemctl daemon-reload || true
    systemctl enable eyegate-mantrap.service || true
    systemctl restart eyegate-mantrap.service || true

    echo "[*] Статус: systemctl status eyegate-mantrap.service"
else
    echo "[!] systemd не найден. Используйте init-скрипт или rc.local (см. deploy/init.d/eyegate-mantrap.example)."
fi

echo "[*] Готово. Web-интерфейс: http://<ip_платы>:8000/"
