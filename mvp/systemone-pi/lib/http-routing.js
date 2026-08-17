'use strict';

function acceptsHtml(value=''){
  return String(value).split(',').some(part=>{
    const media=part.trim().split(';')[0].trim().toLowerCase();
    return media==='text/html'||media==='application/xhtml+xml';
  });
}

function shouldServeAppShell(pathname,accept=''){
  const value=String(pathname||'/');
  if(value.startsWith('/api/')||value.startsWith('/docs/'))return false;
  const segment=value.split('/').pop()||'';
  if(segment.includes('.'))return false;
  return acceptsHtml(accept);
}

function staticResponseHeaders(fileName=''){
  const name=String(fileName).split('/').pop();
  return {
    'Cache-Control':'no-cache',
    ...(name==='service-worker.js'?{'Service-Worker-Allowed':'/'}:{})
  };
}

module.exports={acceptsHtml,shouldServeAppShell,staticResponseHeaders};
