import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/signup")({
  head: () => ({ meta: [{ title: "Hilo · Crea tu cuenta" }] }),
  component: SignupPage,
});

function SignupPage() {
  const navigate = useNavigate();
  const { register, signInWithGoogle, signInWithFacebook } = useAuth();
  const [businessName, setBusinessName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<'google' | 'facebook' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await register(email, password, businessName);
      navigate({ to: '/onboarding' });
    } catch (err) {
      setError((err as Error).message ?? 'Error al crear la cuenta');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setOauthLoading('google');
    setError(null);
    try {
      await signInWithGoogle();
      // signInWithOAuth llama window.location.assign — si llegamos aquí es que aún no navegó
      // (caso raro: redirect URL no whitelistada devuelve sin error). Reseteamos.
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

  const anyLoading = loading || !!oauthLoading;

  // Si el navegador restaura la página desde bfcache (botón atrás después de OAuth),
  // los botones quedan disabled porque oauthLoading sigue en 'google'/'facebook'.
  // pageshow con e.persisted=true indica restauración desde caché.
  useEffect(() => {
    const reset = (e: PageTransitionEvent) => {
      if (e.persisted) {
        setOauthLoading(null);
        setLoading(false);
      }
    };
    window.addEventListener('pageshow', reset);
    return () => window.removeEventListener('pageshow', reset);
  }, []);

  return (
    <div className="auth">
      {/* form side */}
      <div className="auth-form-side">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link className="auth-brand" to="/">
            <span style={{ width: 32, height: 32, borderRadius: 10, background: 'var(--wine)', display: 'grid', placeItems: 'center' }}>
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 3v6a4 4 0 0 0 8 0 4 4 0 0 1 4 4v8" />
                <circle cx="6" cy="3" r="1.4" fill="#fff" stroke="none" />
                <circle cx="18" cy="21" r="1.4" fill="#fff" stroke="none" />
              </svg>
            </span>
            <span className="auth-brand-name">Hilo</span>
          </Link>
          <Link className="auth-back" to="/">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M15 5l-7 7 7 7" /></svg>
            Volver al inicio
          </Link>
        </div>

        <div className="auth-form-wrap">
          <div className="auth-card">
            <h1 className="auth-h">Crea tu cuenta</h1>
            <p className="auth-sub">Empieza gratis 14 días. Sin tarjeta de crédito.</p>

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

            {/* Facebook */}
            <button
              onClick={handleFacebook}
              disabled={anyLoading}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                padding: '11px 16px', border: '1.5px solid var(--line-strong)', borderRadius: 'var(--r-md)',
                background: 'var(--surface)', cursor: anyLoading ? 'not-allowed' : 'pointer', marginBottom: 16,
                font: '500 14.5px/1 var(--font-sans)', color: '#1877F2',
                transition: 'all var(--dur-2)', opacity: anyLoading ? 0.6 : 1,
              }}
              onMouseEnter={e => { if (!anyLoading) (e.currentTarget as HTMLElement).style.background = 'rgba(24,119,242,0.06)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'var(--surface)'; }}
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
            </button>

            <div className="auth-or">o con tu correo</div>

            <form onSubmit={handleSubmit}>
              <div className="field">
                <label htmlFor="biz">Nombre del negocio</label>
                <input
                  id="biz" type="text" required
                  placeholder="ej: Barbería Juanes"
                  value={businessName}
                  onChange={e => setBusinessName(e.target.value)}
                />
              </div>
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
                  id="pass" type="password" required minLength={8}
                  placeholder="Mínimo 8 caracteres"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                />
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
                {loading ? 'Creando cuenta…' : 'Crear cuenta gratis'}
              </button>
            </form>

            <div className="auth-foot">
              ¿Ya tienes cuenta?{' '}
              <Link to="/login">Inicia sesión</Link>
            </div>
          </div>
        </div>
        <div />
      </div>

      {/* brand side */}
      <div className="auth-brand-side">
        <div className="abs-glow" />
        <div className="abs-eyebrow">Tu agenda vive en WhatsApp</div>
        <div>
          <p className="abs-quote">"Dejé de perder citas por no contestar a tiempo. Hilo responde por mí, hasta cuando estoy con cliente."</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 20, position: 'relative', zIndex: 1 }}>
            <span style={{ width: 42, height: 42, borderRadius: '50%', background: 'rgba(255,255,255,0.18)', display: 'grid', placeItems: 'center', font: '600 15px/1 var(--font-sans)' }}>CR</span>
            <div>
              <div style={{ font: '600 14.5px/1.2 var(--font-sans)' }}>Camilo Restrepo</div>
              <div style={{ font: '400 12.5px/1.2 var(--font-sans)', color: 'rgba(255,255,255,0.65)' }}>Navaja &amp; Tinta · Medellín</div>
            </div>
          </div>
        </div>
        <ul className="abs-list">
          <li><span className="ci"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></span>Gratis 14 días · sin tarjeta</li>
          <li><span className="ci"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></span>Conserva tu número de WhatsApp</li>
          <li><span className="ci"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></span>Listo en minutos, sin instalar nada</li>
        </ul>
      </div>
    </div>
  );
}
