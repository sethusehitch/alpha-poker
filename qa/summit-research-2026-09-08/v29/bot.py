from __future__ import annotations
"""Summit v29: public range equity and correlated-evidence tempering.

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
    particles=[]; sample_hands=[]
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
        particles.append((ws,qs[len(b)],eq)); sample_hands.append(o)
    # Keep a hand's strong betting from instantly reclassifying a value
    # opponent as a random aggressor. Style priors come from cross-hand
    # public frequencies; update the card range separately inside each style.
    masses=[sum(ws[k] for ws,_,_ in particles) for k in range(3)]
    for ws,_,_ in particles:
        for k in range(3):ws[k]*=priors[k]/max(1e-30,masses[k])
    total=sum(sum(ws) for ws,_,_ in particles)
    q=sum(sum(ws)*eq for ws,_,eq in particles)/max(total,1e-30)
    premium=(.045 if len(b)<5 else 0)*min(1,spr/2)
    call_ev=(q-premium)*(pot+tc)-tc
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
                value+=w*(fold*pot+(1-fold)*((eq-premium)*(pot+tc+2*extra)-tc-extra))
        value/=max(total,1e-30)
        # Small model uncertainty cost discourages marginal large-pot gambles.
        value-=.015*extra
        if value>best_ev+.015*pot:
            best_ev=value;best=({'action':'raise','amount':target} if 'raise' in legal else {'action':'all_in'})
    return lookahead(s, particles, sample_hands, rng, best) if len(b) in (3,4) else best

# Public AlphaPoker state machine, reused solely for synthetic-deal rollouts.
# No engine import or access to the real deal, seed, or opponent process.
import copy
from typing import Any, Mapping, Sequence
SCHEMA_VERSION='2026-09-01'
RANKS='23456789TJQKA'
SUITS='cdhs'
def evaluate(cards):return rank([INDEX[c] for c in cards])
def validate_card(card):
    if card not in INDEX:raise ValueError('invalid card')
def describe(value):return str(value[0])
class HoldemHand:
    """Mutable hand state. Bots only receive copies returned by ``bot_state``."""

    streets = ("preflop", "flop", "turn", "river")

    def __init__(
        self,
        *,
        hand_id: str,
        seed: int,
        match_id: str = "local-match",
        hand_number: int = 1,
        dealer: int = 0,
        starting_stack: int = 10_000,
        starting_stacks: tuple[int, int] | None = None,
        small_blind: int = 50,
        big_blind: int = 100,
        betting_limit: str = "no_limit",
        decision_deadline_ms: int = 1_000,
        bot_random_seeds: tuple[int, int] | None = None,
        deal: Mapping[str, Any] | None = None,
    ) -> None:
        initial = tuple(starting_stacks or (starting_stack, starting_stack))
        if len(initial) != 2 or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in initial):
            raise ValueError("starting stacks must contain two positive integers")
        if not 0 < small_blind <= big_blind:
            raise ValueError("invalid stack or blinds")
        if betting_limit not in {"no_limit", "pot_limit"}:
            raise ValueError("betting_limit must be no_limit or pot_limit")
        self.hand_id, self.seed, self.dealer = hand_id, seed, dealer
        self.match_id, self.hand_number = match_id, hand_number
        self.decision_deadline_ms = decision_deadline_ms
        self.bot_random_seeds = bot_random_seeds or (seed * 2, seed * 2 + 1)
        self.starting_stacks = list(initial)
        self.starting_stack = starting_stack
        self.small_blind, self.big_blind = small_blind, big_blind
        self.betting_limit = betting_limit
        dealt = copy.deepcopy(dict(deal)) if deal is not None else shuffled_deal(seed)
        self.holes = [list(cards) for cards in dealt["holes"]]
        self.full_board = list(dealt["board"])
        all_cards = self.holes[0] + self.holes[1] + self.full_board
        if len(self.holes[0]) != 2 or len(self.holes[1]) != 2 or len(self.full_board) != 5:
            raise ValueError("a deal requires two hole cards per seat and five board cards")
        if len(set(all_cards)) != 9:
            raise ValueError("deal cards must be unique")
        for card in all_cards:
            validate_card(card)

        self.stacks = list(initial)
        self.total_contrib = [0, 0]
        self.street_contrib = [0, 0]
        self.street_index = 0
        self.board: list[str] = []
        self.folded: int | None = None
        self.finished = False
        self.winners: tuple[int, ...] = ()
        self.events: list[dict[str, Any]] = []
        self.acted: set[int] = set()
        self.last_full_raise = big_blind
        self.current_bet = 0

        self._post_blind(dealer, small_blind, "small_blind")
        self._post_blind(1 - dealer, big_blind, "big_blind")
        self.current_bet = max(self.street_contrib)
        self.actor = dealer

    @property
    def street(self) -> str:
        return self.streets[self.street_index]

    @property
    def pot(self) -> int:
        return sum(self.total_contrib)

    def _post_blind(self, seat: int, amount: int, kind: str) -> None:
        paid = min(amount, self.stacks[seat])
        self.stacks[seat] -= paid
        self.street_contrib[seat] += paid
        self.total_contrib[seat] += paid
        self.events.append({"type": kind, "seat": seat, "amount": paid, "all_in": self.stacks[seat] == 0})

    def legal_actions(self, seat: int | None = None) -> list[dict[str, Any]]:
        seat = self.actor if seat is None else seat
        if self.finished or seat != self.actor:
            return []
        other = 1 - seat
        to_call = self.current_bet - self.street_contrib[seat]
        actions: list[dict[str, Any]] = [{"type": "fold"}]
        if to_call == 0:
            actions.append({"type": "check"})
        else:
            actions.append({"type": "call", "amount": min(to_call, self.stacks[seat])})
        effective_to = min(
            self.street_contrib[seat] + self.stacks[seat],
            self.street_contrib[other] + self.stacks[other],
        )
        maximum_to = effective_to
        if self.betting_limit == "pot_limit":
            # A pot-sized raise first calls, then raises by the size of the pot
            # after that call. Preflop at 50/100 this caps a raise at 300 total.
            maximum_to = min(
                effective_to,
                self.street_contrib[seat] + to_call + self.pot + to_call,
            )
        min_to = self.current_bet + self.last_full_raise
        if maximum_to >= min_to:
            actions.append(
                {
                    "type": "raise",
                    "min_to": min_to,
                    "max_to": maximum_to,
                }
            )
        if effective_to > self.street_contrib[seat] and (
            effective_to <= self.current_bet or effective_to <= maximum_to
        ):
            actions.append({"type": "all_in", "to": effective_to})
        return actions

    def bot_state(self, seat: int) -> dict[str, Any]:
        internal_legal = self.legal_actions(seat)
        by_name = {item["type"]: item for item in internal_legal}
        # Folding with nothing to call remains an internal escape hatch for a bot
        # failure, but is not offered as a strategic action in the public API.
        legal_names = [
            item["type"]
            for item in internal_legal
            if not (item["type"] == "fold" and "check" in by_name)
        ]
        raise_bounds = by_name.get("raise")
        return {
            "schema_version": SCHEMA_VERSION,
            "match_id": self.match_id,
            "hand_id": self.hand_id,
            "hand_number": self.hand_number,
            "seat": seat,
            "button_seat": self.dealer,
            "street": self.street,
            "hole_cards": list(self.holes[seat]),
            "community_cards": list(self.board),
            "pot": self.pot,
            "stacks": {str(i): amount for i, amount in enumerate(self.stacks)},
            "committed": {str(i): amount for i, amount in enumerate(self.street_contrib)},
            "to_call": self.current_bet - self.street_contrib[seat],
            "min_raise_to": raise_bounds["min_to"] if raise_bounds else None,
            "max_raise_to": raise_bounds["max_to"] if raise_bounds else None,
            "legal_actions": legal_names,
            "action_history": copy.deepcopy(self.events),
            "decision_deadline_ms": self.decision_deadline_ms,
            "bot_random_seed": self.bot_random_seeds[seat],
        }

    def act(self, action: Mapping[str, Any]) -> None:
        if self.finished:
            raise ValueError("hand is finished")
        seat, other = self.actor, 1 - self.actor
        kind = action.get("type")
        legal = {item["type"]: item for item in self.legal_actions()}
        if kind not in legal:
            raise ValueError(f"illegal action {kind!r}")
        to_call = self.current_bet - self.street_contrib[seat]

        if kind == "fold":
            self.folded = seat
            self.events.append({"type": "action", "seat": seat, "action": "fold", "street": self.street})
            self._award((other,), "fold")
            return
        if kind == "check":
            paid, raise_size = 0, 0
        elif kind == "call":
            paid, raise_size = min(to_call, self.stacks[seat]), 0
        else:
            target = legal[kind].get("to") if kind == "all_in" else action.get("to")
            if not isinstance(target, int):
                raise ValueError("raise action requires integer 'to'")
            bounds = legal.get("raise")
            effective_max = bounds["max_to"] if bounds else legal["all_in"]["to"]
            if target > effective_max or target <= self.street_contrib[seat]:
                raise ValueError("raise is outside the legal range")
            if kind == "raise" and target < bounds["min_to"]:
                raise ValueError("raise is below the minimum")
            paid = target - self.street_contrib[seat]
            raise_size = max(0, target - self.current_bet)

        self.stacks[seat] -= paid
        self.street_contrib[seat] += paid
        self.total_contrib[seat] += paid
        if raise_size:
            previous_raise = self.last_full_raise
            self.current_bet = self.street_contrib[seat]
            if raise_size >= previous_raise:
                self.last_full_raise = raise_size
                self.acted = {seat}
            else:
                self.acted.add(seat)
        else:
            self.acted.add(seat)
        self.events.append(
            {
                "type": "action",
                "seat": seat,
                "action": kind,
                "amount": paid,
                "to": self.street_contrib[seat],
                "street": self.street,
                "pot_after": self.pot,
                "all_in": self.stacks[seat] == 0,
            }
        )

        self._return_uncalled_all_in()
        contributions_equal = self.street_contrib[0] == self.street_contrib[1]
        someone_all_in = 0 in self.stacks
        round_complete = contributions_equal and (len(self.acted) == 2 or someone_all_in)
        if round_complete:
            self._advance_or_showdown()
        else:
            self.actor = other

    def _return_uncalled_all_in(self) -> None:
        """Return the unmatched portion of a heads-up bet after a short all-in.

        With only two players there is no side pot. Once the all-in player's
        contribution is lower, the excess chips from the other player were
        never called and must be returned before showdown.
        """
        for all_in_seat in (0, 1):
            other = 1 - all_in_seat
            if self.stacks[all_in_seat] != 0:
                continue
            unmatched = self.street_contrib[other] - self.street_contrib[all_in_seat]
            if unmatched <= 0:
                continue
            self.street_contrib[other] -= unmatched
            self.total_contrib[other] -= unmatched
            self.stacks[other] += unmatched
            self.current_bet = self.street_contrib[all_in_seat]
            self.events.append(
                {
                    "type": "uncalled_return",
                    "seat": other,
                    "amount": unmatched,
                    "street": self.street,
                }
            )

    def forfeit(self, seat: int) -> None:
        """End the hand after a bot failure, independent of strategic actions."""
        if self.finished or seat != self.actor:
            raise ValueError("only the acting seat can forfeit an active hand")
        self.folded = seat
        self.events.append({"type": "forfeit", "seat": seat, "street": self.street})
        self._award((1 - seat,), "bot_forfeit")

    def _advance_or_showdown(self) -> None:
        if self.street_index == 3 or 0 in self.stacks:
            self.board = list(self.full_board)
            self.events.append({"type": "board", "street": "showdown", "cards": list(self.board)})
            ranks = [evaluate(self.holes[seat] + self.board) for seat in range(2)]
            self.events.append(
                {
                    "type": "showdown",
                    "hands": [
                        {
                            "seat": seat,
                            "hole_cards": list(self.holes[seat]),
                            "rank": list(ranks[seat]),
                            "category": describe(ranks[seat]),
                        }
                        for seat in range(2)
                    ],
                }
            )
            outcome = (ranks[0] > ranks[1]) - (ranks[0] < ranks[1])
            self._award((0,) if outcome > 0 else (1,) if outcome < 0 else (0, 1), "showdown")
            return
        self.street_index += 1
        count = (3, 4, 5)[self.street_index - 1]
        self.board = self.full_board[:count]
        self.street_contrib = [0, 0]
        self.current_bet = 0
        self.last_full_raise = self.big_blind
        self.acted.clear()
        self.actor = 1 - self.dealer
        self.events.append({"type": "board", "street": self.street, "cards": list(self.board)})

    def _award(self, winners: tuple[int, ...], reason: str) -> None:
        pot = self.pot
        share, odd = divmod(pot, len(winners))
        for winner in winners:
            self.stacks[winner] += share
        if odd:
            odd_recipient = next(seat for seat in (1 - self.dealer, self.dealer) if seat in winners)
            self.stacks[odd_recipient] += odd
        self.winners = winners
        self.finished = True
        self.events.append({"type": "result", "winners": list(winners), "pot": pot, "reason": reason})

    def result(self) -> HandResult:
        if not self.finished:
            raise ValueError("hand is not finished")
        profits = tuple(self.stacks[seat] - self.starting_stacks[seat] for seat in range(2))
        history = {
            "schema_version": "1.0",
            "hand_id": self.hand_id,
            "match_id": self.match_id,
            "hand_number": self.hand_number,
            "seed": self.seed,
            "game": "PLHE" if self.betting_limit == "pot_limit" else "NLHE",
            "betting_limit": self.betting_limit,
            "currency": "play_chips",
            "dealer": self.dealer,
            "blinds": {"small": self.small_blind, "big": self.big_blind},
            "starting_stacks": list(self.starting_stacks),
            "hole_cards": copy.deepcopy(self.holes),
            "board": list(self.board),
            "pot": self.pot,
            "events": copy.deepcopy(self.events),
            "winners": list(self.winners),
            "final_stacks": list(self.stacks),
            "profits": list(profits),
        }
        return HandResult(self.hand_id, self.seed, self.dealer, self.winners, profits, history)


def lookahead(s, particles, holes, rng, fallback):
    seat=s['seat']; get=lambda table,i:table.get(str(i),table.get(i,0))
    legal=s['legal_actions'];actions=[{'action':'check' if 'check' in legal else 'call'}]
    if 'fold' in legal:actions.append({'action':'fold'})
    if fallback not in actions:actions.append(fallback)
    if 'raise' in legal:
        target=int(max(s['min_raise_to'],min(s['max_raise_to'],get(s['committed'],seat)+s['to_call']+.5*(s['pot']+s['to_call']))))
        other={'action':'raise','amount':target}
        if other not in actions:actions.append(other)
    initial=[get(s['stacks'],i) for i in (0,1)]
    blinds={}
    for event in s['action_history']:
        if event.get('type') in ('small_blind','big_blind','action'):
            initial[event['seat']]+=event.get('amount',0)
        if event.get('type') in ('small_blind','big_blind'):blinds[event['type']]=event['amount']
    weights=[w for ws,_,_ in particles for w in ws]
    values=[0.]*len(actions)
    for _ in range(64):
        index=rng.choices(range(len(weights)),weights=weights,k=1)[0]
        o=holes[index//3];kind=index%3
        h=[INDEX[c] for c in s['hole_cards']];b=[INDEX[c] for c in s['community_cards']]
        deck=[c for c in range(52) if c not in h+b+o]
        board=b+rng.sample(deck,5-len(b));dealt=[None,None]
        dealt[seat]=s['hole_cards'];dealt[1-seat]=[CARDS[c] for c in o]
        hand=HoldemHand(hand_id='simulation',seed=0,dealer=s['button_seat'],starting_stacks=tuple(initial),
            small_blind=max(1,blinds['small_blind']),big_blind=max(blinds.values()),betting_limit='pot_limit',
            deal={'holes':dealt,'board':[CARDS[c] for c in board]})
        for event in s['action_history']:
            if event.get('type')=='action':hand.act({'type':event['action'],'to':event.get('to')})
        if hand.finished or hand.actor!=seat or hand.pot!=s['pot']:
            return fallback
        key=rng.getrandbits(64)
        # Common equity estimates across root alternatives reduce rollout
        # noise and avoid repeating identical public-card calculations.
        equity_cache={}
        for actor in (0,1):
            for count in (3,4,5):
                equity_cache[actor,count]=public_equity([INDEX[c] for c in dealt[actor]],board[:count],rng,8)
        for ai,action in enumerate(actions):
            game=copy.deepcopy(hand);local=random.Random(key)
            game.act({'type':action['action'],'to':action.get('amount')})
            for step in range(32):
                if game.finished:break
                actor=game.actor;st=game.bot_state(actor);la=st['legal_actions']
                eq=equity_cache[actor,len(st['community_cards'])]
                price=st['to_call']/max(1,st['pot']+st['to_call'])
                if actor!=seat and kind==1:act='check' if 'check' in la else 'call'
                elif actor!=seat and kind==2:
                    act='raise' if 'raise' in la and local.random()<.45 else 'check' if 'check' in la else 'call'
                else:
                    aggressive=eq>.70 or (not st['to_call'] and local.random()<.06)
                    act='raise' if aggressive and 'raise' in la else 'check' if 'check' in la else 'call' if eq>price+(.12 if actor!=seat else .06) else 'fold'
                move={'type':act}
                if act=='raise':move['to']=int(max(st['min_raise_to'],min(st['max_raise_to'],get(st['committed'],actor)+st['to_call']+.6*(st['pot']+st['to_call']))))
                game.act(move)
            if not game.finished:
                # Bounded rollout tail, settled using the synthetic board.
                game._advance_or_showdown()
                if not game.finished:
                    scores=[evaluate(game.holes[i]+game.full_board) for i in (0,1)]
                    winners=(0,1) if scores[0]==scores[1] else (int(scores[1]>scores[0]),)
                    game._award(winners,'rollout_horizon')
            values[ai]+=game.stacks[seat]
    best=max(range(len(actions)),key=lambda i:values[i])
    fallback_index=actions.index(fallback)
    # Require a useful margin before replacing the lower-variance static estimate.
    return actions[best] if values[best]>values[fallback_index]+.08*s['pot']*64 else fallback
