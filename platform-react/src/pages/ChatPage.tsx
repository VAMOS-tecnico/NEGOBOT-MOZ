import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { CheckCheck, FileText, Image as ImageIcon, Loader2, MessageCircle, Paperclip, RefreshCw, Search, Send, Users, WifiOff, X } from "lucide-react";
import { usePlatformLanguage } from "../lib/platformLanguage";
import { api, type ChatMessage, type Contact, type Conversation, type WhatsAppGroup } from "../lib/api";

function normalizePhone(value: string) {
  const raw = value.trim();
  return raw.endsWith("@g.us") ? raw : raw.replace(/\D/g, "");
}

function validAddress(value: string) {
  const normalized = normalizePhone(value);
  return normalized.endsWith("@g.us") || normalized.length >= 8;
}

function isPlaceholderName(value?: string) {
  return !value || ["contacto", "contact", "cliente", "customer", "unknown", "undefined", "null", "sem nome"].includes(value.trim().toLowerCase());
}

function displayName(item: Contact | WhatsAppGroup | Conversation) {
  if ("group_jid" in item) return item.name || "Grupo sem nome";
  return item.name && !isPlaceholderName(item.name) && item.name !== item.phone ? item.name : "Sem nome";
}

function displayAddress(item: Contact | WhatsAppGroup | Conversation) {
  if ("group_jid" in item) return item.group_jid;
  return item.phone || "";
}

function messageTime(value?: string | null) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const documentTypes = new Set([
  "application/pdf", "application/msword", "application/rtf", "application/zip",
  "application/vnd.ms-excel", "application/vnd.ms-powerpoint",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain", "text/csv",
]);

