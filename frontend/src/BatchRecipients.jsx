import React,{useEffect,useState} from 'react';
import {api} from './api';

export default function BatchRecipients({id,onReview}){
 const [value,setValue]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[checked,setChecked]=useState(false);
 useEffect(()=>{setValue(null);setChecked(false);setError('');onReview(null);},[id,onReview]);
 return <section><button disabled={busy} onClick={async()=>{setBusy(true);setError('');setChecked(false);onReview(null);try{setValue(await api('/batches/'+id));}catch(e){setValue(null);setError(e.message);}finally{setBusy(false);}}}>Review batch recipients</button>{error&&<p role="alert">{error}</p>}{value&&<><p><strong>{value.name}</strong> · {value.students.length} recipients: {value.students.map(s=>s.name+(s.active?'':' (inactive)')).join(', ')}</p><p>Each student receives a private answer workspace. Later batch edits will not change this assignment.</p><label><input type="checkbox" checked={checked} disabled={value.students.some(s=>!s.active)} onChange={e=>{setChecked(e.target.checked);onReview(e.target.checked?value:null);}}/>I reviewed these batch recipients.</label></>}</section>;
}
