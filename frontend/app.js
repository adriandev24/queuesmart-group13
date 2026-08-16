const state = {
  token: localStorage.getItem('queuesmart_token') || '',
  role: localStorage.getItem('queuesmart_role') || '',
  name: localStorage.getItem('queuesmart_name') || '',
  email: localStorage.getItem('queuesmart_email') || '',
  services: []
};

const $ = (id) => document.getElementById(id);

function authHeaders(json = false) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (json) headers['Content-Type'] = 'application/json';
  return headers;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) {
        detail = body.detail.map(item => item.msg || JSON.stringify(item)).join('; ');
      } else if (body.detail) detail = body.detail;
    } catch (_) {}
    throw new Error(detail);
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response;
}

function message(text, isError = false) {
  const box = $('message');
  box.textContent = text;
  box.classList.remove('hidden', 'error');
  if (isError) box.classList.add('error');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  setTimeout(() => box.classList.add('hidden'), 4500);
}

function clearAuthForms() {
  $('loginForm').reset();
  $('registerForm').reset();
  ['loginEmail', 'loginPassword', 'registerName', 'registerEmail', 'registerPassword'].forEach(id => {
    const field = $(id);
    field.value = '';
    field.defaultValue = '';
  });
  $('registerRole').value = 'user';
}

function clearBrowserRestoredAuthValues() {
  clearAuthForms();
  // Some browsers restore/autofill credentials just after the page is painted.
  // Clear one more time after restoration without affecting later user typing.
  window.setTimeout(clearAuthForms, 75);
}

function setSession(data) {
  state.token = data.token;
  state.role = data.role;
  state.name = data.full_name || '';
  state.email = data.email || '';
  localStorage.setItem('queuesmart_token', state.token);
  localStorage.setItem('queuesmart_role', state.role);
  localStorage.setItem('queuesmart_name', state.name);
  localStorage.setItem('queuesmart_email', state.email);
  syncNav();
}

function clearSession() {
  Object.assign(state, { token: '', role: '', name: '', email: '' });
  ['queuesmart_token','queuesmart_role','queuesmart_name','queuesmart_email'].forEach(k => localStorage.removeItem(k));
  syncNav();
}

function syncNav() {
  document.querySelectorAll('.user-only').forEach(el => el.classList.toggle('hidden', state.role !== 'user'));
  document.querySelectorAll('.admin-only').forEach(el => el.classList.toggle('hidden', state.role !== 'administrator'));
  $('logoutButton').classList.toggle('hidden', !state.token);
  $('sessionPill').textContent = state.token ? `${state.name || state.email} · ${state.role}` : 'Not signed in';
}

function showView(id) {
  document.querySelectorAll('.view').forEach(view => view.classList.remove('active'));
  $(id).classList.add('active');
  if (id === 'authView') clearAuthForms();
  if (id === 'userView') loadUserDashboard();
  if (id === 'historyView') loadHistoryAndNotifications();
  if (id === 'adminView') loadAdminDashboard();
  if (id === 'reportsView') prepareReports();
  $('sideNav').classList.remove('open');
  if (window.matchMedia('(max-width: 980px)').matches) {
    $('menuButton').setAttribute('aria-expanded', 'false');
  }
}