export function ChatPage() {
  const { language } = usePlatformLanguage();
  const english = language === "en";
  const [tab, setTab] = useState<"contacts" | "groups">("contacts");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [groups, setGroups] = useState<WhatsAppGroup[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Contact | WhatsAppGroup | Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [avatarUrls, setAvatarUrls] = useState<Record<string, string>>({});
  const [avatarChecked, setAvatarChecked] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    const errors: string[] = [];
    const [contactResult, groupResult] = await Promise.allSettled([api.client.contacts(), api.client.groups()]);
    if (contactResult.status === "fulfilled") setContacts(contactResult.value.contacts || []);
    else errors.push(english ? "contacts" : "contactos");
    if (groupResult.status === "fulfilled") setGroups(groupResult.value.groups || []);
    else errors.push(english ? "groups" : "grupos");
    setLoading(false);
    if (errors.length) setError(english ? `Could not load ${errors.join(" and ")}.` : `Não foi possível carregar ${errors.join(" e ")}.`);
    try {
      const conversationResult = await api.client.conversations();
      setConversations(conversationResult.conversations || []);
    } catch {
      setError((current) => current || (english ? "Conversation history is temporarily unavailable." : "O histórico de conversas está temporariamente indisponível."));
    }
  }

  useEffect(() => { void load(); }, []);

  const conversationByPhone = useMemo(() => new Map(conversations.map((item) => [normalizePhone(item.phone || item.id || ""), item])), [conversations]);
  const directoryContacts = useMemo(() => {
    const byPhone = new Map<string, Contact>();
    for (const item of contacts) {
      const phone = normalizePhone(item.phone);
      if (!validAddress(item.phone) || phone.endsWith("@g.us")) continue;
      byPhone.set(phone, { ...item, phone, name: isPlaceholderName(item.name) || item.name === phone ? "" : item.name });
    }
    for (const conversation of conversations) {
      const phone = normalizePhone(conversation.phone || conversation.id || "");
      if (!validAddress(phone) || phone.endsWith("@g.us")) continue;
      const existing = byPhone.get(phone);
      const name = conversation.name || "";
      if (!existing || isPlaceholderName(existing.name) || existing.name === phone) {
        byPhone.set(phone, { id: conversation.id || phone, name: isPlaceholderName(name) || name === phone ? "" : name, phone });
      }
    }
    return [...byPhone.values()];
  }, [contacts, conversations]);

  const directoryGroups = useMemo(() => {
    const byJid = new Map(groups.filter((item) => item.group_jid.endsWith("@g.us")).map((item) => [item.group_jid, item]));
    for (const conversation of conversations) {
      const groupJid = conversation.phone || conversation.id || "";
      if (!groupJid.endsWith("@g.us") || byJid.has(groupJid)) continue;
      byJid.set(groupJid, {
        id: conversation.id || groupJid,
        group_jid: groupJid,
        name: isPlaceholderName(conversation.name) ? "Grupo sem nome" : conversation.name || "Grupo sem nome",
        admin_verified: false,
        status: "historical",
      });
    }
    return [...byJid.values()];
  }, [groups, conversations]);

  const filteredContacts = useMemo(() => directoryContacts.filter((item) => `${item.name} ${item.phone}`.toLowerCase().includes(search.toLowerCase().trim())), [directoryContacts, search]);
  const filteredGroups = useMemo(() => directoryGroups.filter((item) => `${item.name} ${item.group_jid}`.toLowerCase().includes(search.toLowerCase().trim())), [directoryGroups, search]);
  const directoryItems = useMemo(() => [...directoryContacts, ...directoryGroups], [directoryContacts, directoryGroups]);

  useEffect(() => {
    const known: Record<string, string> = {};
    for (const conversation of conversations) {
      const address = normalizePhone(conversation.phone || conversation.id || "");
      if (address && conversation.avatar_url) known[address] = conversation.avatar_url;
    }
    if (Object.keys(known).length) setAvatarUrls((current) => ({ ...current, ...known }));
  }, [conversations]);

  useEffect(() => {
    let cancelled = false;
    const missing = directoryItems.filter((item) => !avatarChecked[displayAddress(item)] && !avatarUrls[displayAddress(item)]).slice(0, 40);
    if (!missing.length) return () => { cancelled = true; };
    void Promise.all(missing.map(async (item) => {
      const address = displayAddress(item);
      try {
        const result = await api.client.conversationProfile(address);
        return { address, url: result.profile_picture_url || "" };
      } catch {
        return { address, url: "" };
      }
    })).then((rows) => {
      if (cancelled) return;
      const urls: Record<string, string> = {};
      const checked: Record<string, boolean> = {};
      for (const row of rows) {
        checked[row.address] = true;
        if (row.url) urls[row.address] = row.url;
      }
      setAvatarChecked((current) => ({ ...current, ...checked }));
      if (Object.keys(urls).length) setAvatarUrls((current) => ({ ...current, ...urls }));
    });
    return () => { cancelled = true; };
  }, [directoryItems, avatarChecked]);

  const selectedPhone = selected ? displayAddress(selected) : "";

  async function openChat(item: Contact | WhatsAppGroup | Conversation) {
    setSelected(item);
    setMessages([]);
    setSelectedFile(null);
    setLoadingMessages(true);
    setError("");
    try {
      const result = await api.client.conversationMessages(displayAddress(item));
      setMessages(result.messages || []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (english ? "Could not load this conversation." : "Não foi possível carregar esta conversa."));
    } finally {
      setLoadingMessages(false);
    }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!selected || sending || (!draft.trim() && !selectedFile)) return;
    setSending(true);
    setError("");
    setNotice("");
    try {
      const result = selectedFile
        ? await api.client.sendConversationMedia(displayAddress(selected), selectedFile, draft.trim())
        : await api.client.sendConversationMessage(displayAddress(selected), draft.trim());
      setMessages((current) => [...current, result.message]);
      setDraft("");
      setSelectedFile(null);
      setNotice(english ? "Message sent." : "Mensagem enviada.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (english ? "The message could not be sent." : "Não foi possível enviar a mensagem."));
    } finally {
      setSending(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] || null;
    if (!file) return;
    if (file.size > 16 * 1024 * 1024) {
      setError(english ? "Files cannot exceed 16 MB." : "Os ficheiros não podem exceder 16 MB.");
      event.target.value = "";
      return;
    }
    if (!file.type.startsWith("image/") && !documentTypes.has(file.type)) {
      setError(english ? "Select an image or a supported document." : "Selecciona uma imagem ou um documento suportado.");
      event.target.value = "";
      return;
    }
    setError("");
    setSelectedFile(file);
  }

  function avatar(address: string, label: string, large = false) {
    const url = avatarUrls[address];
    return url ? <img className={`chat-avatar-image ${large ? "large" : ""}`} src={url} alt="" onError={() => setAvatarUrls((current) => { const next = { ...current }; delete next[address]; return next; })} /> : <span className={`chat-avatar ${large ? "large" : ""}`}>{label.slice(0, 1).toUpperCase() || "?"}</span>;
  }

  const listItems = tab === "contacts" ? filteredContacts : filteredGroups;
  const noItems = tab === "contacts" ? (english ? "No contacts found." : "Nenhum contacto encontrado.") : (english ? "No groups found." : "Nenhum grupo encontrado.");
  const selectedIsGroup = Boolean(selected && "group_jid" in selected);
  const selectedBlocked = selectedIsGroup && (selected as WhatsAppGroup).admin_verified !== true;

  return <div className="content-stack chat-page">
    <div className="module-header"><div><span className="eyebrow">{english ? "WHATSAPP CHAT" : "CHAT WHATSAPP"}</span><h1>Chat</h1><p>{english ? "View contacts, groups and conversations from your connected WhatsApp instance." : "Vê contactos, grupos e conversas da tua instância WhatsApp conectada."}</p></div><button className="secondary-button compact" onClick={() => void load()} disabled={loading}><RefreshCw size={16} className={loading ? "spin" : ""} />{english ? "Refresh" : "Actualizar"}</button></div>
    {error && <div className="alert error"><WifiOff size={16} />{error}</div>}
    {notice && <div className="alert info"><CheckCheck size={16} />{notice}</div>}
    <div className="chat-layout">
      <section className="data-panel chat-directory">
        <div className="chat-directory-header"><div><span className="eyebrow">{english ? "INBOX" : "CAIXA DE ENTRADA"}</span><h3>{english ? "Conversations" : "Conversas"}</h3></div><MessageCircle size={19} /></div>
        <div className="chat-tabs"><button className={tab === "contacts" ? "active" : ""} onClick={() => setTab("contacts")}><MessageCircle size={15} />{english ? "Contacts" : "Contactos"}<span>{filteredContacts.length}</span></button><button className={tab === "groups" ? "active" : ""} onClick={() => setTab("groups")}><Users size={15} />{english ? "Groups" : "Grupos"}<span>{filteredGroups.length}</span></button></div>
        <label className="chat-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={english ? "Search contacts or groups" : "Pesquisar contactos ou grupos"} /></label>
        <div className="chat-list">{loading ? <div className="loading-box"><Loader2 size={18} className="spin" />{english ? "Loading..." : "A carregar..."}</div> : listItems.length ? listItems.map((item) => { const address = displayAddress(item); const conversation = conversationByPhone.get(normalizePhone(address)); const isSelected = selected && normalizePhone(selectedPhone) === normalizePhone(address); const blocked = "group_jid" in item && item.admin_verified !== true; return <button key={"group_jid" in item ? item.id : item.id || item.phone} className={`chat-list-item ${isSelected ? "selected" : ""}`} onClick={() => void openChat(item)}>{avatar(address, displayName(item))}<span className="chat-list-copy"><strong>{displayName(item)}</strong><small>{conversation?.last_message || address}</small></span>{blocked ? <span className="chat-lock">{english ? "Blocked" : "Bloqueado"}</span> : conversation?.last_interaction ? <time>{messageTime(conversation.last_interaction)}</time> : null}</button>; }) : <div className="empty-state">{noItems}</div>}</div>
      </section>
      <section className="data-panel chat-thread">
        {selected ? <><header className="chat-thread-header">{avatar(selectedPhone, displayName(selected), true)}<div><h3>{displayName(selected)}</h3><small>{selectedPhone}</small></div><span className={`chat-connection-pill ${selectedBlocked ? "blocked" : ""}`}>{selectedBlocked ? (english ? "Blocked group" : "Grupo bloqueado") : "WhatsApp"}</span></header><div className="chat-messages">{loadingMessages ? <div className="loading-box"><Loader2 size={18} className="spin" />{english ? "Loading history..." : "A carregar histórico..."}</div> : messages.length ? messages.map((message, index) => <div key={message.id || `${message.timestamp}-${index}`} className={`chat-message ${message.from_me ? "from-me" : "from-contact"}`}><div className="chat-bubble">{message.media_type === "image" ? (message.media_url ? <img className="chat-media-image" src={message.media_url} alt={message.caption || message.file_name || "Image"} /> : <span className="chat-attachment"><ImageIcon size={18} />{message.file_name || (english ? "Image sent" : "Imagem enviada")}</span>) : message.media_type === "document" ? <span className="chat-attachment"><FileText size={18} />{message.file_name || (english ? "Document sent" : "Documento enviado")}</span> : null}{message.caption && <p className="chat-caption">{message.caption}</p>}{!message.media_type && message.text}<span>{messageTime(message.timestamp)} {message.from_me && <CheckCheck size={13} />}</span></div></div>) : <div className="chat-empty-thread"><MessageCircle size={26} /><strong>{english ? "No messages yet" : "Ainda não há mensagens"}</strong><small>{english ? "New messages received by WhatsApp will appear here." : "As novas mensagens recebidas pelo WhatsApp aparecerão aqui."}</small></div>}</div><form className="chat-composer" onSubmit={sendMessage}><label className="chat-attach-button" title={english ? "Attach image or document" : "Anexar imagem ou documento"}><Paperclip size={17} /><input type="file" accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.txt,.rtf,.zip" onChange={handleFileChange} disabled={selectedBlocked || sending} /></label><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={selectedFile ? (english ? "Add a caption (optional)..." : "Adicionar legenda (opcional)...") : (english ? "Type a message..." : "Escreve uma mensagem...")} maxLength={4000} disabled={selectedBlocked || sending} />{selectedFile && <span className="chat-selected-file"><span>{selectedFile.type.startsWith("image/") ? <ImageIcon size={14} /> : <FileText size={14} />}{selectedFile.name}</span><button type="button" onClick={() => setSelectedFile(null)} aria-label={english ? "Remove attachment" : "Remover anexo"}><X size={14} /></button></span>}<button className="primary-button chat-send" type="submit" disabled={selectedBlocked || sending || (!draft.trim() && !selectedFile)}>{sending ? <Loader2 size={17} className="spin" /> : <Send size={17} />}</button></form>{selectedBlocked && <p className="chat-helper">{english ? "Only verified own groups where this connected instance is an administrator can receive messages." : "Só os grupos próprios verificados, onde esta instância conectada é administradora, podem receber mensagens."}</p>}</> : <div className="chat-empty-thread"><MessageCircle size={32} /><strong>{english ? "Select a conversation" : "Selecciona uma conversa"}</strong><small>{english ? "Choose a contact or group to view its history and reply." : "Escolhe um contacto ou grupo para ver o histórico e responder."}</small></div>}
      </section>
    </div>
  </div>;
}
