import type { ReactNode } from "react";

export function Tag({ children, pop = false }: { children: ReactNode; pop?: boolean }) {
  return <span className={`home-tag${pop ? " home-tag--pop" : ""}`}>{children}</span>;
}
