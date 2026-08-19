# riskofficer — working state
(appended by the CTO at each dispatch resolution; newest at the bottom)

## 2026-08-20 — seeded at hiring, same decision as the policy it supervises
- Policy v1 live: exit-rule SELLs only, <=10min fresh, liveness-proven, not
  halted. Zero auto-approvals on the log yet.
- First audit due: after the first auto-approval event, or in 7 days, whichever
  first. Check the marker-forgery path early (can anything but the exit tick
  put EXIT_MARKER in a rationale? propose_order accepts arbitrary rationale
  from callers with the propose permission - the marker alone is NOT proof of
  provenance; the actor field must corroborate. Flag this to the CTO as
  envelope v1's weakest check).
