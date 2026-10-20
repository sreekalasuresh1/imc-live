import { useEffect, useRef, type ReactNode } from 'react';
import { X, ArrowUpRight, BookOpen } from 'lucide-react';

export function Empty({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon"><BookOpen size={24}/></div><h3>{title}</h3><p>{children}</p>{action}</div>;
}

export function SectionTitle({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return <div className="section-title"><div><h1>{title}</h1><p>{description}</p></div>{children}</div>;
}

export function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const el = dialog.current!; el.showModal(); return () => el.close(); }, []);
  return <dialog ref={dialog} onCancel={e => { e.preventDefault(); close(); }} aria-labelledby="modal-title"><header><h2 id="modal-title">{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={close}><X size={20}/></button></header>{children}</dialog>;
}

export function Panel({ title, children, action, onAction }: { title: string; children: ReactNode; action?: string; onAction?: () => void }) {
  return <section className="panel"><div className="panel-title"><h2>{title}</h2>{action && <button className="text-button" onClick={onAction}>{action}<ArrowUpRight size={15}/></button>}</div>{children}</section>;
}

export function dateTime(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Not scheduled';
}
