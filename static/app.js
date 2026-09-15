const userId = Number(localStorage.getItem('user_id') || 0);
const username = localStorage.getItem('username') || 'demo';
const token = localStorage.getItem('token') || '';
const role = localStorage.getItem('role') || 'user';
const form = document.getElementById('expense-form');
const expenseList = document.getElementById('expense-list');
const totalExpense = document.getElementById('total-expense');
const currentMonthTotal = document.getElementById('current-month-total');
const formStatus = document.getElementById('form-status');
const refreshBtn = document.getElementById('refresh-btn');
const logoutBtn = document.getElementById('logout-btn');
const submitBtn = document.getElementById('submit-btn');
const cancelEditBtn = document.getElementById('cancel-edit');
const expenseIdInput = document.getElementById('expense-id');
const welcomeLabel = document.getElementById('welcome-user');
const filters = ['filter-keyword', 'filter-category', 'filter-start', 'filter-end'];
const filterParams = {
  'filter-keyword': 'keyword',
  'filter-category': 'category',
  'filter-start': 'start_date',
  'filter-end': 'end_date',
};

if (welcomeLabel) {
  welcomeLabel.textContent = `Xin chào, ${username}`;
}

if (form && !userId) {
  window.location.href = '/login';
}

const buildHeaders = (options = {}) => {
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return { ...options, headers };
};

const formatCurrency = (value) => {
  const amount = Number(value || 0);
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
  }).format(amount);
};

const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character]));

const setStatus = (message, isError = false) => {
  formStatus.textContent = message;
  formStatus.classList.toggle('error', isError);
};

const resetFormState = () => {
  form.reset();
  expenseIdInput.value = '';
  submitBtn.textContent = 'Lưu chi tiêu';
  cancelEditBtn.hidden = true;
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, buildHeaders(options));
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || 'Đã xảy ra lỗi');
  }

  return data;
}

async function loadSummary() {
  const summary = await fetchJson(`/api/summary?user_id=${userId}`);
  totalExpense.textContent = formatCurrency(summary.total_expense);
  currentMonthTotal.textContent = formatCurrency(summary.current_month_total);
}

async function loadReport() {
  const report = await fetchJson(`/api/summary/report?user_id=${userId}`);
  document.getElementById('transaction-count').textContent = report.transaction_count;
  document.getElementById('top-category').textContent = report.top_category;
  document.getElementById('average-expense').textContent = formatCurrency(report.average_amount);
  document.getElementById('largest-expense').textContent = formatCurrency(report.largest_amount);
  document.getElementById('top-category-total').textContent = formatCurrency(report.top_category_amount);
}

async function renderChart() {
  const stats = await fetchJson(`/api/summary/categories?user_id=${userId}`);
  const canvas = document.getElementById('category-chart');
  if (!canvas) return;

  const labels = stats.map((item) => item.label);
  const values = stats.map((item) => Number(item.value || 0));

  if (window.categoryChartInstance) {
    window.categoryChartInstance.destroy();
  }

  window.categoryChartInstance = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: ['#2563eb', '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#10b981'],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { usePointStyle: true, padding: 20 }
        }
      }
    }
  });

  const [months, years] = await Promise.all([
    fetchJson(`/api/summary/months?user_id=${userId}`),
    fetchJson(`/api/summary/years?user_id=${userId}`),
  ]);
  renderBarChart('monthly-chart', 'monthlyChartInstance', months);
  renderBarChart('yearly-chart', 'yearlyChartInstance', years);
}