function table(headers, rows) {
  if (!rows.length) return '<p class="muted">No data available.</p>';
  return `<div class="table-wrap"><table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}

function stat(label, value) {
  return `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

async function loadServices() {
  state.services = await api('/api/services');
  const options = state.services.map(s => `<option value="${s.id}">${escapeHtml(s.name)} (${s.queue_status})</option>`).join('');
  $('joinService').innerHTML = `<option value="">Select a service</option>${options}`;
  $('adminQueueService').innerHTML = `<option value="">Select a service</option>${options}`;
  $('reportService').innerHTML = `<option value="">All services</option>${options}`;
}

function toggleNavigation() {
  const sideNav = $('sideNav');
  const shell = document.querySelector('.shell');
  const isMobile = window.matchMedia('(max-width: 980px)').matches;

  if (isMobile) {
    const isOpen = sideNav.classList.toggle('open');
    $('menuButton').setAttribute('aria-expanded', String(isOpen));
  } else {
    const isCollapsed = shell.classList.toggle('nav-collapsed');
    $('menuButton').setAttribute('aria-expanded', String(!isCollapsed));
  }
}

function syncMenuState() {
  const sideNav = $('sideNav');
  const shell = document.querySelector('.shell');
  const isMobile = window.matchMedia('(max-width: 980px)').matches;
  $('menuButton').setAttribute(
    'aria-expanded',
    String(isMobile ? sideNav.classList.contains('open') : !shell.classList.contains('nav-collapsed'))
  );
}

$('menuButton').addEventListener('click', toggleNavigation);
window.addEventListener('resize', syncMenuState);
window.addEventListener('pageshow', clearBrowserRestoredAuthValues);
syncMenuState();
clearBrowserRestoredAuthValues();
document.querySelectorAll('[data-view]').forEach(btn => btn.addEventListener('click', () => showView(btn.dataset.view)));

$('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const data = await api('/api/auth/login', {
      method: 'POST', headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({ email: $('loginEmail').value, password: $('loginPassword').value })
    });
    setSession(data);
    clearAuthForms();
    message('Login successful.');
    await loadServices();
    showView(state.role === 'administrator' ? 'adminView' : 'userView');
  } catch (err) { message(err.message, true); }
});

$('registerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await api('/api/auth/register', {
      method: 'POST', headers: { 'Content-Type':'application/json' },
      body: JSON.stringify({
        full_name: $('registerName').value,
        email: $('registerEmail').value,
        password: $('registerPassword').value,
        role: $('registerRole').value
      })
    });
    clearAuthForms();
    message('Registration complete. You can sign in now.');
  } catch (err) { message(err.message, true); }
});

$('logoutButton').addEventListener('click', async () => {
  try { if (state.token) await api('/api/auth/logout', { method:'POST', headers: authHeaders() }); } catch (_) {}
  clearSession();
  clearAuthForms();
  showView('authView');
  message('You have been logged out.');
});

async function loadUserDashboard() {
  try {
    await loadServices();
    const [statusRows, notifications] = await Promise.all([
      api('/api/queues/status', { headers: authHeaders() }),
      api('/api/notifications', { headers: authHeaders() })
    ]);
    $('userStats').innerHTML = [
      stat('Active queues', statusRows.length),
      stat('Available services', state.services.filter(s => s.queue_status === 'open').length),
      stat('Unread notifications', notifications.filter(n => n.status === 'sent').length),
      stat('Total people waiting', state.services.reduce((sum,s) => sum+s.waiting_count,0))
    ].join('');
    $('queueStatus').innerHTML = statusRows.length ? statusRows.map(row => `
      <div class="queue-card"><strong>${escapeHtml(row.service_name)}</strong><p>Position <b>${row.position}</b> · Estimated wait <b>${row.estimated_wait_minutes} min</b></p>
      <button class="secondary leave-queue" data-queue="${row.queue_id}">Leave Queue</button></div>`).join('') : '<p class="muted">You are not currently waiting in a queue.</p>';
    document.querySelectorAll('.leave-queue').forEach(btn => btn.addEventListener('click', async () => {
      try { await api(`/api/queues/${btn.dataset.queue}/leave`, { method:'DELETE', headers:authHeaders() }); message('You left the queue.'); loadUserDashboard(); }
      catch (err) { message(err.message, true); }
    }));
  } catch (err) { message(err.message, true); }
}

$('joinService').addEventListener('change', async () => {
  const id = $('joinService').value;
  $('bestTimeResult').classList.add('hidden');
  if (!id) { $('estimateText').textContent = 'Select a service to view the estimated wait.'; return; }
  try {
    const estimate = await api(`/api/services/${id}/estimate`);
    $('estimateText').textContent = `${estimate.waiting_count} waiting · approximately ${estimate.estimated_wait_minutes} minutes before joining.`;
  } catch (err) { message(err.message, true); }
});

$('joinForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const serviceId = Number($('joinService').value);
  if (!serviceId) return message('Select a service first.', true);
  try {
    const result = await api('/api/queues/join', {
      method:'POST', headers:authHeaders(true),
      body: JSON.stringify({ service_id: serviceId, reason_for_visit: $('joinReason').value })
    });
    message(`Joined ${result.service_name}. Your position is ${result.position}.`);
    $('joinReason').value = '';
    loadUserDashboard();
  } catch (err) { message(err.message, true); }
});

