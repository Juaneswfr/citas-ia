import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/verify-email")({
  head: () => ({ meta: [{ title: "Hilo · Verifica tu correo" }] }),
  validateSearch: (s: Record<string, unknown>) => ({
    email: (s.email as string | undefined) ?? '',
  }),
  component: VerifyEmailPage,
});

function VerifyEmailPage() {
  const { email } = useSearch({ from: '/verify-email' });
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resend = async () => {
    // shortcut: reenvío sin Supabase — muestra mensaje estático
    setResent(true);
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--paper)', padding: '24px',
    }}>
      <div style={{ width: '100%', maxWidth: 460, textAlign: 'center' }}>
        {/* Icon */}
        <div style={{
          width: 72, height: 72, borderRadius: 20, background: 'var(--wine-50)',
          display: 'grid', placeItems: 'center', margin: '0 auto 24px',
        }}>
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--wine)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="4" width="20" height="16" rx="2" />
            <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
          </svg>
        </div>

        <h1 style={{ margin: '0 0 10px', font: '400 30px/1.1 var(--font-serif)', color: 'var(--ink-1)', letterSpacing: '-0.01em' }}>
          Revisa tu <span className="serif-i">correo</span>
        </h1>

        <p style={{ margin: '0 0 6px', font: '400 15px/1.5 var(--font-sans)', color: 'var(--ink-2)' }}>
          Te enviamos un enlace de verificación a:
        </p>
        <p style={{ margin: '0 0 28px', font: '600 15px/1 var(--font-sans)', color: 'var(--ink-1)' }}>
          {email || 'tu correo'}
        </p>

        <div style={{
          background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)',
          padding: '20px 22px', marginBottom: 24, textAlign: 'left',
        }}>
          <div style={{ font: '500 13.5px/1.2 var(--font-sans)', color: 'var(--ink-1)', marginBottom: 10 }}>
            ¿Qué hacer ahora?
          </div>
          <ol style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              'Abre el correo que te enviamos',
              'Haz clic en "Verificar mi cuenta"',
              'Listo — te llevaremos directo al panel',
            ].map((step, i) => (
              <li key={i} style={{ font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-2)' }}>
                {step}
              </li>
            ))}
          </ol>
        </div>

        {/* Resend */}
        {resent ? (
          <div style={{
            padding: '10px 14px', borderRadius: 'var(--r-md)', marginBottom: 16,
            background: 'color-mix(in srgb, var(--success) 10%, var(--surface))',
            border: '1px solid color-mix(in srgb, var(--success) 30%, transparent)',
            font: '400 13px/1.3 var(--font-sans)', color: 'var(--success)',
          }}>
            ¡Correo reenviado! Revisa tu bandeja (y la carpeta de spam).
          </div>
        ) : error ? (
          <div style={{
            padding: '10px 14px', borderRadius: 'var(--r-md)', marginBottom: 16,
            background: 'var(--danger-bg, #fff0f0)',
            border: '1px solid var(--danger, #e53e3e)',
            font: '400 13px/1.3 var(--font-sans)', color: 'var(--danger, #c53030)',
          }}>
            {error}
          </div>
        ) : null}

        <button
          onClick={resend}
          disabled={resending || resent}
          style={{
            width: '100%', padding: '12px', borderRadius: 'var(--r-md)',
            border: '1.5px solid var(--line-strong)', background: 'var(--surface)',
            font: '500 14.5px/1 var(--font-sans)', color: 'var(--ink-2)', cursor: 'pointer',
            marginBottom: 14, opacity: resending || resent ? 0.5 : 1,
            transition: 'all var(--dur-2)',
          }}
          onMouseEnter={e => { if (!resending && !resent) (e.currentTarget as HTMLElement).style.borderColor = 'var(--wine)'; (e.currentTarget as HTMLElement).style.color = 'var(--wine)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--line-strong)'; (e.currentTarget as HTMLElement).style.color = 'var(--ink-2)'; }}
        >
          {resending ? 'Reenviando…' : resent ? 'Correo enviado ✓' : '¿No llegó? Reenviar correo'}
        </button>

        <div style={{ font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-3)' }}>
          <Link to="/login" style={{ color: 'var(--wine)', textDecoration: 'none' }}>
            ← Volver al inicio de sesión
          </Link>
        </div>

        <div style={{ marginTop: 32, font: '400 11.5px/1.4 var(--font-sans)', color: 'var(--ink-4)' }}>
          El enlace expira en 24 horas. Si no encuentras el correo, revisa la carpeta de spam.
        </div>
      </div>
    </div>
  );
}