function renderBarChart(canvasId, instanceName, stats) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (window[instanceName]) window[instanceName].destroy();
  window[instanceName] = new Chart(canvas, {
    type: 'bar',
    data: { labels: stats.map((item) => item.label), datasets: [{ data: stats.map((item) => item.value), backgroundColor: '#14b8a6', borderRadius: 8 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
  });
}

async function loadExpenses() {
  const params = new URLSearchParams({ user_id: String(userId) });
  filters.forEach((id) => { const value = document.getElementById(id)?.value.trim(); if (value) params.set(filterParams[id], value); });
  const items = await fetchJson(`/api/expenses?${params}`);

  if (!items.length) {
    expenseList.innerHTML = '<tr><td colspan="5" class="empty">Chưa có chi tiêu nào.</td></tr>';
    return;
  }

  expenseList.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${item.expense_date}</td>
          <td>${escapeHtml(item.category)}</td>
          <td>${escapeHtml(item.description)}</td>
          <td class="money">${formatCurrency(item.amount)}</td>
          <td class="actions-cell">
            <button class="table-btn edit-btn" data-id="${item.id}">Sửa</button>
            <button class="table-btn delete-btn danger" data-id="${item.id}">Xoá</button>
          </td>
        </tr>
      `
    )
    .join('');
}

async function refreshDashboard() {
  try {
    await Promise.all([loadSummary(), loadReport(), loadExpenses(), renderChart()]);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function importJson(file) {
  const parsed = JSON.parse(await file.text());
  const items = Array.isArray(parsed) ? parsed : parsed.items;
  await fetchJson('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, items }) });
  await refreshDashboard();
  setStatus('Import dữ liệu thành công!');
}

async function loadUsers() {
  if (role !== 'admin') return;
  const users = await fetchJson('/api/admin/users');
  document.getElementById('user-list').innerHTML = users.map((user) => `<tr><td>${user.id}</td><td>${user.username}</td><td>${user.role}</td><td><button class="table-btn edit-btn role-btn" data-id="${user.id}" data-role="${user.role === 'admin' ? 'user' : 'admin'}">Đổi vai trò</button></td></tr>`).join('');
}

const setAiStatus = (message, isError = false) => {
  const status = document.getElementById('ai-status');
  if (!status) return;
  status.textContent = message;
  status.classList.toggle('error', isError);
};

async function loadReviews() {
  const reviews = await fetchJson('/api/ai/reviews');
  const container = document.getElementById('review-list');
  if (!reviews.length) {
    container.innerHTML = '<p class="empty">Chưa có ảnh chờ duyệt.</p>';
    return;
  }
  container.innerHTML = reviews.slice().reverse().map((review) => {
    const suggestion = review.suggestion || {};
    const editable = review.status === 'pending' ? `<div class="review-fields"><input data-field="amount" type="number" min="0.01" step="0.01" value="${escapeHtml(suggestion.amount || '')}" placeholder="Số tiền"><input data-field="category" value="${escapeHtml(suggestion.category || '')}" placeholder="Danh mục"><input data-field="description" value="${escapeHtml(suggestion.description || '')}" placeholder="Mô tả"><input data-field="expense_date" type="date" value="${escapeHtml(suggestion.expense_date || '')}"></div>` : '';
    const actions = review.status === 'pending' ? `<label class="table-btn secondary">Đổi ảnh<input class="replace-image" data-id="${escapeHtml(review.id)}" type="file" accept="image/jpeg,image/png,image/webp" hidden></label><button class="table-btn secondary review-save" data-id="${escapeHtml(review.id)}">Lưu sửa</button><button class="table-btn edit-btn review-action" data-id="${escapeHtml(review.id)}" data-status="approved">Duyệt và thêm</button><button class="table-btn delete-btn review-action" data-id="${escapeHtml(review.id)}" data-status="rejected">Loại bỏ</button>` : `<span class="review-status">${escapeHtml(review.status)}</span>`;
    return `<article class="review-item"><div class="review-main"><div class="review-heading"><img src="/api/ai/reviews/${escapeHtml(review.id)}/image?v=${encodeURIComponent(review.created_at || '')}" alt="Hóa đơn"><div><strong>${escapeHtml(review.filename)}</strong><p>${escapeHtml(review.message || '')}</p><small>Độ tin cậy: ${suggestion.confidence ? `${Math.round(Number(suggestion.confidence) * 100)}%` : 'chưa xác định'}</small></div></div>${editable}</div><div class="review-actions">${actions}</div></article>`;
  }).join('');
}

document.getElementById('receipt-input')?.addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const body = new FormData();
  body.append('image', file);
  try {
    setAiStatus('Đang phân tích và lưu ảnh vào hàng chờ...');
    await fetchJson('/api/ai/analyze-image', { method: 'POST', body });
    setAiStatus('Đã lưu đề xuất. Hãy kiểm tra trước khi duyệt.');
    await loadReviews();
  } catch (error) { setAiStatus(error.message, true); }
  event.target.value = '';
});

document.getElementById('refresh-reviews')?.addEventListener('click', loadReviews);
document.getElementById('review-list')?.addEventListener('change', async (event) => {
  const input = event.target.closest('.replace-image');
  if (!input || !input.files[0]) return;
  const body = new FormData();
  body.append('image', input.files[0]);
  try {
    setAiStatus('Đang cập nhật và xác thực ảnh mới...');
    await fetchJson(`/api/ai/reviews/${input.dataset.id}/image`, { method: 'PUT', body });
    setAiStatus('Đã cập nhật ảnh và phân tích lại. Hãy kiểm tra đề xuất.');
    await loadReviews();
  } catch (error) { setAiStatus(error.message, true); }
  input.value = '';
});
document.getElementById('review-list')?.addEventListener('click', async (event) => {
  const saveButton = event.target.closest('.review-save');
  if (saveButton) {
    const item = saveButton.closest('.review-item');
    const suggestion = {};
    item.querySelectorAll('[data-field]').forEach((field) => { suggestion[field.dataset.field] = field.value; });
    try {
      await fetchJson(`/api/ai/reviews/${saveButton.dataset.id}/suggestion`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ suggestion }) });
      setAiStatus('Đã lưu chỉnh sửa đề xuất.');
    } catch (error) { setAiStatus(error.message, true); }
    return;
  }
  const button = event.target.closest('.review-action');
  if (!button) return;
  try {
    await fetchJson(`/api/ai/reviews/${button.dataset.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: button.dataset.status }) });
    setAiStatus(button.dataset.status === 'approved' ? 'Đã thêm giao dịch sau khi duyệt.' : 'Đã loại bỏ đề xuất.');
    await Promise.all([loadReviews(), refreshDashboard()]);
  } catch (error) { setAiStatus(error.message, true); }
});

