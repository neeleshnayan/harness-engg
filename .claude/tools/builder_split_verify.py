"""builder_split_verify.py — proves the 2026-08-28 builder.md split lost nothing.

Usage (before the chair applies the split):
    python builder_split_verify.py
        --original "C:/Users/user/Documents/Krypton Fund/.claude/state/builder.md"
        --hot      "<janitor2>/builder_hot.md"
        --archive  "<janitor2>/builder_archive_2026-08.md"
All three default to those locations. After the split is applied, pass the
pre-split original via --original (e.g. a file produced by
`git show <pre-split-rev>:.claude/state/builder.md > original.md`).

WHAT IT PROVES (exit 0 only if ALL hold):
  1. BYTE CONTINUATION — the original file, split at the declared boundary
     line (the first 2026-08-26 entry), reappears byte-for-byte: the archive
     file ENDS WITH original lines 1..1103 exactly, and the hot file ENDS
     WITH original lines 1104..end exactly. Everything preceding those
     bodies in each output is new header/distillation (additions only).
  2. PARTITION — archive body + hot body == original, exactly (no byte lost,
     none duplicated across the two verbatim halves).
  3. HEADINGS — every '## ' section heading of the original appears in
     exactly one output's verbatim half (counted, not assumed).
  4. LINE COVERAGE — every non-blank original line appears somewhere in
     hot+archive combined; any absent line is printed. (Redundant given 1-2,
     kept as an independent check that does not trust the boundary constant.)
  5. NULL ARM — the checker is run against a deliberately corrupted copy
     (one byte removed mid-archive-body) and MUST fail there, or the
     instrument itself is broken (the seat's own census rule: find the
     defect you planted before trusting the zero).

HONEST LIMITS:
  - This proves the VERBATIM halves. It cannot judge the STANDING LESSONS
    distillation (new prose) — that is the chair's read and the builder's
    next-dispatch review, by design.
  - Check 4 matches whole lines; a line that also occurs in the new header
    text would be vacuously covered. Checks 1-2 are the real proof; 4 is
    belt-and-braces.
  - The boundary line number (1103/1104) is pinned to the 2026-08-28
    original (270,765 bytes, 1,508 keepends-lines). Against any other
    original the script refuses rather than guessing.
"""
import argparse
import sys

DEF_ORIG = r"C:\Users\user\Documents\Krypton Fund\.claude\state\builder.md"
DEF_BASE = (r"C:\Users\user\AppData\Local\Temp\claude"
            r"\C--Users-user-Documents-Krypton-Fund"
            r"\e585e083-6f7e-471f-b51b-6e9c3b249cbe\scratchpad\janitor2")
SPLIT_LINE = 1103
EXPECT_LINES = 1508
EXPECT_BYTES = 270765
BOUNDARY_PREFIX = b"## BINDS carried by the co-CTO 2026-08-26"
KNOWN_HEADING = b"## 2026-08-20 \xe2\x80\x94 seeded at hiring"  # null probe: must be found


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def check(original, hot, archive, quiet=False):
    """Returns list of problem strings (empty = pass)."""
    problems = []
    kl = original.splitlines(keepends=True)
    if len(kl) != EXPECT_LINES or len(original) != EXPECT_BYTES:
        problems.append(
            "original is not the 2026-08-28 file this split was cut from "
            "(%d lines / %d bytes vs expected %d / %d) — refusing to guess a boundary"
            % (len(kl), len(original), EXPECT_LINES, EXPECT_BYTES))
        return problems
    if not kl[SPLIT_LINE].startswith(BOUNDARY_PREFIX):
        problems.append("boundary line %d is not the expected 2026-08-26 heading" % (SPLIT_LINE + 1))
        return problems
    arch_body = b"".join(kl[:SPLIT_LINE])
    hot_body = b"".join(kl[SPLIT_LINE:])

    # 2. partition
    if arch_body + hot_body != original:
        problems.append("partition arithmetic broken (internal)")

    # 1. byte continuation
    if not archive.endswith(arch_body):
        problems.append("archive file does NOT end with original lines 1..%d byte-for-byte" % SPLIT_LINE)
    if not hot.endswith(hot_body):
        problems.append("hot file does NOT end with original lines %d..end byte-for-byte" % (SPLIT_LINE + 1))

    # 3. headings in exactly one verbatim half
    arch_half = archive[len(archive) - len(arch_body):] if archive.endswith(arch_body) else b""
    hot_half = hot[len(hot) - len(hot_body):] if hot.endswith(hot_body) else b""
    heads = [ln for ln in original.split(b"\n") if ln.startswith(b"## ")]
    n_arch = n_hot = 0
    for h in heads:
        a = h in arch_half
        b = h in hot_half
        if a and not b:
            n_arch += 1
        elif b and not a:
            n_hot += 1
        elif a and b:
            # duplicate heading TEXT (e.g. bare '## STATE' occurs 5x in the
            # archive era) — count by which half holds it; both-halves is only
            # a problem for headings unique in the original
            if original.count(b"\n" + h) <= 1 and not original.startswith(h):
                problems.append("unique heading in BOTH halves: %r" % h[:60])
            n_arch += 1  # attributed by position below anyway via checks 1-2
        else:
            problems.append("heading in NEITHER half: %r" % h[:60])
    # null probe for the heading scanner itself
    if KNOWN_HEADING not in arch_half and not problems:
        problems.append("null probe failed: known heading not found — scanner broken, not the tree")

    # 4. line coverage
    combined = hot + archive
    missing = []
    for i, ln in enumerate(original.split(b"\n")):
        if ln.strip() and ln not in combined:
            missing.append((i + 1, ln[:80]))
    if missing:
        problems.append("%d original lines absent from both outputs; first: line %d %r"
                        % (len(missing), missing[0][0], missing[0][1]))

    if not quiet:
        print("headings: %d total, %d archive-side, %d hot-side" % (len(heads), n_arch, n_hot))
        print("archive verbatim body: %d bytes; hot verbatim body: %d bytes; sum == original: %s"
              % (len(arch_body), len(hot_body), arch_body + hot_body == original))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", default=DEF_ORIG)
    ap.add_argument("--hot", default=DEF_BASE + r"\builder_hot.md")
    ap.add_argument("--archive", default=DEF_BASE + r"\builder_archive_2026-08.md")
    args = ap.parse_args()

    original = open(args.original, "rb").read()
    hot = open(args.hot, "rb").read()
    archive = open(args.archive, "rb").read()

    problems = check(original, hot, archive)
    for p in problems:
        print("PROBLEM: " + p)

    # 5. NULL ARM — corrupt a byte mid-archive-body; the checker must fail.
    mid = len(archive) - 90000  # inside the verbatim body, well past the header
    corrupted = archive[:mid] + archive[mid + 1:]
    null_problems = check(original, hot, corrupted, quiet=True)
    if not null_problems:
        print("NULL ARM FAILED: checker passed a corrupted archive — instrument broken")
        sys.exit(1)
    print("null arm: corrupted-archive run correctly FAILED (%d problems) — instrument live"
          % len(null_problems))

    if problems:
        sys.exit(1)
    print("PASS: split verified — every original byte present in exactly one output; additions are header/distillation only")


if __name__ == "__main__":
    main()