$('bestTimeButton').addEventListener('click', async () => {
  const serviceId = Number($('joinService').value);
  if (!serviceId) return message('Select a service before requesting a recommendation.', true);
  try {
    const data = await api(`/api/services/${serviceId}/best-time`, { headers:authHeaders() });
    const box = $('bestTimeResult');
    box.innerHTML = `<span class="eyebrow">Smart recommendation</span><br><strong>${escapeHtml(data.recommended_window)}</strong><p>${escapeHtml(data.explanation)}</p><small>${data.historical_samples} historical served visits analyzed · Confidence: ${data.confidence} · Current waiting: ${data.current_waiting}</small>`;
    box.classList.remove('hidden');
  } catch (err) { message(err.message, true); }
});

async function loadHistoryAndNotifications() {
  try {
    const [history, notifications] = await Promise.all([
      api('/api/history', { headers:authHeaders() }),
      api('/api/notifications', { headers:authHeaders() })
    ]);
    $('historyTable').innerHTML = table(['Date','Service','Wait','Outcome'], history.map(row => `<tr><td>${new Date(row.completed_at).toLocaleString()}</td><td>${escapeHtml(row.service_name)}</td><td>${row.wait_minutes} min</td><td><span class="badge">${row.outcome}</span></td></tr>`));
    $('notificationList').innerHTML = notifications.length ? notifications.map(n => `<div class="notification"><b>${escapeHtml(n.message)}</b><small>${new Date(n.timestamp).toLocaleString()} · ${n.status}</small></div>`).join('') : '<p class="muted">No notifications yet.</p>';
  } catch (err) { message(err.message, true); }
}

$('refreshUser').addEventListener('click', loadUserDashboard);
$('refreshHistory').addEventListener('click', loadHistoryAndNotifications);

$('serviceForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await api('/api/services', {
      method:'POST', headers:authHeaders(true),
      body: JSON.stringify({
        name:$('serviceName').value,
        description:$('serviceDescription').value,
        expected_duration:Number($('serviceDuration').value),
        priority_level:$('servicePriority').value
      })
    });
    event.target.reset();
    message('Service created.');
    loadAdminDashboard();
  } catch (err) { message(err.message, true); }
});

async function loadAdminDashboard() {
  try {
    await loadServices();
    const data = await api('/api/admin/dashboard', { headers:authHeaders() });
    $('adminStats').innerHTML = [stat('Services',data.service_count),stat('Open queues',data.open_queues),stat('Waiting users',data.waiting_users),stat('Database','SQLite')].join('');
    $('serviceTable').innerHTML = table(['Service','Duration','Priority','Queue','Waiting','Action'], data.services.map(s => `<tr><td><b>${escapeHtml(s.name)}</b><br><small>${escapeHtml(s.description)}</small></td><td>${s.expected_duration} min</td><td>${s.priority_level}</td><td>${s.queue_status}</td><td>${s.waiting_count}</td><td><button class="secondary toggle-service" data-id="${s.id}">${s.queue_status === 'open' ? 'Close' : 'Open'}</button></td></tr>`));
    document.querySelectorAll('.toggle-service').forEach(btn => btn.addEventListener('click', async () => {
      try { await api(`/api/services/${btn.dataset.id}/queue/toggle`, { method:'POST', headers:authHeaders() }); loadAdminDashboard(); }
      catch (err) { message(err.message, true); }
    }));
  } catch (err) { message(err.message, true); }
}

$('refreshAdmin').addEventListener('click', loadAdminDashboard);
$('loadAdminQueue').addEventListener('click', loadSelectedAdminQueue);
$('serveNext').addEventListener('click', async () => {
  const id = $('adminQueueService').value;
  if (!id) return message('Select a service first.', true);
  try { await api(`/api/admin/queues/${id}/serve-next`, { method:'POST', headers:authHeaders() }); message('Next user served.'); loadSelectedAdminQueue(); loadAdminDashboard(); }
  catch (err) { message(err.message, true); }
});

