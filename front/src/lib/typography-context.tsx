import { createContext, useContext, useEffect, useMemo, useState } from "react";

export interface FontPair {
  id: string;
  label: string;
  heading: string;
  body: string;
  description: string;
}

export const FONT_PAIRS: FontPair[] = [
  {
    id: "cabin-epilogue",
    label: "Cabin + Epilogue",
    heading: '"Cabin", ui-sans-serif, system-ui, sans-serif',
    body: '"Epilogue", ui-sans-serif, system-ui, sans-serif',
    description: "Calido y profesional. Por defecto.",
  },
  {
    id: "fraunces-manrope",
    label: "Fraunces + Manrope",
    heading: '"Fraunces", ui-serif, Georgia, serif',
    body: '"Manrope", ui-sans-serif, system-ui, sans-serif',
    description: "Editorial con cuerpo neutro.",
  },
  {
    id: "outfit-figtree",
    label: "Outfit + Figtree",
    heading: '"Outfit", ui-sans-serif, system-ui, sans-serif',
    body: '"Figtree", ui-sans-serif, system-ui, sans-serif',
    description: "Moderno y amigable.",
  },
  {
    id: "dm-serif-dm-sans",
    label: "DM Serif + DM Sans",
    heading: '"DM Serif Display", ui-serif, Georgia, serif',
    body: '"DM Sans", ui-sans-serif, system-ui, sans-serif',
    description: "Magazine con contraste alto.",
  },
];

const STORAGE_KEY = "citaflow.font.pair.v1";

interface Ctx {
  current: FontPair;
  setPair: (id: string) => void;
  pairs: FontPair[];
}

const TypographyContext = createContext<Ctx | null>(null);

function applyPair(pair: FontPair) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.style.setProperty("--font-heading-family", pair.heading);
  root.style.setProperty("--font-body-family", pair.body);
}

export function TypographyProvider({ children }: { children: React.ReactNode }) {
  const [currentId, setCurrentId] = useState<string>(FONT_PAIRS[0].id);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved && FONT_PAIRS.some((p) => p.id === saved)) {
      setCurrentId(saved);
    }
  }, []);

  const current = useMemo(
    () => FONT_PAIRS.find((p) => p.id === currentId) ?? FONT_PAIRS[0],
    [currentId]
  );

  useEffect(() => {
    applyPair(current);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, current.id);
    }
  }, [current]);

  const value = useMemo<Ctx>(
    () => ({ current, setPair: setCurrentId, pairs: FONT_PAIRS }),
    [current]
  );

  return <TypographyContext.Provider value={value}>{children}</TypographyContext.Provider>;
}

export function useTypography() {
  const ctx = useContext(TypographyContext);
  if (!ctx) throw new Error("useTypography must be used inside TypographyProvider");
  return ctx;
}
