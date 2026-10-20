import React,{useEffect,useRef,useState} from 'react';
import {SharedContent} from './ParentSharing';
import './parents.css';

async function request(path,method='GET',body){
 const r=await fetch('/api/parent-portal'+path,{method,credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 if(!r.ok){const e=await r.json().catch(()=>({}));throw Error(typeof e.detail==='string'?e.detail:'This parent view is unavailable. Please contact the teacher.');}return r.json();
}

export default function ParentPortal(){
 const [token,setToken]=useState(()=>location.hash.slice(1)),[content,setContent]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[closed,setClosed]=useState(false);const generation=useRef(0),expectedShare=useRef(null);
 useEffect(()=>{const followLink=()=>{const next=location.hash.slice(1);if(next){generation.current++;expectedShare.current=null;setContent(null);setError('');setClosed(false);setToken(next);history.replaceState(null,'',location.pathname);}};history.replaceState(null,'',location.pathname);window.addEventListener('hashchange',followLink);return()=>window.removeEventListener('hashchange',followLink);},[]);
 async function load(){const version=generation.current;try{const data=await request('/view');if(expectedShare.current&&expectedShare.current!==data.share_id)throw Error('Another parent link was opened in this browser. Reopen the intended link.');if(version===generation.current){expectedShare.current=data.share_id;setContent(data);setError('');}}catch(e){if(version===generation.current){setContent(null);setError(e.message);}}}
 useEffect(()=>{if(token||closed)return;void load();const id=setInterval(()=>void load(),15000);const focus=()=>{if(document.visibilityState==='visible')void load();};document.addEventListener('visibilitychange',focus);window.addEventListener('focus',focus);return()=>{generation.current++;clearInterval(id);document.removeEventListener('visibilitychange',focus);window.removeEventListener('focus',focus);};},[token,closed]);
 useEffect(()=>{if(!content)return;const id=setTimeout(()=>{if(Date.now()>=new Date(content.expires_at).getTime()){generation.current++;setContent(null);setError('This parent link has expired. Please contact the teacher.');}},Math.min(2147483647,Math.max(0,new Date(content.expires_at)-Date.now())));return()=>clearTimeout(id);},[content]);
 async function open(){setBusy(true);setError('');try{await request('/open','POST',{token});setToken('');}catch(e){setContent(null);setError(e.message);}finally{setBusy(false);}}
 return <main className="parent-portal"><h1>MY CLASSROOM · Parent view</h1><p>Read-only work selected by the teacher.</p>{error&&<p className="error" role="alert">{error}</p>}{token?<><p>Open this private link to see the selected work. Keep the link private.</p><button className="primary" disabled={busy} onClick={open}>Open shared work</button></>:closed?<p>Parent view closed. Use the original private link to open it again.</p>:content?<><p>Access expires {new Date(content.expires_at).toLocaleString()}.</p><button onClick={()=>void load()}>Refresh shared work</button><button onClick={async()=>{setBusy(true);try{await request('/close','POST');generation.current++;setContent(null);setClosed(true);}catch(e){setError(e.message);}finally{setBusy(false);}}} disabled={busy}>Close parent view</button><SharedContent content={content} assetRoot={`/api/parent-portal/${content.share_id}/assets`}/></>:!error&&<p>Opening shared work…</p>}</main>;
}
