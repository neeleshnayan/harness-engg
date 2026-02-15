/**
 * Shared error-parsing helper for consistent user-facing messages from API and runtime errors.
 * Handles axios response.data (message, detail as string or array of { msg }), Error.message, and fallback.
 */
export function parseErrorMessage(
  error: unknown,
  defaultMessage: string = "Something went wrong. Please try again."
): string {
  if (error == null) return defaultMessage;

  // Axios-style: response.data
  const response = (error as { response?: { data?: unknown } }).response;
  const data = response?.data;
  if (data !== undefined && data !== null) {
    if (typeof data === "string" && data.trim()) return data.trim();
    if (typeof data === "object") {
      const obj = data as Record<string, unknown>;
      const msg = obj.message ?? obj.error;
      if (typeof msg === "string" && msg.trim()) return msg.trim();
      const detail = obj.detail;
      if (typeof detail === "string" && detail.trim()) return detail.trim();
      if (Array.isArray(detail) && detail.length > 0) {
        const parts = detail.map((e: unknown) => {
          if (e && typeof e === "object" && "msg" in e && typeof (e as { msg: unknown }).msg === "string")
            return (e as { msg: string }).msg;
          return JSON.stringify(e);
        });
        const joined = parts.filter(Boolean).join("; ");
        if (joined) return joined;
      }
      if (detail && typeof detail === "object" && "msg" in detail && typeof (detail as { msg: unknown }).msg === "string")
        return (detail as { msg: string }).msg;
    }
  }

  // Standard Error
  if (error instanceof Error && error.message?.trim()) return error.message.trim();

  return defaultMessage;
}
