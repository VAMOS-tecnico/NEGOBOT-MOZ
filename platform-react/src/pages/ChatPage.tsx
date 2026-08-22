import { useEffect, useMemo, useState, type FormEvent } from "react";
import { CheckCheck, Loader2, MessageCircle, RefreshCw, Search, Send, Users, WifiOff } from "lucide-react";
import { usePlatformLanguage } from "../lib/platformLanguage";
import { api, type ChatMessage, type Contact, type Conversation, type WhatsAppGroup } from "../lib/api";

function normalizePhone(value: string) {
  return value.endsWith("@g.us") ? value : value.replace(/\D/g, "");
}

function displayName(item: Contact | WhatsAppGroup | Conversation) {
  if ("group_jid" in item) return item.name || item.group_jid;
  return item.name || item.phone || "Contact";
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
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [contactResult, groupResult, conversationResult] = await Promise.all([api.client.contacts(), api.client.groups(), api.client.conversations()]);
      setContacts(contactResult.contacts || []);
      setGroups(groupResult.groups || []);
      setConversations(conversationResult.conversations || []);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (english ? "Could not load your chats." : "Não foi possível carregar os teus chats."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const conversationByPhone = useMemo(() => new Map(conversations.map((item) => [normalizePhone(item.phone || item.id || ""), item])), [conversations]);
  const filteredContacts = useMemo(() => contacts.filter((item) => `${item.name} ${item.phone}`.toLowerCase().includes(search.toLowerCase().trim())), [contacts, search]);
  const filteredGroups = useMemo(() => groups.filter((item) => `${item.name} ${item.group_jid}`.toLowerCase().includes(search.toLowerCase().trim())), [groups, search]);
  const selectedPhone = selected ? displayAddress(selected) : "";
  const selectedConversation = selectedPhone ? conversationByPhone.get(normalizePhone(selectedPhone)) : undefined;

  async function openChat(item: Contact | WhatsAppGroup | Conversation) {
    setSelected(item);
    setMessages([]);
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
    if (!selected || !draft.trim() || sending) return;
    setSending(true);
    setError("");
    setNotice("");
    try {
      const result = await api.client.sendConversationMessage(displayAddress(selected), draft.trim());
      setMessages((current) => [...current, result.message]);
      setDraft("");
      setNotice(english ? "Message sent." : "Mensagem enviada.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (english ? "The message could not be sent." : "Não foi possível enviar a mensagem."));
    } finally {
      setSending(false);
    }
  }

  const listItems = tab === "contacts" ? filteredContacts : filteredGroups;
  const noItems = tab === "contacts" ? (english ? "No contacts found." : "Nenhum contacto encontrado.") : (english ? "No groups found." : "Nenhum grupo encontrado.");
  const selectedIsGroup = Boolean(selected && "group_jid" in selected);
  const selectedBlocked = selectedIsGroup && (selected as WhatsAppGroup).admin_verified !== true;

  return <div className="content-stack chat-page">
    <div className="module-header"><div><span className="eyebrow">{english ? "WHATSAPP CHAT" : "CHAT WHATSAPP"}</span><h1>{english ? "Chat" : "Chat"}</h1><p>{english ? "View contacts, groups and conversations from your connected WhatsApp instance." : "Vê contactos, grupos e conversas da tua instância WhatsApp conectada."}</p></div><button className="secondary-button compact" onClick={() => void load()} disabled={loading}><RefreshCw size={16} className={loading ? "spin" : ""} />{english ? "Refresh" : "Actualizar"}</button></div>
    {error && <div className="alert error"><WifiOff size={16} />{error}</div>}
    {notice && <div className="alert info"><CheckCheck size={16} />{notice}</div>}
    <div className="chat-layout">
      <section className="data-panel chat-directory">
        <div className="chat-directory-header"><div><span className="eyebrow">{english ? "INBOX" : "CAIXA DE ENTRADA"}</span><h3>{english ? "Conversations" : "Conversas"}</h3></div><MessageCircle size={19} /></div>
        <div className="chat-tabs"><button className={tab === "contacts" ? "active" : ""} onClick={() => setTab("contacts")}><MessageCircle size={15} />{english ? "Contacts" : "Contactos"}<span>{contacts.length}</span></button><button className={tab === "groups" ? "active" : ""} onClick={() => setTab("groups")}><Users size={15} />{english ? "Groups" : "Grupos"}<span>{groups.length}</span></button></div>
        <label className="chat-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={english ? "Search contacts or groups" : "Pesquisar contactos ou grupos"} /></label>
        <div className="chat-list">{loading ? <div className="loading-box"><Loader2 size={18} className="spin" />{english ? "Loading..." : "A carregar..."}</div> : listItems.length ? listItems.map((item) => { const address = displayAddress(item); const conversation = conversationByPhone.get(normalizePhone(address)); const isSelected = selected && normalizePhone(selectedPhone) === normalizePhone(address); const blocked = "group_jid" in item && item.admin_verified !== true; return <button key={"group_jid" in item ? item.id : item.id || item.phone} className={`chat-list-item ${isSelected ? "selected" : ""}`} onClick={() => void openChat(item)}><span className="chat-avatar">{displayName(item).slice(0, 1).toUpperCase()}</span><span className="chat-list-copy"><strong>{displayName(item)}</strong><small>{conversation?.last_message || address}</small></span>{blocked ? <span className="chat-lock">{english ? "Blocked" : "Bloqueado"}</span> : conversation?.last_interaction ? <time>{messageTime(conversation.last_interaction)}</time> : null}</button>; }) : <div className="empty-state">{noItems}</div>}</div>
      </section>
      <section className="data-panel chat-thread">
        {selected ? <><header className="chat-thread-header"><span className="chat-avatar large">{displayName(selected).slice(0, 1).toUpperCase()}</span><div><h3>{displayName(selected)}</h3><small>{displayAddress(selected)}</small></div><span className={`chat-connection-pill ${selectedBlocked ? "blocked" : ""}`}>{selectedBlocked ? (english ? "Blocked group" : "Grupo bloqueado") : (english ? "WhatsApp" : "WhatsApp")}</span></header><div className="chat-messages">{loadingMessages ? <div className="loading-box"><Loader2 size={18} className="spin" />{english ? "Loading history..." : "A carregar histórico..."}</div> : messages.length ? messages.map((message, index) => <div key={message.id || `${message.timestamp}-${index}`} className={`chat-message ${message.from_me ? "from-me" : "from-contact"}`}><div className="chat-bubble">{message.text}<span>{messageTime(message.timestamp)} {message.from_me && <CheckCheck size={13} />}</span></div></div>) : <div className="chat-empty-thread"><MessageCircle size={26} /><strong>{english ? "No messages yet" : "Ainda não há mensagens"}</strong><small>{english ? "New messages received by WhatsApp will appear here." : "As novas mensagens recebidas pelo WhatsApp aparecerão aqui."}</small></div>}</div><form className="chat-composer" onSubmit={sendMessage}><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={english ? "Type a message..." : "Escreve uma mensagem..."} maxLength={4000} disabled={selectedBlocked || sending} /><button className="primary-button chat-send" type="submit" disabled={selectedBlocked || sending || !draft.trim()}>{sending ? <Loader2 size={17} className="spin" /> : <Send size={17} />}</button></form>{selectedBlocked && <p className="chat-helper">{english ? "Only verified own groups where this connected instance is an administrator can receive messages." : "Só os grupos próprios verificados, onde esta instância conectada é administradora, podem receber mensagens."}</p>}</> : <div className="chat-empty-thread"><MessageCircle size={32} /><strong>{english ? "Select a conversation" : "Selecciona uma conversa"}</strong><small>{english ? "Choose a contact or group to view its history and reply." : "Escolhe um contacto ou grupo para ver o histórico e responder."}</small></div>}
      </section>
    </div>
  </div>;
}
