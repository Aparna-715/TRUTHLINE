/**
 * TRUTHLINE — API client
 * ==========================================================================
 * One axios instance, one place that knows the backend URL. Every page calls
 * these functions; nothing else in the app touches fetch/axios directly.
 *
 * The Vite dev server proxies /api -> http://localhost:8000 (see vite.config.ts),
 * so the browser sees a same-origin request and CORS never bites.
 */

import axios from 'axios';
import type {
  AreaResponse,
  CasesResponse,
  GraphResponse,
  HealthResponse,
  Investigation,
  Report,
  TimelineResponse,
} from './types';

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,  // pipeline runs LLM classify per candidate pair — 72s for 21 reports
});

/** True when the error is a network failure (backend not running). */
export function isBackendDown(error: unknown): boolean {
  return axios.isAxiosError(error) && error.code === 'ERR_NETWORK';
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg ?? String(d)).join('; ');
    }
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}

// ── Meta ───────────────────────────────────────────────────────────────────
export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health');
  return data;
}

export async function fetchCases(): Promise<CasesResponse> {
  const { data } = await api.get<CasesResponse>('/cases');
  return data;
}

// ── Operational area ───────────────────────────────────────────────────────
export async function fetchArea(scenarioTime?: string): Promise<AreaResponse> {
  const { data } = await api.get<AreaResponse>('/area', {
    params: scenarioTime ? { scenario_time: scenarioTime } : {},
  });
  return data;
}

export async function seedArea(): Promise<{
  area: { area_id: string; name: string };
  zones_created: number;
  equipment_created: number;
}> {
  const { data } = await api.post('/area/seed');
  return data;
}

export interface CreateZoneParams {
  name: string;
  description?: string;
  threat?: string;
}

export async function createZone(params: CreateZoneParams) {
  const { data } = await api.post('/zones', params);
  return data as { zone_id: string; name: string };
}

export async function deleteZone(zoneId: string) {
  const { data } = await api.delete(`/zones/${zoneId}`);
  return data as { deleted: number; zone_id: string };
}

export interface CreateEquipmentParams {
  name: string;
  source_type: string;
  zone_id?: string | null;
  status?: string;
}

export async function createEquipment(params: CreateEquipmentParams) {
  const { data } = await api.post('/equipment', params);
  return data as { equipment_id: string; name: string };
}

export async function deleteEquipment(equipmentId: string) {
  const { data } = await api.delete(`/equipment/${equipmentId}`);
  return data as { deleted: number; equipment_id: string };
}

// ── Reports (the real data) ────────────────────────────────────────────────
export async function fetchReports(): Promise<{ count: number; reports: Report[] }> {
  const { data } = await api.get('/reports');
  return data;
}

export interface CreateReportParams {
  text: string;
  zone: string;
  equipment_id?: string | null;
  source_type?: string | null;
  source_name?: string | null;
  timestamp?: string | null;
  reliability_class?: string | null;
}

export async function createReport(params: CreateReportParams): Promise<{ report: Report }> {
  const { data } = await api.post('/reports', params);
  return data;
}

export async function deleteReport(sourceId: string) {
  const { data } = await api.delete(`/reports/${sourceId}`);
  return data as { deleted: number; source_id: string };
}

export async function clearReports() {
  const { data } = await api.delete('/reports');
  return data as { deleted: number };
}

// ── Orchestration ──────────────────────────────────────────────────────────
export interface InvestigateParams {
  case_id?: string;
  reports?: Array<Record<string, unknown>>;
  scenario_time?: string;
}

/** Run the pipeline over a labelled fixture case. */
export async function investigate(params: InvestigateParams): Promise<Investigation> {
  const { data } = await api.post<Investigation>('/investigate', {
    case_id: params.case_id ?? null,
    reports: params.reports ?? null,
    scenario_time: params.scenario_time ?? null,
  });
  return data;
}

/** Run the pipeline over the operator's own stored reports. */
export async function investigateArea(
  scenarioTime?: string,
  zone?: string,
): Promise<Investigation> {
  const { data } = await api.post<Investigation>('/area/investigate', null, {
    params: {
      ...(scenarioTime ? { scenario_time: scenarioTime } : {}),
      ...(zone ? { zone } : {}),
    },
  });
  return data;
}

// ── Visualisation ──────────────────────────────────────────────────────────
export async function fetchTimeline(scenarioTime?: string): Promise<TimelineResponse> {
  const { data } = await api.get<TimelineResponse>('/timeline', {
    params: scenarioTime ? { scenario_time: scenarioTime } : {},
  });
  return data;
}

export async function fetchGraph(claimId?: string): Promise<GraphResponse> {
  const { data } = await api.get<GraphResponse>('/graph', {
    params: claimId ? { claim_id: claimId } : {},
  });
  return data;
}

// ── Individual agents ──────────────────────────────────────────────────────
export interface IngestParams {
  text: string;
  source_id?: string;
  source_type?: string;
  location?: string;
  timestamp?: string;
  source_name?: string;
}

export async function ingestReport(params: IngestParams) {
  const { data } = await api.post('/ingest', params);
  return data as { source_id: string; record: Record<string, unknown> };
}

export interface ExtractParams {
  text: string;
  source_id?: string;
  source_type?: string;
  source_name?: string;
}

export async function extractClaims(params: ExtractParams) {
  const { data } = await api.post('/extract', params);
  return data as { claim_count: number; claims: Array<Record<string, unknown>> };
}

/** Run semantic vector search over stored sources (Qdrant). */
export interface RetrieveParams {
  query: string;
  location?: string;
  source_type?: string;
  limit?: number;
}

export interface RetrieveResponse {
  available: boolean;
  count: number;
  evidence: Array<{
    source_id: string;
    source_type: string;
    source_name: string;
    location: string;
    timestamp: string;
    reliability_class: string;
    text: string;
    ingested_at: string;
    score: number;
  }>;
  warning: string | null;
}

export async function apiRetrieve(params: RetrieveParams): Promise<RetrieveResponse> {
  const { data } = await api.post<RetrieveResponse>('/retrieve', params);
  return data;
}
