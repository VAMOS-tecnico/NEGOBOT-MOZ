export type Role = "owner" | "admin" | "client" | "operator";

export type PlatformUser = {
  id: string;
  name: string;
  email?: string;
  role: Role;
  tenant_id?: string | null;
  tenant_role?: "owner" | "operator" | "viewer";
};

export type TeamMember = {
  id: string;
  name: string;
  email: string;
  role: Role;
  tenant_role: "owner" | "operator" | "viewer";
  status: "active" | "suspended";
  created_at?: string;
  last_login_at?: string | null;
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
  price_usd?: number;
  validity_days: number;
  conversation_limit?: number | null;
  contact_limit?: number;
  campaigns_per_month?: number;
  team_seats?: number;
  included_channels?: string[];
  additional_channel_slots?: number;
  mass_broadcast?: boolean;
  ai_media?: boolean;
  benefits: string[];
};

export type PlanAddon = {
  id: string;
  name: string;
  description: string;
  price_mt: number;
  price_usd?: number;
  type: string;
};

export type PlansCatalog = {
  plans: Plan[];
  addons?: PlanAddon[];
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
  limits?: Record<string, number | string[] | boolean | null>;
  usage?: { contacts: number; campaigns_this_month: number; team_seats: number };
  trial_status?: string;
  billing_region?: "mozambique" | "international" | string;
  selected_plan?: string | null;
  trial_access?: boolean;
  trial_access_level?: string;
  trial_features?: string[];
};

export type IntegrationStatus = {
  instance_name?: string;
  state?: string;
  configured?: boolean;
  services?: Record<string, { label: string; status: string }>;
};

export type ChannelStatus = "not_configured" | "pending_authorization" | "pending_review" | "connected" | "disabled" | "error";

export type TelegramChannelInfo = {
  channel: "telegram";
  status: ChannelStatus;
  bot: { id?: string | number; username?: string; name?: string };
  webhook_url?: string | null;
  last_event_at?: string | null;
  last_error?: string | null;
  pending_update_count?: number;
  has_token?: boolean;
};

export type ClientChannel = {
  key: string;
  label: string;
  kind: string;
  provider: string;
  setup: string;
  availability: string;
  status: ChannelStatus;
  external_account_id?: string | null;
  external_account_name?: string | null;
  connected_at?: string | null;
  token_expires_at?: string | null;
  last_event_at?: string | null;
  last_error?: string | null;
  can_connect?: boolean;
  requires_review?: boolean;
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
  avatar_url?: string | null;
  last_message?: string;
  updated_at?: string;
  last_interaction?: string | null;
  contact_id?: string;
  status?: string;
  status_atendimento?: string;
  kind?: "contact" | "group" | string;
};

export type ChatMessage = {
  id?: string;
  role?: string;
  text: string;
  timestamp?: string | null;
  from_me?: boolean;
  media_type?: "image" | "document" | string | null;
  file_name?: string | null;
  mime_type?: string | null;
  caption?: string | null;
  media_url?: string | null;
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
  template_id?: string | null;
  segment_tags?: string[];
  status?: string;
  total?: number;
  sent?: number;
  failed?: number;
  created_at?: string;
  channels?: string[];
  language?: string;
  tone?: string;
  offer?: string;
  scheduled_at?: string | null;
  orchestration_status?: string;
  recipient_limit?: number;
  include_contacts?: boolean;
  include_conversations?: boolean;
  conversation_count?: number;
  skipped?: number;
};

export type GroupKeyword = { trigger: string; response: string };

export type WhatsAppChannelCapability = {
  key: "whatsapp_newsletter" | string;
  label: string;
  status: "pending_authorization" | "connected" | "error" | string;
  provider: string;
  adapter_configured: boolean;
  administrator_verification: boolean;
  can_publish: boolean;
  reason?: string;
};

export type ChannelPublication = {
  id: string;
  tenant_id?: string;
  channel_type: string;
  channel_jid?: string | null;
  channel_name?: string | null;
  title: string;
  body: string;
  rendered_body?: string;
  cta_url?: string | null;
  cta_label?: string | null;
  scheduled_at?: string | null;
  timezone?: string;
  status?: "draft" | "scheduled" | "blocked" | "published" | "cancelled" | string;
  delivery_status?: string;
  adapter_status?: string;
  authorization_status?: string;
  last_error?: string | null;
  created_at?: string | number | null;
  published_at?: string | number | null;
};

