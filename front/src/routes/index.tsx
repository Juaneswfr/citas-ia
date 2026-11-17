import { createFileRoute } from "@tanstack/react-router";
import { useRef } from "react";
import { useReveal } from "@/hooks/use-reveal";
import { Header } from "@/components/landing/Header";
import { Hero } from "@/components/landing/Hero";
import { Intro } from "@/components/landing/Intro";
import { Steps } from "@/components/landing/Steps";
import { Benefits } from "@/components/landing/Benefits";
import { Platform } from "@/components/landing/Platform";
import { Founders } from "@/components/landing/Founders";
import { Faq } from "@/components/landing/Faq";
import { Cta } from "@/components/landing/Cta";
import { Footer } from "@/components/landing/Footer";
import landingCss from "@/styles/landing.css?url";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [{ title: "Zumit · Tú atiendes. Zumit agenda." }],
    links: [
      { rel: "stylesheet", href: landingCss },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap",
      },
    ],
  }),
  component: LandingPage,
});

function LandingPage() {
  const root = useRef<HTMLDivElement>(null);
  useReveal(root);

  return (
    <div ref={root} className="home">
      <Header />
      <main>
        <Hero />
        <Intro />
        <Steps />
        <Benefits />
        <Platform />
        <Founders />
        <Faq />
        <Cta />
      </main>
      <Footer />
    </div>
  );
}
