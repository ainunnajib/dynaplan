#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const API_BASE = process.env.DYNAPLAN_API_URL || 'https://dynaplan-backend-7qlyqseapa-uc.a.run.app';
const FRONTEND_BASE = process.env.DYNAPLAN_FRONTEND_URL || 'https://dynaplan-frontend-7qlyqseapa-uc.a.run.app';
const EMAIL = process.env.DYNAPLAN_EMAIL;
const PASSWORD = process.env.DYNAPLAN_PASSWORD;
const SCALE = (process.env.DYNAPLAN_SCALE || 'large').toLowerCase();

if (!EMAIL || !PASSWORD) {
  console.error('Missing DYNAPLAN_EMAIL or DYNAPLAN_PASSWORD');
  process.exit(1);
}

const SCALE_CONFIG = {
  small: {
    regions: 2,
    products: 4,
    channels: 3,
    months: 6,
    versions: 2,
    seeded_measures: 3,
    chunk_size: 120,
    concurrency: 4,
  },
  large: {
    regions: 3,
    products: 8,
    channels: 4,
    months: 12,
    versions: 3,
    seeded_measures: 4,
    chunk_size: 220,
    concurrency: 6,
  },
  massive: {
    regions: 5,
    products: 12,
    channels: 5,
    months: 12,
    versions: 4,
    seeded_measures: 6,
    chunk_size: 300,
    concurrency: 8,
  },
};

if (!SCALE_CONFIG[SCALE]) {
  console.error(`Unknown DYNAPLAN_SCALE: ${SCALE}. Use one of: ${Object.keys(SCALE_CONFIG).join(', ')}`);
  process.exit(1);
}

const cfg = SCALE_CONFIG[SCALE];

const REGION_CATALOG = [
  { name: 'Americas', code: 'AMER' },
  { name: 'EMEA', code: 'EMEA' },
  { name: 'APAC', code: 'APAC' },
  { name: 'Japan', code: 'JPN' },
  { name: 'Greater China', code: 'GCN' },
];

const PRODUCT_CATALOG = [
  { name: 'iPhone', code: 'IPH' },
  { name: 'Mac', code: 'MAC' },
  { name: 'iPad', code: 'IPD' },
  { name: 'Wearables', code: 'WAR' },
  { name: 'Services', code: 'SVC' },
  { name: 'AppleCare', code: 'ACR' },
  { name: 'Accessories', code: 'ACC' },
  { name: 'Vision', code: 'VIS' },
  { name: 'TV', code: 'TV' },
  { name: 'Audio', code: 'AUD' },
  { name: 'Cloud', code: 'CLD' },
  { name: 'Enterprise', code: 'ENT' },
];

const CHANNEL_CATALOG = [
  { name: 'Retail', code: 'RTL' },
  { name: 'Online', code: 'ONL' },
  { name: 'Carrier', code: 'CAR' },
  { name: 'Reseller', code: 'RES' },
  { name: 'Enterprise', code: 'B2B' },
];

const MONTH_CATALOG = [
  { name: 'Jan FY26', code: '2026-01' },
  { name: 'Feb FY26', code: '2026-02' },
  { name: 'Mar FY26', code: '2026-03' },
  { name: 'Apr FY26', code: '2026-04' },
  { name: 'May FY26', code: '2026-05' },
  { name: 'Jun FY26', code: '2026-06' },
  { name: 'Jul FY26', code: '2026-07' },
  { name: 'Aug FY26', code: '2026-08' },
  { name: 'Sep FY26', code: '2026-09' },
  { name: 'Oct FY26', code: '2026-10' },
  { name: 'Nov FY26', code: '2026-11' },
  { name: 'Dec FY26', code: '2026-12' },
];

const VERSION_CATALOG = [
  { name: 'Actuals FY26', version_type: 'actuals' },
  { name: 'Forecast FY26', version_type: 'forecast' },
  { name: 'Budget FY26', version_type: 'budget' },
  { name: 'Scenario Upside', version_type: 'scenario' },
];

const LINE_ITEM_BLUEPRINT = [
  { name: 'Units Sold', format: 'number', summary_method: 'sum' },
  { name: 'ASP', format: 'number', summary_method: 'average' },
  { name: 'Gross Revenue', format: 'number', summary_method: 'sum' },
  { name: 'Discount Rate', format: 'number', summary_method: 'average' },
  { name: 'Net Revenue', format: 'number', summary_method: 'sum' },
  { name: 'COGS', format: 'number', summary_method: 'sum' },
  { name: 'Gross Margin', format: 'number', summary_method: 'sum' },
  { name: 'Operating Expense', format: 'number', summary_method: 'sum' },
  { name: 'EBIT', format: 'number', summary_method: 'sum' },
];

const BASE_VALUES = {
  'Units Sold': 50000,
  ASP: 850,
  'Gross Revenue': 42000000,
  'Discount Rate': 0.08,
  'Net Revenue': 38600000,
  COGS: 21500000,
  'Gross Margin': 17100000,
  'Operating Expense': 6400000,
  EBIT: 10700000,
};

