import { useState, type FormEvent } from 'react';
import { api } from './api';
import { Modal } from './components';
import type { Batch, Classroom, Student } from './types';

type Props = { mode: 'student' | 'class' | 'batch' | 'roster'; students: Student[]; batches: Batch[]; classroom?: Classroom; close: () => void; saved: () => void };
export default function Forms({ mode, students, batches, classroom, close, saved }: Props) {
  const [selected, setSelected] = useState<string[]>(classroom?.students.map(s => s.id) || []);
  const [kind, setKind] = useState(classroom?.kind || 'ONE_TO_ONE');
  const [batchId, setBatchId] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const title = { student: 'Add a student', class: 'Create a class', batch: 'Create a batch', roster: 'Edit class students' }[mode];
  function toggle(id: string) { setSelected(current => current.includes(id) ? current.filter(i => i !== id) : (mode === 'class' || mode === 'roster') && kind === 'ONE_TO_ONE' ? [id] : [...current, id]); }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(''); const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      if (mode === 'student') await api('/students', 'POST', { ...data, username: String(data.username).trim().toLowerCase() || undefined, password: data.password || undefined, grade: String(data.grade) });
      else if (mode === 'batch') await api('/batches', 'POST', { name: data.name, student_ids: selected });
      else if (mode === 'roster') await api(`/classes/${classroom!.id}/members`, 'PUT', { student_ids: selected });
      else await api('/classes', 'POST', { name: data.name, subject: data.subject, grade: String(data.grade), kind, batch_id: batchId || null, student_ids: selected, scheduled_at: data.scheduled_at ? new Date(String(data.scheduled_at)).toISOString() : null });
      saved();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save'); } finally { setBusy(false); }
  }
  return <Modal title={title} close={() => { if (!busy) close(); }}><form onSubmit={submit}>
    {mode !== 'roster' && <label>{mode === 'student' ? 'Student name' : 'Name'}<input autoFocus name="name" required maxLength={120} placeholder={mode === 'student' ? 'Student A' : mode === 'batch' ? 'Grade 8 · Algebra group' : 'Algebra · 1-to-1'}/></label>}
    {mode === 'student' && <><label>Username<input name="username" minLength={3} maxLength={80} pattern="[a-zA-Z0-9._\-]+" autoComplete="off" placeholder="student.a"/><small>Letters, numbers, dots, underscores, and hyphens.</small></label><label>Initial password<input name="password" type="password" minLength={12} maxLength={128} autoComplete="new-password"/><small>Optional password sign-in: provide both fields or leave both empty. Temporary access arrives next.</small></label></>}
    {(mode === 'student' || mode === 'class') && <div className="form-row"><label>Grade<input name="grade" defaultValue="8" maxLength={100} placeholder="Grade or level"/></label><label>Subject<input name="subject" defaultValue="Mathematics" required maxLength={80}/></label></div>}
    {mode === 'class' && <><label>Class type<select value={kind} onChange={e => { setKind(e.target.value as typeof kind); setSelected([]); setBatchId(''); }}><option value="ONE_TO_ONE">1-to-1</option><option value="BATCH">Batch / group</option></select></label>{kind === 'BATCH' && <label>Use a saved batch (optional)<select value={batchId} onChange={e => { setBatchId(e.target.value); setSelected(batches.find(b => b.id === e.target.value)?.students.map(s => s.id) || []); }}><option value="">Choose students individually</option>{batches.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>}<label>Class date and time (optional)<input name="scheduled_at" type="datetime-local"/><small>Your local timezone: {Intl.DateTimeFormat().resolvedOptions().timeZone}</small></label></>}
    {mode !== 'student' && <fieldset><legend>Students <span className="muted">({selected.length} selected)</span></legend>{mode === 'roster' && <small>Changes apply to this class only. At least one student is required.</small>}{students.length === 0 ? <p className="muted">Add a student first, then create your class or batch.</p> : <div className="student-picker">{students.map(s => <label key={s.id} className="check-row"><input type="checkbox" checked={selected.includes(s.id)} disabled={!!batchId} onChange={() => toggle(s.id)}/><span>{s.name}<small>Grade {s.grade} · {s.username}</small></span></label>)}</div>}</fieldset>}
    {error && <p className="error" role="alert">{error}</p>}<footer className="form-actions"><button type="button" className="secondary" onClick={close} disabled={busy}>Cancel</button><button className="primary" disabled={busy || (mode !== 'student' && selected.length === 0)}>{busy ? 'Saving…' : mode === 'roster' ? 'Save students' : title}</button></footer>
  </form></Modal>;
}

