class ReconnectController {
  constructor({ diagnostics, minDelayMs = 2000, maxDelayMs = 60000 }) {
    this.diagnostics = diagnostics;
    this.minDelayMs = minDelayMs;
    this.maxDelayMs = maxDelayMs;
    this.reset();
  }

  reset() {
    this.state = 'idle';
    this.attempt = 0;
    this.nextRetryAt = null;
    this.lastSuccessAt = null;
    this.lastFailureAt = null;
    this.lastErrorCode = null;
  }

  success() {
    this.state = 'connected';
    this.attempt = 0;
    this.nextRetryAt = null;
    this.lastSuccessAt = new Date().toISOString();
    this.lastErrorCode = null;
  }

  failure(error) {
    this.attempt += 1;
    const delay = Math.min(this.maxDelayMs, this.minDelayMs * (2 ** Math.min(this.attempt - 1, 8)));
    const jitter = Math.floor(delay * 0.15 * Math.random());
    const retryInMs = delay + jitter;
    this.state = 'backoff';
    this.lastFailureAt = new Date().toISOString();
    this.lastErrorCode = error?.code || 'HUE_SYNC_FAILED';
    this.nextRetryAt = new Date(Date.now() + retryInMs).toISOString();
    this.diagnostics?.record('HUE_RECONNECT_SCHEDULED', 'Hue-Neuverbindung wurde geplant.', {
      severity: 'warning', attempt: this.attempt, retryInMs, errorCode: this.lastErrorCode
    });
    return retryInMs;
  }

  beginAttempt() {
    this.state = 'reconnecting';
  }

  canRetry() {
    return this.state === 'backoff' && this.nextRetryAt && Date.parse(this.nextRetryAt) <= Date.now();
  }

  snapshot() {
    return {
      state: this.state,
      attempt: this.attempt,
      nextRetryAt: this.nextRetryAt,
      lastSuccessAt: this.lastSuccessAt,
      lastFailureAt: this.lastFailureAt,
      lastErrorCode: this.lastErrorCode
    };
  }
}

module.exports = { ReconnectController };
