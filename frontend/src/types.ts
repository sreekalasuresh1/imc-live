export type User = { id: string; name: string; username: string; role: 'TEACHER' | 'STUDENT' };
export type Auth = { user: User; csrf_token: string };
export type Student = User & { grade: string; subject: string; active: boolean; last_login_at: string | null; classes: string[] };
export type Member = { id: string; name: string };
export type Batch = { id: string; name: string; revision: number; students: Member[] };
export type Classroom = Omit<Batch, 'revision'> & { grade: string; subject: string; kind: 'ONE_TO_ONE' | 'BATCH'; batch_id: string | null; scheduled_at: string | null };
export type Section = 'Dashboard' | 'Students' | 'Classes' | 'Batches' | 'Homework' | 'Tests' | 'Student Work' | 'Parent Sharing' | 'Lessons' | 'Settings';

