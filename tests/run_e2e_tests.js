const http = require('http');

const API_URL = 'http://127.0.0.1:8000';

function post(path, body, cookie = '') {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request({
      hostname: '127.0.0.1',
      port: 8000,
      path: path,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        'Cookie': cookie
      }
    }, (res) => {
      let responseBody = '';
      res.on('data', chunk => responseBody += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(responseBody || '{}'), headers: res.headers });
        } catch(e) {
          resolve({ status: res.statusCode, body: responseBody, headers: res.headers });
        }
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

function get(path, cookie = '') {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: '127.0.0.1',
      port: 8000,
      path: path,
      method: 'GET',
      headers: {
        'Cookie': cookie
      }
    }, (res) => {
      let responseBody = '';
      res.on('data', chunk => responseBody += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(responseBody || '{}'), headers: res.headers });
        } catch(e) {
          resolve({ status: res.statusCode, body: responseBody, headers: res.headers });
        }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function patch(path, body, cookie = '') {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request({
      hostname: '127.0.0.1',
      port: 8000,
      path: path,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        'Cookie': cookie
      }
    }, (res) => {
      let responseBody = '';
      res.on('data', chunk => responseBody += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(responseBody || '{}'), headers: res.headers });
        } catch(e) {
          resolve({ status: res.statusCode, body: responseBody, headers: res.headers });
        }
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function runE2ETests() {
  console.log('🚀 Iniciando Suite de Pruebas E2E: NexaCore Agent Manager...\n');

  // 1. SuperAdmin Login
  console.log('1️⃣  Probando Login de SuperAdmin (Nicolás)...');
  const superadminLogin = await post('/api/auth/login', { email: 'admin@nexacore.com.mx', password: 'prueba123' });
  if (superadminLogin.status !== 200) throw new Error(`SuperAdmin Login Falló: ${superadminLogin.status}`);
  const superadminCookie = superadminLogin.headers['set-cookie'][0];
  console.log('   ✅ SuperAdmin autenticado correctamente.');

  // 2. Registro de Vendedores (Edgar & Enedina)
  console.log('\n2️⃣  Registrando Vendedores (Edgar y Enedina)...');
  const ts = Date.now();
  const edgarEmail = `edgar_${ts}@nexacore.com.mx`;
  const enedinaEmail = `enedina_${ts}@nexacore.com.mx`;

  const edgarReg = await post('/api/auth/register', { agency_name: 'NexaCore', name: 'Edgar Trabajador', email: edgarEmail, password: 'Password123!' });
  if (edgarReg.status !== 201) throw new Error(`Registro de Edgar falló: ${edgarReg.status}`);
  const edgarCookie = edgarReg.headers['set-cookie'][0];
  console.log(`   ✅ Vendedor Edgar registrado: ${edgarEmail}`);

  const enedinaReg = await post('/api/auth/register', { agency_name: 'NexaCore', name: 'Enedina Trabajadora', email: enedinaEmail, password: 'Password123!' });
  if (enedinaReg.status !== 201) throw new Error(`Registro de Enedina falló: ${enedinaReg.status}`);
  const enedinaCookie = enedinaReg.headers['set-cookie'][0];
  console.log(`   ✅ Vendedora Enedina registrada: ${enedinaEmail}`);

  // 3. Edgar registra su cliente ($200 MXN / 500,000 tokens)
  console.log('\n3️⃣  Edgar registra cliente "Clínica Dental Edgar" ($200 MXN / 500k tokens)...');
  const edgarClientRes = await post('/api/clients', {
    name: 'Clínica Dental Edgar',
    industry: 'Salud / Odontología',
    billing_mode: 'plan',
    monthly_fee_mxn: 200.0,
    monthly_token_limit: 500000
  }, edgarCookie);
  if (edgarClientRes.status !== 201) throw new Error(`Creación de cliente Edgar falló: ${edgarClientRes.status}`);
  const edgarClient = edgarClientRes.body;
  console.log(`   ✅ Cliente registrado por Edgar ID: ${edgarClient.id} | Fee: $${edgarClient.monthly_fee_mxn} MXN | Límite: ${edgarClient.monthly_token_limit} tokens`);

  // 4. Enedina registra su cliente ($500 MXN / 1,000,000 tokens)
  console.log('\n4️⃣  Enedina registra cliente "Despacho Abogados Enedina" ($500 MXN / 1M tokens)...');
  const enedinaClientRes = await post('/api/clients', {
    name: 'Despacho Abogados Enedina',
    industry: 'Legal',
    billing_mode: 'plan',
    monthly_fee_mxn: 500.0,
    monthly_token_limit: 1000000
  }, enedinaCookie);
  if (enedinaClientRes.status !== 201) throw new Error(`Creación de cliente Enedina falló: ${enedinaClientRes.status}`);
  const enedinaClient = enedinaClientRes.body;
  console.log(`   ✅ Cliente registrado por Enedina ID: ${enedinaClient.id} | Fee: $${enedinaClient.monthly_fee_mxn} MXN | Límite: ${enedinaClient.monthly_token_limit} tokens`);

  // 5. Prueba de Aislamiento (Scoping de Cartera)
  console.log('\n5️⃣  Verificando Aislamiento Estricto de Cartera (Edgar vs Enedina)...');
  const edgarList = await get('/api/clients', edgarCookie);
  const edgarClientNames = edgarList.body.map(c => c.name);
  if (!edgarClientNames.includes('Clínica Dental Edgar') || edgarClientNames.includes('Despacho Abogados Enedina')) {
    throw new Error(`Violación de aislamiento para Edgar: ${JSON.stringify(edgarClientNames)}`);
  }
  console.log('   ✅ Edgar SOLO ve su cliente ("Clínica Dental Edgar").');

  const enedinaList = await get('/api/clients', enedinaCookie);
  const enedinaClientNames = enedinaList.body.map(c => c.name);
  if (!enedinaClientNames.includes('Despacho Abogados Enedina') || enedinaClientNames.includes('Clínica Dental Edgar')) {
    throw new Error(`Violación de aislamiento para Enedina: ${JSON.stringify(enedinaClientNames)}`);
  }
  console.log('   ✅ Enedina SOLO ve su cliente ("Despacho Abogados Enedina").');

  // 6. Prueba de Finanzas de SuperAdmin (Nicolás)
  console.log('\n6️⃣  Verificando Módulo de Finanzas para SuperAdmin (Nicolás)...');
  const financeRes = await get('/api/dashboard/finance', superadminCookie);
  if (financeRes.status !== 200) throw new Error(`Consulta financiera de SuperAdmin falló: ${financeRes.status}`);
  const finance = financeRes.body;
  console.log(`   ✅ Ingresos Mensuales Proyectados: $${finance.total_monthly_revenue_mxn} MXN`);
  console.log(`   ✅ Total de Clientes Activos: ${finance.total_clients}`);
  console.log(`   ✅ Métricas por Vendedor:`, finance.workers_metrics.map(w => `${w.worker_name}: ${w.clients_count} clientes ($${w.monthly_revenue_mxn} MXN)`).join(' | '));

  // 7. Prueba de Portal de Cliente Restringido
  console.log('\n7️⃣  Probando Alta y Autenticación de Portal de Cliente...');
  const portalConfig = await patch(`/api/clients/${edgarClient.id}/portal`, {
    portal_enabled: true,
    portal_email: `dental_${ts}@sonrisas.com`,
    portal_password: 'Password123!'
  }, edgarCookie);
  if (portalConfig.status !== 200) throw new Error(`Habilitar portal falló: ${portalConfig.status}`);
  console.log('   ✅ Portal de Cliente configurado y activado.');

  const portalLogin = await post('/api/portal/login', {
    email: `dental_${ts}@sonrisas.com`,
    password: 'Password123!'
  });
  if (portalLogin.status !== 200) throw new Error(`Login en Portal de Cliente falló: ${portalLogin.status}`);
  console.log('   ✅ Cliente autenticado correctamente en su Portal de Cliente.');

  console.log('\n🎉 ¡TODAS LAS PRUEBAS PASARON AL 100% EXITOSAMENTE!');
}

runE2ETests().catch(err => {
  console.error('\n❌ ERROR EN PRUEBAS E2E:', err);
  process.exit(1);
});
