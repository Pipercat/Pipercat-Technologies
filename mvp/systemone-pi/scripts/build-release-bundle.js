const fs=require('fs');
const path=require('path');
const {execFileSync}=require('child_process');
const {createReleaseBundle}=require('../lib/release-bundle');

const appRoot=path.resolve(__dirname,'..');
const repoRoot=execFileSync('git',['rev-parse','--show-toplevel'],{cwd:appRoot,encoding:'utf8'}).trim();
const prefix=path.relative(repoRoot,appRoot).replaceAll('\\','/');
const dirty=execFileSync('git',['status','--porcelain','--',prefix],{cwd:repoRoot,encoding:'utf8'}).trim();
if(dirty){console.error('Release-Build blockiert: MVP-Arbeitsbaum enthält nicht committe Änderungen.');process.exit(2)}
const sourceCommit=execFileSync('git',['rev-parse','HEAD'],{cwd:repoRoot,encoding:'utf8'}).trim();
const sourceTimestamp=Number(execFileSync('git',['show','-s','--format=%ct',sourceCommit],{cwd:repoRoot,encoding:'utf8'}).trim());
const pkg=require('../package.json');
const tracked=execFileSync('git',['ls-files','-s','--',prefix],{cwd:repoRoot,encoding:'utf8'}).trim().split('\n').filter(Boolean);
const entries=tracked.map(line=>{const match=line.match(/^(100644|100755) [a-f0-9]+ \d+\t(.+)$/);if(!match)throw new Error(`Nicht unterstützter Git-Eintrag: ${line}`);const repoPath=match[2],relative=repoPath.slice(prefix.length+1);return{path:relative,content:fs.readFileSync(path.join(repoRoot,repoPath)),mode:match[1]==='100755'?0o755:0o644}});
const result=createReleaseBundle(entries,{name:pkg.name,version:pkg.version,target:'systemone-pi',sourceCommit,sourceTimestamp});
const dist=path.join(appRoot,'dist');fs.mkdirSync(dist,{recursive:true});
const base=`systemone-pi-${pkg.version}-${sourceCommit.slice(0,12)}`;
const archivePath=path.join(dist,`${base}.tar.gz`),checksumPath=`${archivePath}.sha256`,manifestPath=path.join(dist,`${base}.manifest.json`);
fs.writeFileSync(archivePath,result.archive,{mode:0o644});
fs.writeFileSync(checksumPath,`${result.archiveSha256}  ${path.basename(archivePath)}\n`,{mode:0o644});
fs.writeFileSync(manifestPath,`${JSON.stringify(result.manifest,null,2)}\n`,{mode:0o644});
console.log(`Release-Bundle erstellt: ${path.relative(appRoot,archivePath)}`);
console.log(`Dateien: ${result.manifest.files.length} · SHA-256: ${result.archiveSha256}`);
