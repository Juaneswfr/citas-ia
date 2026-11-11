// Utilidades puras de comprobantes de pago (validación en el cliente y selección del último cobro).
// El backend vuelve a validar el contenido real del archivo; esto solo evita subidas inútiles.

import type { PaymentOut } from '@/lib/types/accounting';

export const RECEIPT_MAX_BYTES = 5 * 1024 * 1024;
export const RECEIPT_ACCEPT = 'image/jpeg,image/png,image/webp,application/pdf';
const ALLOWED_TYPES = RECEIPT_ACCEPT.split(',');

/** Devuelve un mensaje de error si el archivo no sirve como comprobante, o null si es válido. */
export function validateReceipt(file: File): string | null {
  if (file.size === 0) return 'El archivo está vacío.';
  if (file.size > RECEIPT_MAX_BYTES) return 'El archivo supera 5 MB.';
  if (!ALLOWED_TYPES.includes(file.type)) return 'Usa una imagen (JPG, PNG, WebP) o un PDF.';
  return null;
}

/** Id del cobro más reciente de una orden (el backend los devuelve en orden de creación). */
export function latestPaymentId(payments: PaymentOut[]): string | null {
  return payments.length > 0 ? payments[payments.length - 1].id : null;
}

/** Tamaño legible: "340 KB", "2,1 MB". */
export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`;
}
