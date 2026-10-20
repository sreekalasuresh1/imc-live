import {AnswerSession} from './homework-local';

// Reuse the durable answer outbox, but isolate each teacher-authorized test attempt.
export class TestSession extends AnswerSession {
 constructor(uid,snapshot,csrf,changed){super(uid,snapshot,csrf,changed);this.key=`${uid}:${snapshot.id}:test:${snapshot.timing.attempt}`;this.deadline=null;this.setClock(snapshot.timing);}
 setClock(timing){if(timing.deadline_at){const remaining=Math.max(0,Date.parse(timing.deadline_at)-Date.parse(timing.server_now));const next=performance.now()+remaining;this.deadline=this.deadline===null?next:Math.min(this.deadline,next);}}
 remaining(){return this.deadline===null?null:Math.max(0,Math.ceil((this.deadline-performance.now())/1000));}
 expired(){return this.deadline!==null&&performance.now()>=this.deadline;}
 edit(answers){if(this.expired()){this.notify();return;}super.edit(answers);}
 notify(){if(this.expired())this.readOnly=true;super.notify();}
}
