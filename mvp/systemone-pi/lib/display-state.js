function displayState(state, devices) {
  const roomNames = new Map((state.rooms || []).map(room => [room.id, room.name]));
  return {
    generatedAt: new Date().toISOString(),
    home: { name: state.home?.name || 'Mein Zuhause' },
    theme: state.onboarding?.selectedTheme || 'Midnight',
    summary: {
      devices: devices.length,
      online: devices.filter(device => device.online).length,
      activeAutomations: (state.automations || []).filter(item => item.enabled).length
    },
    rooms: (state.rooms || []).map(room => ({ id: room.id, name: room.name, devices: devices.filter(device => device.roomId === room.id).map(device => ({ id: device.id, name: device.name, profile: device.profile, online: Boolean(device.online), room: roomNames.get(device.roomId) || null, status: statusFor(device) })) }))
  };
}

function statusFor(device) {
  if (!device.online) return 'Nicht erreichbar';
  const capabilities = device.capabilities || {};
  if (device.profile === 'light' || device.profile === 'switch') return capabilities.power ? 'Ein' : 'Aus';
  if (device.profile === 'sensor') return `${capabilities.value ?? '–'} ${capabilities.unit || ''}`.trim();
  if (device.profile === 'thermostat') return `${capabilities.temperature ?? '–'} °C`;
  if (device.profile === 'blind') return `${capabilities.position ?? '–'} %`;
  return 'Bereit';
}

module.exports = { displayState, statusFor };
