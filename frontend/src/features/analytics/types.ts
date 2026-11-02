export interface Period {
  period: "day" | "week" | "month" | "year" | "custom";
  anchor_date: string | null;
  date_from: string;
  date_to: string;
  group_by: "day" | "week" | "month";
  timezone: string;
}
export interface Totals {
  liters: string;
  amount: string;
  distance_km: number;
  valid_intervals: number;
  excluded_intervals: number;
  consumption_l_100km: string | null;
  purchase_cost_czk_100km: string | null;
}
export interface Interval {
  vehicle_id: string;
  start_id: string;
  end_id: string;
  start_date: string;
  end_date: string;
  start_odometer_km: number;
  end_odometer_km: number;
  liters: string;
  amount: string;
  distance_km: number;
  fuel_type: string;
  status: string;
  reasons: string[];
  warnings: string[];
  consumption_l_100km: string | null;
  purchase_cost_czk_100km: string | null;
  crosses_period_start: boolean;
  explanation: string;
  record_ids: string[];
}
export interface IntervalRecord {
  id: string;
  date: string;
  day_sequence: number;
  liters: string;
  total_amount: string;
  odometer_km: number | null;
  fuel_type: string;
  is_full_tank: boolean;
  break_before: boolean;
  used_for_totals: boolean;
}
export interface IntervalDetail extends Interval {
  records: IntervalRecord[];
  period: Period;
  history_revision: number;
}
export interface PurchasePoint {
  date: string;
  amount: string;
  liters: string;
  count: number;
  unit_price: string | null;
}
export interface Statistics {
  available_vehicles: { id: string; name: string; status: string }[];
  period: Period;
  explanation: string;
  purchases: {
    amount: string;
    liters: string;
    count: number;
    realized_unit_price: string | null;
  };
  consumption_l_100km: string | null;
  purchase_cost_czk_100km: string | null;
  consumption_by_fuel: (Totals & { fuel_type: string })[];
  comparison: {
    standard: string;
    difference_l_100km: string;
    difference_percent: string;
    methodology: string;
    source: string;
    source_note: string;
  } | null;
  coverage: {
    valid_intervals: number;
    excluded_intervals: number;
    distance_km: number;
    start_date: string | null;
    end_date: string | null;
    reasons: { code: string; count: number }[];
    vehicles: (Totals & {
      vehicle_id: string;
      name: string;
      status: string;
      reasons: string[];
      missing_odometer_ids: string[];
      open_record_ids: string[];
    })[];
  };
  charts: { purchases: PurchasePoint[]; consumption: Interval[] };
  recent_refuelings: (IntervalRecord & {
    vehicle_id: string;
    vehicle_name: string;
  })[];
}
