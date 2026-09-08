"""Summit v26: public range equity and correlated-evidence tempering.

rank/pre/draw adapted from expert-v4; remaining implementation new.
"""
import random
from bisect import bisect_left, bisect_right
from math import exp, log
CARDS=[r+s for r in '23456789TJQKA' for s in 'cdhs']
INDEX={c:i for i,c in enumerate(CARDS)}
MEM={}

def rank(cards):
    counts=[0]*15; suits=[[],[],[],[]]
    for c in cards:
        r=c//4+2;counts[r]+=1;suits[c%4].append(r)
    rs=[r for r in range(14,1,-1) if counts[r]]
    def straight(vals):
        mask=0
        for v in vals:mask|=1<<v
        if mask&(1<<14):mask|=2
        for hi in range(14,4,-1):
            if (mask>>(hi-4))&31==31:return hi
        return 0
    flush=next((sorted(s,reverse=True) for s in suits if len(s)>=5),None)
    if flush:
        st=straight(flush)
        if st:return (8,st)
    quads=[r for r in rs if counts[r]==4]
    if quads:return (7,quads[0],next(r for r in rs if r!=quads[0]))
    trips=[r for r in rs if counts[r]>=3];pairs=[r for r in rs if counts[r]>=2]
    if trips and len(pairs)>1:return (6,trips[0],next(r for r in pairs if r!=trips[0]))
    if flush:return (5,*flush[:5])
    st=straight(rs)
    if st:return (4,st)
    if trips:return (3,trips[0],*[r for r in rs if r!=trips[0]][:2])
    if len(pairs)>1:return (2,*pairs[:2],next(r for r in rs if r not in pairs[:2]))
    if pairs:return (1,pairs[0],*[r for r in rs if r!=pairs[0]][:3])
    return (0,*rs[:5])

