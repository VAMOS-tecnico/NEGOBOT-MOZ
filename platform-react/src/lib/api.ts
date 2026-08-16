export type Role = "owner" | "admin" | "client" | "operator";

export type PlatformUser = {
  id: string;
  name: string;
  email?: string;
  role: Role;
  tenant_id?: string | null;
};

export type AuthState = {
  authenticated: boolean;
  user: PlatformUser | null;
};

export type Overview = {
  role?: Role;
  tenants?: number;
  users?: number;
  active_tenants?: number;
  contacts?: number;
  campaigns?: number;
  conversations?: number;
  tenant?: Record<string, unknown>;
  features?: string[];
};

export type Plan = {
  id: string;
  name: string;
  price_mt: number;
  validity_days: number;
  conversation_limit?: number;
  mass_broadcast?: boolean;
  benefits: string[];
};

export type PlansCatalog = {
  plans: Plan[];
  trial_days?: number;
  mpesa_number?: string;
  mpesa_name?: string;
};

export type ClientPlan = {
  plan: string;
  plan_name: string;
  status: string;
  expires_at?: string | null;
  mass_broadcast: boolean;
  limits?: Record<string, number>;
};

export type IntegrationStatus = {
  instance_name?: string;
  state?: string;
  configured?: boolean;
};

export type Tenant = {
  id: string;
  name: string;
  email?: string;
  status?: string;
  plan?: string;
  created_at?: string;
};

export type Conversation = {
  id?: string;
  phone?: string;
  name?: string;
  last_message?: string;
  updated_at?: string;
  status?: string;
  status_atendimento?: string;
};

export type Contact = {
  id: string;
  name: string;
  phone: string;
  opt_in?: boolean;
  tags?: string[];
};

export type Campaign = {
  id: string;
  name: string;
  message?: string;
  status?: string;
  total?: number;
  sent?: number;
  failed?: number;
  created_at?: string;
};

export type AssistantSettings = {
  diretrizes_corporativas: string;
  base_conhecimento_documentos: string;
  timeout_humano_minutos: number;
  models?: { text?: string; vision?: string };
};

export type AuditEvent = {
  id: string;
  event?: string;
  actor_id?: string;
  actor_role?: string;
  tenant_id?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type Integration = {
  key: string;
  label: string;
  kind?: string;
  configured?: boolean;
  public_url?: string;
  notes?: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init.headers || {}),
    },
    ...init,
  });

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = typeof body === "object" && body?.error
      ? body.error
      : `Pedido recusado (${response.status})`;
    throw new ApiError(message, response.status);
  }

  return body as T;
}

export const api = {
  auth: {
    me: () => request<AuthState>("/api/platform/auth/me"),
    login: (identifier: string, password: string) =>
      request<{ authenticated: true; user: PlatformUser }>("/api/platform/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      }),
    logout: () => request<{ authenticated: false }>("/api/platform/auth/logout", { method: "POST" }),
  },
  admin: {
    overview: () => request<Overview>("/api/platform/admin/overview"),
    tenants: () => request<{ tenants: Tenant[] }>("/api/platform/admin/tenants"),
    createTenant: (name: string, email: string, password: string) => request<{ created: true; tenant: Tenant }>("/api/platform/admin/tenants", { method: "POST", body: JSON.stringify({ name, email, password }) }),
    health: () => request<{ services: Record<string, string>; worker?: string }>("/api/platform/admin/health"),
    audit: () => request<{ events: AuditEvent[] }>("/api/platform/admin/audit"),
    integrations: () => request<{ integrations: Integration[] }>("/api/platform/admin/integrations"),
    updateIntegration: (key: string, fields: { label?: string; public_url?: string; notes?: string }) => request<{ updated: true }>(`/api/platform/admin/integrations/${key}`, { method: "PATCH", body: JSON.stringify(fields) }),
  },
  client: {
    overview: () => request<Overview>("/api/platform/client/overview"),
    plans: () => request<PlansCatalog>("/api/platform/client/plans"),
    plan: () => request<ClientPlan>("/api/platform/client/plan"),
    integrationStatus: () => request<IntegrationStatus>("/api/platform/client/integration/status"),
    conversations: () => request<{ conversations: Conversation[] }>("/api/platform/client/conversations"),
    handoff: (phone: string, mode: "bot" | "humano") => request<{ updated: true }>(`/api/platform/client/conversations/${encodeURIComponent(phone)}/handoff`, { method: "POST", body: JSON.stringify({ mode }) }),
    contacts: () => request<{ contacts: Contact[] }>("/api/platform/client/contacts"),
    createContact: (name: string, phone: string) => request<{ created: true; contact: Contact }>("/api/platform/client/contacts", { method: "POST", body: JSON.stringify({ name, phone, opt_in: true }) }),
    importContacts: (file: File) => { const form = new FormData(); form.append("file", file); return request<{ imported: number; skipped: number; total_rows: number }>("/api/platform/client/contacts/import", { method: "POST", body: form }); },
    campaigns: () => request<{ campaigns: Campaign[] }>("/api/platform/client/campaigns"),
    createCampaign: (name: string, message: string) => request<{ created: true; campaign: Campaign }>("/api/platform/client/campaigns", { method: "POST", body: JSON.stringify({ name, message }) }),
    campaignAction: (id: string, action: "pause" | "resume" | "cancel") => request<{ updated: true; status: string }>(`/api/platform/client/campaigns/${id}/actions/${action}`, { method: "POST" }),
    assistant: () => request<AssistantSettings>("/api/platform/client/assistant"),
    updateAssistant: (settings: Partial<AssistantSettings>) => request<{ updated: true }>("/api/platform/client/assistant", { method: "PATCH", body: JSON.stringify(settings) }),
    verifyPayment: (messageText: string, clientPhone: string) => request<{ processed: true; response: string }>("/api/platform/client/payments/mpesa/verify", { method: "POST", body: JSON.stringify({ message_text: messageText, client_phone: clientPhone }) }),
    evolutionQr: (phone: string) => request<{ state: string; instance_name: string; qrcode?: string | null }>("/api/platform/client/evolution/qr", { method: "POST", body: JSON.stringify({ phone }) }),
  },
};
