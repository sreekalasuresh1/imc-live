import {useEffect,useState} from 'react';
import {api} from './api';
export default function LiveHistory({classId}:{classId:string}){
 const [rows,setRows]=useState<{id:string;generation:number;sequence:number}[]>([]),[message,setMessage]=useState('');
 async function refresh(){try{setRows(await api(`/classes/${classId}/live/history`));}catch(e){setMessage((e as Error).message);}}
 useEffect(()=>{void refresh();},[classId]);
 return <section><h3>Saved live sessions</h3><button onClick={()=>void refresh()}>Refresh live history</button>{rows.map(r=><p key={r.id}>Session {r.generation} · {r.sequence} saved changes <button onClick={async()=>{try{await api(`/classes/${classId}/live/${r.id}/retain`,'POST');setMessage('A copy is available in your private notebooks.');}catch(e){setMessage((e as Error).message);}}}>Copy to private notebooks</button></p>)}{message&&<p role="status">{message}</p>}</section>;
}