document.getElementById('llm-btn')?.addEventListener('click', async () => {
  const prompt = document.getElementById('llm-prompt').value.trim();
  if (!prompt) return;
  try {
    const result = await fetchJson('/api/ai/llm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }) });
    document.getElementById('llm-result').textContent = result.text || result.message;
  } catch (error) { document.getElementById('llm-result').textContent = error.message; }
});

async function populateFormForEdit(expenseId) {
  try {
    const item = await fetchJson(`/api/expenses/${expenseId}?user_id=${userId}`);
    Object.entries({
      amount: item.amount,
      category: item.category,
      description: item.description,
      expense_date: item.expense_date,
      id: item.id,
    }).forEach(([key, value]) => {
      const input = form.elements.namedItem(key);
      if (input) {
        input.value = value;
      }
    });

    submitBtn.textContent = 'Cập nhật chi tiêu';
    cancelEditBtn.hidden = false;
    setStatus('Đang chỉnh sửa khoản chi tiêu.', false);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function deleteExpense(expenseId) {
  const confirmed = window.confirm('Bạn có chắc muốn xoá khoản chi tiêu này?');
  if (!confirmed) {
    return;
  }

  try {
    await fetchJson(`/api/expenses/${expenseId}?user_id=${userId}`, {
      method: 'DELETE',
    });

    setStatus('Xoá chi tiêu thành công!');
    resetFormState();
    await refreshDashboard();
  } catch (error) {
    setStatus(error.message, true);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  const expenseId = payload.id;
  const requestOptions = {
    method: expenseId ? 'PUT' : 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ...payload,
      user_id: userId,
    }),
  };

  try {
    setStatus('Đang lưu...', false);

    const url = expenseId ? `/api/expenses/${expenseId}?user_id=${userId}` : '/api/expenses';
    await fetchJson(url, requestOptions);

    resetFormState();
    setStatus(expenseId ? 'Cập nhật chi tiêu thành công!' : 'Thêm chi tiêu thành công!');
    await refreshDashboard();
  } catch (error) {
    setStatus(error.message, true);
  }
});

expenseList.addEventListener('click', async (event) => {
  const button = event.target.closest('button');
  if (!button) {
    return;
  }

  const { id } = button.dataset;
  if (!id) {
    return;
  }

  if (button.classList.contains('edit-btn')) {
    await populateFormForEdit(Number(id));
  }

  if (button.classList.contains('delete-btn')) {
    await deleteExpense(Number(id));
  }
});

cancelEditBtn?.addEventListener('click', () => {
  resetFormState();
  setStatus('Đã huỷ chỉnh sửa.', false);
});

refreshBtn?.addEventListener('click', refreshDashboard);
logoutBtn?.addEventListener('click', () => {
  localStorage.removeItem('user_id');
  localStorage.removeItem('username');
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  window.location.href = '/login';
});

if (form) {
  resetFormState();
  refreshDashboard();
  document.body.classList.toggle('dark-mode', localStorage.getItem('theme') === 'dark');
  document.getElementById('admin-panel').hidden = role !== 'admin';
  loadUsers();
  loadReviews();
}

document.getElementById('report-btn')?.addEventListener('click', () => document.getElementById('report-panel')?.scrollIntoView({ behavior: 'smooth' }));
document.getElementById('today-filter')?.addEventListener('click', () => {
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('filter-start').value = today;
  document.getElementById('filter-end').value = today;
  loadExpenses();
});

document.getElementById('theme-btn')?.addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');
  localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
});
document.getElementById('export-btn')?.addEventListener('click', async () => {
  const response = await fetch(`/api/export/csv?user_id=${userId}`, buildHeaders());
  const blob = await response.blob();
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'expenses.csv'; link.click(); URL.revokeObjectURL(link.href);
});
document.getElementById('import-input')?.addEventListener('change', async (event) => { try { await importJson(event.target.files[0]); } catch (error) { setStatus(error.message, true); } });
filters.forEach((id) => document.getElementById(id)?.addEventListener('input', loadExpenses));
document.getElementById('clear-filters')?.addEventListener('click', () => { filters.forEach((id) => { document.getElementById(id).value = ''; }); loadExpenses(); });
document.getElementById('refresh-users')?.addEventListener('click', loadUsers);
document.getElementById('user-list')?.addEventListener('click', async (event) => { const button = event.target.closest('.role-btn'); if (!button) return; await fetchJson(`/api/admin/users/${button.dataset.id}/role`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role: button.dataset.role }) }); await loadUsers(); });
