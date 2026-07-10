const screens = document.querySelectorAll('.screen');
const navButtons = document.querySelectorAll('[data-screen]');
const sideMenu = document.getElementById('sideMenu');
const menuToggle = document.getElementById('menuToggle');
const closeMenu = document.getElementById('closeMenu');
const menuBackdrop = document.getElementById('menuBackdrop');

function showScreen(screenId) {
  screens.forEach((screen) => screen.classList.toggle('active', screen.id === screenId));
  navButtons.forEach((button) => button.classList.toggle('active', button.dataset.screen === screenId));
  window.location.hash = screenId;
  closeSideMenu();
}

function openSideMenu() {
  sideMenu.classList.add('open');
  menuBackdrop.classList.add('show');
}

function closeSideMenu() {
  sideMenu.classList.remove('open');
  menuBackdrop.classList.remove('show');
}

navButtons.forEach((button) => {
  button.addEventListener('click', () => showScreen(button.dataset.screen));
});

menuToggle.addEventListener('click', openSideMenu);
closeMenu.addEventListener('click', closeSideMenu);
menuBackdrop.addEventListener('click', closeSideMenu);

const initialScreen = window.location.hash.replace('#', '') || 'login';
if (document.getElementById(initialScreen)) {
  showScreen(initialScreen);
}

function setError(id, message) {
  const errorElement = document.getElementById(id);
  if (errorElement) errorElement.textContent = message || '';
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

const loginForm = document.getElementById('loginForm');
loginForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const email = document.getElementById('loginEmail').value;
  const password = document.getElementById('loginPassword').value;
  let valid = true;

  if (!isValidEmail(email)) {
    setError('loginEmailError', 'Enter a valid email address.');
    valid = false;
  } else {
    setError('loginEmailError', '');
  }

  if (password.trim().length < 6) {
    setError('loginPasswordError', 'Password must be at least 6 characters.');
    valid = false;
  } else {
    setError('loginPasswordError', '');
  }

  if (valid) showScreen('user-dashboard');
});

const registerForm = document.getElementById('registerForm');
registerForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const fullName = document.getElementById('fullName').value.trim();
  const email = document.getElementById('registerEmail').value;
  const password = document.getElementById('registerPassword').value;
  const role = document.getElementById('roleSelect').value;
  let valid = true;

  if (!fullName) {
    setError('fullNameError', 'Full name is required.');
    valid = false;
  } else if (fullName.length > 60) {
    setError('fullNameError', 'Full name must be 60 characters or less.');
    valid = false;
  } else {
    setError('fullNameError', '');
  }

  if (!isValidEmail(email)) {
    setError('registerEmailError', 'Enter a valid email address.');
    valid = false;
  } else {
    setError('registerEmailError', '');
  }

  if (password.trim().length < 8) {
    setError('registerPasswordError', 'Password must be at least 8 characters.');
    valid = false;
  } else {
    setError('registerPasswordError', '');
  }

  if (!role) {
    setError('roleSelectError', 'Choose an account type.');
    valid = false;
  } else {
    setError('roleSelectError', '');
  }

  if (valid) showScreen(role === 'Administrator' ? 'admin-dashboard' : 'user-dashboard');
});

const serviceChoice = document.getElementById('serviceChoice');
const waitPreview = document.getElementById('waitPreview');
serviceChoice.addEventListener('change', () => {
  const selected = serviceChoice.selectedOptions[0];
  const wait = selected?.dataset?.wait;
  waitPreview.textContent = wait ? `${wait} minutes` : 'Select a service';
});

const joinQueueForm = document.getElementById('joinQueueForm');
joinQueueForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const service = serviceChoice.value;
  const reason = document.getElementById('visitReason').value.trim();
  let valid = true;

  if (!service) {
    setError('serviceChoiceError', 'Please select a service.');
    valid = false;
  } else {
    setError('serviceChoiceError', '');
  }

  if (!reason) {
    setError('visitReasonError', 'Reason for visit is required.');
    valid = false;
  } else if (reason.length > 90) {
    setError('visitReasonError', 'Reason must be 90 characters or less.');
    valid = false;
  } else {
    setError('visitReasonError', '');
  }

  if (valid) {
    document.getElementById('joinQueueMessage').textContent = `You joined the ${service} queue.`;
  }
});

document.getElementById('leaveQueueBtn').addEventListener('click', () => {
  document.getElementById('joinQueueMessage').textContent = 'You left the selected queue in this UI simulation.';
});

const serviceForm = document.getElementById('serviceForm');
serviceForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const serviceName = document.getElementById('serviceName').value.trim();
  const description = document.getElementById('serviceDescription').value.trim();
  const duration = Number(document.getElementById('expectedDuration').value);
  const priority = document.getElementById('priorityLevel').value;
  let valid = true;

  if (!serviceName) {
    setError('serviceNameError', 'Service name is required.');
    valid = false;
  } else if (serviceName.length > 100) {
    setError('serviceNameError', 'Service name must be 100 characters or less.');
    valid = false;
  } else {
    setError('serviceNameError', '');
  }

  if (!description) {
    setError('serviceDescriptionError', 'Description is required.');
    valid = false;
  } else {
    setError('serviceDescriptionError', '');
  }

  if (!duration || duration < 1 || duration > 180) {
    setError('expectedDurationError', 'Enter a duration from 1 to 180 minutes.');
    valid = false;
  } else {
    setError('expectedDurationError', '');
  }

  if (!priority) {
    setError('priorityLevelError', 'Choose a priority level.');
    valid = false;
  } else {
    setError('priorityLevelError', '');
  }

  if (valid) {
    document.getElementById('serviceMessage').textContent = `${serviceName} was saved in the mock UI.`;
  }
});

const serveNextBtn = document.getElementById('serveNextBtn');
serveNextBtn.addEventListener('click', () => {
  const firstRow = document.querySelector('#queueAdminList .queue-admin-row');
  if (firstRow) {
    const userName = firstRow.querySelector('strong').textContent;
    firstRow.remove();
    document.getElementById('serveMessage').textContent = `${userName} was marked as served in this UI simulation.`;
  } else {
    document.getElementById('serveMessage').textContent = 'There are no users left in this mock queue.';
  }
});
