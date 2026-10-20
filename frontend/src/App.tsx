import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, CalendarDays, CheckCircle2, ChevronRight, CircleHelp, ClipboardList, GraduationCap, LayoutDashboard, LogOut, Menu, Plus, Search, Settings, Users, X } from 'lucide-react';
import { api, ApiError, setCsrf } from './api';
import { dateTime, Empty, Panel, SectionTitle } from './components';
import Forms from './Forms';
import Login from './Login';
import Notebooks from './Notebooks';
import Join from './Join';
import ClassAccess from './ClassAccess';
import {flushLive} from './live-client';
import HomeworkTeacher from './HomeworkTeacher';
import TestTeacher from './TestTeacher';
import HomeworkPortal from './HomeworkPortal';
import StudentWork from './StudentWork';
import ParentSharing from './ParentSharing';
import BatchWorkspace from './BatchWorkspace';
import ParentPortal from './ParentPortal';
import './access.css';
import type { Auth, Batch, Classroom, Section, Student, User } from './types';

const icons = { Dashboard: LayoutDashboard, Students: GraduationCap, Classes: CalendarDays, Batches: Users, Homework: ClipboardList, Tests: ClipboardList, 'Student Work': ClipboardList, 'Parent Sharing': Users, Lessons: BookOpen, Settings };

export default function Entry() { return location.pathname === '/parent' ? <ParentPortal/> : location.pathname === '/homework' ? <HomeworkPortal/> : location.pathname === '/join' ? <Join/> : <App/>; }
function App() {
  const [name, setName] = useState('My Classroom'); const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false); const [bootError, setBootError] = useState('');
  const [notice, setNotice] = useState('');
  const accept = useCallback((auth: Auth) => { setCsrf(auth.csrf_token); setUser(auth.user); setNotice(''); }, []);
  const boot = useCallback(async () => {
    setBootError(''); setReady(false);
    try {
      const config = await api<{ app_name: string }>('/config'); setName(config.app_name); document.title = config.app_name;
      try { accept(await api<Auth>('/auth/me')); } catch (e) { if (!(e instanceof ApiError) || e.status !== 401) throw e; }
    } catch { setBootError('The classroom server could not be reached. Check that the backend is running, then try again.'); }
    finally { setReady(true); }
  }, [accept]);
  useEffect(() => { void boot(); }, [boot]);
  useEffect(() => {
    function expired() { setUser(current => { if (current) setNotice('Your session has ended. Please sign in again.'); return null; }); setCsrf(''); }
    window.addEventListener('session-expired', expired); return () => window.removeEventListener('session-expired', expired);
  }, []);
  if (!ready) return <main className="fatal"><BookOpen size={32}/><p>Opening your classroom…</p></main>;
  if (bootError) return <main className="fatal"><h1>Let’s reconnect</h1><p role="alert">{bootError}</p><button className="primary" onClick={boot}>Try again</button></main>;
  return user ? <Workspace key={user.id} name={name} user={user} signedOut={message => { setUser(null); setCsrf(''); setNotice(message); }}/>
    : <Login name={name} onLogin={accept} notice={notice}/>;
}

