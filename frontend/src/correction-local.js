import {api} from './api';
import {homeworkLocal} from './homework-local';

// Independent correction outbox. It never targets the homework-answer or live APIs.
export class CorrectionSession {
 constructor(uid,snapshot,changed){Object.assign(this,{key:`correction:${uid}:${snapshot.id}`,id:snapshot.id,body:snapshot.body,revision:snapshot.revision,changed,dirty:false,pending:null,returnPending:null,blocked:false,storageFailed:false,chain:Promise.resolve(),status:'Private correction · saved on server'});}
 notify(){this.changed({body:this.body,revision:this.revision,status:this.status,busy:!!this.running,locked:!!this.returnPending||this.storageFailed,blocked:this.blocked,unsaved:this.dirty||!!this.pending||!!this.returnPending||this.storageFailed});}
 async init(){const saved=await homeworkLocal(this.key);if(saved&&(saved.dirty||saved.pending||saved.returnPending)){const revision=this.revision;Object.assign(this,saved);this.status='Recovered private correction';if(!this.pending&&!this.returnPending&&revision!==this.revision){this.blocked=true;this.status='A newer server correction exists. Download your local recovery copy before reopening.';}}this.notify();}
 persist(){const saved=structuredClone({body:this.body,revision:this.revision,dirty:this.dirty,pending:this.pending,returnPending:this.returnPending});this.chain=this.chain.then(()=>homeworkLocal(this.key,saved));return this.chain.catch(e=>{this.storageFailed=true;this.status='Local saving failed. Download your correction before closing.';this.notify();throw e;});}
 edit(body){if(this.returnPending||this.storageFailed)return;this.body=body;this.dirty=true;this.status='Saving private correction locally…';this.notify();void this.persist().then(()=>{this.status='Private correction saved locally · waiting to sync';this.notify();}).catch(()=>{});}
 async sync(){if(this.running)return this.running;if(this.blocked||this.storageFailed)return false;this.running=this.send().finally(()=>{this.running=null;this.notify();});this.notify();return this.running;}
 async send(){try{await this.chain;if(this.pending||this.dirty){if(!this.pending)this.pending={expected_revision:this.revision,key:crypto.randomUUID(),body:structuredClone(this.body)};await this.persist();const ack=await api(`/student-work/${this.id}/correction`,'PUT',this.pending);this.dirty=JSON.stringify(this.body)!==JSON.stringify(this.pending.body);this.revision=ack.revision;this.pending=null;await this.persist();this.status=this.dirty?'Private correction saved locally · waiting to sync':'Private correction · saved on server';}
  if(this.returnPending){const receipt=await api(`/student-work/${this.id}/return`,'POST',this.returnPending);this.returnPending=null;await this.persist();this.status=`Returned to student · version ${receipt.number}`;}
  return true;
 }catch(e){if(this.storageFailed)return false;if(e.status===409||e.status===422){this.blocked=true;this.status=e.message+' Your local correction is retained.';}else this.status=e.status?e.message:'Offline · private correction saved locally; retrying';return false;}}
 async flush(){for(let i=0;i<5&&(this.dirty||this.pending||this.returnPending);i++)if(!await this.sync())break;return !this.dirty&&!this.pending&&!this.returnPending&&!this.storageFailed;}
 async returnWork(){if(this.returnPending)return this.sync();if(this.blocked||this.storageFailed||!await this.flush())return false;this.returnPending={expected_revision:this.revision,key:crypto.randomUUID()};this.status='Returning correction…';this.notify();try{await this.persist();return await this.sync();}catch{return false;}}
}
