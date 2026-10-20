// Durable outbox. Acknowledgements remove work only after the authoritative event arrives.
export function liveStore(key, value) {
 return new Promise((resolve,reject)=>{
  const open=indexedDB.open('my-classroom-live',1);
  open.onupgradeneeded=()=>open.result.createObjectStore('sessions');
  open.onerror=()=>reject(open.error);
  open.onsuccess=()=>{const db=open.result,tx=db.transaction('sessions',value===undefined?'readonly':'readwrite'),s=tx.objectStore('sessions'),r=value===undefined?s.get(key):s.put(value,key);tx.oncomplete=()=>{db.close();resolve(r.result);};tx.onerror=()=>{db.close();reject(tx.error);};};
 });
}
export function applyLive(document, command) {
 const d=structuredClone(document),p=d.pages.find(p=>p.id===command.page_id),o=command.object;
 if(command.type==='add'&&p&&!d.pages.some(p=>p.objects.some(x=>x.id===o.id)))p.objects.push(o);
 if(command.type==='remove'&&p)p.objects=p.objects.filter(x=>x.id!==command.object_id);
 if(command.type==='replace'&&p)p.objects=p.objects.map(x=>x.id===command.object_id?o:x);
 if(command.type==='newPage'&&!p){d.pages.push({id:command.page_id,width:900,height:1273,objects:[]});d.activePageId=command.page_id;}
 if(command.type==='page'&&p)d.activePageId=p.id;
 return d;
}
export async function flushLive(classId){const promises=[];window.dispatchEvent(new CustomEvent('classroom-live-flush',{detail:{classId,promises}}));await Promise.all(promises);}
export class LiveClient {
 constructor(classId,csrf,changed){Object.assign(this,{classId,csrf,changed,pending:[],failed:[],online:false,stopped:false,serial:Promise.resolve()});this.offline=()=>this.ws?.close();window.addEventListener('offline',this.offline);this.watchdog=setInterval(()=>{if(this.online&&Date.now()-this.lastMessage>12000)this.ws?.close();},2000);}
 notify(){let document=this.base;for(const p of this.pending)document=applyLive(document,p.command);this.changed({document,online:this.online,pending:this.pending.length,failed:this.failed,canWrite:this.canWrite,teacher:this.teacher,boardId:this.boardId,message:this.message});}
 transaction(fn){this.serial=this.serial.then(fn).catch(e=>{this.storageFailed=true;this.canWrite=false;this.message='Local saving failed. Download a recovery copy before closing: '+e.message;this.online=false;this.ws?.close();this.notify();});return this.serial;}
 async save(){await liveStore(this.key,{pending:this.pending,failed:this.failed,document:this.base});}
 async lock(key){
  if(this.lockKey===key)return true;
  this.release?.();this.lockKey=null;
  return new Promise((resolve,reject)=>{navigator.locks.request('live-outbox:'+key,{ifAvailable:true},async lock=>{if(!lock){resolve(false);return;}this.lockKey=key;await new Promise(done=>{this.release=done;resolve(true);if(this.stopped)done();});}).catch(reject);});
 }
 connect(){if(this.stopped||this.storageFailed)return;if(!navigator.onLine){this.timer=setTimeout(()=>this.connect(),2000);return;}const ws=this.ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/join/live/${this.classId}/socket`);
  ws.onopen=()=>ws.send(JSON.stringify({type:'hello',csrf:this.csrf}));
  ws.onmessage=e=>this.transaction(async()=>{if(this.stopped||ws!==this.ws)return;this.lastMessage=Date.now();const m=JSON.parse(e.data);
   if(m.type==='snapshot'){
    this.boardId=m.board_id;this.key=m.actor+':'+m.board_id;
    if(!await this.lock(this.key)){this.base=m.document;this.canWrite=false;this.message='This live board is already open in another tab. Close that tab to reconnect here.';this.notify();ws.close();return;}
    const saved=await liveStore(this.key);
    this.pending=saved?.pending||[];this.failed=saved?.failed||[];this.base=m.document;this.sequence=m.sequence;this.canWrite=m.can_write;this.teacher=m.teacher;this.online=true;this.inflight=null;this.message='Connected';
    // IDs already in the snapshot may be retries after an acknowledgement was lost.
    await this.save();this.notify();this.pump();
   } else if(m.type==='operation'){
    if(m.sequence>this.sequence){this.base=applyLive(this.base,m.command);this.sequence=m.sequence;}
    this.pending=this.pending.filter(p=>p.operation_id!==m.operation_id);if(this.inflight===m.operation_id)this.inflight=null;await this.save();this.notify();this.pump();
   } else if(m.type==='ack'){
    // On reconnect an already committed operation is represented in the snapshot.
    if(m.sequence<=this.sequence){this.pending=this.pending.filter(p=>p.operation_id!==m.operation_id);this.inflight=null;await this.save();this.notify();this.pump();}
   } else if(m.type==='rejected'){
    const p=this.pending.find(p=>p.operation_id===m.operation_id);if(p){this.failed.push({...p,error:m.message});this.pending=this.pending.filter(x=>x!==p);this.inflight=null;await this.save();}this.message=m.message;this.notify();this.pump();
   } else if(m.type==='permission'){this.canWrite=m.can_write;this.notify();}
   else if(m.type==='transients')this.onTransients?.(m.items);
  });
  ws.onclose=e=>{if(ws!==this.ws||this.storageFailed)return;if(e.code===1008)this.canWrite=false;this.online=false;this.inflight=null;this.message='Disconnected — completed writing is queued locally. Reconnecting…';if(this.base)this.notify();if(!this.stopped)this.timer=setTimeout(()=>this.connect(),2000);};
 }
 enqueue(command){return this.transaction(async()=>{if(!this.base)throw Error('Wait for the live board.');this.pending.push({type:'operation',board_id:this.boardId,operation_id:crypto.randomUUID(),command});await this.save();this.notify();this.pump();});}
 async flush(){await this.serial;const deadline=Date.now()+8000;while(this.pending.length&&this.online&&Date.now()<deadline)await new Promise(r=>setTimeout(r,50));if(this.pending.length||this.storageFailed)throw Error('Writing is still queued locally. Reconnect and wait for 0 queued before ending or leaving the class. You can download a recovery copy now.');}
 pump(){if(!this.online||this.inflight||this.ws?.readyState!==1)return;const p=this.pending[0];if(p){this.inflight=p.operation_id;this.ws.send(JSON.stringify(p));}}
 transient(body){if(this.online&&this.ws?.readyState===1)this.ws.send(JSON.stringify(body));}
 stop(){this.stopped=true;clearTimeout(this.timer);clearInterval(this.watchdog);window.removeEventListener('offline',this.offline);this.ws?.close();void this.serial.finally(()=>this.release?.());}
}
