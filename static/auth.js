const authForm = document.getElementById('auth-form');
const authStatus = document.getElementById('auth-status');
const body = document.body;
const mode = body.dataset.mode || 'login';

const setStatus = (message, isError = false) => {
  if (!authStatus) return;
  authStatus.textContent = message;
  authStatus.classList.toggle('error', isError);
};

async function callAuthApi(payload) {
  const response = await fetch(mode === 'login' ? '/api/auth/login' : '/api/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || 'Xử lý không thành công');
  }

  return data;
}

authForm?.addEventListener('submit', async (event) => {
  event.preventDefault();

  const formData = new FormData(authForm);
  const payload = Object.fromEntries(formData.entries());

  try {
    setStatus('Đang xử lý...', false);
    const result = await callAuthApi(payload);
    setStatus(mode === 'login' ? 'Đăng nhập thành công!' : 'Đăng ký thành công!');

    if (result.user_id) {
      localStorage.setItem('user_id', String(result.user_id));
      localStorage.setItem('username', result.username || payload.username);
      localStorage.setItem('token', result.token || '');
      localStorage.setItem('role', result.role || 'user');
      window.location.href = '/';
    }
  } catch (error) {
    setStatus(error.message, true);
  }
});
