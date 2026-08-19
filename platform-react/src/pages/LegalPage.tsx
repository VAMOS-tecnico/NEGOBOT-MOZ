import { ArrowLeft, ShieldCheck } from "lucide-react";
import { useState } from "react";

type Language = "en" | "pt";
type LegalKind = "terms" | "privacy";

const CONTENT: Record<Language, Record<LegalKind, { title: string; intro: string; sections: { heading: string; body: string }[] }>> = {
  en: {
    terms: {
      title: "Terms of Service",
      intro: "These Terms govern access to and use of the NEGOBOT-MOZ customer-care and omnichannel automation platform.",
      sections: [
        { heading: "1. The service", body: "NEGOBOT-MOZ provides a hosted workspace for customer conversations, contact management, campaigns, AI-assisted workflows and authorised channel integrations. Features depend on the plan, provider availability and the permissions granted by each connected channel." },
        { heading: "2. Account and workspace", body: "You are responsible for the accuracy of your registration information, the security of your access credentials and activity performed in your workspace. Each customer workspace is isolated from other customers. You must not share access with people who are not authorised by your business." },
        { heading: "3. Trials, plans and payments", body: "Eligible accounts receive one two-day Premium trial under the platform trial policy. A trial does not guarantee that every external provider will approve a channel. Paid plans, local M-Pesa verification and international checkout are described in the platform and may be updated with notice." },
        { heading: "4. Connected channels", body: "When you connect WhatsApp, Instagram, Facebook, TikTok, Telegram, LinkedIn, X or another provider, you authorise NEGOBOT-MOZ to use only the permissions and credentials required for the selected integration. You may disconnect a channel from the platform. Provider terms, rate limits, reviews and regional restrictions continue to apply." },
        { heading: "5. Responsible use", body: "You must have a lawful basis and the required consent to contact people. Do not use the platform for unlawful messages, impersonation, fraud, harassment, bulk spam, unauthorised scraping or content that violates a provider's policies. Campaign tools include consent and anti-spam controls, but you remain responsible for the messages and recipients you select." },
        { heading: "6. Availability and termination", body: "We may suspend or limit access to protect the platform, a connected provider, customers or third parties, or when an account breaches these Terms. We aim to keep the service available, but external APIs, networks and provider reviews are outside our control." },
        { heading: "7. Contact and updates", body: "Questions can be submitted through the support area of the platform. We may update these Terms when the service, providers or applicable requirements change. The latest version will remain available at this URL." },
      ],
    },
    privacy: {
      title: "Privacy Policy",
      intro: "This Policy explains how NEGOBOT-MOZ handles information when a customer creates a workspace or connects an authorised channel.",
      sections: [
        { heading: "1. Information we handle", body: "We may handle account details, workspace and billing region, business profile information, contacts entered by the customer, conversation events, campaign records, support requests, technical logs and integration status. We do not ask customers to send provider passwords to NEGOBOT-MOZ." },
        { heading: "2. Connected-channel credentials", body: "OAuth access and refresh tokens, Telegram bot tokens and webhook secrets are received by the backend, encrypted at rest and associated with the customer's tenant. Tokens are not intentionally displayed in the React interface, public pages or API responses. A customer can disconnect an integration from the platform." },
        { heading: "3. Why we use information", body: "We use information to provide the requested service, route inbound events, operate automations, enforce tenant isolation, protect accounts, process payments and support customers. AI features process only the content needed for the selected workflow and may be subject to the configured provider's terms." },
        { heading: "4. Providers and external services", body: "Connected channels remain controlled by their own providers, including Meta, TikTok, Telegram, X, LinkedIn and Evolution API. When a customer authorises a provider, that provider may process data under its own privacy policy. We do not claim ownership of a customer's social account or content." },
        { heading: "5. Retention and security", body: "We retain workspace records while needed to provide the service, meet operational requirements or resolve disputes. We use tenant-scoped access checks, encrypted secrets, HTTPS callbacks, webhook verification and audit records. No internet service can guarantee absolute security, so customers must protect their own credentials and authorised users." },
        { heading: "6. Customer responsibilities and rights", body: "Customers must have the necessary rights and notices for contact data and messages they provide. You may request correction, disconnection or deletion of information through the platform support area, subject to records we must retain for security, legal or payment purposes." },
        { heading: "7. Changes and contact", body: "We may update this Policy when our service or integrations change. The current version is published at this URL. Privacy questions can be sent through the support area of the NEGOBOT-MOZ platform." },
      ],
    },
  },
  pt: {
    terms: {
      title: "Termos de Serviço",
      intro: "Estes Termos regulam o acesso e a utilização da plataforma de atendimento e automação omnichannel da NEGOBOT-MOZ.",
      sections: [
        { heading: "1. O serviço", body: "A NEGOBOT-MOZ fornece um espaço alojado para conversas com clientes, gestão de contactos, campanhas, fluxos assistidos por IA e integrações autorizadas. As funcionalidades dependem do plano, da disponibilidade do fornecedor e das permissões concedidas em cada canal." },
        { heading: "2. Conta e espaço", body: "És responsável pela exactidão dos dados de registo, pela segurança das credenciais e pela actividade realizada no teu espaço. Cada espaço de cliente é isolado dos restantes. Não deves partilhar o acesso com pessoas não autorizadas pelo teu negócio." },
        { heading: "3. Demonstração, planos e pagamentos", body: "As contas elegíveis recebem uma demonstração Premium de dois dias segundo a política da plataforma. A demonstração não garante que um fornecedor externo aprove todos os canais. Os planos, a validação M-Pesa e o checkout internacional estão descritos na plataforma e podem ser actualizados com aviso." },
        { heading: "4. Canais ligados", body: "Ao ligares WhatsApp, Instagram, Facebook, TikTok, Telegram, LinkedIn, X ou outro fornecedor, autorizas a NEGOBOT-MOZ a utilizar apenas as permissões e credenciais necessárias para a integração escolhida. Podes desligar um canal na plataforma. Os termos, limites, revisões e restrições regionais do fornecedor continuam aplicáveis." },
        { heading: "5. Utilização responsável", body: "Deves ter base legal e consentimento necessário para contactar pessoas. Não uses a plataforma para mensagens ilícitas, personificação, fraude, assédio, spam em massa, scraping não autorizado ou conteúdo que viole as políticas do fornecedor. Continuas responsável pelas mensagens e destinatários que seleccionares." },
        { heading: "6. Disponibilidade e suspensão", body: "Podemos suspender ou limitar o acesso para proteger a plataforma, um fornecedor, clientes ou terceiros, ou quando estes Termos forem violados. Procuramos manter o serviço disponível, mas APIs, redes e revisões externas não estão totalmente sob o nosso controlo." },
        { heading: "7. Contacto e actualizações", body: "As dúvidas podem ser enviadas pela área de suporte da plataforma. Podemos actualizar estes Termos quando o serviço, fornecedores ou requisitos aplicáveis mudarem. A versão actual ficará disponível neste endereço." },
      ],
    },
    privacy: {
      title: "Política de Privacidade",
      intro: "Esta Política explica como a NEGOBOT-MOZ trata informações quando um cliente cria um espaço ou liga um canal autorizado.",
      sections: [
        { heading: "1. Informação tratada", body: "Podemos tratar dados da conta, espaço e região de facturação, perfil empresarial, contactos introduzidos pelo cliente, eventos de conversas, campanhas, pedidos de suporte, logs técnicos e estado das integrações. Não pedimos que os clientes enviem passwords dos fornecedores para a NEGOBOT-MOZ." },
        { heading: "2. Credenciais dos canais", body: "Tokens OAuth, tokens de bots Telegram e secrets de webhooks são recebidos pelo backend, cifrados em repouso e associados ao tenant do cliente. Os tokens não são intencionalmente mostrados na interface React, páginas públicas ou respostas da API. O cliente pode desligar a integração." },
        { heading: "3. Finalidades", body: "Usamos a informação para prestar o serviço, receber eventos, executar automações, aplicar isolamento por tenant, proteger contas, processar pagamentos e apoiar clientes. As funcionalidades de IA tratam apenas o conteúdo necessário para o fluxo escolhido e podem estar sujeitas aos termos do fornecedor configurado." },
        { heading: "4. Fornecedores externos", body: "Os canais ligados continuam sob o controlo dos respectivos fornecedores, incluindo Meta, TikTok, Telegram, X, LinkedIn e Evolution API. Quando um cliente autoriza um fornecedor, esse fornecedor pode tratar dados segundo a sua própria política de privacidade. Não reclamamos a propriedade da conta social ou do conteúdo do cliente." },
        { heading: "5. Conservação e segurança", body: "Conservamos registos enquanto forem necessários para prestar o serviço, cumprir requisitos operacionais ou resolver disputas. Usamos verificações por tenant, segredos cifrados, callbacks HTTPS, validação de webhooks e auditoria. Nenhum serviço online garante segurança absoluta; os clientes devem proteger as suas credenciais." },
        { heading: "6. Responsabilidades e direitos", body: "Os clientes devem ter os direitos e avisos necessários para os dados de contactos e mensagens fornecidos. Podes pedir correcção, desligamento ou eliminação pela área de suporte, sujeito aos registos que tenhamos de conservar por segurança, lei ou pagamentos." },
        { heading: "7. Alterações e contacto", body: "Podemos actualizar esta Política quando o serviço ou as integrações mudarem. A versão actual é publicada neste endereço. As questões de privacidade podem ser enviadas pela área de suporte da plataforma NEGOBOT-MOZ." },
      ],
    },
  },
};

