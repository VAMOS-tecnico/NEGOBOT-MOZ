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
  features?: string[];
};

export type Plan = {
  id: string;
  name: string;
  price: number;
  duration_days: number;
  benefits: string[];
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

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
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
    health: () => request<Record<string, unknown>>("/api/platform/admin/health"),
    integrations: () => request<Record<string, unknown>>("/api/platform/admin/integrations"),
  },
  client: {
    overview: () => request<Record<string, unknown>>("/api/platform/client/overview"),
    plans: () => request<{ plans: Plan[] }>("/api/platform/client/plans"),
    plan: () => request<ClientPlan>("/api/platform/client/plan"),
    integrationStatus: () => request<IntegrationStatus>("/api/platform/client/integration/status"),
    conversations: () => request<{ conversations: Conversation[] }>("/api/platform/client/conversations"),
    contacts: () => request<{ contacts: Contact[] }>("/api/platform/client/contacts"),
    createContact: (name: string, phone: string) => request<{ created: true; contact: Contact }>("/api/platform/client/contacts", { method: "POST", body: JSON.stringify({ name, phone, opt_in: true }) }),
    campaigns: () => request<{ campaigns: Campaign[] }>("/api/platform/client/campaigns"),
    createCampaign: (name: string, message: string) => request<{ created: true; campaign: Campaign }>("/api/platform/client/campaigns", { method: "POST", body: JSON.stringify({ name, message }) }),
    campaignAction: (id: string, action: "pause" | "resume" | "cancel") => request<{ updated: true; status: string }>(`/api/platform/client/campaigns/${id}/actions/${action}`, { method: "POST" }),
    assistant: () => request<Record<string, unknown>>("/api/platform/client/assistant"),
  },
};