function chunk(items, size) {
  const out = [];
  for (let i = 0; i < items.length; i += size) {
    out.push(items.slice(i, i + size));
  }
  return out;
}

async function withConcurrency(limit, tasks) {
  const results = new Array(tasks.length);
  let idx = 0;

  async function worker() {
    while (true) {
      const current = idx;
      idx += 1;
      if (current >= tasks.length) return;
      results[current] = await tasks[current]();
    }
  }

  const workers = Array.from({ length: Math.min(limit, tasks.length) }, () => worker());
  await Promise.all(workers);
  return results;
}

async function api(pathname, { method = 'GET', token, body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = await fetch(`${API_BASE}${pathname}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const isJson = (resp.headers.get('content-type') || '').includes('application/json');
  const payload = isJson ? await resp.json().catch(() => ({})) : await resp.text().catch(() => '');

  if (!resp.ok) {
    throw new Error(`${method} ${pathname} failed (${resp.status}): ${typeof payload === 'string' ? payload.slice(0, 240) : JSON.stringify(payload).slice(0, 240)}`);
  }

  return payload;
}

function pick(list, count) {
  return list.slice(0, count);
}

function hashString(value) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function valueForCell(lineItemName, key, versionIndex) {
  const base = BASE_VALUES[lineItemName] ?? 1000;
  const h = hashString(`${lineItemName}|${key}|${versionIndex}`);

  const swing = ((h % 2401) - 1200) / 10000; // roughly +/- 12%
  const versionFactor = 1 + versionIndex * 0.03;
  const result = base * (1 + swing) * versionFactor;

  if (lineItemName === 'Discount Rate') {
    return Math.max(0, Math.min(0.35, Number(result.toFixed(4))));
  }
  if (lineItemName === 'ASP') {
    return Number(result.toFixed(2));
  }
  return Number(result.toFixed(0));
}

async function main() {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');

  console.log(`[seed] Login against ${API_BASE}`);
  const login = await api('/auth/login', {
    method: 'POST',
    body: { email: EMAIL, password: PASSWORD },
  });
  const token = login.access_token;

  const workspaceName = `Apple FP&A Global ${stamp}`;
  const modelName = `Global Operations Plan FY26 ${stamp.slice(11, 19)}`;

  console.log('[seed] Creating workspace and model');
  const workspace = await api('/workspaces/', {
    method: 'POST',
    token,
    body: {
      name: workspaceName,
      description: 'Synthetic Apple-style FP&A workspace for performance and UX validation.',
    },
  });

  const model = await api('/models', {
    method: 'POST',
    token,
    body: {
      name: modelName,
      description: `Scale=${SCALE}; generated by scripts/seed_apple_fpa_scenario.js`,
      workspace_id: workspace.id,
    },
  });

  const module = await api(`/models/${model.id}/modules`, {
    method: 'POST',
    token,
    body: {
      name: 'Global Revenue & PnL',
      description: 'Core planning module for global revenue, margin, and EBIT.',
    },
  });

  console.log('[seed] Creating dimensions + members');
  const dimensions = {};
  const dimensionMembers = {};

  const dimensionPlan = [
    { key: 'region', name: 'Region', catalog: pick(REGION_CATALOG, cfg.regions) },
    { key: 'product', name: 'Product Family', catalog: pick(PRODUCT_CATALOG, cfg.products) },
    { key: 'channel', name: 'Channel', catalog: pick(CHANNEL_CATALOG, cfg.channels) },
    { key: 'month', name: 'Month', catalog: pick(MONTH_CATALOG, cfg.months) },
  ];

  for (const dim of dimensionPlan) {
    const created = await api(`/models/${model.id}/dimensions`, {
      method: 'POST',
      token,
      body: {
        name: dim.name,
        dimension_type: 'custom',
      },
    });
    dimensions[dim.key] = created;
    dimensionMembers[dim.key] = [];

    for (const member of dim.catalog) {
      const createdMember = await api(`/dimensions/${created.id}/items`, {
        method: 'POST',
        token,
        body: {
          name: member.name,
          code: member.code,
          sort_order: dimensionMembers[dim.key].length,
        },
      });
      dimensionMembers[dim.key].push(createdMember);
    }
  }

  console.log('[seed] Creating versions');
  const versions = [];
  for (const versionSpec of pick(VERSION_CATALOG, cfg.versions)) {
    const v = await api(`/models/${model.id}/versions`, {
      method: 'POST',
      token,
      body: {
        name: versionSpec.name,
        version_type: versionSpec.version_type,
      },
    });
    versions.push(v);
  }

  console.log('[seed] Creating line items');
  const seededLineItems = pick(LINE_ITEM_BLUEPRINT, cfg.seeded_measures);
  const lineItems = [];
  const appliesToDimensions = [
    dimensions.region.id,
    dimensions.product.id,
    dimensions.channel.id,
    dimensions.month.id,
  ];

  for (const item of seededLineItems) {
    const li = await api(`/modules/${module.id}/line-items`, {
      method: 'POST',
      token,
      body: {
        name: item.name,
        format: item.format,
        summary_method: item.summary_method,
        applies_to_dimensions: appliesToDimensions,
      },
    });
    lineItems.push(li);
  }

  console.log('[seed] Generating cell payloads');
  const combos = [];
  for (const region of dimensionMembers.region) {
    for (const product of dimensionMembers.product) {
      for (const channel of dimensionMembers.channel) {
        for (const month of dimensionMembers.month) {
          combos.push({
            key: `${region.id}|${product.id}|${channel.id}|${month.id}`,
            dimension_members: [region.id, product.id, channel.id, month.id],
          });
        }
      }
    }
  }

  const allCells = [];
  versions.forEach((version, versionIndex) => {
    lineItems.forEach((lineItem) => {
      combos.forEach((combo) => {
        allCells.push({
          line_item_id: lineItem.id,
          dimension_members: combo.dimension_members,
          version_id: version.id,
          value: valueForCell(lineItem.name, combo.key, versionIndex),
        });
      });
    });
  });

  console.log(`[seed] Writing ${allCells.length.toLocaleString()} cells in bulk`);
  const chunks = chunk(allCells, cfg.chunk_size);
  let inserted = 0;

  await withConcurrency(
    cfg.concurrency,
    chunks.map((cellsChunk, idx) => async () => {
      const result = await api('/cells/bulk', {
        method: 'POST',
        token,
        body: { cells: cellsChunk },
      });
      inserted += Array.isArray(result) ? result.length : 0;
      if ((idx + 1) % 10 === 0 || idx + 1 === chunks.length) {
        console.log(`[seed] Bulk chunk ${idx + 1}/${chunks.length}`);
      }
      return result;
    })
  );

  console.log('[seed] Creating dashboard and widgets');
  const dashboard = await api(`/models/${model.id}/dashboards`, {
    method: 'POST',
    token,
    body: {
      name: 'Executive FP&A Cockpit',
      description: 'Auto-generated dashboard for scenario and KPI reviews.',
    },
  });

  await api(`/dashboards/${dashboard.id}/widgets`, {
    method: 'POST',
    token,
    body: {
      widget_type: 'kpi_card',
      title: 'Net Revenue (Synthetic)',
      position_x: 0,
      position_y: 0,
      width: 3,
      height: 2,
      config: { label: 'Net Revenue', value: null },
    },
  });

  await api(`/dashboards/${dashboard.id}/widgets`, {
    method: 'POST',
    token,
    body: {
      widget_type: 'grid',
      title: 'Revenue Grid',
      position_x: 3,
      position_y: 0,
      width: 9,
      height: 6,
      config: { module_id: module.id },
    },
  });

  const summary = {
    generated_at: new Date().toISOString(),
    scale: SCALE,
    api_base: API_BASE,
    workspace: {
      id: workspace.id,
      name: workspace.name,
      url: `${FRONTEND_BASE}/workspaces/${workspace.id}`,
    },
    model: {
      id: model.id,
      name: model.name,
      url: `${FRONTEND_BASE}/models/${model.id}`,
    },
    module: {
      id: module.id,
      name: module.name,
      url: `${FRONTEND_BASE}/models/${model.id}/modules/${module.id}`,
    },
    dashboard: {
      id: dashboard.id,
      name: dashboard.name,
      url: `${FRONTEND_BASE}/models/${model.id}/dashboards/${dashboard.id}`,
    },
    dimensions: Object.fromEntries(
      Object.entries(dimensions).map(([k, dim]) => [k, { id: dim.id, name: dim.name, members: dimensionMembers[k].length }])
    ),
    versions: versions.map((v) => ({ id: v.id, name: v.name, version_type: v.version_type })),
    line_items: lineItems.map((li) => ({ id: li.id, name: li.name })),
    cell_count_target: allCells.length,
    cell_count_written: inserted,
    combination_count: combos.length,
    notes: [
      'Synthetic data only; values are deterministic pseudo-randomized by dimension tuple.',
      'Use this model for browser workflows, backpressure tests, and Rust engine load checks.',
    ],
  };

  const outDir = '/Users/ainunnajib/dynaplan/test-results/data-seed';
  fs.mkdirSync(outDir, { recursive: true });
  const outPath = path.join(outDir, `apple-fpa-${stamp}.json`);
  fs.writeFileSync(outPath, `${JSON.stringify(summary, null, 2)}\n`);

  console.log(JSON.stringify(summary, null, 2));
  console.log(`SUMMARY_PATH=${outPath}`);
}

main().catch((err) => {
  console.error(`[seed] FATAL: ${err && err.stack ? err.stack : String(err)}`);
  process.exit(1);
});