export type WhatsAppGroup = {
  id: string;
  tenant_id?: string;
  instance_name?: string;
  group_jid: string;
  name: string;
  bot_jid?: string;
  bot_is_admin?: boolean;
  admin_verified?: boolean;
  authorization_reason?: string;
  status?: "active" | "rejected" | string;
  automation_enabled?: boolean;
  mention_required?: boolean;
  welcome_enabled?: boolean;
  welcome_message?: string;
  keywords?: GroupKeyword[];
  participant_count?: number;
  last_synced_at?: string | number | null;
  last_event_at?: string | number | null;
  last_error?: string | null;
};

export type CampaignSettings = {
  timezone: string;
  silence_start: string;
  silence_end: string;
  daily_limit: number;
  min_delay_seconds: number;
  max_delay_seconds: number;
};

export type CampaignTemplate = {
  id: string;
  name: string;
  body: string;
  variables?: string[];
  status?: "active" | "archived";
};

export type DeliveryMetrics = { total: number; by_status: Record<string, number>; sent: number; failed: number; delivery_rate: number };

export type TenantMetrics = {
  contacts: { total: number; opt_in: number; opt_out: number };
  conversations: number;
  campaigns: { total: number; by_status: Record<string, number>; recent: Campaign[] };
  deliveries: DeliveryMetrics;
};

export type VideoScene = { text: string; duration_seconds?: number; asset_url?: string };

export type VideoJob = { id: string; tenant_id?: string; title: string; scenes?: VideoScene[]; status?: "queued" | "processing" | "completed" | "deleted" | "failed"; progress?: number; output_available?: boolean; output_url?: string; error?: string; created_at?: string; deleted_at?: string; deletion_reason?: string };

export type SupportTicket = {
  id: string;
  tenant_id?: string;
  subject: string;
  message: string;
  category?: string;
  priority?: "low" | "normal" | "high" | "urgent";
  status?: "open" | "in_progress" | "waiting_client" | "resolved" | "closed";
  last_client_message?: string;
  last_admin_reply?: string;
  created_at?: string;
  updated_at?: string;
};

export type AdminMetrics = {
  generated_at?: string;
  tenants: { total: number; active: number };
  users: { total: number; active: number };
  campaigns: { total: number; by_status: Record<string, number> };
  payments: { total: number; confirmed: number };
  support: { total: number; open: number };
};

export type PaymentRecord = {
  id: string;
  provider?: "mpesa" | "lemonsqueezy" | string;
  payment_provider?: string;
  plan_id?: string;
  plan_name?: string;
  client_phone?: string;
  transaction_id?: string | null;
  checkout_url?: string;
  status?: string;
  created_at?: string;
  confirmed_at?: string;
};

export type LemonSqueezyStatus = {
  configured: boolean;
  currency?: string;
  plans: Record<string, boolean>;
  addons?: Record<string, boolean>;
};

export type LemonSqueezyCheckout = {
  created: true;
  payment_intent_id: string;
  checkout_url: string;
  plan_id: string;
};

