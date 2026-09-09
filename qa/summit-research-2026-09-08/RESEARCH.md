# Renewed foundation review, September 8, 2026

This supplements the earlier pinned review at `../../dojo-calibration-round2-2026-09-08/research/reusable-foundations.md`. Current upstream README review is not a locally reproduced performance claim.

- [Slumbot2019](https://github.com/ericgjackson/slumbot2019): MIT C++ CFR+/MCCFR, abstractions and endgame solving. The supplied full-deck tutorial still calls for 100-million-iteration batches and generated abstraction data. Useful algorithm/training foundation, not a verified ready policy in the two-file Python contract. No heavyweight training launched.
- [PokerKit](https://github.com/uoftcprg/pokerkit): MIT simulation/evaluation library. Useful independent rules/evaluation infrastructure; no reviewed ready-made champion policy. Replacing our engine is outside the immediate strength problem.
- [HoldemLab](https://github.com/HFossdal/poker-game-simulator): explicit no-pretrained-model statement. Its README reports coarse CFR abstraction transferring poorly to full hold'em and losing to its equity baseline. This reinforces that an algorithm name is not strength evidence. No code imported; reuse license was not verified.
- [Texas-Holdem-AI](https://github.com/thotbreakerr/Texas-Holdem-AI): advertises multiple bot families and training pipelines. Reviewed root page did not establish a licensed, trained, validated PLHE policy that meets our portable contract. No code or model imported.
- Treys remains the earlier actually reused MIT evaluator candidate. Earlier broad regressions do not justify choosing that whole policy simply because it uses an external evaluator.

## Practical experiment

v16 retains the existing public evaluator and state reconstruction. New original policy code computes approximate equity for sampled opponent holdings at the streets where their public actions occurred, maintains a mixture of generic value/calling/pressure response models, and evaluates check/call and four legal raise sizes by expected chip value. It has no opponent-identity branches, seed inversion, hidden cards, network, or filesystem access. No new upstream strategy code was copied.

This is an approximate one-decision response model, not CFR or equilibrium solving. It assumes showdown after the modeled response, with a modest depth-dependent realization penalty. Opponent reraises and future betting are not fully solved. Broad regressions and held-out tests determine whether it is useful. It must not be described as GTO, unexploitable, or a trained champion.

## Evidence policy

Versioned development batches use independent strategy randomness and never count as fresh confirmation. Freeze source before two disjoint 20-series Mirage checks. Keep failed outcomes. Continue to compare against diverse prior student attacks; an 18/20 Mirage result alone cannot promote a specialist.
