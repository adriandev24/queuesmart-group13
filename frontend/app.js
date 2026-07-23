const state = {
  token: localStorage.getItem("queuesmartToken") || "",
  user: JSON.parse(localStorage.getItem("queuesmartUser") || "null"),
  services: [],
  activeQueue: null,
};

const screens = [...document.querySelectorAll(".screen")];
const drawer = document.getElementById("drawer");
const backdrop = document.getElementById("drawerBackdrop");
const messageBox = document.getElementById("globalMessage");

function showMessage(message, isError = false) {
  messageBox.textContent = message;
  messageBox.className = `global-message${isError ? " error" : ""}`;
  clearTimeout(showMessage.timeout);
  showMessage.timeout = setTimeout(() => messageBox.classList.add("hidden"), 4200);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  let payload = {};
  try { payload = await response.json(); } catch (_) { payload = {}; }
  if (!response.ok) {
    const validation = payload.details?.map(item => `${item.field}: ${item.message}`).join("; ");
    throw new Error(validation || payload.error || "The request could not be completed.");
  }
  return payload;
}

function saveSession(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem("queuesmartToken", token);
  localStorage.setItem("queuesmartUser", JSON.stringify(user));
  updateSessionUI();
}

function clearSession() {
  state.token = "";
  state.user = null;
  state.activeQueue = null;
  localStorage.removeItem("queuesmartToken");
  localStorage.removeItem("queuesmartUser");
  updateSessionUI();
}

function updateSessionUI() {
  document.getElementById("sessionBadge").textContent = state.user ? `${state.user.full_name} · ${state.user.role}` : "Not signed in";
  document.getElementById("logoutButton").classList.toggle("hidden", !state.user);
  document.querySelectorAll("[data-role]").forEach(element => {
    element.classList.toggle("hidden", !state.user || element.dataset.role !== state.user.role);
  });
}

function closeDrawer() {
  drawer.classList.remove("open");
  backdrop.classList.add("hidden");
  document.getElementById("menuButton").setAttribute("aria-expanded", "false");
}

async function showScreen(screenId) {
  const protectedUser = ["user-dashboard", "join-queue", "queue-status", "history"];
  const protectedAdmin = ["admin-dashboard", "service-management", "queue-management"];
  if (protectedUser.includes(screenId) && state.user?.role !== "user") {
    showMessage("Please sign in with a user account.", true);
    screenId = "login";
  }
  if (protectedAdmin.includes(screenId) && state.user?.role !== "administrator") {
    showMessage("Please sign in with an administrator account.", true);
    screenId = "login";
  }
  screens.forEach(screen => screen.classList.toggle("hidden", screen.id !== screenId));
  history.replaceState(null, "", `#${screenId}`);
  closeDrawer();
  try {
    if (screenId === "user-dashboard") await loadUserDashboard();
    if (screenId === "join-queue") await prepareJoinQueue();
    if (screenId === "queue-status") await loadQueueStatus();
    if (screenId === "history") await loadHistory();
    if (screenId === "admin-dashboard") await loadAdminDashboard();
    if (screenId === "service-management") await loadServiceManagement();
    if (screenId === "queue-management") await prepareQueueManagement();
  } catch (error) {
    showMessage(error.message, true);
  }
}

function statCard(label, value, note) {
  return `<article class="stat-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`;
}

