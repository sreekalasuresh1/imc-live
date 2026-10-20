import React,{useEffect,useRef,useState} from 'react';
import { ... } from './shared/document.mjs';
import {applyCommand,validateDocument} from './shared/document.mjs';
import {Drawing} from './foundation/Drawing.jsx';
import {collectSamples,strokePath} from './foundation/ink.mjs';
import {compositeMask} from './foundation/masks.mjs';
import './notebooks.css';
import {draftStore} from './notebook-drafts';

function PrivateImage({object:o,documentId}){
  const [source,setSource]=useState(''),[error,setError]=useState(false);
  useEffect(()=>{let live=true;setSource('');setError(false);const image=new Image();image.src=`/api/documents/${documentId}/assets/${o.assetId}`;
    image.decode().then(()=>{const url=o.masks?.length?compositeMask(document.createElement('canvas'),image,o.masks).toDataURL('image/png'):image.src;if(live)setSource(url);}).catch(()=>{if(live)setError(true);});return()=>{live=false;};
  },[documentId,o.assetId,JSON.stringify(o.masks)]);
  return source?<image href={source} x={o.x} y={o.y} width={o.width} height={o.height} preserveAspectRatio="none" transform={`rotate(${o.rotation} ${o.x+o.width/2} ${o.y+o.height/2})`}/>:<text x={o.x} y={o.y+20}>{error?'Image unavailable':'Loading image…'}</text>;
}

