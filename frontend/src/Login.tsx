import { useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, Check, Eye, EyeOff, LockKeyhole } from 'lucide-react';
import { api } from './api';
import type { Auth } from './types';

export default function Login({ name, onLogin, notice }: { name: string; onLogin: (auth: Auth) => void; notice: string }) {
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [visible, setVisible] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError('');
    const data = new FormData(e.currentTarget);
    try { onLogin(await api<Auth>('/auth/login', 'POST', { username: String(data.get('username')).trim().toLowerCase(), password: data.get('password') })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Sign in failed'); } finally { setBusy(false); }
  }
  return <div className="login-layout"><aside className="login-story"><a className="brand" href="/"><span className="brand-icon"><BookOpen size={23}/></span>{name}</a><div className="story-copy"><span className="eyebrow">A LITTLE CLARITY. A LOT OF POSSIBILITY.</span><h1>Great learning<br/>starts here.</h1><p>A private space for your students,<br/>your lessons, and their next breakthrough.</p><div className="math-card"><span className="math-caption">ONE STEP AT A TIME</span><div>2x + 3 = 11</div><div>2x = 8</div><div className="math-answer">x = 4 <Check size={27}/></div><span className="math-note">There’s always a way forward.</span></div></div><span className="story-footer">Your classroom. Your teaching. Your space.</span></aside><main className="login-main"><div className="login-form"><span className="login-lock"><LockKeyhole size={23}/></span><h2>Welcome to your classroom</h2><p>Sign in with your teacher or student account.</p>{notice && <div className="notice" role="status">{notice}</div>}<form onSubmit={submit}><label>Username<input name="username" autoComplete="username" required minLength={3} maxLength={80} placeholder="Your username" autoFocus/></label><label>Password<span className="password-input"><input name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" required maxLength={128} placeholder="Your password"/><button type="button" className="icon-button" aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18}/> : <Eye size={18}/>}</button></span></label>{error && <p className="error" role="alert">{error}</p>}<button className="primary wide" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<ArrowRight size={18}/></button></form><div className="login-help"><strong>Need access?</strong><p>Have a class invitation? <a href="/join">Join without a password</a>. For optional account sign-in, use the credentials your teacher provided.</p></div></div><footer>Private access · Teacher and student accounts</footer></main></div>;
}

