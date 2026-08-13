const evidence = require('../release-evidence.json');
const { evaluateReleaseEvidence } = require('../lib/release-gates');

const report = evaluateReleaseEvidence(evidence);
for (const gate of report.results) console.log(`${gate.passed ? '✓' : '○'} ${gate.id}${gate.evidence.length ? ` — ${gate.evidence.join('; ')}` : ''}`);
console.log(`\n${report.passed}/${report.total} Release-Gates bestanden`);
if (!report.ready) {
  console.error('Pilotfreigabe blockiert: Pflicht-Gates sind noch offen.');
  process.exitCode = 1;
}