export default function Notebooks({onDirty,userId}){
  const [rows,setRows]=useState([]),[doc,setDoc]=useState(null),[title,setTitle]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[dirty,setDirty]=useState(false),[saved,setSaved]=useState('');
  const [color,setColor]=useState('#203b35'),[size,setSize]=useState(3),[tool,setTool]=useState('stroke'),[text,setText]=useState(''),[preview,setPreview]=useState(null),[history,setHistory]=useState([]);
  const current=useRef(null),gesture=useRef(null),serverRevision=useRef(0),saveBusy=useRef(false),dirtyRef=useRef(false);
  current.current=doc;dirtyRef.current=dirty;
  useEffect(()=>{onDirty(dirty||busy||!!preview);return()=>onDirty(false);},[dirty,busy,!!preview,onDirty]);
  useEffect(()=>{if(doc&&dirty)draftStore(userId,doc.id,{document:doc,serverRevision:serverRevision.current}).catch(()=>setError('Browser recovery storage failed. Keep this notebook open and save or download it.'));},[doc,dirty,userId]);
  useEffect(()=>{const warn=e=>{if(dirtyRef.current||gesture.current||saveBusy.current){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[]);
  async function refresh(){try{setRows(await api('/documents'));}catch(e){setError(e.message);}}
  useEffect(()=>{refresh();},[]);
  function accept(next){validateDocument(next);serverRevision.current=next.revision;setDoc(next);current.current=next;setTitle(next.title);setDirty(false);setHistory([]);setSaved('Saved on server');setError('');}
  async function open(id){if(dirtyRef.current||saveBusy.current)return;setBusy(true);try{accept(await api(`/documents/${id}`));const recovered=await draftStore(userId,id);if(recovered){validateDocument(recovered.document);if(recovered.document.id!==id)throw Error('Invalid browser recovery draft');setDoc(recovered.document);current.current=recovered.document;serverRevision.current=recovered.serverRevision;setDirty(true);setSaved('Recovered browser draft · not saved on server');}}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function create(e){e.preventDefault();setBusy(true);try{accept(await api('/documents','POST',{title}));await refresh();}catch(e){setError(e.message);}finally{setBusy(false);}}
  function command(cmd){try{const before=current.current,next=applyCommand(before,cmd);setHistory(h=>[...h.slice(-29),before]);current.current=next;setDoc(next);setDirty(true);setSaved('Unsaved changes');setError('');}catch(e){setError(e.message);}}
  async function save(){if(saveBusy.current||gesture.current||!dirtyRef.current)return;saveBusy.current=true;setBusy(true);setError('');try{await draftStore(userId,current.current.id,{document:current.current,serverRevision:serverRevision.current});const next=await api(`/documents/${current.current.id}`,'PUT',{expected_revision:serverRevision.current,document:current.current});await draftStore(userId,next.id,null);accept(next);await refresh();}catch(e){setError(e.message+' Your browser draft is retained when local storage is available.');}finally{saveBusy.current=false;setBusy(false);}}
  async function upload(e){const file=e.target.files?.[0];e.target.value='';if(!file)return;if(file.size>4*1024*1024){setError('Choose an image up to 4 MB.');return;}setBusy(true);try{
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});
    const asset=await api(`/documents/${doc.id}/assets`,'POST',{data});const ratio=Math.min(1,700/asset.width,1000/asset.height);
    command({type:'addObject',pageId:doc.activePageId,object:{id:crypto.randomUUID(),type:'image',assetId:asset.assetId,x:50,y:50,width:Math.max(5,asset.width*ratio),height:Math.max(5,asset.height*ratio),rotation:0}});
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  async function download(){setBusy(true);try{const assets={};for(const id of new Set(doc.pages.flatMap(p=>p.objects.filter(o=>o.type==='image').map(o=>o.assetId)))){const response=await fetch(`/api/documents/${doc.id}/assets/${id}`);if(!response.ok)throw Error('Reconnect to include all images in the recovery download.');assets[id]=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;response.blob().then(b=>r.readAsDataURL(b)).catch(reject);});}
    const url=URL.createObjectURL(new Blob([JSON.stringify({format:'my-classroom-browser-recovery-v1',document:doc,assets})],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='Notebook-recovery.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){setError(e.message);}finally{setBusy(false);}}
  async function reopen(){if(!window.confirm('Discard this unsaved browser draft and reopen the server copy? Download a recovery copy first if you want to keep these edits.'))return;setBusy(true);try{const next=await api(`/documents/${doc.id}`);await draftStore(userId,doc.id,null);accept(next);}catch(e){setError(e.message);}finally{setBusy(false);}}
  const page=doc?.pages.find(p=>p.id===doc.activePageId),index=doc?.pages.indexOf(page);
  function down(e){if(busy||gesture.current||e.button!==0||e.pointerType==='touch')return;const samples=collectSamples(e.nativeEvent,e.currentTarget.getBoundingClientRect());
    if(tool==='text'){command({type:'addObject',pageId:page.id,object:{id:crypto.randomUUID(),type:'text',color,size:20,x:samples[0][0],y:samples[0][1],width:0,height:0,text}});return;}
    const object={id:crypto.randomUUID(),type:tool,color,size,pressureEnabled:true,pressureCurve:1,inputType:e.pointerType==='pen'?'pen':'mouse',points:samples.map(p=>p.slice(0,3))};gesture.current={pointer:e.pointerId,object};e.currentTarget.setPointerCapture(e.pointerId);setPreview({...object});
  }
  function move(e){const g=gesture.current;if(!g||g.pointer!==e.pointerId)return;g.object.points.push(...collectSamples(e.nativeEvent,e.currentTarget.getBoundingClientRect()).map(p=>p.slice(0,3)));if(g.object.points.length>50000){gesture.current=null;setPreview(null);setError('Stroke too long. Use shorter strokes.');return;}setPreview({...g.object,points:[...g.object.points]});}
  function finish(e,cancel=false){const g=gesture.current;if(!g||g.pointer!==e.pointerId)return;gesture.current=null;setPreview(null);if(!cancel)command({type:'addObject',pageId:page.id,object:g.object});}
  return <section className="notebooks"><h1>Private notebooks</h1><p>Your pages are visible only to your account. Saving here does not submit work or share it with a class.</p>
    {error&&<p className="error" role="alert">{error}</p>}
    {!doc?<><form className="notebook-actions" onSubmit={create}><label>Notebook title<input required maxLength={200} value={title} onChange={e=>setTitle(e.target.value)}/></label><button className="primary" disabled={busy||!title.trim()}>Create notebook</button></form><div className="notebook-list">{rows.map(r=><button className="secondary" key={r.id} disabled={busy} onClick={()=>open(r.id)}>{r.title}</button>)}{!rows.length&&<p>No notebooks yet.</p>}</div></>:<>
      <div className="notebook-actions"><button className="secondary" disabled={busy||dirty||!!preview} onClick={()=>{setDoc(null);setTitle('');}}>Back to notebooks</button><label>Notebook title<input value={doc.title} maxLength={200} disabled={busy||!!preview} onChange={e=>{if(!e.target.value.trim())return;command({type:'metadata',title:e.target.value});}}/></label><button className="primary" disabled={busy||!dirty||!!preview} onClick={save}>Save notebook</button><button className="secondary" disabled={busy||!!preview} onClick={download}>Download recovery copy</button><span role="status">{saved}</span></div>
      <div className="notebook-actions"><fieldset disabled={busy||!!preview}><legend>Writing tools</legend><label>Tool<select aria-label="Tool" value={tool} onChange={e=>setTool(e.target.value)}><option value="stroke">Pen</option><option value="highlighter">Highlighter</option><option value="text">Text</option></select></label><label>Ink color<input type="color" value={color} onChange={e=>setColor(e.target.value)}/></label><label>Ink size<input type="number" min="1" max="20" value={size} onChange={e=>setSize(Math.max(1,Math.min(20,Number(e.target.value))))}/></label>{tool==='text'&&<label>Text to place<input value={text} onChange={e=>setText(e.target.value)} maxLength={2000}/></label>}<label>Insert image<input type="file" accept="image/png,image/jpeg" onChange={upload}/></label><button className="secondary" disabled={!history.length} onClick={()=>{const before=history.at(-1);setHistory(h=>h.slice(0,-1));setDoc(before);current.current=before;setDirty(true);setSaved('Unsaved changes');}}>Undo</button></fieldset></div>
      <div className="notebook-actions"><button className="secondary" disabled={busy||!!preview||index===0} onClick={()=>command({type:'activatePage',pageId:doc.pages[index-1].id})}>Previous page</button><span>Page {index+1} of {doc.pages.length}</span><button className="secondary" disabled={busy||!!preview||index===doc.pages.length-1} onClick={()=>command({type:'activatePage',pageId:doc.pages[index+1].id})}>Next page</button><button className="secondary" disabled={busy||!!preview} onClick={()=>command({type:'addPage'})}>New page</button></div>
      <svg className="browser-paper" viewBox="0 0 900 1273" aria-label="Notebook whiteboard" onPointerDown={down} onPointerMove={move} onPointerUp={finish} onPointerCancel={e=>finish(e,true)} onLostPointerCapture={e=>finish(e,true)}>{page.objects.map(o=>o.type==='image'?<PrivateImage key={o.id} object={o} documentId={doc.id}/>:<Drawing key={o.id} object={o}/>)}{preview&&<path d={strokePath(preview)} fill={preview.color} opacity={preview.type==='highlighter'?.28:1}/>}</svg>
      <p>Save before leaving this notebook. Recovery downloads include private source images. Touch scrolls; mouse and pen write.</p>
      {dirty&&<button className="secondary" disabled={busy||!!preview} onClick={reopen}>Discard draft and reopen server copy</button>}
    </>}
  </section>;
}

