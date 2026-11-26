import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AuthLegal } from "@/components/auth/AuthLegal";
import { AuthBanners } from "@/components/auth/AuthBanners";
import { useAuth } from "@/lib/auth-context";
import { requestPasswordReset, resetPassword } from "@/lib/api/auth";
import { SHOW_FACEBOOK_LOGIN } from "@/lib/features";

export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Zumit · Inicia sesión" }] }),
  component: LoginPage,
});

/** Motivos que devuelve el callback de Google o Facebook (?auth_error=…), en palabras del usuario. */
const AUTH_ERRORS: Record<string, string> = {
  oauth: 'No pudimos completar el acceso. Inténtalo de nuevo y acepta los permisos que se piden.',
  denied: 'Cancelaste el acceso. Puedes intentarlo de nuevo cuando quieras.',
  unverified: 'Tu correo de Google no está verificado, así que no podemos usarlo.',
  no_email: 'Tu cuenta de Facebook no comparte un correo con nosotros. Usa otro método o crea la cuenta con tu correo.',
  exists: 'Ya existe una cuenta con ese correo asociada a otra cuenta de Google. Entra con tu contraseña.',
  exists_other: 'Ya existe una cuenta con ese correo creada con otro método (Google o Facebook). Entra con ese mismo método.',
  blocked: 'Esta cuenta está bloqueada. Escríbenos si crees que es un error.',
  suspended: 'Este negocio está suspendido. Escríbenos para reactivarlo.',
  server: 'Algo salió mal al entrar. Inténtalo de nuevo en un momento.',
};

/** Correo que viaja dentro del ticket de vinculación (solo para mostrarlo; el servidor no confía en esto). */
function emailFromTicket(ticket: string): string {
  try {
    const body = ticket.split('.')[0].replace(/-/g, '+').replace(/_/g, '/');
    const json = JSON.parse(atob(body + '='.repeat((4 - (body.length % 4)) % 4)));
    return typeof json.email === 'string' ? json.email : '';
  } catch {
    return '';
  }
}

/** Qué se ve en la tarjeta: entrar, pedir el enlace, elegir contraseña nueva o vincular Google a la cuenta. */
type Mode = 'login' | 'forgot' | 'reset' | 'link';

