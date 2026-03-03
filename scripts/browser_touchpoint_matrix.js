#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const FRONTEND_URL = process.env.DYNAPLAN_FRONTEND_URL || 'https://dynaplan-frontend-7qlyqseapa-uc.a.run.app';
const EMAIL = process.env.DYNAPLAN_EMAIL;
const PASSWORD = process.env.DYNAPLAN_PASSWORD;

if (!EMAIL || !PASSWORD) {
  console.error('Missing DYNAPLAN_EMAIL or DYNAPLAN_PASSWORD');
  process.exit(1);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const outDir = '/Users/ainunnajib/dynaplan/test-results/browser-audit';
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage'],
  });

  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 },
    recordVideo: {
      dir: outDir,
      size: { width: 1366, height: 768 },
    },
  });

  const page = await context.newPage();
  const video = page.video();

  const report = {
    generated_at: new Date().toISOString(),
    frontend_url: FRONTEND_URL,
    passed_steps: [],
    failed_steps: [],
    route_checks: [],
    created_entities: {},
  };

  let workspaceId = null;
  let modelId = null;
  let moduleId = null;
  let dashboardId = null;

  const workspaceName = `Touchpoint WS ${stamp}`;
  const modelName = `Touchpoint Model ${stamp}`;
  const moduleName = `Touchpoint Module ${stamp.slice(11, 19)}`;
  const dashboardName = `Touchpoint Dashboard ${stamp.slice(11, 19)}`;

  const log = (...args) => {
    console.log(`[${new Date().toISOString()}]`, ...args);
  };

  async function runStep(name, fn, critical = false) {
    log(`STEP: ${name}`);
    try {
      await fn();
      report.passed_steps.push(name);
      return true;
    } catch (err) {
      const message = err && err.message ? err.message : String(err);
      report.failed_steps.push({ name, error: message });
      log(`FAILED STEP: ${name}: ${message}`);
      if (critical) throw err;
      return false;
    }
  }

  async function safeGoto(pathname) {
    const url = `${FRONTEND_URL}${pathname}`;
    const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    const status = resp ? resp.status() : null;
    const finalUrl = page.url();
    const title = await page.title().catch(() => '');
    report.route_checks.push({ pathname, status, final_url: finalUrl, title });
    return { status, finalUrl, title };
  }

  async function collectLinks() {
    const origin = new URL(FRONTEND_URL).origin;
    const hrefs = await page.$$eval('a[href]', (links) =>
      links
        .map((a) => a.getAttribute('href') || '')
        .filter(Boolean)
    );
    const normalized = new Set();
    for (const href of hrefs) {
      try {
        const url = new URL(href, origin);
        if (url.origin !== origin) continue;
        if (url.hash) url.hash = '';
        normalized.add(`${url.pathname}${url.search}`);
      } catch {
        // ignore invalid hrefs
      }
    }
    return Array.from(normalized);
  }

  async function clickByRoleNames(role, names) {
    for (const name of names) {
      const locator = page.getByRole(role, { name });
      if ((await locator.count()) > 0) {
        await locator.first().click();
        return true;
      }
    }
    return false;
  }

  try {
    await runStep('Unauthenticated route guard check for /models', async () => {
      const result = await safeGoto('/models');
      if (result.finalUrl.includes('/login')) {
        report.auth_guard_models = 'redirected_to_login';
      } else {
        report.auth_guard_models = 'public_route_accessible';
        report.failed_steps.push({
          name: 'Auth guard gap: /models remains accessible without login',
          error: `Observed final URL ${result.finalUrl}`,
        });
      }
    });

    await runStep('Open public pages', async () => {
      await safeGoto('/');
      await safeGoto('/login');
      await safeGoto('/register');
    }, true);

    await runStep('Invalid login branch shows failure and stays on login', async () => {
      await safeGoto('/login');
      await page.fill('#email', EMAIL);
      await page.fill('#password', `${PASSWORD}-invalid`);
      const clicked = await clickByRoleNames('button', [/^Sign In$/i, /^Login$/i]);
      if (!clicked) {
        throw new Error('Login button not found for invalid-login branch');
      }
      await sleep(1000);
      if (!page.url().includes('/login')) {
        throw new Error(`Invalid login unexpectedly navigated away: ${page.url()}`);
      }
    });

    await runStep('Login with valid credentials', async () => {
      await safeGoto('/login');
      await page.fill('#email', EMAIL);
      await page.fill('#password', PASSWORD);
      const clicked = await clickByRoleNames('button', [/^Sign In$/i, /^Login$/i]);
      if (!clicked) throw new Error('Valid login button not found');
      await page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 60000 });
      await page.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {});
    }, true);

    await runStep('Visit logged-in top-nav links', async () => {
      await safeGoto('/');
      const links = await collectLinks();
      const candidates = links
        .filter((href) => href.startsWith('/'))
        .filter((href) => !href.startsWith('/logout'))
        .filter((href) => !href.includes('/api/'))
        .slice(0, 40);

      for (const href of candidates) {
        await safeGoto(href);
      }
    });

    await runStep('Create workspace via UI', async () => {
      await safeGoto('/workspaces');
      const clicked = await clickByRoleNames('link', [/Create Workspace/i]);
      if (!clicked) throw new Error('Create Workspace link not found');
      await page.waitForURL(/\/workspaces\/new$/, { timeout: 30000 });
      await page.fill('#name', workspaceName);
      const desc = page.locator('#description');
      if ((await desc.count()) > 0) {
        await desc.fill('Touchpoint matrix workspace');
      }
      const submit = page.getByRole('button', { name: /^Create Workspace$/i });
      await submit.first().click();
      await page.waitForURL(/\/workspaces\/[0-9a-f-]+$/, { timeout: 45000 });
      workspaceId = (page.url().match(/\/workspaces\/([0-9a-f-]+)/i) || [])[1] || null;
      if (!workspaceId) throw new Error('Workspace ID parse failed');
      report.created_entities.workspace_id = workspaceId;
    }, true);

    await runStep('Create model via UI', async () => {
      const clicked = await clickByRoleNames('link', [/^Create Model$/i]);
      if (!clicked) throw new Error('Create Model link not found');
      await page.waitForURL(new RegExp(`/workspaces/${workspaceId}/models/new$`), { timeout: 30000 });
      await page.fill('#name', modelName);
      const desc = page.locator('#description');
      if ((await desc.count()) > 0) {
        await desc.fill('Touchpoint matrix model');
      }
      await page.getByRole('button', { name: /^Create Model$/i }).first().click();
      await page.waitForURL(/\/models\/[0-9a-f-]+$/, { timeout: 45000 });
      modelId = (page.url().match(/\/models\/([0-9a-f-]+)/i) || [])[1] || null;
      if (!modelId) throw new Error('Model ID parse failed');
      report.created_entities.model_id = modelId;
    }, true);

    await runStep('Create module from model page', async () => {
      const createModuleButton = page.getByRole('button', { name: /^Create Module$/i });
      await createModuleButton.first().click();
      const modal = page.locator('div.fixed.inset-0').first();
      await modal.waitFor({ state: 'visible', timeout: 30000 });
      await modal.locator('#module-name').fill(moduleName);
      const desc = modal.locator('#module-description');
      if ((await desc.count()) > 0) {
        await desc.fill('Touchpoint matrix module');
      }
      await modal.getByRole('button', { name: /^Create Module$/i }).first().click();
      await page.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {});

      const moduleHref =
        (await page
          .locator(`a[href*="/models/${modelId}/modules/"]`)
          .first()
          .getAttribute('href')) || '';
      moduleId = (moduleHref.match(/\/modules\/([0-9a-f-]+)/i) || [])[1] || null;
      if (!moduleId) throw new Error('Module ID parse failed');
      report.created_entities.module_id = moduleId;
    }, true);

    await runStep('Model-scoped route crawl', async () => {
      await safeGoto(`/models/${modelId}`);
      const links = await collectLinks();
      const modelLinks = links
        .filter((href) => href.includes(`/models/${modelId}`))
        .filter((href) => !href.includes('/logout'))
        .slice(0, 80);
      for (const href of modelLinks) {
        await safeGoto(href);
      }
    });

    await runStep('Blueprint branch: add line item', async () => {
      await safeGoto(`/models/${modelId}/blueprint`);
      const addLineItem = page.getByRole('button', { name: /^Add Line Item$/i });
      if ((await addLineItem.count()) === 0) {
        throw new Error('Add Line Item button not found in blueprint');
      }
      await addLineItem.first().click();
      await page.waitForTimeout(1200);
    });

    await runStep('Grid branch: edit first cell', async () => {
      await safeGoto(`/models/${modelId}/modules/${moduleId}`);
      const cell = page.locator('[role="gridcell"]').first();
      await cell.waitFor({ state: 'visible', timeout: 30000 });
      await cell.dblclick();
      const editor = page.locator('td input[type="text"], td input[type="date"]').first();
      await editor.fill('777');
      await editor.press('Enter');
      await page.waitForTimeout(1000);
    });

    await runStep('Dashboard branch: create and add text widget', async () => {
      await safeGoto(`/models/${modelId}/dashboards`);
      const newDashboard = page.getByRole('button', { name: /^New Dashboard$/i });
      await newDashboard.first().click();
      const dialog = page.locator('div.fixed.inset-0').first();
      await dialog.waitFor({ state: 'visible', timeout: 30000 });
      await dialog.locator('input[placeholder*="Q1 Sales Overview"]').fill(dashboardName);
      const desc = dialog.locator('textarea[placeholder*="Optional description"]');
      if ((await desc.count()) > 0) {
        await desc.fill('Touchpoint dashboard for branch audit.');
      }
      await dialog.getByRole('button', { name: /^Create Dashboard$/i }).first().click();
      await page.waitForURL(new RegExp(`/models/${modelId}/dashboards/[0-9a-f-]+$`), { timeout: 45000 });
      dashboardId = (page.url().match(/\/dashboards\/([0-9a-f-]+)/i) || [])[1] || null;
      if (!dashboardId) throw new Error('Dashboard ID parse failed');
      report.created_entities.dashboard_id = dashboardId;

      await page.getByRole('button', { name: /^Edit Layout$/i }).first().click();
      await page.getByRole('button', { name: /^Add Widget$/i }).first().click();
      const widgetModal = page.locator('div.fixed.inset-0').first();
      await widgetModal.waitFor({ state: 'visible', timeout: 30000 });
      await widgetModal.getByRole('button', { name: /Text/i }).first().click();
      const titleInput = widgetModal.locator('input[placeholder="e.g. Total Revenue"]');
      if ((await titleInput.count()) > 0) {
        await titleInput.fill('Branch Notes');
      }
      const jsonArea = widgetModal.locator('textarea').first();
      await jsonArea.fill(JSON.stringify({ content: 'Touchpoint matrix completed.' }, null, 2));
      await widgetModal.getByRole('button', { name: /^Add Widget$/i }).first().click();
      await page.waitForTimeout(1200);
    });

    await runStep('Logout branch', async () => {
      const logout = page.getByRole('button', { name: /^Logout$/i });
      if ((await logout.count()) > 0) {
        await logout.first().click();
        await page.waitForURL(/\/login$/, { timeout: 30000 });
      }
    });
  } catch (err) {
    const fatal = err && err.stack ? err.stack : String(err);
    report.fatal_error = fatal;
    console.error('[touchpoint] FATAL', fatal);
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  report.stats = {
    passed: report.passed_steps.length,
    failed: report.failed_steps.length,
    route_checks: report.route_checks.length,
  };

  const rawVideoPath = await video.path();
  const finalVideoPath = path.join(outDir, `touchpoint-matrix-${stamp}.webm`);
  fs.copyFileSync(rawVideoPath, finalVideoPath);
  report.video = finalVideoPath;

  const summaryPath = path.join(outDir, `touchpoint-matrix-${stamp}.json`);
  fs.writeFileSync(summaryPath, `${JSON.stringify(report, null, 2)}\n`);

  console.log(JSON.stringify(report, null, 2));
  console.log(`SUMMARY_PATH=${summaryPath}`);

  if (report.failed_steps.length > 0 || report.fatal_error) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error('[touchpoint] Unhandled error:', err && err.stack ? err.stack : String(err));
  process.exit(1);
});
