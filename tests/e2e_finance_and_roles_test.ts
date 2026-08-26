import { test, expect, APIRequestContext } from '@playwright/test';

const API_URL = process.env.API_URL || 'http://localhost:8000';

const SUPERADMIN = { email: 'admin@nexacore.com.mx', password: 'prueba123' };
const SELLER_PASSWORD = 'Password123!';

/**
 * Logs in and returns the raw session cookie.
 *
 * Sellers must be created through POST /api/agency/users, NOT through
 * /api/auth/register: register always creates a brand new agency, so sellers
 * registered that way end up isolated by agency_id and the portfolio scoping
 * under test is never actually exercised.
 */
async function login(request: APIRequestContext, email: string, password: string): Promise<string> {
  const res = await request.post(`${API_URL}/api/auth/login`, { data: { email, password } });
  expect(res.status(), `login failed for ${email}`).toBe(200);
  const cookie = res.headers()['set-cookie'];
  expect(cookie, `no session cookie for ${email}`).toBeTruthy();
  return cookie.split(';')[0];
}

async function createSeller(request: APIRequestContext, adminCookie: string, name: string, email: string) {
  const res = await request.post(`${API_URL}/api/agency/users`, {
    headers: { Cookie: adminCookie },
    data: { name, email, password: SELLER_PASSWORD, role: 'seller' },
  });
  expect(res.status(), `could not create seller ${email}`).toBe(201);
  return res.json();
}

async function createClient(request: APIRequestContext, cookie: string, data: Record<string, unknown>) {
  const res = await request.post(`${API_URL}/api/clients`, { headers: { Cookie: cookie }, data });
  expect(res.status(), `could not create client ${data.name}`).toBe(201);
  return res.json();
}

