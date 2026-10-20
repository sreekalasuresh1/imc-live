export function homeworkLocal(key,value){return new Promise((resolve,reject)=>{const open=indexedDB.open('my-classroom-homework',1);open.onupgradeneeded=()=>open.result.createObjectStore('answers');open.onerror=()=>reject(open.error);open.onsuccess=()=>{const db=open.result,tx=db.transaction('answers',value===undefined?'readonly':'readwrite'),s=tx.objectStore('answers'),r=value===undefined?s.get(key):value===null?s.delete(key):s.put(value,key);tx.oncomplete=()=>{db.close();resolve(r.result);};tx.onerror=()=>{db.close();reject(tx.error);};};});}
export async function portalApi(path,method='GET',body,csrf=''){
 const r=await fetch('/api/homework-portal'+path,{method,credentials:'same-origin',headers:{...(body?{'Content-Type':'application/json'}:{}),...(method!=='GET'?{'X-CSRF-Token':csrf}:{})},body:body?JSON.stringify(body):undefined});
 if(!r.ok){const data=await r.json().catch(()=>({}));throw Object.assign(Error(typeof data.detail==='string'?data.detail:'Homework request failed.'),{status:r.status});}return r.status===204?null:r.json();
}
export class AnswerSession {
 constructor(uid,snapshot,csrf,changed){Object.assign(this,{key:uid+':'+snapshot.id,id:snapshot.id,snapshot,csrf,changed,answers:snapshot.answers,revision:snapshot.revision,dirty:false,pending:null,submitPending:null,blocked:false,storageFailed:false,chain:Promise.resolve(),status:'Saved on server'});}
 notify(){this.changed({answers:this.answers,status:this.status,dirty:this.dirty,locked:this.readOnly||!!this.submitPending||this.storageFailed,blocked:this.blocked,busy:!!this.running,submitted:this.snapshot.status==='SUBMITTED'});}
 async init(){this.readOnly=this.snapshot.status==='SUBMITTED';const saved=await homeworkLocal(this.key);if(saved&&(saved.dirty||saved.pending||saved.submitPending)){Object.assign(this,saved);if(!this.pending&&!this.submitPending&&this.revision!==this.snapshot.revision){this.blocked=true;this.status='A newer server draft exists. Your local answers are retained for recovery.';}else this.status='Recovered local answers';}this.notify();}
 persist(){const value=structuredClone({answers:this.answers,revision:this.revision,dirty:this.dirty,pending:this.pending,submitPending:this.submitPending});this.chain=this.chain.then(()=>homeworkLocal(this.key,value));return this.chain.catch(e=>{this.storageFailed=true;this.status='Local saving failed. Download your answers before closing.';this.notify();throw e;});}
 edit(answers){if(this.readOnly||this.submitPending||this.storageFailed)return;this.answers=answers;this.dirty=true;this.status='Saving locally…';this.notify();void this.persist().then(()=>{this.status='Saved locally · waiting to sync';this.notify();}).catch(()=>{});}
 async sync(){if(this.running)return this.running;if(this.blocked||this.storageFailed)return false;
  this.running=this.send().finally(()=>{this.running=null;this.notify();});this.notify();return this.running;
 }
 async send(){try{
  await this.chain;
  if(this.pending||this.dirty){
   if(!this.pending)this.pending={expected_revision:this.revision,save_key:crypto.randomUUID(),answers:structuredClone(this.answers)};
   await this.persist();const ack=await portalApi(`/assignments/${this.id}/draft`,'PUT',this.pending,this.csrf);
   this.dirty=JSON.stringify(this.answers)!==JSON.stringify(this.pending.answers);this.revision=ack.revision;this.pending=null;await this.persist();this.status=this.dirty?'Saved locally · waiting to sync':'Saved on server';
  }
  if(this.submitPending){const receipt=await portalApi(`/assignments/${this.id}/submit`,'POST',this.submitPending,this.csrf);this.submitPending=null;this.snapshot.status='SUBMITTED';this.readOnly=true;await this.persist();this.status=`Submitted · version ${receipt.number} · ${new Date(receipt.submitted_at).toLocaleString()}`;}
  return true;
 }catch(e){if(this.storageFailed)return false;if(e.status===409||e.status===422){this.blocked=true;this.status=e.message+' Local answers are retained; download a recovery copy.';}else this.status=e.status?e.message:'Offline · answers saved locally; retrying when connected';return false;}}
 async submit(){if(this.submitPending)return this.sync();if(this.readOnly||this.blocked||this.storageFailed)return;for(let i=0;i<5&&(this.dirty||this.pending);i++)if(!await this.sync())return;if(this.dirty||this.pending)return;this.submitPending={expected_revision:this.revision,submit_key:crypto.randomUUID()};this.status='Submitting…';this.notify();try{await this.persist();await this.sync();}catch{}}
 async flush(){for(let i=0;i<5&&(this.dirty||this.pending||this.submitPending);i++)if(!await this.sync())break;return !this.dirty&&!this.pending&&!this.submitPending&&!this.storageFailed;}
}
