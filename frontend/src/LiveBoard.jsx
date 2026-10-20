import React,{useEffect,useRef,useState} from 'react';
import {Drawing} from './foundation/Drawing';
import {collectSamples,strokePath} from './foundation/ink.mjs';
import {LiveClient} from './live-client';
import './live.css';
/** @param {{classId:string,csrf:string,students?:Array<{id:string,name:string}>}} props */
export default function LiveBoard({classId,csrf,students=[]}){
 const [state,setState]=useState({}),[tool,setTool]=useState('stroke'),[color,setColor]=useState('#164e63'),[size,setSize]=useState(3),[shape,setShape]=useState('ring'),[text,setText]=useState(''),[draft,setDraft]=useState(null),[transients,setTransients]=useState([]),[clock,setClock]=useState(Date.now());
 const client=useRef(),gesture=useRef(),lastPreview=useRef(0),history=useRef([]);
 useEffect(()=>{const c=new LiveClient(classId,csrf,setState);client.current=c;c.onTransients=setTransients;c.connect();const flush=e=>{if(e.detail.classId===classId)e.detail.promises.push(c.flush());};window.addEventListener('classroom-live-flush',flush);const timer=setInterval(()=>setClock(Date.now()),150);return()=>{c.stop();clearInterval(timer);window.removeEventListener('classroom-live-flush',flush);};},[classId,csrf]);
 const page=state.document?.pages.find(p=>p.id===state.document.activePageId);
 function send(command){return client.current.enqueue(command);}
 function add(object,pageId=page.id){history.current.push({object,pageId});void send({type:'add',page_id:pageId,object});}
 function point(e){return collectSamples(e.nativeEvent,e.currentTarget.getBoundingClientRect(),null).map(p=>p.slice(0,3));}
 function down(e){if((!state.canWrite&&tool!=='pointer')||e.button!==0||gesture.current)return;e.currentTarget.setPointerCapture(e.pointerId);const points=point(e),[x,y]=points[0];
  if(tool==='pointer'){move(e);return;}
  if(tool==='text'){if(text.trim())add({id:crypto.randomUUID(),type:'text',color,size:20,x,y,width:0,height:0,text:text.trim()});return;}
  const o=['stroke','highlighter'].includes(tool)?{id:crypto.randomUUID(),type:tool,color,size,points,inputType:e.pointerType==='pen'?'pen':'mouse'}:{id:crypto.randomUUID(),type:tool,color,size,x,y,width:0,height:0};
  gesture.current={object:o,pageId:page.id,pointer:e.pointerId};setDraft(structuredClone(o));
 }
 function move(e){if(!state.canWrite&&tool!=='pointer')return;const pts=point(e),[x,y]=pts.at(-1),stamp=Date.now();
  if(tool==='pointer'){if(stamp-lastPreview.current>80){client.current.transient({type:'pointer',page_id:page.id,x,y,color,size:Math.max(6,size*3),shape});lastPreview.current=stamp;}return;}
  const g=gesture.current;if(!g||g.pointer!==e.pointerId)return;const o=g.object;
  if(o.points)o.points.push(...pts.slice(0,50000-o.points.length));else{o.width=x-o.x;o.height=y-o.y;}
  setDraft(structuredClone(o));if(o.points&&stamp-lastPreview.current>100){client.current.transient({type:'preview',page_id:g.pageId,object:{...o,points:o.points.slice(-2000)}});lastPreview.current=stamp;}
 }
 function up(e){const g=gesture.current;if(!g||g.pointer!==e.pointerId)return;gesture.current=null;setDraft(null);add(g.object,g.pageId);}
 function recover(){const blob=new Blob([JSON.stringify({document:state.document,pending:client.current.pending,failed:state.failed},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='classroom-live-recovery.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function drawing(o){return o.type==='image'?<image key={o.id} data-object-id={o.id} href={`/api/join/live/${classId}/assets/${state.boardId}/${o.assetId}`} x={o.x} y={o.y} width={o.width} height={o.height} preserveAspectRatio="none" transform={`rotate(${o.rotation} ${o.x+o.width/2} ${o.y+o.height/2})`}/>:<Drawing key={o.id+JSON.stringify(o)} object={o}/>;}
 return <section className="live-board" aria-label="Live classroom"><h3>Live classroom</h3><p role="status">{state.document?`${state.message} · ${state.pending||0} queued · ${state.canWrite?'Writing enabled':'View only'}`:'Waiting for the teacher to open the live board…'}</p>
 {state.document&&<><div className="live-tools"><label>Tool<select aria-label="Live tool" value={tool} onChange={e=>setTool(e.target.value)}>{['stroke','highlighter','line','rectangle','ellipse','text','pointer'].map(t=><option key={t}>{t}</option>)}</select></label><label>Color<input aria-label="Live color" type="color" value={color} onChange={e=>setColor(e.target.value)}/></label><label>Size<input aria-label="Live size" type="range" min="1" max="12" value={size} onChange={e=>setSize(+e.target.value)}/></label>{tool==='text'&&<label>Text<input value={text} maxLength={2000} onChange={e=>setText(e.target.value)}/></label>}{tool==='pointer'&&<label>Pointer shape<select value={shape} onChange={e=>setShape(e.target.value)}>{['dot','ring','cross'].map(s=><option key={s}>{s}</option>)}</select></label>}<button disabled={!state.canWrite} onClick={()=>{const last=history.current.pop();if(last)void send({type:'remove',page_id:last.pageId,object_id:last.object.id,expected:last.object});}}>Undo my last object</button><button onClick={recover}>Download recovery copy</button></div>
 {state.teacher&&<div className="live-tools"><label>Shared page<select aria-label="Shared page" value={page.id} onChange={e=>void send({type:'page',page_id:e.target.value})}>{state.document.pages.map((p,i)=><option key={p.id} value={p.id}>Page {i+1}</option>)}</select></label><button onClick={()=>void send({type:'newPage',page_id:crypto.randomUUID()})}>Add shared page</button>{students.map(s=><span key={s.id}>{s.name} <button onClick={()=>void send({type:'permission',student_id:s.id,allow:true})}>Allow writing</button> <button onClick={()=>void send({type:'permission',student_id:s.id,allow:false})}>Disable writing</button></span>)}</div>}
 {!!state.failed?.length&&<p role="alert">{state.failed.length} edits could not be merged. Their full contents are retained in the recovery download.</p>}
 <div className="live-sheet"><svg aria-label="Live page" viewBox="0 0 900 1273" style={{touchAction:state.canWrite?'none':'pan-y'}} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
 {page.objects.map(drawing)}{draft&&drawing(draft)}
 {transients.filter(t=>t.expires*1000>clock&&t.body.page_id===page.id).map(t=>{const b=t.body;return b.type==='preview'?<path data-preview="true" key={t.actor} d={strokePath(b.object)} fill={b.object.color} opacity={b.object.type==='highlighter'?.28:1}/>:<g data-pointer="true" key={t.actor} stroke={b.color} strokeWidth="2" fill={b.shape==='dot'?b.color:'none'}>{b.shape==='cross'?<path d={`M${b.x-b.size} ${b.y}h${b.size*2}M${b.x} ${b.y-b.size}v${b.size*2}`}/>:<circle cx={b.x} cy={b.y} r={b.size}/>}</g>;})}</svg></div></>}
 </section>;
}