function serviceItem(service, withEdit = false) {
  return `<div class="service-item"><div><b>${escapeHtml(service.name)}</b><p>${service.queue_length} waiting · ${service.expected_duration} min each · ${service.priority_level} priority</p></div>${withEdit ? `<button class="table-action" data-edit-service="${service.id}">Edit</button>` : `<span class="badge ${service.is_open ? "open" : "closed"}">${service.is_open ? "Open" : "Closed"}</span>`}</div>`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

async function loadServices() {
  const payload = await api("/api/services");
  state.services = payload.services;
  return state.services;
}

async function loadUserDashboard() {
  const payload = await api("/api/dashboard/user");
  state.services = payload.services;
  state.activeQueue = payload.queue_status;
  document.getElementById("userStats").innerHTML = [
    statCard("Current Position", payload.queue_status ? `#${payload.queue_status.position}` : "—", payload.queue_status?.service_name || "No active queue"),
    statCard("Estimated Wait", payload.queue_status ? `${payload.queue_status.estimated_wait} min` : "0 min", "Calculated by the backend"),
    statCard("Notifications", payload.notifications.length, "Latest queue updates"),
  ].join("");
  document.getElementById("dashboardServices").innerHTML = payload.services.map(service => serviceItem(service)).join("");
  document.getElementById("dashboardNotifications").innerHTML = payload.notifications.length
    ? payload.notifications.map(note => `<div class="notification-item"><b>${escapeHtml(note.message)}</b><span>${new Date(note.created_at).toLocaleString()}</span></div>`).join("")
    : `<div class="empty-state">No notifications yet.</div>`;
}

async function prepareJoinQueue() {
  const services = await loadServices();
  const select = document.getElementById("joinService");
  select.innerHTML = `<option value="">Choose a service</option>` + services.filter(service => service.is_open).map(service => `<option value="${service.id}">${escapeHtml(service.name)}</option>`).join("");
  try {
    const status = await api("/api/queues/status");
    state.activeQueue = status.queue_status;
  } catch (_) { state.activeQueue = null; }
}

async function updateEstimate() {
  const serviceId = Number(document.getElementById("joinService").value);
  if (!serviceId) {
    document.getElementById("joinEstimate").textContent = "Select a service";
    document.getElementById("joinPosition").textContent = "Backend calculation: position × expected duration";
    return;
  }
  try {
    const payload = await api(`/api/services/${serviceId}/estimate`);
    document.getElementById("joinEstimate").textContent = `${payload.estimated_wait} min`;
    document.getElementById("joinPosition").textContent = `Predicted position: ${payload.position}`;
  } catch (error) { showMessage(error.message, true); }
}

async function loadQueueStatus() {
  const payload = await api("/api/queues/status");
  state.activeQueue = payload.queue_status;
  const container = document.getElementById("statusContent");
  if (!payload.queue_status) {
    container.innerHTML = `<article class="panel empty-state">You are not currently waiting in a queue.</article>`;
    return;
  }
  const item = payload.queue_status;
  container.innerHTML = `
    <article class="queue-ticket"><p>Active Ticket · ${escapeHtml(item.service_name)}</p><h2>Position #${item.position}</h2><strong>${item.estimated_wait} min estimated wait</strong><span class="badge open">${item.position <= 3 ? "Almost Ready" : "Waiting"}</span></article>
    <article class="panel"><h2>Status Updates</h2><div class="timeline">
      <div class="timeline-item done"><b>Joined</b><span>${new Date(item.joined_at).toLocaleString()}</span></div>
      <div class="timeline-item done"><b>Waiting</b><span>Priority: ${item.priority}</span></div>
      <div class="timeline-item ${item.position <= 3 ? "active" : ""}"><b>Almost Ready</b><span>${item.position <= 3 ? "You are close to being served." : "Notification will be generated when you reach the front."}</span></div>
      <div class="timeline-item"><b>Served</b><span>Not completed yet</span></div>
    </div></article>`;
}

async function loadHistory() {
  const payload = await api("/api/history");
  const container = document.getElementById("historyTable");
  if (!payload.history.length) {
    container.innerHTML = `<div class="empty-state">No queue history is available.</div>`;
    return;
  }
  container.innerHTML = `<table><thead><tr><th>Date</th><th>Service</th><th>Wait Time</th><th>Outcome</th></tr></thead><tbody>${payload.history.map(item => `<tr><td>${new Date(item.completed_at).toLocaleDateString()}</td><td>${escapeHtml(item.service_name)}</td><td>${item.wait_minutes} min</td><td><span class="badge ${item.outcome}">${item.outcome.replace("_", " ")}</span></td></tr>`).join("")}</tbody></table>`;
}

async function loadAdminDashboard() {
  const payload = await api("/api/dashboard/admin");
  state.services = payload.services;
  document.getElementById("adminStats").innerHTML = [
    statCard("Open Queues", payload.open_services, "Across campus services"),
    statCard("Total Waiting", payload.total_waiting, "Current in-memory count"),
    statCard("Longest Wait", `${payload.longest_wait} min`, "Queue length × service duration"),
  ].join("");
  document.getElementById("adminServiceTable").innerHTML = `<table><thead><tr><th>Service</th><th>Queue Length</th><th>Expected Duration</th><th>Priority</th></tr></thead><tbody>${payload.services.map(service => `<tr><td>${escapeHtml(service.name)}</td><td>${service.queue_length}</td><td>${service.expected_duration} min</td><td><span class="badge ${service.priority_level}">${service.priority_level}</span></td></tr>`).join("")}</tbody></table>`;
}

async function loadServiceManagement() {
  const services = await loadServices();
  document.getElementById("serviceCards").innerHTML = services.map(service => serviceItem(service, true)).join("");
  document.querySelectorAll("[data-edit-service]").forEach(button => button.addEventListener("click", () => editService(Number(button.dataset.editService))));
}

function editService(serviceId) {
  const service = state.services.find(item => item.id === serviceId);
  if (!service) return;
  document.getElementById("editingServiceId").value = service.id;
  document.getElementById("serviceName").value = service.name;
  document.getElementById("serviceDescription").value = service.description;
  document.getElementById("serviceDuration").value = service.expected_duration;
  document.getElementById("servicePriority").value = service.priority_level;
  document.getElementById("serviceFormTitle").textContent = "Update Service";
  document.getElementById("cancelEditButton").classList.remove("hidden");
}

function resetServiceForm() {
  document.getElementById("serviceForm").reset();
  document.getElementById("editingServiceId").value = "";
  document.getElementById("serviceFormTitle").textContent = "Create Service";
  document.getElementById("cancelEditButton").classList.add("hidden");
}

async function prepareQueueManagement() {
  const services = await loadServices();
  const select = document.getElementById("adminQueueService");
  const current = select.value;
  select.innerHTML = services.map(service => `<option value="${service.id}">${escapeHtml(service.name)}</option>`).join("");
  if (current && services.some(service => String(service.id) === current)) select.value = current;
  await loadAdminQueue();
}

async function loadAdminQueue() {
  const serviceId = Number(document.getElementById("adminQueueService").value);
  const container = document.getElementById("adminQueueTable");
  if (!serviceId) { container.innerHTML = `<div class="empty-state">No service selected.</div>`; return; }
  const payload = await api(`/api/admin/queues/${serviceId}`);
  if (!payload.queue.length) { container.innerHTML = `<div class="empty-state">No users are waiting in this queue.</div>`; return; }
  container.innerHTML = `<table><thead><tr><th>Position</th><th>User</th><th>Reason</th><th>Priority</th><th>Estimated Wait</th></tr></thead><tbody>${payload.queue.map(item => `<tr><td>#${item.position}</td><td>${escapeHtml(item.user_name)}</td><td>${escapeHtml(item.reason)}</td><td><span class="badge ${item.priority}">${item.priority}</span></td><td>${item.estimated_wait} min</td></tr>`).join("")}</tbody></table>`;
}

// Navigation and drawer
document.getElementById("menuButton").addEventListener("click", () => {
  const open = drawer.classList.toggle("open");
  backdrop.classList.toggle("hidden", !open);
  document.getElementById("menuButton").setAttribute("aria-expanded", String(open));
});
backdrop.addEventListener("click", closeDrawer);
document.querySelectorAll("[data-screen]").forEach(element => element.addEventListener("click", () => showScreen(element.dataset.screen)));
document.getElementById("logoutButton").addEventListener("click", () => { clearSession(); showScreen("login"); showMessage("You have been logged out."); });

// Authentication
document.getElementById("loginForm").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const payload = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email: loginEmail.value, password: loginPassword.value, role: loginRole.value }) });
    saveSession(payload.token, payload.user);
    showMessage(payload.message);
    showScreen(payload.user.role === "administrator" ? "admin-dashboard" : "user-dashboard");
  } catch (error) { showMessage(error.message, true); }
});

