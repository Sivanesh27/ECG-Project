import { useState, type ChangeEvent, type FormEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'
import { Logo } from '../layouts/AppLayout'
import { ErrorBox } from '../components/ui'
import { passwordProblems } from '../utils/format'

function Shell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-full grid place-items-center bg-ink px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center"><Link to="/"><Logo /></Link></div>
        <div className="panel p-6"><h1 className="text-2xl font-bold mb-5">{title}</h1>{children}</div>
      </div>
    </div>
  )
}
const Field = ({ id, label, ...p }: { id: string; label: string } & InputHTMLAttributes<HTMLInputElement>) => (
  <div className="mb-4"><label htmlFor={id} className="label">{label}</label><input id={id} className="field" {...p} /></div>
)

export function Login() {
  const { login } = useAuth(); const nav = useNavigate(); const loc = useLocation() as any
  const [email, setEmail] = useState(''); const [pw, setPw] = useState(''); const [rem, setRem] = useState(false)
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => { e.preventDefault(); setBusy(true); setErr('')
    try { await login(email, pw, rem); nav(loc.state?.from || '/app', { replace: true }) } catch (x: any) { setErr(x.message) } finally { setBusy(false) } }
  return (
    <Shell title="Sign in">
      <form onSubmit={submit} noValidate>
        {err && <div className="mb-4"><ErrorBox message={err} /></div>}
        <Field id="email" label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field id="pw" label="Password" type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} />
        <div className="flex items-center justify-between mb-5 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={rem} onChange={(e) => setRem(e.target.checked)} /> Keep me signed in</label>
          <Link to="/forgot-password" className="text-orange hover:underline">Forgot password?</Link>
        </div>
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="text-sm text-muted mt-5">No account? <Link to="/register" className="text-orange hover:underline">Create one</Link></p>
    </Shell>
  )
}

export function Register() {
  const { register } = useAuth(); const nav = useNavigate()
  const [f, setF] = useState({ name: '', email: '', password: '', confirm_password: '', organization: '', role: '' })
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof f) => (e: ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })
  const probs = passwordProblems(f.password)
  const submit = async (e: FormEvent) => { e.preventDefault(); setErr('')
    if (probs.length) return setErr('Password needs: ' + probs.join(', '))
    if (f.password !== f.confirm_password) return setErr('Passwords do not match')
    setBusy(true)
    try { await register({ ...f, organization: f.organization || null, role: f.role || null }); nav('/app', { replace: true }) } catch (x: any) { setErr(x.message) } finally { setBusy(false) } }
  return (
    <Shell title="Create your account">
      <form onSubmit={submit} noValidate>
        {err && <div className="mb-4"><ErrorBox message={err} /></div>}
        <Field id="name" label="Full name" autoComplete="name" required value={f.name} onChange={set('name')} />
        <Field id="email" label="Email" type="email" autoComplete="email" required value={f.email} onChange={set('email')} />
        <Field id="pw" label="Password" type="password" autoComplete="new-password" required value={f.password} onChange={set('password')} aria-describedby="pwhelp" />
        <p id="pwhelp" className={`-mt-2 mb-4 text-xs ${f.password && !probs.length ? 'text-green-300' : 'text-muted'}`}>{f.password && !probs.length ? '✓ Strong enough' : 'At least 10 characters with upper case, lower case and a digit.'}</p>
        <Field id="pw2" label="Confirm password" type="password" autoComplete="new-password" required value={f.confirm_password} onChange={set('confirm_password')} />
        <div className="grid grid-cols-2 gap-3"><Field id="org" label="Institution (optional)" value={f.organization} onChange={set('organization')} /><Field id="role" label="Role (optional)" value={f.role} onChange={set('role')} /></div>
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
      </form>
      <p className="text-sm text-muted mt-5">Already registered? <Link to="/login" className="text-orange hover:underline">Sign in</Link></p>
    </Shell>
  )
}

export function Forgot() {
  const [email, setEmail] = useState(''); const [done, setDone] = useState(''); const [err, setErr] = useState('')
  const submit = async (e: FormEvent) => { e.preventDefault(); try { setDone((await api.forgot(email)).message) } catch (x: any) { setErr(x.message) } }
  return (
    <Shell title="Reset your password">
      {done ? <p className="text-sm">{done}</p> : (
        <form onSubmit={submit}>{err && <ErrorBox message={err} />}
          <Field id="email" label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <button className="btn-primary w-full">Send reset link</button></form>)}
      <p className="text-sm text-muted mt-5"><Link to="/login" className="text-orange hover:underline">Back to sign in</Link></p>
    </Shell>
  )
}

export function ResetPassword() {
  const [sp] = useSearchParams(); const nav = useNavigate()
  const [pw, setPw] = useState(''); const [err, setErr] = useState('')
  const submit = async (e: FormEvent) => { e.preventDefault(); setErr('')
    try { await api.reset(sp.get('token') || '', pw); nav('/login') } catch (x: any) { setErr(x.message) } }
  return (
    <Shell title="Choose a new password">
      <form onSubmit={submit}>{err && <div className="mb-4"><ErrorBox message={err} /></div>}
        <Field id="pw" label="New password" type="password" autoComplete="new-password" required value={pw} onChange={(e) => setPw(e.target.value)} />
        <button className="btn-primary w-full">Save password</button></form>
    </Shell>
  )
}