export function LegalPage({ kind }: { kind: LegalKind }) {
  const [language, setLanguage] = useState<Language>("en");
  const copy = CONTENT[language][kind];
  return <div className="public-site"><main className="public-section" style={{ minHeight: "100vh" }}><div className="public-container" style={{ maxWidth: 860 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "center", marginBottom: 48 }}><a className="public-button public-button-light" href="/"><ArrowLeft size={16} /> {language === "en" ? "Back to NEGOBOT-MOZ" : "Voltar à NEGOBOT-MOZ"}</a><div className="public-language-switcher" aria-label="Language"><button className={language === "pt" ? "active" : ""} onClick={() => setLanguage("pt")}>PT</button><span>/</span><button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>EN</button></div></div><p className="public-eyebrow"><ShieldCheck size={15} /> NEGOBOT-MOZ</p><h1>{copy.title}</h1><p className="public-lead" style={{ maxWidth: 760 }}>{copy.intro}</p><p className="muted" style={{ marginTop: 12 }}>{language === "en" ? "Last updated: 19 August 2026" : "Última actualização: 19 de Agosto de 2026"}</p><div style={{ marginTop: 48, display: "grid", gap: 30 }}>{copy.sections.map((section) => <section key={section.heading}><h2>{section.heading}</h2><p style={{ lineHeight: 1.8, maxWidth: 780 }}>{section.body}</p></section>)}</div></div></main></div>;
}
