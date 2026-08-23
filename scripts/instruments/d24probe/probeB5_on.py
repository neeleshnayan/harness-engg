"""Run the adversary's probeB5 UNCHANGED, with the enforcement flag ON.

The probe is not edited: it is exec'd after this wrapper has imported
`app.fund.desk` and set `DESK_ROUTING_ENFORCE = True`, which is exactly what
the chair's one-line versioned change will do. The pair of runs (flag off,
flag on) is the acceptance criterion for repair 6.
"""
import runpy, sys

WT = r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\d22ch"
sys.path.insert(0, WT)
from app.fund import desk

desk.DESK_ROUTING_ENFORCE = True
print(f"[wrapper] desk.DESK_ROUTING_ENFORCE = {desk.DESK_ROUTING_ENFORCE}")
runpy.run_path(
    r"C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-Krypton-Fund"
    r"\bbc88cbf-5b81-4236-8781-b009121ec21f\scratchpad\advd22\probeB5.py",
    run_name="__main__")
