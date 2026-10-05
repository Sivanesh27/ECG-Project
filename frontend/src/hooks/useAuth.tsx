import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from '../services/api'
import type { User } from '../types'

interface AuthCtx {
  user: User | null; loading: boolean
  login: (email: string, password: string, remember: boolean) => Promise<void>
  register: (b: Record<string, unknown>) => Promise<void>
  logout: () => Promise<void>
}
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false)) }, [])
  const login = useCallback(async (e: string, p: string, r: boolean) => setUser(await api.login(e, p, r)), [])
  const register = useCallback(async (b: Record<string, unknown>) => setUser(await api.register(b)), [])
  const logout = useCallback(async () => { await api.logout().catch(() => undefined); setUser(null) }, [])
  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>
}
