'use strict';

const fs=require('fs');
const {execFileSync}=require('child_process');
const {scanTrackedEntries}=require('../lib/secret-preflight');

const files=execFileSync('git',['ls-files','-z'],{encoding:'utf8'}).split('\0').filter(Boolean);
const entries=[];
for(const file of files){
  let data;try{data=fs.readFileSync(file)}catch{continue}
  if(data.includes(0))continue;
  entries.push({path:file,content:data.toString('utf8')});
}
const findings=scanTrackedEntries(entries);
if(findings.length){
  console.error(`Secret-Preflight blockiert: ${findings.length} redigierte Treffer.`);
  for(const finding of findings)console.error(`${finding.path}:${finding.line} [${finding.rule}]`);
  process.exitCode=1;
}else console.log(`Secret-Preflight bestanden: ${files.length} versionierte Dateien, keine Secretmuster.`);
