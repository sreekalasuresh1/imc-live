import React,{useEffect,useState} from 'react';
import {portalApi} from './homework-local';
import CorrectionCanvas from './CorrectionCanvas';
export default function ReturnedCorrections({assignmentId}){
 const [rows,setRows]=useState([]),[selected,setSelected]=useState(null),[error,setError]=useState('');
 async function refresh(){try{setRows(await portalApi(`/assignments/${assignmentId}/corrections`));setError('');}catch(e){setError(e.message);}}
 useEffect(()=>{void refresh();},[assignmentId]);
 return <section className="hw-review"><h3>Returned corrections</h3><button onClick={refresh}>Refresh returned corrections</button>{error&&<p role="alert">{error}</p>}{!rows.length&&<p>No corrections have been returned yet.</p>}{rows.map(r=><button className="hw-card" key={r.id} onClick={async()=>{try{setSelected(await portalApi(`/assignments/${assignmentId}/corrections/${r.id}`));setError('');}catch(e){setError(e.message);}}}>View returned correction {r.number} · Submission {r.submission_number} · {new Date(r.returned_at).toLocaleString()}</button>)}{selected&&<><h4>Returned correction {selected.number} · Submission {selected.submission_number}</h4><p className="hw-instructions">{selected.body.comments}</p><p>Marks: {selected.body.marks||'Not specified'}</p><button onClick={()=>setSelected(null)}>Close returned correction</button><CorrectionCanvas key={selected.id} document={selected.document} body={selected.body} readOnly assetRoot={`/api/homework-portal/assignments/${assignmentId}/assets`}/></>}</section>;
}
