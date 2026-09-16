const userId = Number(localStorage.getItem('user_id') || 0);
const token = localStorage.getItem('token') || '';
const username = localStorage.getItem('username') || 'demo';
const role = localStorage.getItem('role') || 'user';

if (!userId || !token) {
  window.location.href = '/login';
}

document.getElementById('profile-username').textContent = username;
document.getElementById('profile-role').textContent = role === 'admin' ? 'Quản trị viên' : 'Tài khoản người dùng';
document.getElementById('profile-avatar').textContent = username.charAt(0).toUpperCase();
document.getElementById('sidebar-user-name')?.replaceChildren(document.createTextNode(username));
document.getElementById('sidebar-avatar')?.replaceChildren(document.createTextNode(username.charAt(0).toUpperCase()));

const buildHeaders = (options = {}) => {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  return { ...options, headers };
};

const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character]));

const showToast = (message, type = 'success') => {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<i data-lucide="${type === 'error' ? 'circle-alert' : 'circle-check'}"></i><span>${escapeHtml(message)}</span>`;
  document.getElementById('toast-region').appendChild(toast);
  window.lucide?.createIcons();
  setTimeout(() => toast.remove(), 3600);
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, buildHeaders(options));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Đã xảy ra lỗi');
  return data;
}

function applyTheme(theme) {
  document.body.classList.remove('dark-mode', 'theme-violet', 'theme-orange', 'theme-green', 'theme-high-contrast');
  if (theme === 'dark') document.body.classList.add('dark-mode');
  if (theme && theme !== 'blue' && theme !== 'dark') document.body.classList.add(`theme-${theme}`);
  localStorage.setItem('theme', theme || 'blue');
  document.querySelectorAll('.theme-choice').forEach((button) => button.classList.toggle('selected', button.dataset.theme === theme));
}

function downloadBlob(blob, filename) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function downloadFile(url, filename) {
  const response = await fetch(url, buildHeaders());
  if (!response.ok) throw new Error('Không thể xuất dữ liệu.');
  downloadBlob(await response.blob(), filename);
}

async function loadSettings() {
  try {
    const settings = await fetchJson(`/api/settings?user_id=${userId}`);
    document.getElementById('default-currency').value = settings.default_currency || 'VND';
    applyTheme(localStorage.getItem('theme') || settings.theme || 'blue');
    const monthlyBudget = document.getElementById('monthly-budget');
    if (monthlyBudget) monthlyBudget.value = Number(localStorage.getItem(`budget_${userId}`) || 0);
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function loadCategoryBudgets() {
  const list = document.getElementById('category-budget-list');
  if (!list) return;
  try {
    const budgets = await fetchJson(`/api/category-budgets?user_id=${userId}`);
    list.innerHTML = budgets.length
      ? budgets.map((item) => `<li><span>${escapeHtml(item.category)}</span><strong>${new Intl.NumberFormat('vi-VN', { style: 'currency', currency: item.currency || 'VND' }).format(Number(item.budget_amount || 0))}</strong><small>${escapeHtml(item.currency || 'VND')}</small></li>`).join('')
      : '<li class="muted-copy">Chưa có ngân sách danh mục.</li>';
  } catch (error) {
    list.innerHTML = '<li class="muted-copy">Không tải được ngân sách danh mục.</li>';
  }
}

document.getElementById('sidebar-toggle')?.addEventListener('click', () => document.getElementById('sidebar').classList.toggle('is-open'));
document.querySelectorAll('.theme-choice').forEach((button) => button.addEventListener('click', () => applyTheme(button.dataset.theme)));
document.getElementById('save-settings').addEventListener('click', async () => {
  try {
    await fetchJson('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, default_currency: document.getElementById('default-currency').value, theme: localStorage.getItem('theme') || 'blue' }) });
    showToast('Đã lưu cài đặt hiển thị.');
  } catch (error) { showToast(error.message, 'error'); }
});

document.getElementById('save-monthly-budget')?.addEventListener('click', () => {
  const value = Number(document.getElementById('monthly-budget')?.value || 0);
  localStorage.setItem(`budget_${userId}`, String(value));
  showToast('Đã lưu ngân sách tháng.');
});

document.getElementById('save-category-budget')?.addEventListener('click', async () => {
  const category = document.getElementById('budget-category')?.value.trim();
  const amount = Number(document.getElementById('budget-amount')?.value || 0);
  const currency = document.getElementById('budget-currency')?.value || 'VND';
  if (!category || amount <= 0) {
    showToast('Vui lòng nhập danh mục và số tiền hợp lệ.', 'error');
    return;
  }
  try {
    await fetchJson('/api/category-budgets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, category, budget_amount: amount, currency }) });
    document.getElementById('budget-category').value = '';
    document.getElementById('budget-amount').value = '';
    await loadCategoryBudgets();
    showToast('Đã lưu ngân sách danh mục.');
  } catch (error) { showToast(error.message, 'error'); }
});

document.getElementById('change-password-btn').addEventListener('click', () => {
  const form = document.getElementById('password-form');
  form.hidden = !form.hidden;
});
document.getElementById('password-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const newPassword = document.getElementById('new-password').value;
  const confirmation = document.getElementById('confirm-password').value;
  if (newPassword !== confirmation) {
    showToast('Mật khẩu xác nhận không khớp.', 'error');
    return;
  }
  fetchJson('/api/auth/change-password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ current_password: document.getElementById('current-password').value, new_password: newPassword }) })
    .then(() => { showToast('Đổi mật khẩu thành công.'); event.target.reset(); event.target.hidden = true; })
    .catch((error) => showToast(error.message, 'error'));
});

document.getElementById('logout-btn').addEventListener('click', () => {
  localStorage.removeItem('user_id');
  localStorage.removeItem('username');
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  window.location.href = '/login';
});

document.getElementById('export-json-btn').addEventListener('click', async () => {
  try { await downloadFile(`/api/export/json?user_id=${userId}`, 'finance-data.json'); showToast('Đã xuất JSON.'); } catch (error) { showToast(error.message, 'error'); }
});
document.getElementById('export-csv-btn').addEventListener('click', async () => {
  try { await downloadFile(`/api/export/csv?user_id=${userId}`, 'expenses.csv'); showToast('Đã xuất CSV.'); } catch (error) { showToast(error.message, 'error'); }
});
document.getElementById('export-pdf-btn').addEventListener('click', async () => {
  try { await downloadFile(`/api/export/pdf?user_id=${userId}`, 'finance-report.pdf'); showToast('Đã xuất PDF.'); } catch (error) { showToast(error.message, 'error'); }
});
document.getElementById('backup-btn').addEventListener('click', async () => {
  try {
    const response = await fetchJson('/api/backup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId }) });
    showToast(response.message || 'Đã sao lưu dữ liệu.');
  } catch (error) { showToast(error.message, 'error'); }
});
document.getElementById('import-input').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    await fetchJson('/api/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, expenses: parsed.expenses || parsed.items || [] }) });
    showToast('Đã nhập dữ liệu JSON.');
  } catch (error) { showToast(error.message, 'error'); }
  event.target.value = '';
});

applyTheme(localStorage.getItem('theme') || 'blue');
loadSettings();
loadCategoryBudgets();
window.lucide?.createIcons();