document.getElementById("registerForm").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const payload = await api("/api/auth/register", { method: "POST", body: JSON.stringify({ full_name: registerName.value, email: registerEmail.value, password: registerPassword.value, role: registerRole.value }) });
    saveSession(payload.token, payload.user);
    showMessage(payload.message);
    showScreen(payload.user.role === "administrator" ? "admin-dashboard" : "user-dashboard");
  } catch (error) { showMessage(error.message, true); }
});

// Queue actions
document.getElementById("joinService").addEventListener("change", updateEstimate);
document.getElementById("joinQueueForm").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const payload = await api("/api/queues/join", { method: "POST", body: JSON.stringify({ service_id: Number(joinService.value), reason: joinReason.value }) });
    state.activeQueue = payload.queue_entry;
    showMessage(`${payload.message}. Position ${payload.queue_entry.position}.`);
    showScreen("queue-status");
  } catch (error) { showMessage(error.message, true); }
});
document.getElementById("leaveQueueButton").addEventListener("click", async () => {
  try {
    const status = await api("/api/queues/status");
    if (!status.queue_status) throw new Error("You do not have an active queue entry.");
    await api(`/api/queues/${status.queue_status.service_id}/leave`, { method: "DELETE" });
    state.activeQueue = null;
    showMessage("You left the queue. The result was added to history.");
    showScreen("history");
  } catch (error) { showMessage(error.message, true); }
});
document.getElementById("refreshStatusButton").addEventListener("click", loadQueueStatus);

// Service management
document.getElementById("serviceForm").addEventListener("submit", async event => {
  event.preventDefault();
  const id = Number(document.getElementById("editingServiceId").value);
  const body = { name: serviceName.value, description: serviceDescription.value, expected_duration: Number(serviceDuration.value), priority_level: servicePriority.value };
  try {
    const payload = await api(id ? `/api/services/${id}` : "/api/services", { method: id ? "PUT" : "POST", body: JSON.stringify(body) });
    showMessage(payload.message);
    resetServiceForm();
    await loadServiceManagement();
  } catch (error) { showMessage(error.message, true); }
});
document.getElementById("cancelEditButton").addEventListener("click", resetServiceForm);

// Admin queue actions
document.getElementById("adminQueueService").addEventListener("change", loadAdminQueue);
document.getElementById("serveNextButton").addEventListener("click", async () => {
  const serviceId = Number(document.getElementById("adminQueueService").value);
  try {
    const payload = await api(`/api/admin/queues/${serviceId}/serve-next`, { method: "POST" });
    showMessage(`${payload.served_user} was marked as served.`);
    await loadAdminQueue();
  } catch (error) { showMessage(error.message, true); }
});

updateSessionUI();
showScreen(location.hash.slice(1) || (state.user?.role === "administrator" ? "admin-dashboard" : state.user ? "user-dashboard" : "login"));
