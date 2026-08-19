import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { PLATFORM_TRANSLATIONS } from "./platformTranslations";

const ORIGINAL_TEXT = new WeakMap<Text, string>();
const ORIGINAL_ATTRIBUTES = new WeakMap<Element, Record<string, string>>();
const TRANSLATABLE_ATTRIBUTES = ["placeholder", "title", "aria-label"];
const ENGLISH_TO_PORTUGUESE = Object.fromEntries(Object.entries(PLATFORM_TRANSLATIONS).map(([portuguese, english]) => [english, portuguese]));

function translatePlatformDom(language: PlatformLanguage) {
  if (typeof document === "undefined" || !document.body) return;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    const textNode = node as Text;
    if (!ORIGINAL_TEXT.has(textNode)) { const current = textNode.nodeValue || ""; const trimmedCurrent = current.trim(); ORIGINAL_TEXT.set(textNode, language === "en" ? (ENGLISH_TO_PORTUGUESE[trimmedCurrent] || current) : current); }
    const original = ORIGINAL_TEXT.get(textNode) || "";
    const trimmed = original.trim();
    const translated = language === "en" ? PLATFORM_TRANSLATIONS[trimmed] : undefined;
    if (translated) {
      const leading = original.match(/^\s*/)?.[0] || "";
      const trailing = original.match(/\s*$/)?.[0] || "";
      const nextValue = `${leading}${translated}${trailing}`;
      if (textNode.nodeValue !== nextValue) textNode.nodeValue = nextValue;
    } else if (language === "pt") {
      if (textNode.nodeValue !== original) textNode.nodeValue = original;
    }
  }
  document.body.querySelectorAll<HTMLElement>("[placeholder], [title], [aria-label]").forEach((element) => {
    const existing = ORIGINAL_ATTRIBUTES.get(element) || {};
    for (const attribute of TRANSLATABLE_ATTRIBUTES) {
      const value = element.getAttribute(attribute);
      if (value !== null && existing[attribute] === undefined) existing[attribute] = language === "en" ? (ENGLISH_TO_PORTUGUESE[value] || value) : value;
      const original = existing[attribute];
      if (original !== undefined) { const nextValue = language === "en" ? (PLATFORM_TRANSLATIONS[original] || original) : original; if (element.getAttribute(attribute) !== nextValue) element.setAttribute(attribute, nextValue); }
    }
    ORIGINAL_ATTRIBUTES.set(element, existing);
  });
}

export type PlatformLanguage = "en" | "pt";

type PlatformLanguageContextValue = {
  language: PlatformLanguage;
  setLanguage: (language: PlatformLanguage) => void;
};

const STORAGE_KEY = "negobot-platform-language";
const PlatformLanguageContext = createContext<PlatformLanguageContextValue | null>(null);

export function PlatformLanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<PlatformLanguage>(() => {
    if (typeof window === "undefined") return "en";
    return window.localStorage.getItem(STORAGE_KEY) === "pt" ? "pt" : "en";
  });

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language === "en" ? "en" : "pt-MZ";
    translatePlatformDom(language);
    const observer = new MutationObserver(() => translatePlatformDom(language));
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: TRANSLATABLE_ATTRIBUTES });
    return () => observer.disconnect();
  }, [language]);

  const value = useMemo(() => ({ language, setLanguage }), [language]);
  return <PlatformLanguageContext.Provider value={value}>{children}</PlatformLanguageContext.Provider>;
}

export function usePlatformLanguage() {
  const context = useContext(PlatformLanguageContext);
  if (!context) throw new Error("usePlatformLanguage must be used inside PlatformLanguageProvider");
  return context;
}

export function usePlatformText() {
  const { language } = usePlatformLanguage();
  return (portuguese: string, english: string) => language === "en" ? english : portuguese;
}

export function LanguageToggle() {
  const { language, setLanguage } = usePlatformLanguage();
  return <div className="platform-language-toggle" aria-label="Interface language">
    <button type="button" className={language === "pt" ? "active" : ""} aria-pressed={language === "pt"} onClick={() => setLanguage("pt")}>PT</button>
    <span>/</span>
    <button type="button" className={language === "en" ? "active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button>
  </div>;
}
