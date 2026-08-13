const fs = require('fs');
const path = require('path');

class LocalStorage {
  constructor(baseDir, { onError } = {}) {
    this.baseDir = baseDir;
    this.onError = onError;
    this.stateFile = path.join(baseDir, 'state.json');
    this.secretsFile = path.join(baseDir, 'secrets.json');
    this.sessionsFile = path.join(baseDir, 'sessions.json');
    fs.mkdirSync(baseDir, { recursive: true, mode: 0o700 });
  }

  report(code, message, details = {}) {
    const error = Object.assign(new Error(message), { code, details });
    if (this.onError) this.onError(error);
    else console.warn(`${code}: ${message}`);
    return error;
  }

  parseFile(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }

  readJson(file, fallback) {
    try {
      return this.parseFile(file);
    } catch (error) {
      if (error.code === 'ENOENT') return fallback;
      const backupFile = `${file}.bak`;
      try {
        const recovered = this.parseFile(backupFile);
        this.report('STORAGE_RECOVERED', 'Beschädigte Speicherdatei wurde aus der letzten Sicherung wiederhergestellt.', { file: path.basename(file), cause: error.message });
        this.writeJson(file, recovered, 0o600, { keepBackup: false });
        return recovered;
      } catch (backupError) {
        this.report('STORAGE_READ_FAILED', 'Lokaler Speicher konnte nicht gelesen oder wiederhergestellt werden.', { file: path.basename(file), cause: error.message, recoveryCause: backupError.message });
      }
      return fallback;
    }
  }

  writeJson(file, value, mode = 0o600, { keepBackup = true } = {}) {
    const tmp = `${file}.${process.pid}.${Date.now()}.tmp`;
    const backup = `${file}.bak`;
    let handle;
    try {
      handle = fs.openSync(tmp, 'wx', mode);
      fs.writeFileSync(handle, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
      fs.fsyncSync(handle); fs.closeSync(handle); handle = null;
      if (keepBackup && fs.existsSync(file)) fs.copyFileSync(file, backup);
      fs.renameSync(tmp, file);
      try { fs.chmodSync(file, mode); } catch {}
      try { const dirHandle = fs.openSync(this.baseDir, 'r'); fs.fsyncSync(dirHandle); fs.closeSync(dirHandle); } catch {}
    } catch (error) {
      if (handle !== null && handle !== undefined) try { fs.closeSync(handle); } catch {}
      try { if (fs.existsSync(tmp)) fs.unlinkSync(tmp); } catch {}
      throw this.report('STORAGE_WRITE_FAILED', 'Lokaler Speicher konnte nicht atomar geschrieben werden.', { file: path.basename(file), cause: error.message });
    }
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

  loadSessions() { return this.readJson(this.sessionsFile, []); }
  saveSessions(sessions) { this.writeJson(this.sessionsFile, sessions, 0o600); }
}

module.exports = { LocalStorage };
