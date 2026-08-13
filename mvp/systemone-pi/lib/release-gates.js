const REQUIRED_GATES = Object.freeze(['automated', 'app', 'security', 'hardware', 'backupRecovery', 'updateRollback', 'operations', 'pilot']);

function evaluateReleaseEvidence(input) {
  if (!input || input.schemaVersion !== 1 || typeof input.gates !== 'object') throw Object.assign(new Error('Release-Evidence besitzt ein ungültiges Format.'), { code: 'RELEASE_EVIDENCE_INVALID' });
  const results = REQUIRED_GATES.map(id => {
    const gate = input.gates[id];
    if (!gate || gate.required !== true || typeof gate.passed !== 'boolean' || !Array.isArray(gate.evidence)) throw Object.assign(new Error(`Release-Gate ${id} ist unvollständig.`), { code: 'RELEASE_EVIDENCE_INVALID', details: { gate: id } });
    return { id, passed: gate.passed, evidence: [...gate.evidence] };
  });
  return { ready: results.every(result => result.passed), passed: results.filter(result => result.passed).length, total: results.length, results };
}

module.exports = { REQUIRED_GATES, evaluateReleaseEvidence };
