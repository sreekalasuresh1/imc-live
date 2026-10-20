import React,{useRef,useState} from 'react';
import {Drawing} from './foundation/Drawing';
import {collectSamples} from './foundation/ink.mjs';
import './homework.css';
export default function AnswerCanvas({document,answers,onChange,readOnly=false,assetRoot}){
 const [pageId,setPageId]=useState(document.pages[0].id),[tool,setTool]=useState('stroke'),[color,setColor]=useState('#b91c1c'),[size,setSize]=useState(3),[text,setText]=useState(''),[preview,setPreview]=useState(null);const gesture=useRef();
 const page=document.pages.find(p=>p.id===pageId)||document.pages[0],answer=answers.pages.find(p=>p.id===page.id)||{id:page.id,objects:[]};
 function change(objects){onChange({...answers,pages:answers.pages.map(p=>p.id===page.id?{...p,objects}:p)});}
 function samples(e){return collectSamples(e.nativeEvent,e.currentTarget.getBoundingClientRect()).map(p=>p.slice(0,3));}
 function down(e){if(readOnly||e.button!==0||gesture.current)return;
  if(tool==='eraser'){const id=e.target.closest('[data-answer-id]')?.getAttribute('data-answer-id');if(id)change(answer.objects.filter(o=>o.id!==id));return;}
  const pts=samples(e),[x,y]=pts[0],base={id:crypto.randomUUID(),type:tool,color,size};
  if(tool==='text'){if(text.trim())change([...answer.objects,{...base,size:20,x,y,width:0,height:0,text:text.trim()}]);return;}
  const object=['stroke','highlighter'].includes(tool)?{...base,points:pts,inputType:e.pointerType==='pen'?'pen':'mouse'}:{...base,x,y,width:0,height:0};gesture.current={pointer:e.pointerId,object};e.currentTarget.setPointerCapture(e.pointerId);setPreview(structuredClone(object));
 }
 function move(e){const g=gesture.current;if(!g||g.pointer!==e.pointerId)return;const pts=samples(e),[x,y]=pts.at(-1);if(g.object.points)g.object.points.push(...pts.slice(0,50000-g.object.points.length));else{g.object.width=x-g.object.x;g.object.height=y-g.object.y;}setPreview(structuredClone(g.object));}
 function end(e){const g=gesture.current;if(!g||g.pointer!==e.pointerId)return;gesture.current=null;setPreview(null);change([...answer.objects,g.object]);}
 function drawing(o){return o.type==='image'?<image key={o.id} href={assetRoot+'/'+o.assetId} x={o.x} y={o.y} width={o.width} height={o.height} preserveAspectRatio="none" transform={`rotate(${o.rotation} ${o.x+o.width/2} ${o.y+o.height/2})`}/>:<Drawing key={o.id+JSON.stringify(o)} object={o}/>;}
 return <section className="answer-canvas"><div className="hw-tools"><label>Page<select aria-label="Homework page" disabled={!!preview} value={page.id} onChange={e=>setPageId(e.target.value)}>{document.pages.map((p,i)=><option key={p.id} value={p.id}>Page {i+1}</option>)}</select></label>{!readOnly&&<><label>Answer tool<select aria-label="Answer tool" disabled={!!preview} value={tool} onChange={e=>setTool(e.target.value)}>{['stroke','highlighter','text','line','rectangle','ellipse','eraser'].map(t=><option key={t}>{t}</option>)}</select></label><label>Color<input type="color" value={color} onChange={e=>setColor(e.target.value)}/></label><label>Width<input type="range" min="1" max="12" value={size} onChange={e=>setSize(+e.target.value)}/></label>{tool==='text'&&<label>Answer text<input aria-label="Answer text" maxLength={2000} value={text} onChange={e=>setText(e.target.value)}/></label>}<button disabled={!!preview||!answer.objects.length} onClick={()=>change(answer.objects.slice(0,-1))}>Undo last answer object</button></>}</div><div className="hw-paper"><svg aria-label="Homework answer page" viewBox="0 0 900 1273" style={{touchAction:readOnly?'pan-y':'none'}} onPointerDown={down} onPointerMove={move} onPointerUp={end} onPointerCancel={end}><g data-template="true" pointerEvents="none">{page.objects.map(drawing)}</g><g data-answers="true">{answer.objects.map(o=><g key={o.id} data-answer-id={o.id}>{drawing(o)}</g>)}</g>{preview&&drawing(preview)}</svg></div></section>;
}
