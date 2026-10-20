import React,{useEffect,useState} from 'react';
import {api} from './api';
import CorrectionCanvas from './CorrectionCanvas';
export default function ClassroomCopyReview({id,onPending,onSaved}){
 const [doc,setDoc]=useState(null),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let live=true;api('/documents/'+id).then(d=>{if(live)setDoc(d);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[id]);
 useEffect(()=>{onPending(dirty||busy);return()=>onPending(false);},[dirty,busy,onPending]);
 function edit(next){setDoc(next);setDirty(true);}
 async function save(){setBusy(true);try{setDoc(await api('/documents/'+id,'PUT',{expected_revision:doc.revision,document:doc}));setDirty(false);setError('');onSaved();}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <section><h3>Review private classroom copy</h3><p>Remove names or other identifying objects before publishing. These edits affect only this copy.</p>{error&&<p role="alert">{error}</p>}{doc&&<><fieldset disabled={busy}><label>Reviewed copy title<input aria-label="Reviewed copy title" maxLength={200} value={doc.title} onChange={e=>edit({...doc,title:e.target.value})}/></label>{doc.pages.map((p,i)=><details key={p.id}><summary>Page {i+1} · Remove identifying content</summary>{p.objects.map((o,n)=><div className="hw-tools" key={o.id}><span>{n+1}. {o.type}{o.text?' · '+o.text.slice(0,100):''}</span><button onClick={()=>edit({...doc,pages:doc.pages.map(page=>page.id===p.id?{...page,objects:page.objects.filter(item=>item.id!==o.id)}:page)})}>Remove object {n+1} from page {i+1}</button></div>)}</details>)}<button className="secondary" disabled={!dirty||!doc.title.trim()} onClick={save}>Save reviewed copy</button>{dirty&&<p>Save this reviewed copy before selecting a different copy or sharing.</p>}</fieldset><details><summary>Preview all pages</summary><CorrectionCanvas document={doc} body={{pages:doc.pages.map(p=>({id:p.id,objects:[]}))}} readOnly assetRoot={`/api/documents/${id}/assets`}/></details></>}</section>;
}