async function loadSelectedAdminQueue() {
  const id = $('adminQueueService').value;
  if (!id) return $('adminQueueTable').innerHTML = '<p class="muted">Select a service.</p>';
  try {
    const data = await api(`/api/admin/queues/${id}`, { headers:authHeaders() });
    $('adminQueueTable').innerHTML = table(['Pos.','Customer','Reason','Joined','Actions'], data.entries.map(e => `<tr><td>${e.position}</td><td><b>${escapeHtml(e.name)}</b><br><small>${escapeHtml(e.email)}</small></td><td>${escapeHtml(e.reason_for_visit)}</td><td>${new Date(e.joined_at).toLocaleTimeString()}</td><td><div class="button-row"><button class="secondary move-entry" data-id="${e.id}" data-dir="up">↑</button><button class="secondary move-entry" data-id="${e.id}" data-dir="down">↓</button><button class="secondary remove-entry" data-id="${e.id}">Remove</button></div></td></tr>`));
    document.querySelectorAll('.move-entry').forEach(btn => btn.addEventListener('click', async () => {
      try { await api(`/api/admin/queues/${id}/entries/${btn.dataset.id}/move`, { method:'POST', headers:authHeaders(true), body:JSON.stringify({direction:btn.dataset.dir}) }); loadSelectedAdminQueue(); }
      catch (err) { message(err.message, true); }
    }));
    document.querySelectorAll('.remove-entry').forEach(btn => btn.addEventListener('click', async () => {
      try { await api(`/api/admin/queues/${id}/entries/${btn.dataset.id}`, { method:'DELETE', headers:authHeaders() }); loadSelectedAdminQueue(); loadAdminDashboard(); }
      catch (err) { message(err.message, true); }
    }));
  } catch (err) { message(err.message, true); }
}

async function prepareReports() {
  try { await loadServices(); } catch (err) { message(err.message, true); }
}

function reportQuery() {
  const p = new URLSearchParams();
  if ($('reportStart').value) p.set('start_date', $('reportStart').value);
  if ($('reportEnd').value) p.set('end_date', $('reportEnd').value);
  if ($('reportService').value) p.set('service_id', $('reportService').value);
  return p.toString();
}

$('previewReport').addEventListener('click', async () => {
  try {
    const data = await api(`/api/admin/reports/summary?${reportQuery()}`, { headers:authHeaders() });
    const s = data.statistics;
    $('reportStats').innerHTML = [stat('Served',s.users_served),stat('Avg. wait',`${s.average_wait_minutes} min`),stat('Participations',s.total_participations),stat('Unique customers',s.unique_customers)].join('');
    $('reportServices').innerHTML = table(['Service','Queue','Waiting','Served','Canceled'], data.services.map(row => `<tr><td><b>${escapeHtml(row.name)}</b><br><small>${escapeHtml(row.description)}</small></td><td>${row.queue_status}</td><td>${row.current_waiting}</td><td>${row.served}</td><td>${row.canceled}</td></tr>`));
    const userRows = [];
    data.users.forEach(user => {
      if (!user.history.length) userRows.push(`<tr><td>${escapeHtml(user.full_name)}</td><td>${escapeHtml(user.email)}</td><td colspan="4">No matching participation history</td></tr>`);
      user.history.forEach(h => userRows.push(`<tr><td>${escapeHtml(user.full_name)}</td><td>${escapeHtml(user.email)}</td><td>${escapeHtml(h.service)}</td><td>${new Date(h.completed_at).toLocaleDateString()}</td><td>${h.wait_minutes} min</td><td>${h.outcome}</td></tr>`));
    });
    $('reportUsers').innerHTML = table(['Customer','Email','Service','Date','Wait','Outcome'], userRows);
  } catch (err) { message(err.message, true); }
});

$('exportReport').addEventListener('click', async () => {
  try {
    const response = await api(`/api/admin/reports/export.csv?${reportQuery()}`, { headers:authHeaders() });
    const blob = await response.blob();
    const disposition = response.headers.get('content-disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : 'queuesmart_report.csv';
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
    message('CSV report generated.');
  } catch (err) { message(err.message, true); }
});

syncNav();
(async () => {
  if (!state.token) return showView('authView');
  try {
    await api('/api/profile', { headers:authHeaders() });
    await loadServices();
    showView(state.role === 'administrator' ? 'adminView' : 'userView');
  } catch (_) {
    clearSession();
    showView('authView');
  }
})();
