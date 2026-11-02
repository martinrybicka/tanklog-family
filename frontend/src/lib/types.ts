export type Theme = "SYSTEM" | "LIGHT" | "DARK";
export interface Session {
  id: string;
  username: string;
  display_name?: string;
  system_role?: "ADMIN" | "USER";
  must_change_password: boolean;
  theme?: Theme;
}
export interface User extends Session {
  display_name: string;
  email: string;
  system_role: "ADMIN" | "USER";
  is_active: boolean;
  version: number;
  theme: Theme;
  created_at: string;
  updated_at: string;
}
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface TemporaryPassword {
  user_id: string;
  temporary_password: string;
  expires_at: string;
  must_change_password: true;
}
export interface AuditEvent {
  id: string;
  occurred_at: string;
  actor_name: string | null;
  action: string;
  entity_id: string | null;
  changes: Record<string, unknown>;
}
