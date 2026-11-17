import { create } from 'zustand';
import { api, getStoredUser, getToken, setStoredUser, setToken } from '@/lib/api';
import type { User } from '@/lib/types';

interface AuthState {
  user: User | null;
  token: string | null;
  initialized: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
  setUser: (user: User | null) => void;
}

export const useAuth = create<AuthState>((set, get) => ({
  user: getStoredUser(),
  token: getToken(),
  initialized: true,
  loading: false,

  async login(email, password) {
    set({ loading: true });
    try {
      const res = await api<{ access_token: string; user: User }>('/api/auth/login', {
        method: 'POST',
        body: { email, password },
      });
      setToken(res.access_token);
      setStoredUser(res.user);
      set({ user: res.user, token: res.access_token, loading: false });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },

  async register(name, email, password) {
    set({ loading: true });
    try {
      const res = await api<{ access_token: string; user: User }>('/api/auth/register', {
        method: 'POST',
        body: { name, email, password },
      });
      setToken(res.access_token);
      setStoredUser(res.user);
      set({ user: res.user, token: res.access_token, loading: false });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },

  logout() {
    setToken(null);
    setStoredUser(null);
    set({ user: null, token: null });
  },

  async refreshMe() {
    if (!get().token) return;
    try {
      const res = await api<User>('/api/auth/me');
      setStoredUser(res);
      set({ user: res });
    } catch {
      // ignore — profile stays cached
    }
  },

  setUser(user) {
    setStoredUser(user);
    set({ user });
  },
}));

export async function refreshUserProfile() {
  await useAuth.getState().refreshMe();
}