function Workspace({ name, user, signedOut }: { name: string; user: User; signedOut: (message: string) => void }) {
  const teacher = user.role === 'TEACHER';
  const [accessClass,setAccessClass]=useState<Classroom>();
  const [notebookDirty,setNotebookDirty]=useState(false);
  const [section, setSection] = useState<Section>(teacher && location.pathname==='/student-work'?'Student Work':'Dashboard'); const [menu, setMenu] = useState(false);
  const [students, setStudents] = useState<Student[]>([]); const [classes, setClasses] = useState<Classroom[]>([]); const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [toast, setToast] = useState(''); const [query, setQuery] = useState('');
  const [form, setForm] = useState<'student' | 'class' | 'batch' | 'roster' | null>(null); const [editing, setEditing] = useState<Classroom>();
  const refresh = useCallback(async () => {
    setError(''); setLoading(true);
    try {
      const [c, s, b] = await Promise.all([api<Classroom[]>('/classes'), teacher ? api<Student[]>('/students') : Promise.resolve([]), teacher ? api<Batch[]>('/batches') : Promise.resolve([])]);
      setClasses(c); setStudents(s); setBatches(b);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load your classroom'); }
    finally { setLoading(false); }
  }, [teacher]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { if (toast) { const id = setTimeout(() => setToast(''), 5000); return () => clearTimeout(id); } }, [toast]);
  useEffect(() => { const fn = () => void refresh(); window.addEventListener('focus', fn); return () => window.removeEventListener('focus', fn); }, [refresh]);
  function navigate(next: Section) { if(notebookDirty){setError("Save your work before leaving this workspace.");return;} setSection(next); setQuery(''); setMenu(false); }
  async function logout() { if(notebookDirty){setError("Save your work before signing out.");return;} try { await api('/auth/logout', 'POST'); signedOut('You have been signed out.'); } catch (e) { setError(e instanceof Error ? e.message : 'Sign out failed'); } }
  const sections: Section[] = teacher ? ['Dashboard', 'Students', 'Classes', 'Batches', 'Homework', 'Tests', 'Student Work', 'Parent Sharing', 'Lessons', 'Settings'] : ['Dashboard', 'Classes', 'Homework', 'Tests', 'Lessons', 'Settings'];
  const filtered = students.filter(s => `${s.name} ${s.username} ${s.grade}`.toLowerCase().includes(query.toLowerCase()));
  const today = classes.filter(c => c.scheduled_at && new Date(c.scheduled_at).toDateString() === new Date().toDateString()).sort((a, b) => a.scheduled_at!.localeCompare(b.scheduled_at!));
  const upcoming = classes.filter(c => c.scheduled_at && new Date(c.scheduled_at) > new Date() && !today.includes(c)).sort((a, b) => a.scheduled_at!.localeCompare(b.scheduled_at!));
  function cards(items: Classroom[]) { return <div className="class-list">{items.map(c => <article className="class-card" key={c.id}><span className="class-icon">x²</span><div className="class-info"><span className="eyebrow">GRADE {c.grade} <span>·</span> {c.kind === 'ONE_TO_ONE' ? '1-TO-1' : 'BATCH'}</span><h3>{c.name}</h3><p>{c.subject} · {teacher ? c.students.map(s => s.name).join(', ') : 'You are enrolled'}</p><span className="schedule"><CalendarDays size={13}/>{dateTime(c.scheduled_at)}</span></div><div className="class-actions">{teacher && <button className="secondary small" onClick={()=>setAccessClass(c)}>Classroom access</button>}{teacher && <button className="secondary small" onClick={() => { setEditing(c); setForm('roster'); }}>Edit students</button>}<span className="phase-tag" title="Open Classroom access to teach live">Live room · Phase 10</span></div></article>)}</div>; }
  return <div className="workspace">
    {menu && <button aria-label="Close navigation" className="mobile-scrim" onClick={() => setMenu(false)}/>}
    <aside className={`sidebar ${menu ? 'open' : ''}`}><button className="brand" onClick={() => navigate('Dashboard')}><span className="brand-icon"><BookOpen size={22}/></span><span>{name}</span></button><div className="workspace-label">{teacher ? 'TEACHER WORKSPACE' : 'STUDENT WORKSPACE'}</div><nav aria-label="Main navigation">{sections.map(s => { const Icon = icons[s]; return <button key={s} aria-current={section === s ? 'page' : undefined} className={section === s ? 'active' : ''} onClick={() => navigate(s)}><Icon size={19}/>{s}</button>; })}</nav><div className="sidebar-bottom"><div className="private-note"><LockMark/><strong>Your private classroom</strong><p>A space for you and your students.</p></div><div className="profile"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span><div><strong>{user.name}</strong><small>{teacher ? 'Teacher' : 'Student'}</small></div><button className="icon-button" onClick={logout} aria-label="Sign out"><LogOut size={17}/></button></div></div></aside>
    <div className="main-column"><header className="topbar"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenu(true)}><Menu size={22}/></button><div className="breadcrumb">Workspace <ChevronRight size={14}/><strong>{section}</strong></div><div className="topbar-right"><span className="access-dot"/>Private workspace<span className="top-date">{new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date())}</span></div></header><main className="content">
      {error && <div className="error-banner" role="alert">{error}<button className="text-button" onClick={refresh}>Retry</button></div>}
      {section === 'Dashboard' && <><SectionTitle title={`Welcome back, ${user.name.split(' ')[0]}.`} description={teacher ? 'A clear view of your teaching day.' : 'Your classes and learning, all in one place.'}>{teacher && <button className="primary" onClick={() => setForm('class')}><Plus size={18}/>Create class</button>}</SectionTitle>
        <div className="stats"><Stat label={teacher ? 'YOUR STUDENTS' : 'YOUR CLASSES'} value={loading ? '—' : String(teacher ? students.length : classes.length)} detail={teacher ? 'Ready to learn' : 'Assigned to you'} icon={<Users size={19}/>}/><Stat label="TODAY’S CLASSES" value={loading ? '—' : String(today.length)} detail={today.length ? 'On your schedule' : 'A little room to prepare'} icon={<CalendarDays size={19}/>}/><Stat label="HOMEWORK TO REVIEW" value="—" detail="Open Homework" icon={<ClipboardList size={19}/>}/><Stat label="SAVED LESSONS" value="—" detail="Open Lessons" icon={<BookOpen size={19}/>}/></div>
        <div className="dashboard-grid"><div><Panel title="Today’s classes" action="All classes" onAction={() => navigate('Classes')}>{loading ? <p className="loading">Loading classes…</p> : today.length ? cards(today) : <Empty title="A fresh page for today">{teacher ? 'Create a class and choose a time to see it here.' : 'No classes are scheduled for today.'}{teacher && <button className="text-button centered" onClick={() => setForm('class')}>Schedule a class<ArrowRight size={16}/></button>}</Empty>}</Panel><Panel title="Upcoming classes">{upcoming.length ? cards(upcoming.slice(0, 3)) : <div className="simple-empty"><CalendarDays size={20}/><p>Your next scheduled classes will appear here.</p></div>}</Panel></div><div><section className="start-card"><span className="eyebrow">{teacher ? 'MAKE ROOM FOR LEARNING' : 'YOUR NEXT STEP'}</span><h2>{teacher ? 'Your classroom starts with a student.' : 'Good learning takes practice.'}</h2><p>{teacher ? 'Add your students, then bring them together in a private class.' : 'Your teacher will assign your classes here. Check back before your next lesson.'}</p>{teacher && <button className="primary" onClick={() => setForm('student')}>Add a student<Plus size={17}/></button>}<div className="start-steps"><span><CheckCircle2 size={16}/>Account ready</span><span><span className="step-dot">2</span>{teacher ? 'Add students' : 'View your classes'}</span><span><span className="step-dot">3</span>{teacher ? 'Create a class' : 'Get ready to learn'}</span></div></section><Panel title="Homework"><div className="simple-empty"><ClipboardList size={20}/><p>Open Homework to upload drafts, assign work and view submissions.</p></div></Panel><Panel title="Recent lessons"><div className="simple-empty"><BookOpen size={20}/><p>Open Lessons to create or reopen a private notebook.</p></div></Panel></div></div></>}
      {section === 'Students' && teacher && <><SectionTitle title="Your students" description="A personal learning space for every student."><button className="primary" onClick={() => setForm('student')}><Plus size={18}/>Add student</button></SectionTitle><section className="panel"><div className="panel-title"><h2>Student directory <span className="count">{students.length}</span></h2><label className="search"><Search size={17}/><input aria-label="Search students" placeholder="Search students…" value={query} onChange={e => setQuery(e.target.value)}/></label></div>{loading ? <p className="loading">Loading students…</p> : filtered.length ? <div className="table-scroll"><table><thead><tr><th>Student</th><th>Grade / subject</th><th>Classes</th><th>Last sign-in</th><th>Homework</th></tr></thead><tbody>{filtered.map(s => <tr key={s.id}><td><div className="student-name"><span className="avatar pale">{s.name[0]}</span><div><strong>{s.name}</strong><small>{s.username}</small></div></div></td><td>Grade {s.grade}<small>{s.subject}</small></td><td>{s.classes.length ? s.classes.join(', ') : <span className="muted">Not assigned</span>}</td><td><span className={`badge ${s.last_login_at ? 'green' : ''}`}>{s.last_login_at ? 'Has signed in' : 'Not yet signed in'}</span>{s.last_login_at && <small>{dateTime(s.last_login_at)}</small>}</td><td><span className="muted">Phase 12</span></td></tr>)}</tbody></table></div> : <Empty title={query ? 'No matching students' : 'Meet your first student'}>{query ? 'Try another name or grade.' : 'Add a student to create their private login and get started.'}</Empty>}</section></>}
      {accessClass && teacher && <ClassAccess key={accessClass.id} classroom={accessClass} close={()=>setAccessClass(undefined)}/>} 
      {section === 'Classes' && <><SectionTitle title={teacher ? 'Your classes' : 'My classes'} description={teacher ? 'Individual attention or a small group. Make the space yours.' : 'The classes your teacher has assigned to you.'}>{teacher && <button className="primary" onClick={() => setForm('class')}><Plus size={18}/>Create class</button>}</SectionTitle><Panel title={`${classes.length} ${classes.length === 1 ? 'class' : 'classes'}`}>{loading ? <p className="loading">Loading classes…</p> : classes.length ? cards(classes) : <Empty title="Your first class belongs here">{teacher ? 'Choose a student for a 1-to-1 lesson, or create a batch class.' : 'Your teacher will add you to a class soon.'}</Empty>}</Panel><p className="feature-note"><CircleHelp size={16}/>Use Classroom access to open the live board and invite students.</p></>}
      {section === 'Batches' && teacher && <BatchWorkspace students={students} onChanged={refresh} onOpenClass={async (c:Classroom)=>{try{if(accessClass)await flushLive(accessClass.id);setAccessClass(c);}catch(e){setError(e instanceof Error?e.message:'Save the current classroom before switching.');}}} onDirty={setNotebookDirty}/>}
      {section === 'Homework' && (teacher ? <HomeworkTeacher students={students} batches={batches}/> : <section><h1>My homework</h1><p>Open your homework portal to save answers and submit work.</p><a href='/homework'>Open my homework</a></section>)}
      {section === 'Tests' && (teacher ? <TestTeacher students={students} batches={batches}/> : <section><h1>My tests</h1><p>Open your work portal to start an assigned test.</p><a href='/homework'>Open my tests</a></section>)}
      {section === 'Lessons' && <Notebooks userId={user.id} onDirty={setNotebookDirty}/>} 
      {section === 'Student Work' && teacher && <StudentWork userId={user.id} classes={classes} onDirty={setNotebookDirty}/>}
      {section === 'Parent Sharing' && teacher && <ParentSharing/>}
      {section === 'Settings' && <><SectionTitle title="Account settings" description="Keep your classroom account secure."/><div className="settings-grid"><Panel title="Your account"><dl><dt>Name</dt><dd>{user.name}</dd><dt>Username</dt><dd>{user.username}</dd><dt>Role</dt><dd>{teacher ? 'Teacher' : 'Student'}</dd></dl></Panel><Panel title="Change password"><PasswordForm done={() => signedOut('Password changed. Please sign in with your new password.')}/></Panel></div></>}
      <footer className="workspace-footer"><span>{name}</span><span>Phase 18</span></footer>
    </main></div>{form && <Forms mode={form} students={students} batches={batches} classroom={editing} close={() => setForm(null)} saved={() => { setForm(null); setToast(form === 'student' ? 'Student created. Share optional sign-in credentials privately if provided.' : 'Saved successfully.'); void refresh(); }}/>} {toast && <div className="toast" role="status"><CheckCircle2 size={18}/>{toast}<button aria-label="Dismiss message" className="icon-button" onClick={() => setToast('')}><X size={16}/></button></div>}
  </div>;
}

