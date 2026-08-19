import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

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
  }, [language]);

  const value = useMemo(() => ({ language, setLanguage }), [language]);
  return <PlatformLanguageContext.Provider value={value}>{children}</PlatformLanguageContext.Provider>;
}

export function usePlatformLanguage() {
  const context = useContext(PlatformLanguageContext);
  if (!context) throw new Error("usePlatformLanguage must be used inside PlatformLanguageProvider");
  return context;
}

export function LanguageToggle() {
  const { language, setLanguage } = usePlatformLanguage();
  return <div className="platform-language-toggle" aria-label="Interface language">
    <button type="button" className={language === "pt" ? "active" : ""} aria-pressed={language === "pt"} onClick={() => setLanguage("pt")}>PT</button>
    <span>/</span>
    <button type="button" className={language === "en" ? "active" : ""} aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button>
  </div>;
}