function LoginPage() {
  const navigate = useNavigate();
  const { login, signInWithGoogle, signInWithFacebook, completeOAuthSignIn, completeOAuthLink } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<'google' | 'facebook' | 'ticket' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('login');
  const [linkTicket, setLinkTicket] = useState('');
  const [linkEmail, setLinkEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const anyLoading = loading || !!oauthLoading;
  const handledReturn = useRef(false);

  // Al volver de Google o Facebook el callback deja un ticket en el fragmento (#auth_ticket=…) o un motivo en ?auth_error=…
  // Otros dos fragmentos: #link_ticket (hay que escribir la contraseña para vincular) y #reset_token (enlace del correo).
  useEffect(() => {
    if (handledReturn.current) return;
    handledReturn.current = true;
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const ticket = hash.get('auth_ticket');
    const link = hash.get('link_ticket');
    const reset = hash.get('reset_token');
    const reason = new URLSearchParams(window.location.search).get('auth_error');
    if (!ticket && !link && !reset && !reason) return;
    // Se limpia la URL ya: el ticket no debe quedar en el historial ni en un enlace copiado.
    window.history.replaceState(null, '', window.location.pathname);
    if (reason) { setError(AUTH_ERRORS[reason] ?? AUTH_ERRORS.server); return; }
    if (link) { setLinkTicket(link); setLinkEmail(emailFromTicket(link)); setMode('link'); return; }
    if (reset) { setResetToken(reset); setMode('reset'); return; }
    setOauthLoading('ticket'); // no se sabe por cuál proveedor volvió: se bloquean los botones sin girar ninguno
    completeOAuthSignIn(ticket!)
      .then(({ isNew }) => navigate({ to: isNew ? '/onboarding' : '/dashboard' }))
      .catch((err) => { setError((err as Error).message ?? AUTH_ERRORS.server); setOauthLoading(null); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const goTo = (next: Mode) => { setMode(next); setError(null); setNotice(null); setPassword(''); setNewPassword(''); };

  const handleLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await completeOAuthLink(linkTicket, password);
      navigate({ to: '/dashboard' });
    } catch (err) {
      setError((err as Error).message ?? AUTH_ERRORS.server);
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset(email.trim());
      setNotice('Si ese correo tiene una cuenta, te enviamos un enlace para elegir una contraseña nueva. Revisa también el spam; vence en 1 hora.');
    } catch (err) {
      setError((err as Error).message ?? AUTH_ERRORS.server);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await resetPassword(resetToken, newPassword);
      goTo('login');
      setNotice('Listo, tu contraseña quedó guardada. Ya puedes entrar con ella.');
    } catch (err) {
      setError((err as Error).message ?? AUTH_ERRORS.server);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate({ to: '/dashboard' });
    } catch (err) {
      setError((err as Error).message ?? 'Correo o contraseña incorrectos');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setOauthLoading('google');
    setError(null);
    try {
      await signInWithGoogle();
      // La función navega con window.location — si llegamos aquí, reset por seguridad
      setOauthLoading(null);
    } catch (err) {
      setError((err as Error).message ?? 'Error al conectar con Google');
      setOauthLoading(null);
    }
  };

  const handleFacebook = async () => {
    setOauthLoading('facebook');
    setError(null);
    try {
      await signInWithFacebook();
      setOauthLoading(null);
    } catch (err) {
      setError((err as Error).message ?? 'Error al conectar con Facebook');
      setOauthLoading(null);
    }
  };

  // El botón «atrás» puede restaurar la página desde bfcache con el spinner colgado.
  useEffect(() => {
    const reset = (e: PageTransitionEvent) => { if (e.persisted) setOauthLoading(null); };
    window.addEventListener('pageshow', reset);
    return () => window.removeEventListener('pageshow', reset);
  }, []);

  return (
    <div className="auth">
      {/* form side */}
      <div className="auth-form-side">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link className="auth-brand" to="/">
            <img className="auth-brand__logo" src="/images/logo-borgona.png" alt="Zumit" />
          </Link>
          <Link className="auth-back" to="/">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M15 5l-7 7 7 7" /></svg>
            Volver al inicio
          </Link>
        </div>

        <div className="auth-form-wrap">
          <div className="auth-card">
            <h1 className="auth-h">{{
              login: 'Bienvenido de nuevo',
              link: 'Vincula tu cuenta de Google',
              forgot: 'Recupera tu contraseña',
              reset: 'Elige una contraseña nueva',
            }[mode]}</h1>
            <p className="auth-sub">{{
              login: 'Inicia sesión para entrar al panel de tu negocio.',
              link: <>Ya tienes una cuenta con <strong>{linkEmail || 'ese correo'}</strong>. Escribe su contraseña una vez para vincular Google a ella; no se crea otra cuenta.</>,
              forgot: 'Escribe el correo de tu cuenta y te enviamos un enlace para elegir una contraseña nueva.',
              reset: 'Mínimo 8 caracteres. El enlace sirve una sola vez.',
            }[mode]}</p>
            {oauthLoading === 'ticket' && <p className="auth-sub" role="status">Entrando a tu cuenta…</p>}
            {notice && (
              <div role="status" style={{
                padding: '9px 12px', borderRadius: 'var(--r-sm)', marginBottom: 12,
                background: 'var(--success-bg, #eef8f1)', border: '1px solid var(--success, #2e9b63)',
                color: 'var(--success-fg, #1f6b43)', font: '400 13px/1.4 var(--font-sans)',
              }}>{notice}</div>
            )}

            {mode !== 'login' && (
              <form onSubmit={mode === 'link' ? handleLink : mode === 'forgot' ? handleForgot : handleReset}>
                {mode === 'forgot' && !notice && (
                  <div className="field">
                    <label htmlFor="forgot-email">Correo</label>
                    <input id="forgot-email" type="email" required autoFocus placeholder="tu@negocio.com"
                      value={email} onChange={e => setEmail(e.target.value)} />
                  </div>
                )}
                {mode === 'link' && (
                  <div className="field">
                    <label htmlFor="link-pass">Contraseña de tu cuenta</label>
                    <input id="link-pass" type="password" required autoFocus placeholder="••••••••" autoComplete="current-password"
                      value={password} onChange={e => setPassword(e.target.value)} />
                  </div>
                )}
                {mode === 'reset' && (
                  <div className="field">
                    <label htmlFor="new-pass">Contraseña nueva</label>
                    <input id="new-pass" type="password" required minLength={8} autoFocus placeholder="Mínimo 8 caracteres"
                      autoComplete="new-password" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
                  </div>
                )}

                {error && (
                  <div role="alert" style={{
                    padding: '9px 12px', borderRadius: 'var(--r-sm)',
                    background: 'var(--danger-bg, #fff0f0)', border: '1px solid var(--danger, #e53e3e)',
                    color: 'var(--danger, #c53030)', font: '400 13px/1.4 var(--font-sans)', marginBottom: 4,
                  }}>{error}</div>
                )}

                {!(mode === 'forgot' && notice) && (
                  <button className="auth-btn" type="submit" disabled={anyLoading}>
                    {loading
                      ? 'Un momento…'
                      : mode === 'link' ? 'Vincular y entrar' : mode === 'forgot' ? 'Enviar enlace' : 'Guardar contraseña'}
                  </button>
                )}
                {mode === 'link' && (
                  <div className="auth-row" style={{ marginTop: 12 }}>
                    <a style={{ cursor: 'pointer', color: 'var(--wine)', font: '400 13px/1 var(--font-sans)' }}
                       onClick={() => { setEmail(linkEmail); goTo('forgot'); }}>
                      ¿Olvidaste tu contraseña?
                    </a>
                    <span />
                  </div>
                )}
                <div className="auth-foot">
                  <a style={{ cursor: 'pointer' }} onClick={() => goTo('login')}>Volver a iniciar sesión</a>
                </div>
              </form>
            )}

            {mode === 'login' && (<>
            {/* Google */}
            <button
              className="auth-google"
              onClick={handleGoogle}
              disabled={anyLoading}
              style={{ marginBottom: 10 }}
            >
              {oauthLoading === 'google' ? (
                <span style={{
                  width: 18, height: 18, borderRadius: '50%',
                  border: '2px solid rgba(0,0,0,0.12)', borderTopColor: '#4285F4',
                  display: 'inline-block', animation: 'hilo-spin 0.7s linear infinite',
                }} />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.5 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.9c-.3 1.4-1 2.5-2.2 3.3v2.8h3.6c2.1-1.9 3.2-4.8 3.2-7.9z" />
                  <path fill="#34A853" d="M12 23c2.9 0 5.4-1 7.2-2.6l-3.6-2.8c-1 .7-2.3 1.1-3.6 1.1-2.8 0-5.1-1.9-6-4.4H2.3v2.9C4.1 20.6 7.8 23 12 23z" />
                  <path fill="#FBBC05" d="M6 14.3c-.2-.7-.4-1.4-.4-2.3s.1-1.6.4-2.3V6.8H2.3C1.5 8.3 1 10.1 1 12s.5 3.7 1.3 5.2L6 14.3z" />
                  <path fill="#EA4335" d="M12 5.4c1.6 0 3 .5 4.1 1.6l3.1-3.1C17.4 2.1 14.9 1 12 1 7.8 1 4.1 3.4 2.3 6.8L6 9.7c.9-2.5 3.2-4.3 6-4.3z" />
                </svg>
              )}
              Continuar con Google
            </button>

            {/* Facebook (oculto con SHOW_FACEBOOK_LOGIN) */}
            {SHOW_FACEBOOK_LOGIN && <button
              className="auth-google"
              onClick={handleFacebook}
              disabled={anyLoading}
              style={{ marginBottom: 16, color: '#1877F2' }}
            >
              {oauthLoading === 'facebook' ? (
                <span style={{
                  width: 18, height: 18, borderRadius: '50%',
                  border: '2px solid rgba(24,119,242,0.2)', borderTopColor: '#1877F2',
                  display: 'inline-block', animation: 'hilo-spin 0.7s linear infinite',
                }} />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#1877F2">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                </svg>
              )}
              Continuar con Facebook
            </button>}

            <div className="auth-or">o con tu correo</div>

            <form onSubmit={handleSubmit}>
              <div className="field">
                <label htmlFor="email">Correo</label>
                <input
                  id="email" type="email" required
                  placeholder="tu@negocio.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="pass">Contraseña</label>
                <input
                  id="pass" type="password" required
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                />
              </div>

              <div className="auth-row">
                <span />
                <a style={{ cursor: 'pointer', color: 'var(--wine)', font: '400 13px/1 var(--font-sans)' }}
                   onClick={() => { goTo('forgot'); }}>
                  ¿Olvidaste tu contraseña?
                </a>
              </div>

              {error && (
                <div style={{
                  padding: '9px 12px', borderRadius: 'var(--r-sm)',
                  background: 'var(--danger-bg, #fff0f0)',
                  border: '1px solid var(--danger, #e53e3e)',
                  color: 'var(--danger, #c53030)',
                  font: '400 13px/1.4 var(--font-sans)', marginBottom: 4,
                }}>
                  {error}
                </div>
              )}

              <button className="auth-btn" type="submit" disabled={anyLoading}>
                {loading ? 'Iniciando sesión…' : 'Iniciar sesión'}
              </button>
            </form>

            <div className="auth-foot">
              ¿No tienes cuenta?{' '}
              <Link to="/signup">Crea una gratis</Link>
            </div>
            </>)}
            <AuthLegal action="entrar" />
          </div>
        </div>
        <div />
      </div>

      <AuthBanners />
    </div>
  );
}
