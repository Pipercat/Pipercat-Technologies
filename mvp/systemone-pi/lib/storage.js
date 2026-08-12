const fs = require('fs');
const path = require('path');

class LocalStorage {
  constructor(baseDir) {
    this.baseDir = baseDir;
    this.stateFile = path.join(baseDir, 'state.json');
    this.secretsFile = path.join(baseDir, 'secrets.json');
    fs.mkdirSync(baseDir, { recursive: true, mode: 0o700 });
  }

  readJson(file, fallback) {
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (error) {
      if (error.code !== 'ENOENT') console.warn(`Lokaler Speicher konnte nicht gelesen werden: ${error.message}`);
      return fallback;
    }
  }

  writeJson(file, value, mode = 0o600) {
    const tmp = `${file}.tmp`;
    fs.writeFileSync(tmp, `${JSON.stringify(value, null, 2)}\n`, { mode });
    fs.renameSync(tmp, file);
    try { fs.chmodSync(file, mode); } catch {}
  }

  loadState(fallback) {
    return this.readJson(this.stateFile, fallback);
  }

  saveState(state) {
    this.writeJson(this.stateFile, state, 0o600);
  }

  loadSecrets() {
    return this.readJson(this.secretsFile, {});
  }

  saveSecrets(secrets) {
    this.writeJson(this.secretsFile, secrets, 0o600);
  }
}

module.exports = { LocalStorage };
