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

export interface Vehicle {
  id: string;
  owner_id: string;
  name: string;
  make: string;
  model: string;
  fuel_type: string;
  initial_odometer_km: number;
  manufacture_year: number | null;
  registration_plate: string;
  vin: string | null;
  consumption_mode: string;
  engine_displacement_cc: number | null;
  power_kw: string | null;
  tank_capacity_l: string | null;
  standard_consumption_l_100km: string | null;
  standard_methodology: string;
  standard_source: string;
  standard_source_note: string;
  status: "ACTIVE" | "ARCHIVED";
  version: number;
  history_revision: number;
  archived_at: string | null;
  effective_role: "ADMIN" | "OWNER" | "VIEWER" | "CONTRIBUTOR";
  permissions: {
    edit: boolean;
    archive: boolean;
    restore: boolean;
    manage_access: boolean;
  };
}
export interface VehicleAccess {
  id: string;
  vehicle_id: string;
  user_id: string;
  username: string;
  display_name: string;
  is_active: boolean;
  role: "VIEWER" | "CONTRIBUTOR";
  version: number;
}
