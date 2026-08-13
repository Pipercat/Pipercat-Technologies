'use strict';

const path=require('path');

const PROVIDER_PATTERNS=[
  ['PRIVATE_KEY',new RegExp(['-----BEGIN ','(?:RSA |EC |OPENSSH )?','PRIVATE KEY-----'].join(''))],
  ['GITHUB_TOKEN',new RegExp(['gh','[pousr]_[A-Za-z0-9_]{30,}'].join(''))],
  ['AWS_ACCESS_KEY',new RegExp(['AK','IA[0-9A-Z]{16}'].join(''))],
  ['SLACK_TOKEN',new RegExp(['xo','x[baprs]-[A-Za-z0-9-]{20,}'].join(''))],
  ['STRIPE_LIVE_KEY',new RegExp(['sk','_live_[A-Za-z0-9]{20,}'].join(''))]
];
const GENERIC_CREDENTIAL=/(?:api[_-]?key|token|password|secret)\s*[:=]\s*['"]([A-Za-z0-9+/_=-]{24,})['"]/ig;
const SAFE_VALUES=/^(?:example|placeholder|change-?me|redacted|not-?set|simulation)/i;

function prohibitedPath(file){
  const normalized=String(file).replace(/\\/g,'/'),name=path.posix.basename(normalized).toLowerCase();
  if(normalized.split('/').some(segment=>['data','data-live','data-live-camera','backups'].includes(segment)))return'RUNTIME_DATA';
  if(/\.(?:pem|key|p12|pfx)$/i.test(name))return'PRIVATE_KEY_FILE';
  if((name==='.env'||name.endsWith('.env'))&&!name.endsWith('.env.example'))return'ENV_FILE';
  return null;
}

function scanTrackedEntries(entries=[]){
  const findings=[];
  for(const entry of entries){
    const file=String(entry.path||''),pathRule=prohibitedPath(file);
    if(pathRule)findings.push({path:file,line:1,rule:pathRule});
    const content=String(entry.content||'');
    for(const [rule,pattern] of PROVIDER_PATTERNS){const match=pattern.exec(content);if(match)findings.push({path:file,line:content.slice(0,match.index).split('\n').length,rule})}
    GENERIC_CREDENTIAL.lastIndex=0;let match;
    while((match=GENERIC_CREDENTIAL.exec(content)))if(!SAFE_VALUES.test(match[1]))findings.push({path:file,line:content.slice(0,match.index).split('\n').length,rule:'GENERIC_CREDENTIAL'});
  }
  return findings;
}

function scanHistoricalBlobs(blobs=[]){
  const seen=new Set(),findings=[];
  for(const blob of blobs)for(const finding of scanTrackedEntries([{path:blob.path,content:blob.content}])){
    const item={...finding,object:String(blob.object||'').slice(0,12)},key=[item.object,item.path,item.line,item.rule].join(':');
    if(!seen.has(key)){seen.add(key);findings.push(item)}
  }
  return findings;
}

module.exports={prohibitedPath,scanTrackedEntries,scanHistoricalBlobs};