export type BusinessProfile = {
  email?: string;
  empresa_nome: string;
  nicho: string;
  email_corporativo: string;
  redes_sociais: { facebook: string; instagram: string; twitter_x: string; tiktok: string; telegram: string; linkedin: string };
  instance_name?: string | null;
  status_conexao?: string;
  billing_region?: "mozambique" | "international" | string;
  selected_plan?: string | null;
  preferred_trial_channel?: "whatsapp" | "telegram" | "instagram" | "facebook" | string;
  onboarding_status?: "incomplete" | "completed" | string;
  profile_completed?: boolean;
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
    register: (payload: { name?: string; email: string; password: string; billing_region?: "mozambique" | "international"; plan_id?: string }) =>
      request<{ authenticated: true; user: PlatformUser; tenant: Tenant }>("/api/platform/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    login: (identifier: string, password: string) =>
      request<{ authenticated: true; user: PlatformUser }>("/api/platform/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      }),
    forgotPassword: (email: string) =>
      request<{ accepted: true; message_en: string; message_pt: string }>("/api/platform/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      }),
    resetPassword: (token: string, password: string) =>
      request<{ reset: true; message_en: string; message_pt: string }>("/api/platform/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      }),
    logout: () => request<{ authenticated: false }>("/api/platform/auth/logout", { method: "POST" }),
  },
      admin: {

    overview: () => request<Overview>("/api/platform/admin/overview"),
    tenants: () => request<{ tenants: Tenant[] }>("/api/platform/admin/tenants"),
    createTenant: (name: string, email: string, password: string) => request<{ created: true; tenant: Tenant }>("/api/platform/admin/tenants", { method: "POST", body: JSON.stringify({ name, email, password }) }),
    health: () => request<{ services: Record<string, string>; worker?: string }>("/api/platform/admin/health"),
    groups: () => request<{ groups: WhatsAppGroup[] }>("/api/platform/admin/groups"),
    channelPublications: () => request<{ publications: ChannelPublication[]; capability: WhatsAppChannelCapability }>("/api/platform/admin/channel-publications"),
    audit: () => request<{ events: AuditEvent[] }>("/api/platform/admin/audit"),
    metrics: () => request<AdminMetrics>("/api/platform/admin/metrics"),
    supportTickets: () => request<{ tickets: SupportTicket[] }>("/api/platform/admin/support/tickets"),
    updateSupportTicket: (id: string, fields: { status: SupportTicket["status"]; reply?: string }) => request<{ updated: true }>(`/api/platform/admin/support/tickets/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(fields) }),
    integrations: () => request<{ integrations: Integration[] }>("/api/platform/admin/integrations"),
    updateIntegration: (key: string, fields: { label?: string; public_url?: string; notes?: string }) => request<{ updated: true }>(`/api/platform/admin/integrations/${key}`, { method: "PATCH", body: JSON.stringify(fields) }),
  },
  client: {
    overview: () => request<Overview>("/api/platform/client/overview"),
    plans: () => request<PlansCatalog>("/api/platform/client/plans"),
    plan: () => request<ClientPlan>("/api/platform/client/plan"),
    integrationStatus: () => request<IntegrationStatus>("/api/platform/client/integration/status"),
    channels: () => request<{ tenant_id?: string; channels: ClientChannel[] }>("/api/platform/client/channels"),
    groups: () => request<{ tenant_id?: string; groups: WhatsAppGroup[] }>("/api/platform/client/groups"),
    whatsappChannelCapability: () => request<WhatsAppChannelCapability>("/api/platform/client/whatsapp-channels/capability"),
    channelPublications: () => request<{ publications: ChannelPublication[]; capability: WhatsAppChannelCapability }>("/api/platform/client/channel-publications"),
    createChannelPublication: (payload: { title: string; body: string; channel_jid?: string; channel_name?: string; cta_url?: string; cta_label?: string; scheduled_at?: string; timezone?: string }) => request<{ created: true; publication: ChannelPublication; capability: WhatsAppChannelCapability }>("/api/platform/client/channel-publications", { method: "POST", body: JSON.stringify(payload) }),
    channelPublicationAction: (id: string, action: "cancel" | "retry") => request<{ updated: true; publication_id: string; status: string }>(`/api/platform/client/channel-publications/${encodeURIComponent(id)}/actions/${action}`, { method: "POST" }),
    syncGroups: () => request<{ groups: WhatsAppGroup[]; total: number; verified: number; webhook_configured?: boolean }>("/api/platform/client/groups/sync", { method: "POST" }),
    updateGroup: (id: string, fields: Partial<Pick<WhatsAppGroup, "automation_enabled" | "mention_required" | "welcome_enabled" | "welcome_message" | "keywords">>) => request<{ updated: true; group_id: string; changes: Partial<WhatsAppGroup> }>(`/api/platform/client/groups/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(fields) }),
    updateChannel: (channel: string, status: "disabled" | "not_configured") => request<{ updated: true; channel: string; status: string }>(`/api/platform/client/channels/${encodeURIComponent(channel)}`, { method: "PATCH", body: JSON.stringify({ status }) }),
    authorizeChannel: (channel: string) => request<{ channel: string; provider: string; status: ChannelStatus; authorize_url: string; expires_in: number }>(`/api/platform/client/channels/${encodeURIComponent(channel)}/authorize`),
    disconnectOAuthChannel: (channel: string) => request<{ disconnected: true; channel: string; status: string }>(`/api/platform/client/channels/${encodeURIComponent(channel)}/disconnect`, { method: "POST" }),
    telegramStatus: () => request<TelegramChannelInfo>("/api/platform/client/channels/telegram"),
    connectTelegram: (botToken: string) => request<{ connected: true; channel: "telegram"; bot: TelegramChannelInfo["bot"]; webhook_url: string; pending_update_count: number }>("/api/platform/client/channels/telegram/connect", { method: "POST", body: JSON.stringify({ bot_token: botToken }) }),
    disconnectTelegram: () => request<{ disconnected: true; channel: "telegram" }>("/api/platform/client/channels/telegram/disconnect", { method: "POST" }),
    team: () => request<{ users: TeamMember[]; current_role?: string }>("/api/platform/client/team"),
    createOperator: (name: string, email: string, password: string) => request<{ created: true; user: TeamMember }>("/api/platform/client/team", { method: "POST", body: JSON.stringify({ name, email, password }) }),
    updateTeamMember: (id: string, fields: { status?: "active" | "suspended"; tenant_role?: "operator" | "viewer" }) => request<{ updated: true }>(`/api/platform/client/team/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(fields) }),
    conversations: () => request<{ conversations: Conversation[]; count?: number; instance_name?: string }>("/api/platform/client/conversations"),
    conversationMessages: (phone: string) => request<{ phone: string; messages: ChatMessage[]; count: number }>(`/api/platform/client/conversations/${encodeURIComponent(phone)}/messages`),
    conversationProfile: (phone: string) => request<{ phone: string; profile_picture_url?: string | null; available: boolean }>(`/api/platform/client/conversations/${encodeURIComponent(phone)}/profile`),
    sendConversationMessage: (phone: string, text: string) => request<{ sent: true; phone: string; message: ChatMessage }>(`/api/platform/client/conversations/${encodeURIComponent(phone)}/messages`, { method: "POST", body: JSON.stringify({ text }) }),
    sendConversationMedia: (phone: string, file: File, caption = "") => { const form = new FormData(); form.append("file", file); form.append("caption", caption); return request<{ sent: true; phone: string; message: ChatMessage }>(`/api/platform/client/conversations/${encodeURIComponent(phone)}/media`, { method: "POST", body: form }); },
    campaignConversationAudience: () => request<{ conversations: Conversation[]; count: number; eligibility: string }>("/api/platform/client/campaign-audience/conversations"),
    handoff: (phone: string, mode: "bot" | "humano") => request<{ updated: true }>(`/api/platform/client/conversations/${encodeURIComponent(phone)}/handoff`, { method: "POST", body: JSON.stringify({ mode }) }),
    contacts: (filters: { search?: string; tag?: string; opt_in?: "true" | "false" } = {}) => { const query = new URLSearchParams(); if (filters.search) query.set("search", filters.search); if (filters.tag) query.set("tag", filters.tag); if (filters.opt_in) query.set("opt_in", filters.opt_in); const suffix = query.toString() ? `?${query.toString()}` : ""; return request<{ contacts: Contact[]; count?: number }>(`/api/platform/client/contacts${suffix}`); },
    createContact: (name: string, phone: string, tags: string[] = []) => request<{ created: true; contact: Contact }>("/api/platform/client/contacts", { method: "POST", body: JSON.stringify({ name, phone, tags, opt_in: true }) }),
    updateContact: (id: string, fields: { name?: string; phone?: string; opt_in?: boolean; tags?: string[] }) => request<{ updated: true }>(`/api/platform/client/contacts/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(fields) }),
    archiveContact: (id: string) => request<{ archived: true }>(`/api/platform/client/contacts/${encodeURIComponent(id)}`, { method: "DELETE" }),
    importContacts: (file: File) => { const form = new FormData(); form.append("file", file); return request<{ imported: number; skipped: number; total_rows: number }>("/api/platform/client/contacts/import", { method: "POST", body: form }); },
    campaigns: () => request<{ campaigns: Campaign[] }>("/api/platform/client/campaigns"),
    campaignSettings: () => request<CampaignSettings>("/api/platform/client/campaign-settings"),
    updateCampaignSettings: (settings: CampaignSettings) => request<{ updated: true } & CampaignSettings>("/api/platform/client/campaign-settings", { method: "PATCH", body: JSON.stringify(settings) }),
    metrics: () => request<{ tenant_id?: string; metrics: TenantMetrics }>("/api/platform/client/metrics"),
    campaignReport: () => request<{ tenant_id?: string; generated_at?: string; campaigns: TenantMetrics["campaigns"]; deliveries: DeliveryMetrics }>("/api/platform/client/reports/campaigns"),
    supportTickets: () => request<{ tickets: SupportTicket[] }>("/api/platform/client/support/tickets"),
    createSupportTicket: (fields: { subject: string; message: string; category?: string; priority?: SupportTicket["priority"] }) => request<{ created: true; ticket: SupportTicket }>("/api/platform/client/support/tickets", { method: "POST", body: JSON.stringify(fields) }),
    updateSupportTicket: (id: string, fields: { message?: string; status?: "open" | "closed" }) => request<{ updated: true }>(`/api/platform/client/support/tickets/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(fields) }),
    createVideoJob: (payload: { title: string; scenes: VideoScene[]; language?: string; voice?: string; subtitles?: boolean }) => request<{ accepted: true; job: VideoJob }>("/api/platform/client/videos/jobs", { method: "POST", body: JSON.stringify(payload) }),
    videoJob: (id: string) => request<{ job: VideoJob }>(`/api/platform/client/videos/jobs/${encodeURIComponent(id)}`),
    videoPreviewUrl: (id: string) => `/api/platform/client/videos/jobs/${encodeURIComponent(id)}/preview`,
    downloadVideoJob: async (id: string) => {
      const response = await fetch(`/api/platform/client/videos/jobs/${encodeURIComponent(id)}/download`, { credentials: "same-origin" });
      if (!response.ok) {
        const contentType = response.headers.get("content-type") || "";
        const body = contentType.includes("application/json") ? await response.json() : await response.text();
        const message = typeof body === "object" && body?.error ? body.error : `Download refused (${response.status})`;
        throw new ApiError(message, response.status);
      }
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      return { blob: await response.blob(), filename: match?.[1] || `negobot-video-${id.slice(0, 8)}.mp4` };
    },
    deleteVideoJob: (id: string) => request<{ deleted: true; job_id: string }>(`/api/platform/client/videos/jobs/${encodeURIComponent(id)}`, { method: "DELETE" }),
    templates: () => request<{ templates: CampaignTemplate[] }>("/api/platform/client/templates"),
    createTemplate: (name: string, body: string) => request<{ created: true; template: CampaignTemplate }>("/api/platform/client/templates", { method: "POST", body: JSON.stringify({ name, body }) }),
    updateTemplate: (id: string, fields: { name?: string; body?: string; status?: "active" | "archived" }) => request<{ updated: true }>(`/api/platform/client/templates/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(fields) }),
    createCampaign: (name: string, message: string, options: { template_id?: string; tags?: string[]; channels?: string[]; language?: string; tone?: string; offer?: string; scheduled_at?: string; recipient_limit?: number; include_contacts?: boolean; include_conversations?: boolean; consent_confirmed?: boolean; group_jids?: string[]; group_authorization_confirmed?: boolean } = {}) => request<{ created: true; campaign: Campaign }>("/api/platform/client/campaigns", { method: "POST", body: JSON.stringify({ name, message, ...options }) }),
    campaignAction: (id: string, action: "pause" | "resume" | "cancel") => request<{ updated: true; status: string }>(`/api/platform/client/campaigns/${id}/actions/${action}`, { method: "POST" }),
    profile: () => request<BusinessProfile>("/api/platform/client/profile"),
    updateProfile: (profile: Partial<BusinessProfile>) => request<{ updated: true; fields: string[] }>("/api/platform/client/profile", { method: "PATCH", body: JSON.stringify(profile) }),
    assistant: () => request<AssistantSettings>("/api/platform/client/assistant"),
    updateAssistant: (settings: Partial<AssistantSettings>) => request<{ updated: true }>("/api/platform/client/assistant", { method: "PATCH", body: JSON.stringify(settings) }),
    verifyPayment: (messageText: string, clientPhone: string, addonId?: string) => request<{ processed: true; response: string; state?: string; instance_name?: string | null; qrcode?: string | null }>("/api/platform/client/payments/mpesa/verify", { method: "POST", body: JSON.stringify({ message_text: messageText, client_phone: clientPhone, ...(addonId ? { addon_id: addonId } : {}) }) }),
    paymentHistory: () => request<{ payments: PaymentRecord[] }>("/api/platform/client/payments/history"),
    lemonSqueezyStatus: () => request<LemonSqueezyStatus>("/api/platform/client/payments/lemonsqueezy/status"),
    createLemonSqueezyCheckout: (planId: string) => request<LemonSqueezyCheckout>("/api/platform/client/payments/lemonsqueezy/checkout", { method: "POST", body: JSON.stringify({ plan_id: planId }) }),
    createLemonSqueezyAddonCheckout: (addonId: string) => request<LemonSqueezyCheckout & { addon_id: string }>("/api/platform/client/payments/lemonsqueezy/addon-checkout", { method: "POST", body: JSON.stringify({ addon_id: addonId }) }),
    evolutionQr: (phone: string) => request<{ state: string; instance_name: string; qrcode?: string | null }>("/api/platform/client/evolution/qr", { method: "POST", body: JSON.stringify({ phone }) }),
  },
};
