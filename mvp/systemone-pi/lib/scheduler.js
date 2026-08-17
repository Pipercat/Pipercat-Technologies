const { EventEmitter } = require('events');

function minuteKey(date) { return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}-${date.getHours()}-${date.getMinutes()}`; }
function localTime(date) { return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`; }

class AutomationScheduler extends EventEmitter {
  constructor({ engine, solarProvider = null, now = () => new Date(), initialExecuted = {}, onExecutedChange = null }) {
    super(); this.engine = engine; this.solarProvider = solarProvider; this.now = now; this.executed = new Map(Object.entries(initialExecuted || {})); this.onExecutedChange = onExecutedChange; this.timer = null;
  }
  async dueAt(automation, date) {
    if (automation.trigger.type === 'time') return automation.trigger.at === localTime(date);
    if (automation.trigger.type !== 'sun' || !this.solarProvider) return false;
    const events = await this.solarProvider(date);
    const base = events?.[automation.trigger.event];
    if (!(base instanceof Date) || Number.isNaN(base.getTime())) return false;
    const target = new Date(base.getTime() + automation.trigger.offsetMinutes * 60000);
    return minuteKey(target) === minuteKey(date);
  }
  async tick(date = this.now()) {
    const key = minuteKey(date), results = [];
    for (const automation of this.engine.list()) {
      if (!automation.enabled || !['time', 'sun'].includes(automation.trigger.type) || this.executed.get(automation.id) === key || !await this.dueAt(automation, date)) continue;
      this.executed.set(automation.id, key); this.onExecutedChange?.(Object.fromEntries(this.executed));
      const result = await this.engine.executeScheduled(automation.id); results.push(result); this.emit('executed', { automationId: automation.id, date: date.toISOString(), result });
    }
    let changed=false;for (const [id, oldKey] of this.executed) if (oldKey !== key && !this.engine.list().some(value => value.id === id)){this.executed.delete(id);changed=true}if(changed)this.onExecutedChange?.(Object.fromEntries(this.executed));
    return results;
  }
  start(intervalMs = 15000) { if (this.timer) return; this.timer = setInterval(() => this.tick().catch(error => this.emit('error', error)), intervalMs); this.timer.unref(); }
  stop() { if (this.timer) clearInterval(this.timer); this.timer = null; }
  status() { return { running: Boolean(this.timer), solarAvailable: Boolean(this.solarProvider), checkedAt: this.now().toISOString(), timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'system-local', executed: Object.fromEntries(this.executed) }; }
}

module.exports = { AutomationScheduler, minuteKey, localTime };
