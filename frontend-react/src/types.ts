/**
 * TRUTHLINE — shared types
 * ==========================================================================
 * These mirror the FastAPI response shapes in api/main.py. Every field here
 * was read off a live response, not guessed. When the backend changes, change
 * this file first.
 */

// ── Verdicts ──────────────────────────────────────────────────────────────
// The Judge's five possible outputs, in priority order (first match wins).
export type Verdict = 'SUPPORTED' | 'CONFLICTING' | 'STALE' | 'UNCERTAIN' | 'UPDATED';

export type FreshnessLabel = 'FRESH' | 'AGING' | 'STALE' | 'EXPIRED';

export type SourceType = 'drone' | 'ground' | 'satellite' | 'intel';

export type RelationType = 'contradicts' | 'supports' | 'unrelated';

export type Threat = 'low' | 'elevated' | 'high';

export type EquipmentStatus = 'online' | 'degraded' | 'offline';

// ── Health ────────────────────────────────────────────────────────────────
export interface HealthResponse {
  status: string;
  time: string;
  qdrant: { available: boolean; error?: string };
  sqlite: { path: string; tables: string[] };
  llm: { available: boolean; model: string };
  tau: Record<string, number>;
  stale_threshold: number;
  verdict_counts: Record<string, number>;
  avg_freshness: number;
  totals: {
    sources: number;
    claims: number;
    relations: number;
    gaps: number;
    decisions: number;
  };
}

// ── Cases (the labelled validation fixtures) ──────────────────────────────
export interface CaseSummary {
  case_id: string;
  name: string;
  expected_verdict: string;
  report_count: number;
}

export interface CasesResponse {
  cases: CaseSummary[];
}

// ── Operational area ──────────────────────────────────────────────────────
export interface Area {
  area_id: string;
  name: string;
  designation: string | null;
  created_at?: string;
}

export interface Zone {
  zone_id: string;
  name: string;
  description: string | null;
  threat: Threat | string;
  report_count: number;
  source_count: number;
  stale_count: number;
  avg_freshness: number;
  sources: string[];
}

export interface Equipment {
  equipment_id: string;
  area_id: string;
  name: string;
  source_type: SourceType | string;
  zone_id: string | null;
  status: EquipmentStatus | string;
  created_at?: string;
}

/** A field report — the shape the pipeline consumes. */
export interface Report {
  id: string;
  source: string;
  source_type: SourceType | string;
  location: string;
  event: string;
  timestamp: string;
  reliability_class?: string | null;
}

export interface AreaResponse {
  area: Area | null;
  zones: Zone[];
  equipment: Equipment[];
  reports: Report[];
  report_count: number;
  zone_count: number;
  equipment_count: number;
}

// ── Claims (what the decay agent returns) ─────────────────────────────────
export interface Claim {
  id: string;
  source: string;
  source_type: SourceType | string;
  location: string;
  event: string;
  timestamp: string;
  age_minutes: number;
  freshness_score: number;
  freshness_label: FreshnessLabel;
  is_stale: boolean;
}

// ── Relations (what the contradiction agent returns) ──────────────────────
export interface Relation {
  claim_a: string;
  claim_b: string;
  relation_type: RelationType;
  /**
   * null when the pair was matched by rule on differing wording (no LLM
   * classifier configured) — the relation is real but unscored. The UI must
   * render "unverified" rather than assuming a number.
   */
  confidence: number | null;
  reason: string;
  classified_by: 'rule' | 'llm';
}

// ── Gaps (what the evidence-gap agent returns) ────────────────────────────
export interface Gap {
  claim_id: string;
  location: string;
  missing_attribute: string;
  severity: 'low' | 'medium' | 'high';
  suggested_verification: string;
  detected_at: string;
}

// ── Freshness entries (pipeline summary form) ─────────────────────────────
export interface FreshnessEntry {
  claim_id: string;
  age_minutes: number;
  score: number;
  label: FreshnessLabel;
}

// ── Investigation summary ─────────────────────────────────────────────────
export interface InvestigationSummary {
  total_claims: number;
  total_relations: number;
  total_contradictions: number;
  total_supports: number;
  total_gaps: number;
  stale_count: number;
  avg_freshness: number;
  locations_checked: number;
  scenario_time: string;
  expected_verdict?: string;
}

// ── The main payload: POST /investigate or /area/investigate ─────────────
export interface Investigation {
  case_id: string;
  case_name: string;
  claims: Claim[];
  relations: Relation[];
  gaps: Gap[];
  freshness: FreshnessEntry[];
  verdict: Verdict;
  rationale: string;
  evidence_ids: string[];
  citation_violations: string[];
  summary: InvestigationSummary;
  generated_at: string;
}

// ── Timeline ──────────────────────────────────────────────────────────────
export interface TimelineEvent {
  source_id: string;
  source_type: string;
  source_name: string;
  location: string;
  timestamp: string;
  text: string;
}

export interface TimelineResponse {
  available: boolean;
  scenario_time: string | null;
  location: string | null;
  count: number;
  events: TimelineEvent[];
  warning: string | null;
}

// ── Evidence graph ────────────────────────────────────────────────────────
export interface GraphNode {
  id: string;
  label: string;
  source_type: string;
  freshness?: number;
  is_stale?: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation_type: RelationType;
  confidence: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ── Radar blip (derived, not a backend type) ─────────────────────────────
export interface RadarBlip {
  id: string;
  label: string;
  /** 0-1 — drives radius on the radar. */
  severity: number;
  /** freshness colour band */
  band: FreshnessLabel;
}
