import {useEffect,useState} from 'react';
import {api} from './api';
import LiveBoard from './LiveBoard';
import type {Classroom} from './types';
export default function LiveSession({classroom}:{classroom:Classroom}){
 const [sources,setSources]=useState<{id:string;title:string}[]>([]),[source,setSource]=useState(''),[csrf,setCsrf]=useState(''),[open,setOpen]=useState(false),[error,setError]=useState('');
 useEffect(()=>{void api<{id:string;title:string}[]>('/documents').then(setSources).catch(e=>setError(e.message));void api<{csrf_token:string}>('/auth/me').then(s=>setCsrf(s.csrf_token)).catch(e=>setError(e.message));},[]);
 async function start(){try{await api(`/classes/${classroom.id}/live`,'POST',{source_id:source||null});setOpen(true);setError('');}catch(e){setError((e as Error).message);}}
 return <div><h3>Teach live</h3><p>Publish a copy of a prepared web notebook, or start with a blank board. An existing live session resumes without replacing its work.</p>{!open&&<><label>Notebook to publish<select value={source} onChange={e=>setSource(e.target.value)}><option value="">Blank live board</option>{sources.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label><button disabled={!csrf} onClick={()=>void start()}>Open live classroom</button></>}{error&&<p role="alert">{error}</p>}{open&&csrf&&<LiveBoard classId={classroom.id} csrf={csrf} students={classroom.students}/>}</div>;
}
