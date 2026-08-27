import json
def grab(fn,tags):
    d=json.load(open(fn)); out={}
    for tax,cons in d['facts'].items():
        for k,v in cons.items():
            if k in tags:
                for unit,rows in v['units'].items():
                    for r in rows:
                        dt=r.get('end') or r.get('instant')
                        if r.get('start') and r.get('end') and r['start']!=r['end']:
                            continue  # instant only
                        out.setdefault(k,{}).setdefault(dt,set()).add(r['val'])
    return out
for lbl,fn,tags in [("GS-ETHmini","cf_0002020455.json",["InvestmentOwnedBalanceContracts","SharesOutstanding","NetAssetValuePerShare","InvestmentOwnedAtFairValue","CommonStockOtherSharesOutstanding"]),
                    ("ETHA","cf_0002000638.json",["CryptoAssetNumberOfUnits","TemporaryEquitySharesOutstanding","NetAssetValuePerShare","InvestmentOwnedAtFairValue"])]:
    print("=====",lbl)
    g=grab(fn,tags)
    for k in g:
        print(" --",k)
        for dt in sorted(g[k]):
            print("   ",dt,sorted(g[k][dt]))
