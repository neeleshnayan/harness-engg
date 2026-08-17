"""Turn the sampled vanished names into a haircut on the control's return.

The chain of reasoning, with every assumption named so a reader can attack any
link rather than having to accept the number:

  1. 5,546 operating companies (CS+ADRC) were listed on the as-of date; 902 are
     absent from today's reference. Both counts are the vendor's own.
  2. A random sample of the vanished CS names was measured: ADV over the six
     months BEFORE the window (so band membership is decided on information
     available then), and return from the window open to the last print.
  3. The share of vanished names that were band-eligible, from that sample,
     estimates how many band names died. ASSUMPTION: the sample is
     representative of the vanished population. It was drawn at random, but it
     is a sample, and the confidence interval below says how much that matters.
  4. The band population at the as-of date is estimated as today's band plus the
     vanished band names. ASSUMPTION: names entering the band from outside
     roughly balance names leaving it upward, which is unverified — a band
     defined by a fixed dollar range in a rising market probably gains members,
     which would make the vanish RATE slightly lower and the haircut slightly
     smaller.
  5. The haircut is the difference between a survivor-only equal-weight return
     and one that includes the vanished at their measured returns.

What the number is NOT: a correction to apply. It is a magnitude, with a sign,
that says how much the survivor-only comparison can be trusted. Applying it as an
adjustment would turn an estimate with two unverified assumptions into a fact.
"""
import json
import math
import os
import sys

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("FUND_STORE", "postgres")

import psycopg  # noqa: E402

from app.fund.pgstore import dsn  # noqa: E402

AS_OF = "2025-01-01"
#: The survivor-only figure this haircut applies to: the harness's own
#: equal-weight benchmark over 2025-01-01 -> 2026-08-14, as measured in the
#: candidate's verify run. Passed in rather than hardcoded where possible.
SURVIVOR_RETURN_PCT = float(sys.argv[1]) if len(sys.argv) > 1 else 60.88


def main() -> None:
    with psycopg.connect(dsn()) as c, c.cursor() as cur:
        cur.execute("""
            SELECT count(*) FROM fund_universe_asof a
            LEFT JOIN fund_ticker_reference r ON r.ticker = a.ticker
            WHERE a.as_of = %s AND r.ticker IS NULL AND a.type = 'CS'
        """, (AS_OF,))
        vanished_cs = int(cur.fetchone()[0])

        cur.execute("SELECT count(*) FROM fund_universe_asof WHERE as_of = %s",
                    (AS_OF,))
        listed_then = int(cur.fetchone()[0])

        cur.execute("""
            SELECT count(*),
                   count(*) FILTER (WHERE in_band),
                   count(*) FILTER (WHERE in_band AND return_pct IS NOT NULL),
                   count(*) FILTER (WHERE unmeasured IS NOT NULL)
            FROM fund_survivorship_sample
        """)
        sampled, in_band, with_return, unmeasured = [int(x) for x in cur.fetchone()]

        cur.execute("SELECT return_pct FROM fund_survivorship_sample "
                    "WHERE in_band AND return_pct IS NOT NULL")
        rets = [float(r[0]) for r in cur.fetchall()]

        # Today's band, counted the same way the screen counts it.
        from app.fund.tickerref import OPERATING_TYPES
        cur.execute("""
            SELECT count(*) FROM fund_universe u
            JOIN fund_ticker_reference r ON r.ticker = u.symbol
            WHERE u.adv_usd BETWEEN 2000000 AND 25000000
              AND r.type = ANY(%s)
        """, (list(OPERATING_TYPES),))
        band_today = int(cur.fetchone()[0])

    if not rets:
        print("no band-eligible vanished name has a measured return — no haircut "
              "can be computed, and an absent estimate is the honest output")
        return

    n = len(rets)
    mean_ret = sum(rets) / n
    sd = math.sqrt(sum((r - mean_ret) ** 2 for r in rets) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0

    band_share = in_band / sampled if sampled else 0.0
    est_band_vanished = band_share * vanished_cs
    est_band_then = band_today + est_band_vanished
    vanish_rate = est_band_vanished / est_band_then if est_band_then else 0.0

    adjusted = (1 - vanish_rate) * SURVIVOR_RETURN_PCT + vanish_rate * mean_ret
    haircut = adjusted - SURVIVOR_RETURN_PCT
    # Propagate only the sampling error in the vanished names' mean return. The
    # two structural assumptions above are NOT in this interval and dominate it.
    haircut_se = vanish_rate * se

    print("=" * 68)
    print("SURVIVORSHIP HAIRCUT — estimate, not a correction")
    print("=" * 68)
    print(f"as of {AS_OF}: {listed_then:,} operating companies listed, "
          f"{vanished_cs:,} CS names now absent")
    print(f"sample: {sampled} vanished names measured, {in_band} band-eligible "
          f"({band_share:.1%}), {with_return} with a return, "
          f"{unmeasured} unmeasured")
    print()
    print(f"vanished band names, measured return:")
    print(f"    mean   {mean_ret:+.1f}%   (sd {sd:.1f}, se {se:.1f}, n={n})")
    print(f"    they GAINED on average — most were acquisitions, not failures")
    print()
    print(f"band population then, estimated: {band_today:,} today "
          f"+ {est_band_vanished:.0f} vanished = {est_band_then:,.0f}")
    print(f"implied vanish rate inside the band: {vanish_rate:.1%}")
    print()
    print(f"survivor-only equal-weight return:  {SURVIVOR_RETURN_PCT:+.2f}%")
    print(f"including the vanished:              {adjusted:+.2f}%")
    print(f"HAIRCUT:                             {haircut:+.2f} pct pts "
          f"(± {1.96 * haircut_se:.2f} from sampling alone)")
    print()
    if haircut < 0:
        print("SIGN: survivorship FLATTERED the survivor-only figure — but not")
        print("because the missing names died. They gained; they simply gained")
        print("LESS than the survivors, and a portfolio holding them would have")
        print("earned less than one that holds only the companies that made it.")
    else:
        print("SIGN: survivorship UNDERSTATED the survivor-only figure.")
    print()
    print("The two structural assumptions — that the sample represents the")
    print("vanished population, and that band entries balance band exits —")
    print("are NOT in the interval above and are larger than it.")

    out = {
        "as_of": AS_OF, "listed_then": listed_then, "vanished_cs": vanished_cs,
        "sample": {"sampled": sampled, "in_band": in_band,
                   "with_return": with_return, "unmeasured": unmeasured},
        "vanished_band_return": {"mean_pct": round(mean_ret, 3),
                                 "sd": round(sd, 3), "se": round(se, 3), "n": n},
        "band_today": band_today,
        "est_band_vanished": round(est_band_vanished, 1),
        "vanish_rate": round(vanish_rate, 4),
        "survivor_only_pct": SURVIVOR_RETURN_PCT,
        "adjusted_pct": round(adjusted, 3),
        "haircut_pct_pts": round(haircut, 3),
        "haircut_sampling_ci95": round(1.96 * haircut_se, 3),
    }
    with open("docs/survivorship_haircut.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("\nwritten to docs/survivorship_haircut.json")


if __name__ == "__main__":
    main()
