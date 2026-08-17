class DeviceAdapter {
  constructor(id) { if (new.target === DeviceAdapter) throw new Error('DeviceAdapter ist abstrakt.'); this.id = id; }
  async discover() { throw new Error(`${this.id}.discover ist nicht implementiert.`); }
  async pair() { throw new Error(`${this.id}.pair ist nicht implementiert.`); }
  async listDevices() { throw new Error(`${this.id}.listDevices ist nicht implementiert.`); }
  async applyCapabilities() { throw new Error(`${this.id}.applyCapabilities ist nicht implementiert.`); }
}

function assertAdapter(adapter) {
  for (const method of ['discover', 'pair', 'listDevices', 'applyCapabilities']) {
    if (typeof adapter?.[method] !== 'function') throw Object.assign(new Error(`Adapter-Methode ${method} fehlt.`), { code: 'ADAPTER_INVALID' });
  }
  return adapter;
}

module.exports = { DeviceAdapter, assertAdapter };
