const roomsEl = document.querySelector('#rooms');
const bridgeStatusEl = document.querySelector('#bridgeStatus');
const toastEl = document.querySelector('#toast');
let latestState = null;
let liveTimer = null;

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
  toast._timer = window.setTimeout(() => toastEl.classList.remove('show'), 3000);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
}

function renderRooms(state) {
  const unassigned = state.devices.filter(device => !state.rooms.some(room => room.id === device.roomId));
  const visibleRooms = [...state.rooms, ...(unassigned.length ? [{ id: '__unassigned', name: 'Nicht zugeordnet' }] : [])];

  roomsEl.innerHTML = visibleRooms.map(room => {
    const devices = room.id === '__unassigned'
      ? unassigned
      : state.devices.filter(device => device.roomId === room.id);

    const deviceHtml = devices.length ? devices.map(device => {
      const roomOptions = state.rooms.map(option => `<option value="${escapeHtml(option.id)}" ${option.id === device.roomId ? 'selected' : ''}>${escapeHtml(option.name)}</option>`).join('');
      return `
      <div class="device ${device.online ? '' : 'offline'}" data-device-id="${escapeHtml(device.id)}">
        <div class="device-main">
          <div class="device-heading">
            <div class="device-name">${escapeHtml(device.name)}</div>
            <span class="badge ${device.online ? '' : 'error'}">${device.online ? 'online' : 'offline'}</span>
          </div>
          <div class="device-meta">Philips Hue · ${device.online ? `${device.brightness}% Helligkeit` : 'nicht erreichbar'}</div>
          <div class="device-edit">
            <input class="name-input" maxlength="60" value="${escapeHtml(device.name)}" aria-label="Gerätename" />
            <select class="room-select" aria-label="Raum zuweisen">
              <option value="">Raum wählen</option>${roomOptions}
            </select>
            <button class="save-device secondary">Speichern</button>
          </div>
        </div>
        <div class="controls">
          <input class="brightness" type="range" min="1" max="100" value="${device.brightness}" ${device.online ? '' : 'disabled'} aria-label="Helligkeit ${escapeHtml(device.name)}" />
          <button class="switch ${device.on ? 'on' : ''}" ${device.online ? '' : 'disabled'} aria-label="${device.on ? 'Ausschalten' : 'Einschalten'}"></button>
        </div>
      </div>`;
    }).join('') : '<p class="muted">Noch keine Geräte in diesem Raum.</p>';

    return `<article class="room-card"><div class="room-top"><div><p class="eyebrow">RAUM</p><h3>${escapeHtml(room.name)}</h3></div><span class="badge">${devices.length} Geräte</span></div><div class="device-list">${deviceHtml}</div></article>`;
  }).join('');

  document.querySelectorAll('.device').forEach(deviceEl => {
    const id = deviceEl.dataset.deviceId;
    const switchEl = deviceEl.querySelector('.switch');
    const rangeEl = deviceEl.querySelector('.brightness');
    const saveEl = deviceEl.querySelector('.save-device');
    const nameEl = deviceEl.querySelector('.name-input');
    const roomEl = deviceEl.querySelector('.room-select');

    switchEl?.addEventListener('click', async () => {
      const desired = !switchEl.classList.contains('on');
      try {
        await api(`/api/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ on: desired }) });
        await refresh(false);
        toast(desired ? 'Lampe eingeschaltet' : 'Lampe ausgeschaltet');
      } catch (error) { toast(error.message); }
    });

    rangeEl?.addEventListener('change', async event => {
      try {
        await api(`/api/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ brightness: Number(event.target.value) }) });
        await refresh(false);
        toast(`Helligkeit auf ${event.target.value}% gesetzt`);
      } catch (error) { toast(error.message); }
    });

    saveEl?.addEventListener('click', async () => {
      const patch = { name: nameEl.value.trim() };
      if (roomEl.value) patch.roomId = roomEl.value;
      try {
        await api(`/api/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(patch) });
        await refresh(false);
        toast('Gerät lokal gespeichert');
      } catch (error) { toast(error.message); }
    });
  });
}

function renderHeader(state) {
  const hue = state.integrations.hue;
  if (hue.paired) {
    bridgeStatusEl.textContent = hue.syncError ? `${hue.bridge?.name || 'Hue'} · Syncfehler` : `${hue.bridge?.name || 'Hue'} verbunden`;
  } else if (hue.discovered) {
    bridgeStatusEl.textContent = `${hue.bridge?.name || 'Hue Bridge'} gefunden`;
  } else {
    bridgeStatusEl.textContent = 'Keine Bridge gefunden';
  }
  const pairHue = document.querySelector('#pairHue');
  pairHue.textContent = hue.paired ? 'Hue verbunden' : hue.discovered ? 'Link-Taste drücken & koppeln' : 'Hue suchen';
  pairHue.disabled = hue.paired;
  document.querySelector('#pairAdmin').textContent = state.onboarding.adminPaired ? 'Admin gekoppelt' : 'Admin koppeln';
  document.querySelector('#pairAdmin').disabled = state.onboarding.adminPaired;
}

async function refresh(sync = true) {
  const state = await api(`/api/state${sync ? '?sync=1' : ''}`);
  latestState = state;
  renderRooms(state);
  renderHeader(state);
}

document.querySelector('#pairAdmin').addEventListener('click', async () => {
  try {
    await api('/api/onboarding/pair-admin', { method: 'POST', body: '{}' });
    toast('Administratorgerät lokal gekoppelt');
    await refresh(false);
  } catch (error) { toast(error.message); }
});

document.querySelector('#pairHue').addEventListener('click', async () => {
  try {
    if (!latestState?.integrations?.hue?.discovered) {
      const discovered = await api('/api/integrations/hue/discover');
      if (!discovered.discovered) {
        toast('Keine Hue Bridge im lokalen Netzwerk gefunden');
        await refresh(false);
        return;
      }
      toast('Hue Bridge gefunden. Jetzt Link-Taste drücken und erneut koppeln.');
      await refresh(false);
      return;
    }
    await api('/api/integrations/hue/pair', { method: 'POST', body: '{}' });
    toast('Hue Bridge lokal gekoppelt');
    await refresh(true);
  } catch (error) {
    if (error.code === 'HUE_LINK_BUTTON_REQUIRED') toast('Link-Taste auf der Hue Bridge drücken und innerhalb von 30 Sekunden erneut koppeln.');
    else toast(error.message);
  }
});

document.querySelector('#addRoom').addEventListener('click', async () => {
  const input = document.querySelector('#newRoomName');
  const name = input.value.trim();
  if (!name) return toast('Bitte zuerst einen Raumnamen eingeben');
  try {
    await api('/api/rooms', { method: 'POST', body: JSON.stringify({ name }) });
    input.value = '';
    await refresh(false);
    toast(`Raum „${name}“ angelegt`);
  } catch (error) { toast(error.message); }
});

document.querySelector('#newRoomName').addEventListener('keydown', event => {
  if (event.key === 'Enter') document.querySelector('#addRoom').click();
});

document.querySelector('#refresh').addEventListener('click', async () => {
  try { await refresh(true); toast('Hue-Zustände synchronisiert'); } catch (error) { toast(error.message); }
});

async function liveRefresh() {
  if (document.hidden || !latestState?.integrations?.hue?.paired) return;
  try { await refresh(true); } catch {}
}

refresh(false).then(() => {
  liveTimer = window.setInterval(liveRefresh, 3000);
}).catch(error => toast(error.message));

window.addEventListener('beforeunload', () => window.clearInterval(liveTimer));
