
function showToast(msg, type='success', duration=4000) {
    const t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(100px)'; setTimeout(() => t.remove(), 400); }, duration);
}

function togglePassword(btn) {
    const input = btn.parentElement.querySelector('input');
    if (input.type === 'password') { input.type = 'text'; btn.textContent = '🙈'; }
    else { input.type = 'password'; btn.textContent = '👁'; }
}

function checkStrength(pw) {
    let s = 0;
    if (pw.length >= 8) s++;
    if (/[A-Z]/.test(pw)) s++;
    if (/[a-z]/.test(pw)) s++;
    if (/\d/.test(pw)) s++;
    if (/[!@#$%^&*(),.?":{}|<>]/.test(pw)) s++;
    const bar = document.getElementById('str-bar');
    const txt = document.getElementById('str-text');
    if (!bar) return;
    const colors = ['#EF4444','#EF4444','#F59E0B','#F59E0B','#10B981','#10B981'];
    const labels = ['','Very Weak','Weak','Medium','Strong','Very Strong'];
    bar.style.width = (s*20) + '%';
    bar.style.background = colors[s] || '#E2E8F0';
    if (txt) { txt.textContent = labels[s] || ''; txt.style.color = colors[s]; }
}

function setLoading(btn, loading) {
    if (loading) { btn.classList.add('loading'); btn.disabled = true; }
    else { btn.classList.remove('loading'); btn.disabled = false; }
}

async function submitForm(formId, url, successRedirect, successMsg) {
    const form = document.getElementById(formId);
    const btn = form.querySelector('button[type=submit]');
    const data = {};
    new FormData(form).forEach((v, k) => {
        if (k === 'remember_me') data[k] = true;
        else data[k] = v;
    });
    if (!data.remember_me) data.remember_me = false;
    setLoading(btn, true);
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data),
        });
        const result = await res.json();
        if (res.ok) {
            showToast(successMsg || result.message || 'Success!', 'success');
            if (successRedirect) setTimeout(() => window.location.href = successRedirect, 1000);
        } else {
            const d = result.detail || 'Something went wrong';
            if (Array.isArray(d)) d.forEach(e => showToast(e.msg || JSON.stringify(e), 'error'));
            else showToast(d, 'error');
        }
    } catch (err) {
        showToast('Network error. Please try again.', 'error');
    }
    setLoading(btn, false);
}

async function logout() {
    await fetch('/api/auth/logout', {method: 'POST'});
    window.location.href = '/login';
}
