# Recap title transitions

The selected angled white, navy, blue and gold banner displays the actual highlight title, retained hand number, and player names. No synthetic rivalry score is shown. The duplicate left-side title is removed.

Replay introduces the current highlight. During playback the result holds for 1.5 seconds before advancing to the next selected highlight, in chronological order. The 2.8-second banner enters quickly from the left, crosses the center slowly, and accelerates off the right. Actions retain their 2.2-second pacing. Playback stops after the last highlight. Pause freezes the banner through CSS animation-play-state; Replay restarts it; manual highlight selection cancels it. Reduced motion uses an opacity fade.

Completed recaps expose both players' retained cards throughout every step, including folded hands. Missing retained cards remain unavailable. Existing challenge access checks and completed-match checks remain in force. Equity eligibility remains limited to complete showdowns.

Validation: production build, focused API and route tests; browser verification at mobile and desktop widths confirmed both cards at step 1, banner pause/resume, removal after animation, and automatic progression from highlight 4 (hand 6) to highlight 5 (hand 8), updating the URL and title. Screenshot inspection verified the angled banner and mobile wrapping.