function LockMark() { return <span className="lock-mark"><BookOpen size={17}/></span>; }
function Stat({ label, value, detail, icon }: { label: string; value: string; detail: string; icon: React.ReactNode }) { return <div className="stat"><div><span>{label}</span>{icon}</div><strong>{value}</strong><small>{detail}</small></div>; }
function PasswordForm({ done }: { done: () => void }) {
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const d = new FormData(e.currentTarget); setError('');
    if (d.get('new') !== d.get('confirm')) { setError('The new passwords do not match'); return; }
    setBusy(true); try { await api('/auth/password', 'POST', { current_password: d.get('current'), new_password: d.get('new') }); done(); } catch (e) { setError(e instanceof Error ? e.message : 'Could not update password'); } finally { setBusy(false); }
  }
  return <form className="password-form" onSubmit={submit}><label>Current password<input name="current" type="password" required autoComplete="current-password" maxLength={128}/></label><label>New password<input name="new" type="password" required minLength={12} maxLength={128} autoComplete="new-password"/><small>At least 12 characters.</small></label><label>Confirm new password<input name="confirm" type="password" required minLength={12} maxLength={128} autoComplete="new-password"/></label>{error && <p className="error" role="alert">{error}</p>}<p className="muted">Changing your password signs out all your sessions.</p><button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Update password'}</button></form>;
}