def pre(h):
    a,b=sorted((c//4+2 for c in h),reverse=True)
    if a==b:return .50+.025*a
    return .27+.017*a+.010*b+.026*(h[0]%4==h[1]%4)-.008*max(0,a-b-1)

def draw(h,b):
    if len(b)>=5:return 0.
    cs=h+b;ss=[sum(c%4==s for c in cs) for s in range(4)]
    flush=any(ss[c%4]==4 for c in h)
    rr={c//4+2 for c in cs}
    if 14 in rr:rr.add(1)
    straight=max(sum(r in rr for r in range(k,k+5)) for k in range(1,11))==4
    return .16*flush+.09*straight

def sig(x):return 1/(1+exp(max(-35,min(35,-x))))

def kernel(q,d,price,k,raises,button,shift=0.):
    """One normalized behavioral distribution: fold/passive/raise.

    Nonzero support preserves traps and mixed marginal defenses. Aggression
    shifts cannot force calls; costly decisions still depend on hand strength.
    """
    if not k and raises==0:
        r=.025+.925*sig(30*(q-(.455 if button else .615)))
        cont=.50+.495*sig(30*(q-.36)) if button else 1.
    elif price:
        margin=.045 if k==0 else .035 if k==3 else .015 if k==4 else 0.
        cont=.003+.994*sig(42*(q-price-margin))
        value=.82*sig(26*(q-(.76 if raises<2 else .87)))
        bluff=.10*sig(35*(d-.12))*sig(20*(.57-q))*(1-price)
        r=min(.94,value+bluff)
        return (1-cont,cont*(1-r),cont*r)
    else:
        value=.84*sig(22*(q-.69))
        bluff=.15*sig(22*(.30-q))+.50*d*sig(18*(.64-q))
        r=min(.95,max(.005,.025+value+bluff+shift))
        cont=1.
    return (1-cont,cont*(1-r),cont*r)

def histories(s):
    """Reconstruct actual prices and raise counts, avoiding paid/raise confusion."""
    contrib=[0,0];current='preflop';raises=0;out=[]
    get=lambda table,i:table.get(str(i),table.get(i,0))
    remaining=[get(s['stacks'],i) for i in (0,1)]
    for event in s['action_history']:
        if event.get('type') in ('small_blind','big_blind','action'):
            remaining[event['seat']]+=event.get('amount',0)
    for e in s['action_history']:
        if e.get('type') in ('small_blind','big_blind'):
            contrib[e['seat']]+=e['amount'];remaining[e['seat']]-=e['amount'];continue
        if e.get('type')!='action':continue
        if e['street']!=current:current=e['street'];contrib=[0,0];raises=0
        seat=e['seat'];tc=max(contrib)-contrib[seat]
        before=max(1,e['pot_after']-e.get('amount',0))
        cap=min(contrib[i]+remaining[i] for i in (0,1))
        e=dict(e,_size_capped=e.get('all_in',False) or e.get('to',0)>=cap)
        remaining[seat]-=e.get('amount',0)
        out.append((e,tc/(before+tc),raises,tc,before))
        contrib[seat]=e.get('to',contrib[seat]+e.get('amount',0))
        raises+=e['action'] in ('raise','all_in')
    return out

def observe(s,history,mem):
    if mem.get('match')!=s.get('match_id'):
        mem.clear();mem.update(match=s.get('match_id'),hand=None,seen=0,n=0.,r=0.,pn=0.,pr=0.,responses=[0.,0.],folds=[0.,0.],on=0.,orr=0.)
    pending=mem.pop('pending',None)
    if pending:
        hand,street,index,prior_raises=pending
        category=0 if street=='preflop' else 1
        answer=None
        if hand!=s.get('hand_id'):
            # A non-all-in raise before river cannot end the hand through a
            # call: both players would still have chips and must act again.
            answer=True
        else:
            for event in s['action_history'][index:]:
                if event.get('type')=='action' and event.get('seat')!=s['seat'] and event.get('street')==street:
                    answer=event.get('action')=='fold'
                    break
        if answer is not None:
            mem['responses'][category]=.995*mem['responses'][category]+1
            mem['folds'][category]=.995*mem['folds'][category]+answer
            if answer and street=='preflop' and prior_raises==0:
                mem['pn']=.995*mem['pn']+1
                mem['pr']=.995*mem['pr']
    if mem['hand']!=s.get('hand_id'):
        mem.update(hand=s.get('hand_id'),seen=0)
    for i,(e,price,raises,tc,before) in enumerate(history):
        if i<mem['seen'] or e['seat']==s['seat']:continue
        if e['street']=='preflop':
            if raises==0 and e['seat']==s['button_seat']:
                mem['on']=.995*mem['on']+1
                mem['orr']=.995*mem['orr']+(e['action'] in ('raise','all_in'))
            if raises==1:
                mem['pn']=.995*mem['pn']+1
                mem['pr']=.995*mem['pr']+(e['action'] in ('raise','all_in'))
            continue
        if raises:continue
        mem['n']=.997*mem['n']+1;mem['r']=.997*mem['r']+(e['action'] in ('raise','all_in'))
    mem['seen']=len(history)
    # Prior of 30 visible opportunities, at most 0.12 absolute behavior shift.
    return max(-.12,min(.12,((mem['r']+3.5)/(mem['n']+10)-.35)*.45))

def size_density(ratio,q):
    # Broad overlapping lognormal density; no hand-dependent hard size holes.
    mu=log(.70+.18*sig(15*(q-.80)))
    return .04+.96*exp(-.5*((log(max(.03,ratio))-mu)/.65)**2)


def public_equity(h,b,rng,samples=16):
    deck=[c for c in range(52) if c not in h+b]
    score=0.
    for _ in range(samples):
        cs=rng.sample(deck,7-len(b));board=b+cs[2:]
        a,z=rank(h+board),rank(cs[:2]+board)
        score+=(a>z)+.5*(a==z)
    return score/samples


def likelihood(q,price,action,kind):
    # Generic value, calling, and pressure models. All retain nonzero support.
    if kind==1:
        raise_p=.015+.05*sig(20*(q-.85));cont=.98
    elif kind==2:
        raise_p=.45;cont=.94
    else:
        raise_p=.025+.91*sig(24*(q-.72))
        cont=.02+.97*sig(25*(q-price-.13))
    if action in ('raise','all_in'):return raise_p
    if action=='fold':return (1-raise_p)*(1-cont)
    return (1-raise_p)*(cont if price else 1.)


def decide(s,memory=None):
    mem=MEM if memory is None else memory
    history=histories(s);observe(s,history,mem)
    seat=s['seat'];legal=s['legal_actions'];b=[INDEX[c] for c in s['community_cards']]
    h=[INDEX[c] for c in s['hole_cards']]
    rng=random.Random(s['bot_random_seed'] ^ (len(s['action_history'])*1000003+827))
    get=lambda table,i:table.get(str(i),table.get(i,0))
    tc=min(s['to_call'],get(s['stacks'],seat));pot=s['pot'];own=get(s['committed'],seat)
    rem=max(0,min(get(s['stacks'],seat)-tc,get(s['stacks'],1-seat)))
    spr=rem/max(1,pot+tc)
    deck=[c for c in range(52) if c not in h+b]
    ks={'preflop':0,'flop':3,'turn':4,'river':5}
    enemy_history=[(e,price,raises) for e,price,raises,*_ in history if e['seat']!=seat]
    streets={len(b)}|{ks[e['street']] for e,_,_ in enemy_history}
    aggression=(mem.get('r',0)+2)/(mem.get('n',0)+8)
    pressure=max(.025,min(.9,(aggression-.30)*3.5))
    passive=max(.025,min(.8,(.14-aggression)*4.))
    priors=[max(.05,1-pressure-passive),passive,pressure]
    particles=[]
    for _ in range(96):
        o=rng.sample(deck,2)
        qs={k:public_equity(o,b[:k],rng,12) for k in streets}
        ws=priors[:]
        for e,price,raises in enemy_history:
            q=qs[ks[e['street']]]
            for kind in range(3):
                ws[kind]*=max(.01,likelihood(q,price,e['action'],kind))**(.5 if raises>=2 else .8)
        # Use common sampled opponent holdings for equity and response value.
        score=0.
        rest=[c for c in deck if c not in o]
        for _ in range(4 if len(b)<5 else 1):
            board=b+rng.sample(rest,5-len(b));a,z=rank(h+board),rank(o+board)
            score+=(a>z)+.5*(a==z)
        eq=score/(4 if len(b)<5 else 1)
        particles.append((ws,qs[len(b)],eq))
    # Keep a hand's strong betting from instantly reclassifying a value
    # opponent as a random aggressor. Style priors come from cross-hand
    # public frequencies; update the card range separately inside each style.
    masses=[sum(ws[k] for ws,_,_ in particles) for k in range(3)]
    for ws,_,_ in particles:
        for k in range(3):ws[k]*=priors[k]/max(1e-30,masses[k])
    total=sum(sum(ws) for ws,_,_ in particles)
    q=sum(sum(ws)*eq for ws,_,eq in particles)/max(total,1e-30)
    premium=(.045 if len(b)<5 else 0)*min(1,spr/2)
    # A concave chip utility values preserving future playing opportunities.
    # This is a risk-sensitive tournament heuristic, not a GTO claim.
    stack=get(s['stacks'],seat)
    utility=lambda chips:max(0.,chips)**.4
    base=utility(stack)
    call_ev=(q-premium)*utility(stack+pot)+(1-q+premium)*utility(stack-tc)-base
    best_ev=call_ev;best={'action':'check' if 'check' in legal else 'call'}
    if 'fold' in legal and call_ev<0:best_ev=0.;best={'action':'fold'}
    targets=[]
    if 'raise' in legal:
        targets=sorted(set(int(max(s['min_raise_to'],min(s['max_raise_to'],own+tc+f*(pot+tc)))) for f in (.25,.5,.75,1.)))
    elif 'all_in' in legal and get(s['stacks'],seat)>tc:
        targets=[own+get(s['stacks'],seat)]
    for target in targets:
        extra=target-own-tc
        price=extra/max(1,pot+tc+2*extra)
        value=0.
        for ws,oq,eq in particles:
            for kind,w in enumerate(ws):
                fold=likelihood(oq,price,'fold',kind)
                # Extra chips are only attractive when the continuing range pays.
                value+=w*(fold*(utility(stack+pot)-base)+(1-fold)*((eq-premium)*utility(stack+pot+extra)+(1-eq+premium)*utility(stack-tc-extra)-base))
        value/=max(total,1e-30)
        # Small model uncertainty cost discourages marginal large-pot gambles.
        value-=.015*(utility(stack+extra)-base)
        if value>best_ev+.015*(utility(stack+pot)-base):
            best_ev=value;best=({'action':'raise','amount':target} if 'raise' in legal else {'action':'all_in'})
    return best
