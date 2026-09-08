"""Fixed-stack NLHE ratings, isolated mirrored legs, versioned source evidence."""
import argparse
import concurrent.futures
import hashlib
import itertools
import json
from pathlib import Path
import random
from alpha_poker.dojo import IDS, PackagedBot, catalog
from alpha_poker.engine import play_hand, shuffled_deal

ROOT=Path(__file__).resolve().parents[1]

def matchup(task):
    a,b,seed,strategy_seed=task
    rows=[]
    for match in range(10):
        legs=[(PackagedBot(a),PackagedBot(b)),(PackagedBot(b),PackagedBot(a))]
        rng=random.Random(strategy_seed+match)
        net=errors=0
        for pair in range(100):
            deal_seed=seed+match*10000+pair
            for seat in (0,1):
                result=play_hand(legs[seat],seed=deal_seed,deal=shuffled_deal(deal_seed),dealer=0,
                    hand_id=f'cal-{match}-{pair}-{seat}',match_id=f'cal-{match}-leg-{seat}',
                    starting_stack=2000,small_blind=10,big_blind=20,timeout_seconds=.25,
                    bot_random_seeds=(rng.getrandbits(64),rng.getrandbits(64)))
                net+=result.profits[seat]
                errors+=sum(e.get('type')=='bot_error' for e in result.history['events'])
        rows.append(dict(net_chips=net,errors=errors))
    return dict(a=a,b=b,wins=sum(x['net_chips']>0 for x in rows),losses=sum(x['net_chips']<0 for x in rows),
                ties=sum(x['net_chips']==0 for x in rows),net_chips=sum(x['net_chips'] for x in rows),
                errors=sum(x['errors'] for x in rows),matches=rows,deal_seed=seed,strategy_seed=strategy_seed)

def ratings(rows):
    values={bot:1200. for bot in IDS}
    for _ in range(2000):
        delta={bot:0. for bot in IDS}
        for row in rows:
            a,b=row['a'],row['b'];observed=(row['wins']+.5*row['ties']+.5)/11
            expected=1/(1+10**((values[b]-values[a])/400))
            delta[a]+=observed-expected;delta[b]-=observed-expected
        for bot in IDS:values[bot]+=4*delta[bot]
    return {bot:round(value) for bot,value in values.items()}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    protected=[ROOT/'server/alpha_poker'/name for name in ['dojo.py','summit_policy.py','engine.py','evaluator.py','dojo_catalog.json']]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    report=dict(method='200-hand fixed-stack NLHE, 100 isolated duplicate deals per match, 10 matches per pairing; logistic match-score fit with half-win prior, centered at 1200',
                versions={b['id']:b['version'] for b in catalog()['bots']},source_hashes=hashes)
    for label,base in [('calibration',9810202600),('validation',9910302600)]:
        tasks=[(a,b,base+i*1000000,base*193+i*1000000) for i,(a,b) in enumerate(itertools.combinations(IDS,2))]
        (args.out/f'{label}-plan.json').write_text(json.dumps(tasks,indent=2))
        rows=[]
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for row in pool.map(matchup,tasks):
                rows.append(row);(args.out/f"{label}-{row['a']}-{row['b']}.json").write_text(json.dumps(row,indent=2));print(label,row['a'],row['b'],row['wins'],row['losses'],row['errors'],flush=True)
        report[label]=dict(ratings=ratings(rows),matchups=rows,total_hands=20000)
    if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise RuntimeError('Source changed during calibration')
    if any(row['errors'] for label in ['calibration','validation'] for row in report[label]['matchups']):raise RuntimeError('Bot errors invalidate calibration')
    (args.out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k]['ratings'] for k in ['calibration','validation']},indent=2))
