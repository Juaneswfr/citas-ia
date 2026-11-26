import { Link } from "@tanstack/react-router";

/** Aviso legal de las pantallas de acceso. Con Google o Facebook la cuenta se crea sola si el correo no existe,
 *  así que también se dice aquí, no solo en /signup. */
export function AuthLegal({ action }: { action: "entrar" | "crear" }) {
  return (
    <p className="auth-legal" style={{ marginTop: 14, font: "400 12px/1.5 var(--font-sans)", textAlign: "center", opacity: 0.75 }}>
      {action === "crear"
        ? "Al crear tu cuenta aceptas las "
        : "Si aún no tienes cuenta, continuar con Google o Facebook la crea con prueba gratis. Al continuar aceptas las "}
      <Link to="/condiciones-del-servicio">Condiciones del servicio</Link> y la{" "}
      <Link to="/politicas-de-privacidad">Política de privacidad</Link>.
    </p>
  );
}
