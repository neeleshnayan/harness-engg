/**
 * Turn an API failure into something true.
 *
 * The UI used to answer every error with "is ClarkHarness running on :8090?" —
 * which sends the operator to check a service that is running and a config that
 * is correct, while the real cause goes unnamed. The spine now returns a cause
 * on infrastructure faults (503); prefer it over any guess we could make here.
 */
export function spineError(e: any): string {
  const detail = e?.response?.data?.detail;
  const status = e?.response?.status;

  if (typeof detail === "string" && detail.trim()) return detail;

  if (status === 503) return "The fund service is temporarily unavailable.";
  if (status === 404) return "That fund resource does not exist.";
  if (status === 422) return "The fund service rejected the request as invalid.";

  // genuinely could not reach it — now the connectivity hint is the right one
  if (e?.code === "ERR_NETWORK" || e?.message?.includes("Network Error")) {
    return "Cannot reach the fund service — is ClarkHarness running on :8090?";
  }
  return e?.message || "Unknown error talking to the fund service.";
}
