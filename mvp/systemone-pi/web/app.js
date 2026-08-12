const roomsEl = document.querySelector('#rooms');
const bridgeStatusEl = document.querySelector('#bridgeStatus');
const toastEl = document.querySelector('#toast');

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json();
  if (!response.ok || !payload.success) {
    const error = new Error(payload?.error?.message || 'Unbekannter Fehler');
    error.code = payload?.error?.code;
    throw error;
  }
  return payload.data;
}

function toast(message) {
  toastEl.textContent = message;
  toastEl.classList.add('show');
  window.clearTimeout(toast._timer);
  toast._timer = window.setTimeout(() => toastEl.classList.remove('show'), 2600);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
}

function renderRooms(state) {
  roomsEl.innerHTML = state.rooms.map(room => {
    const devices = state.devices.filter(device => device.roomId === room.id);
    const deviceHtml = devices.length ? devices.map(device => `
      <div class="device ${device.online ? '' : 'offline'}" data-device-id="${escapeHtml(device.id)}">
        <div>
          <div class="device-name">${escapeHtml(device.name)}</div>
          <div class="device-meta">Philips Hue · ${device.online ? `${device.brightness}% Helligkeit` : 'nicht erreichbar'}</div>
        </div>
        <div class="controls">
          <span class="badge ${device.online ? '' : 'error'}">${device.online ? 'online' : 'offline'}</span>
          <input class="brightness" type="range" min="1" max="100" value="${device.brightness}" ${device.online ? '' : 'disabled'} aria-label="Helligkeit ${escapeHtml(device.name)}" />
          <button class="switch ${device.on ? 'on' : ''}" ${device.online ? '' : 'disabled'} aria-label="${device.on ? 'Ausschalten' : 'Einschalten'}"></button>
        </div>
      </div>
    `).join('') : '<p class="muted">Noch keine Geräte in diesem Raum.</p>';

    return `<article class="room-card"><div class="room-top"><div><p class="eyebrow">RAUM</p><h3>${escapeHtml(room.name)}</h3></div><span class="badge">${devices.length} Geräte</span></div><div class="device-list">${deviceHtml}</div></article>`;
  }).join('');

  document.querySelectorAll('.device').forEach(deviceEl => {
    const id = deviceEl.dataset.deviceId;
    const switchEl = deviceEl.querySelector('.switch');
    const rangeEl = deviceEl.querySelector('.brightness');

    switchEl?.addEventListener('click', async () => {
      const desired = !switchEl.classList.contains('on');
      try {
        await api(`/api/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ on: desired }) });
        await refresh();
        toast(desired ? 'Lampe eingeschaltet' : 'Lampe ausgeschaltet');
      } catch (error) { toast(error.message); }
    });

    rangeEl?.addEventListener('change', async event => {
      try {
        await api(`/api/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ brightness: Number(event.target.value) }) });
        await refresh();
        toast(`Helligkeit auf ${event.target.value}% gesetzt`);
      } catch (error) { toast(error.message); }
    });
  });
}

async function refresh() {
  const state = await api('/api/state');
  renderRooms(state);
  const hue = state.integrations.hue;
  bridgeStatusEl.textContent = hue.paired ? `${hue.bridge.name} verbunden` : hue.discovered ? `${hue.bridge.name} gefunden` : 'Keine Bridge gefunden';
  document.querySelector('#pairHue').textContent = hue.paired ? 'Hue verbunden' : 'Hue verbinden';
  document.querySelector('#pairHue').disabled = hue.paired;
  document.querySelector('#pairAdmin').textContent = state.onboarding.adminPaired ? 'Admin gekoppelt' : 'Admin koppeln';
  document.querySelector('#pairAdmin').disabled = state.onboarding.adminPaired;
}

document.querySelector('#pairAdmin').addEventListener('click', async () => {
  try {
    await api('/api/onboarding/pair-admin', { method: 'POST', body: '{}' });
    toast('Administratorgerät lokal gekoppelt');
    await refresh();
  } catch (error) { toast(error.message); }
});

document.querySelector('#pairHue').addEventListener('click', async () => {
  try {
    await api('/api/integrations/hue/pair', { method: 'POST', body: '{}' });
    toast('Hue Bridge gekoppelt');
    await refresh();
  } catch (error) { toast(error.message); }
});

document.querySelector('#refresh').addEventListener('click', async () => {
  try { await refresh(); toast('Zustände aktualisiert'); } catch (error) { toast(error.message); }
});

refresh().catch(error => toast(error.message));
