# UI E2E (Playwright) — черновик сценариев и пример кода

> Playwright не входит в зависимости проекта. Ниже — инструкция, как быстро поднять e2e-тесты в отдельной Node.js-папке, чтобы прогнать браузерные сценарии регистрации/логина/дашборда.

## Установка локально
```bash
npm init -y
npm install -D @playwright/test
npx playwright install chromium
```

## Пример `e2e.spec.ts`
```ts
import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'http://localhost:8000';

test('register -> login -> dashboard WAIT_ENTER', async ({ page }) => {
  await page.goto(`${BASE}/register`);
  await page.fill('input[name="name"]', 'UserP');
  await page.fill('input[name="login"]', 'userp');
  await page.fill('input[name="card_id"]', 'CARDP');
  await page.fill('input[name="password"]', 'passw0rd');
  await page.fill('input[name="password_confirm"]', 'passw0rd');
  await page.click('button:has-text("Create user")');
  await expect(page.locator('#register-message')).toContainText('User #');

  await page.goto(`${BASE}/login`);
  await page.fill('input[name="login"]', 'userp');
  await page.fill('input[name="password"]', 'passw0rd');
  await page.click('button:has-text("Sign in")');
  await expect(page.locator('#login-message')).toContainText('OK');

  await page.goto(`${BASE}/`);
  await expect(page.locator('#status-content')).toContainText('WAIT_ENTER');
});

test('invalid password shows error', async ({ page }) => {
  await page.goto(`${BASE}/login`);
  await page.fill('input[name="login"]', 'userp');
  await page.fill('input[name="password"]', 'wrong');
  await page.click('button:has-text("Sign in")');
  await expect(page.locator('#login-message')).toContainText('Invalid');
});
```

## Дополнительные сценарии
- Tailgating: настроить Vision dummy на people_count=2 (через API/конфиг) → на UI увидеть ALARM/room-state=ALARM.
- NO_FACE/NO_MATCH: people_count=0 или NO_MATCH → ACCESS_DENIED/ALARM; схема дверей меняется.
- Проверка таблицы событий: LOGIN_OK, ROOM_ANALYZED, ACCESS_GRANTED/ALARM.

## Запуск
```bash
npx playwright test
```

## Замечания
- Для headless можно `npx playwright install --with-deps`.
- Захват камеры в e2e опционален: регистрация может пройти без face_image_b64 (smoke). Для полноценного теста камеры нужны разрешения браузера.
