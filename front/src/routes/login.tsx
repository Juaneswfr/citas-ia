import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Hilo · Inicia sesión" }] }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { login, signInWithGoogle } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const anyLoading = loading || googleLoading;

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
    setGoogleLoading(true);
    setError(null);
    try {
      await signInWithGoogle();
      // window.location.assign ejecutado — si llegamos aquí, reset por seguridad
      setGoogleLoading(false);
    } catch (err) {
      setError((err as Error).message ?? 'Error al conectar con Google');
      setGoogleLoading(false);
    }
  };

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
            <h1 className="auth-h">Bienvenido de nuevo</h1>
            <p className="auth-sub">Inicia sesión para entrar al panel de tu negocio.</p>

            {/* Google */}
            <button
              className="auth-google"
              onClick={handleGoogle}
              disabled={anyLoading}
              style={{ marginBottom: 16 }}
            >
              {googleLoading ? (
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
                <a style={{ cursor: 'pointer', color: 'var(--wine)', font: '400 13px/1 var(--font-sans)' }}>
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
