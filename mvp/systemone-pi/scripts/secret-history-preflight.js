'use strict';

const {execFileSync}=require('child_process');
const {scanHistoricalBlobs}=require('../lib/secret-preflight');

const timingStart=Date.now(),timings=[];const mark=name=>timings.push(`${name}=${Date.now()-timingStart}ms`);
const git=(args,options={})=>execFileSync('git',args,{maxBuffer:128*1024*1024,...options});
const refs=git(['for-each-ref','--format=%(refname)','refs/heads','refs/remotes','refs/tags'],{encoding:'utf8'}).trim().split('\n').filter(Boolean);
mark('refs');
if(!refs.length){console.error('Secret-Historien-Preflight: keine Git-Refs gefunden.');process.exit(1)}
const objects=git(['rev-list','--objects',...refs],{encoding:'utf8'}).trim().split('\n').filter(Boolean),pathsByHash=new Map();
for(const line of objects){const split=line.indexOf(' '),hash=split<0?line:line.slice(0,split),file=split<0?'':line.slice(split+1);if(!pathsByHash.has(hash))pathsByHash.set(hash,new Set());if(file)pathsByHash.get(hash).add(file)}
mark('objects');
const hashes=[...pathsByHash.keys()],check=git(['cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],{input:hashes.join('\n')+'\n',encoding:'utf8'}).trim().split('\n');
mark('check');
const blobs=[];let skippedLarge=0;
for(const line of check){const [hash,type,sizeText]=line.split(' '),size=Number(sizeText);if(type!=='blob')continue;if(size>2*1024*1024){skippedLarge++;continue}blobs.push({hash,size})}
const batch=git(['cat-file','--batch'],{input:blobs.map(item=>item.hash).join('\n')+'\n'});let offset=0,scanned=0,skippedBinary=0,history=[];
mark('batch');
for(const expected of blobs){const newline=batch.indexOf(10,offset);if(newline<0)throw new Error('Git-Batchausgabe ist unvollständig.');const header=batch.slice(offset,newline).toString('utf8').split(' '),hash=header[0],size=Number(header[2]);offset=newline+1;const data=batch.subarray(offset,offset+size);offset+=size+1;if(data.includes(0)){skippedBinary++;continue}scanned++;const paths=[...(pathsByHash.get(hash)||[])];for(const file of paths.length?paths:['(unbekannter Pfad)'])history.push({object:hash,path:file,content:data.toString('utf8')})}
const findings=scanHistoricalBlobs(history);
mark('scan');if(process.env.SYSTEMONE_SECRET_TIMING==='1')console.error(timings.join(' '));
if(findings.length){console.error(`Secret-Historien-Preflight blockiert: ${findings.length} redigierte Treffer.`);for(const item of findings)console.error(`${item.path}:${item.line} [${item.rule}] object=${item.object}`);process.exitCode=1}
else console.log(`Secret-Historien-Preflight bestanden: ${refs.length} Refs, ${scanned} Textblobs, ${skippedBinary} Binärblobs und ${skippedLarge} große Blobs übersprungen.`);