test.describe('Finance, seller scoping and client portal', () => {
  const stamp = Date.now();
  const edgarEmail = `edgar_${stamp}@nexacore.com.mx`;
  const enedinaEmail = `enedina_${stamp}@nexacore.com.mx`;

  let adminCookie: string;
  let edgarCookie: string;
  let enedinaCookie: string;
  let edgar: any;
  let enedina: any;
  let dentalClient: any;
  let lawClient: any;

  test.beforeAll(async ({ playwright }) => {
    const request = await playwright.request.newContext();

    adminCookie = await login(request, SUPERADMIN.email, SUPERADMIN.password);
    edgar = await createSeller(request, adminCookie, 'Edgar Vendedor', edgarEmail);
    enedina = await createSeller(request, adminCookie, 'Enedina Vendedora', enedinaEmail);

    edgarCookie = await login(request, edgarEmail, SELLER_PASSWORD);
    enedinaCookie = await login(request, enedinaEmail, SELLER_PASSWORD);

    dentalClient = await createClient(request, edgarCookie, {
      name: `Consultorio Dental Sonrisas ${stamp}`,
      industry: 'Salud / Odontologia',
      billing_mode: 'plan',
      monthly_fee_mxn: 200.0,
      monthly_token_limit: 500000,
    });
    lawClient = await createClient(request, enedinaCookie, {
      name: `Despacho Juridico Enedina ${stamp}`,
      industry: 'Legal',
      billing_mode: 'plan',
      monthly_fee_mxn: 500.0,
      monthly_token_limit: 1000000,
    });

    await request.dispose();
  });

  test('sellers belong to the same agency as the superadmin', async ({ request }) => {
    // This is the premise the whole isolation suite rests on. If sellers landed
    // in separate agencies, every assertion below would pass for the wrong
    // reason: agency_id isolation, not the seller scoping under test.
    const res = await request.get(`${API_URL}/api/agency`, { headers: { Cookie: edgarCookie } });
    expect(res.status()).toBe(200);
    const edgarAgency = await res.json();

    const adminRes = await request.get(`${API_URL}/api/agency`, { headers: { Cookie: adminCookie } });
    const adminAgency = await adminRes.json();

    expect(edgarAgency.id).toBe(adminAgency.id);
  });

  test('a new client is owned by its creator and cuts on the signup day', async () => {
    expect(dentalClient.created_by_user_id).toBe(edgar.id);
    expect(Number(dentalClient.monthly_fee_mxn)).toBe(200);
    expect(dentalClient.monthly_token_limit).toBe(500000);
    expect(dentalClient.billing_anchor_day).toBe(new Date().getUTCDate());
  });

  test('a seller only sees their own portfolio', async ({ request }) => {
    const edgarList = await (
      await request.get(`${API_URL}/api/clients`, { headers: { Cookie: edgarCookie } })
    ).json();
    const edgarIds = edgarList.map((c: any) => c.id);
    expect(edgarIds).toContain(dentalClient.id);
    expect(edgarIds).not.toContain(lawClient.id);

    const enedinaList = await (
      await request.get(`${API_URL}/api/clients`, { headers: { Cookie: enedinaCookie } })
    ).json();
    const enedinaIds = enedinaList.map((c: any) => c.id);
    expect(enedinaIds).toContain(lawClient.id);
    expect(enedinaIds).not.toContain(dentalClient.id);
  });

  test('reaching another seller client by direct id returns 404, not 403', async ({ request }) => {
    // 403 would confirm the client exists and leak the shape of the portfolio.
    const res = await request.get(`${API_URL}/api/clients/${dentalClient.id}`, {
      headers: { Cookie: enedinaCookie },
    });
    expect(res.status()).toBe(404);
  });

  test('a seller cannot attribute a new client to another seller', async ({ request }) => {
    const res = await request.post(`${API_URL}/api/clients`, {
      headers: { Cookie: enedinaCookie },
      data: {
        name: `Intento de suplantacion ${stamp}`,
        billing_mode: 'plan',
        created_by_user_id: edgar.id,
      },
    });
    expect(res.status()).toBe(201);
    const created = await res.json();
    // Ownership comes from the session; the payload field must be ignored.
    expect(created.created_by_user_id).toBe(enedina.id);
  });

  test('the superadmin sees every client and the consolidated projection', async ({ request }) => {
    const clients = await (
      await request.get(`${API_URL}/api/clients`, { headers: { Cookie: adminCookie } })
    ).json();
    const ids = clients.map((c: any) => c.id);
    expect(ids).toContain(dentalClient.id);
    expect(ids).toContain(lawClient.id);

    const res = await request.get(`${API_URL}/api/dashboard/finance`, { headers: { Cookie: adminCookie } });
    expect(res.status()).toBe(200);
    const finance = await res.json();

    expect(finance.total_clients).toBeGreaterThanOrEqual(2);
    expect(finance.total_monthly_revenue_mxn).toBeGreaterThanOrEqual(700);

    const byEdgar = finance.workers_metrics.find((w: any) => w.worker_id === edgar.id);
    const byEnedina = finance.workers_metrics.find((w: any) => w.worker_id === enedina.id);
    expect(byEdgar.monthly_revenue_mxn).toBe(200);
    expect(byEnedina.monthly_revenue_mxn).toBeGreaterThanOrEqual(500);
  });

  test('the finance dashboard is closed to sellers', async ({ request }) => {
    const res = await request.get(`${API_URL}/api/dashboard/finance`, { headers: { Cookie: edgarCookie } });
    expect(res.status()).toBe(403);
  });

  test('a seller cannot create users', async ({ request }) => {
    const res = await request.post(`${API_URL}/api/agency/users`, {
      headers: { Cookie: edgarCookie },
      data: { name: 'Colado', email: `colado_${stamp}@nexacore.com.mx`, password: SELLER_PASSWORD, role: 'seller' },
    });
    expect(res.status()).toBe(403);
  });

  test('quota starts empty and reports the cycle window', async ({ request }) => {
    const client = await (
      await request.get(`${API_URL}/api/clients/${dentalClient.id}`, { headers: { Cookie: edgarCookie } })
    ).json();
    expect(client.used_tokens_current_cycle).toBe(0);
    expect(client.percentage_tokens_used).toBe(0);
    expect(client.is_blocked).toBe(false);
  });

  test('the client portal authenticates against its own slug', async ({ request }) => {
    const portalEmail = `dental_${stamp}@sonrisas.com`;
    const configured = await request.patch(`${API_URL}/api/clients/${dentalClient.id}/portal`, {
      headers: { Cookie: edgarCookie },
      data: { portal_enabled: true, portal_email: portalEmail, portal_password: SELLER_PASSWORD },
    });
    expect(configured.status()).toBe(200);
    const client = await configured.json();
    expect(client.portal_password_configured).toBe(true);

    // The portal is slug-scoped: /api/portal/{slug}/login, not /api/portal/login.
    const res = await request.post(`${API_URL}/api/portal/${client.portal_slug}/login`, {
      data: { email: portalEmail, password: SELLER_PASSWORD },
    });
    expect(res.status()).toBe(200);
    const session = await res.json();
    expect(session.client_id).toBe(dentalClient.id);
  });
});
