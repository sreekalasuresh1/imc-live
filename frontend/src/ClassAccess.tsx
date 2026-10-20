import {useEffect,useState} from 'react';
import {api} from './api';
import type {Classroom} from './types';
import LiveSession from './LiveSession';
import LiveHistory from './LiveHistory';
import {flushLive} from './live-client';
type Status={open:boolean;expires_at:string|null;invitations:{id:string;student_id:string;expires_at:string;consumed:boolean;revoked:boolean}[]};
type Invitation={id:string;code:string;url:string;qr:string;expires_at:string};
export default function ClassAccess({classroom,close}:{classroom:Classroom;close:()=>void}){
 const [state,setState]=useState<Status>(),[student,setStudent]=useState(classroom.students[0]?.id||''),[minutes,setMinutes]=useState(30),[invite,setInvite]=useState<Invitation>(),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const base=`/classes/${classroom.id}`;
 async function refresh(){try{setState(await api<Status>(base+'/access'));}catch(e){setError((e as Error).message);}}
 useEffect(()=>{void refresh();},[classroom.id]);
 async function run(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <section className="panel access-panel" aria-label="Classroom access"><h2>{classroom.name} · Classroom access</h2><p>{state?.open?`Open until ${new Date(state.expires_at!).toLocaleString()}`:'Classroom access is closed.'}</p>{error&&<p role="alert" className="error">{error}</p>}
 <div className="access-actions"><button className="secondary" disabled={busy} onClick={()=>void run(async()=>{await flushLive(classroom.id);close();})}>Close access panel</button>{state?.open?<button className="secondary" disabled={busy} onClick={()=>void run(async()=>{await flushLive(classroom.id);await api(base+'/access/end','POST');setInvite(undefined);})}>End classroom access</button>:<button className="primary" disabled={busy||!state} onClick={()=>void run(async()=>{await api(base+'/access','POST',{minutes:120});setInvite(undefined);})}>Start classroom access</button>}</div>
 {state?.open&&<><fieldset disabled={busy}><legend>Invite an enrolled student</legend><label>Student<select aria-label="Invitation student" value={student} onChange={e=>{setStudent(e.target.value);setInvite(undefined);}}>{classroom.students.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Invitation valid for<select aria-label="Invitation duration" value={minutes} onChange={e=>setMinutes(Number(e.target.value))}>{[5,15,30,60,120].map(n=><option key={n} value={n}>{n} minutes</option>)}</select></label><button className="primary" disabled={!student} onClick={()=>void run(async()=>setInvite(await api<Invitation>(base+'/invitations','POST',{student_id:student,minutes})))}>Generate new invitation</button><p>Generating a new invitation ends this student's previous access to this class. Share it privately with the intended student.</p></fieldset>
 {invite&&<div className="invitation"><h3>Invitation for {classroom.students.find(s=>s.id===student)?.name}</h3><p>Use once before {new Date(invite.expires_at).toLocaleString()}.</p><label>Class code<input readOnly value={invite.code}/></label><label>Join link<input readOnly value={invite.url}/></label><img src={invite.qr} alt="Classroom invitation QR code" width={260} height={260}/><button className="secondary" disabled={busy} onClick={()=>void run(async()=>{await navigator.clipboard.writeText(invite.url);})}>Copy join link</button><p>The code and QR are shown only now. Generate a replacement if you close this panel.</p></div>}
 <h3>Current invitations</h3>{state.invitations.map(i=><div className="access-actions" key={i.id}><span>{classroom.students.find(s=>s.id===i.student_id)?.name||'Former participant'} · {i.revoked?'Revoked':i.consumed?'Redeemed':new Date(i.expires_at)<new Date()?'Expired':'Ready to join'}</span><button className="secondary" disabled={busy||i.revoked} onClick={()=>void run(async()=>{await api(base+`/invitations/${i.id}/revoke`,'POST');if(invite?.id===i.id)setInvite(undefined);})}>Revoke invitation</button></div>)}</>}
 {state?.open&&<LiveSession classroom={classroom}/>}<LiveHistory classId={classroom.id}/></section>;
}
