"""D24 re-review: (1) what the flag would cost TODAY (routing_errors, ungated);
(2) does the 'one predicate, asked once' claim hold - i.e. does validate_routing
give the answer the DOOR would give for a caller that declared routing_version?"""
import json, urllib.request, sys
WT = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d22ch"
sys.path.insert(0, WT)
from app.fund import desk as D
def get(p):
    with urllib.request.urlopen("http://127.0.0.1:8090/api/v1"+p, timeout=60) as r:
        return json.load(r)
runs=[r for r in get("/fund/desk/runs?limit=500")["runs"] if r.get("recommendations")]
today=[r for r in runs if str(r.get("resolved_at","")).startswith("2026-08-23")]
bad=0; seats=set()
for r in today:
    if any(D.routing_errors(rec,i) for i,rec in enumerate(r["recommendations"])):
        bad+=1; seats.add(r.get("seat"))
print(f"runs recorded today: {len(today)}")
print(f"  UNGATED measurement (routing_errors): would 422 if the flag flipped = {bad}/{len(today)}  seats {sorted(seats)}")
gated=sum(1 for r in today if any(D.validate_routing(rec,i) for i,rec in enumerate(r['recommendations'])))
print(f"  GATED  (validate_routing, flag False): {gated}/{len(today)}   DESK_ROUTING_ENFORCE={D.DESK_ROUTING_ENFORCE}")

# The 'one answer' claim: a caller that DECLARES routing_version=1 is refused by
# the door. Does validate_routing say so?
sample=None
for r in today:
    for i,rec in enumerate(r["recommendations"]):
        if D.routing_errors(rec,i): sample=(r["run_id"],i,rec); break
    if sample: break
rid,i,rec = sample
print(f"\nspecimen {rid} rec#{i}")
print(f"  routing_errors        -> {len(D.routing_errors(rec,i))} error(s): {D.routing_errors(rec,i)[:1]}")
print(f"  validate_routing      -> {D.validate_routing(rec,i)}   <- what a pre-flight caller sees")
print(f"  validate_routing(enforce=True) -> {len(D.validate_routing(rec,i,enforce=True))} error(s)")
# what the DOOR does for the same rec when routing_version=1 is declared
enforce = bool(D.DESK_ROUTING_ENFORCE) or (1 is not None and 1 >= D.ROUTING_ENFORCED_FROM_VERSION)
print(f"  the DOOR with routing_version=1 -> enforce={enforce} => 422")
print("\n  => validate_routing() does NOT model the door for an opt-in caller:"
      f" door says 422, validate_routing says {D.validate_routing(rec,i)}")
import subprocess
print("\ncallers of validate_routing in app/ + scripts/:")
print(subprocess.run(["grep","-rn","validate_routing","--include=*.py","app/","scripts/"],
                     cwd=WT, capture_output=True, text=True).stdout or "  (none)")
