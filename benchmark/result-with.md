I loaded the whole policy into the logic engine (169 declared clauses: role hierarchy, clearance grants, people, documents, denials/exemptions, succession/embargo) and queried it for each question, then double-checked the load-bearing intermediate facts (person_covers, overridden, active_embargo/lapsed) directly. Two findings worth flagging up front, since they drive several answers:

Two embargo chains almost fully lapsed. Of the 7 embargoed docs, only d14 is still actively embargoed. d04, d06, d11, d17, d19, d21 all have a non-embargoed document somewhere downstream in their succession chain (R9), so their embargoes have lapsed and no longer block anyone.
"Outranks" is not reflexive. Two people holding the same role never outrank each other (a role doesn't inherit from itself), which sinks several exemptions where the issuer and the denial-recorder hold identical roles.
Answers
#	Question	Answer
1	Chen read d05?	No
2	Kowalski read d04?	Yes
3	Moreau read d13?	Yes
4	Nakamura read d05?	Yes
5	Dubois read d02?	No
6	Hoffman read d13?	Yes
7	Moreau read d14?	No
8	Eriksson read d10?	Yes
9	Okafor read d18?	No
10	Rossi read d03?	Yes
11	Chen read d04?	No
12	Adams read d06?	Yes
13	Silva read d11?	No
14	Gupta read d17?	Yes
15	Jansen read d01?	Yes
16	Who can read d05?	Farah, Gupta, Nakamura, Vasquez
17	Who can read d19?	Farah, Gupta, Nakamura, Vasquez
18	Who can read d14?	No one
19	Roles granting top_secret?	security_lead, deputy_director, director
20	Who can read d22?	Chen, Farah, Gupta, Haddad, Hoffman, Kowalski, Moreau, Nakamura, Petrov, Tanaka, Vasquez, Yilmaz
Reasoning
Clearance chains (R1–R4). Note the roles table has some non-obvious long inheritance chains: auditor → principal → senior_analyst → analyst → staff → visitor, so auditor, reviewer, and archivist all inherit secret from principal, despite their own listed level being public/internal/public. Likewise deputy_director and director inherit top_secret from security_lead. R3 explicitly warns "a role's own listed level is not necessarily the highest it grants" — this table is built to make that bite.

Chen → d05 (top_secret): No. Chen holds only auditor, whose highest granted level is secret (via principal). secret doesn't cover top_secret (R5). Insufficient clearance — never reaches the blocking check.

Kowalski → d04 (secret): Yes. archivist → reviewer → auditor → principal grants secret, which covers secret (R5). d04 is embargoed but its embargo has lapsed (d09 supersedes it and d09 isn't embargoed, R9), and no denial exists against Kowalski for d04.

Moreau → d13 (secret): Yes. reviewer → auditor → principal grants secret. No denial recorded against Moreau for d13 (the only d13 denial is Hoffman's), no embargo on d13.

Nakamura → d05 (top_secret): Yes. deputy_director → security_lead grants top_secret. No denial, d05 not embargoed.

Dubois → d02 (internal): No. Dubois holds only visitor → public. public doesn't cover internal.

Hoffman → d13 (secret): Yes. principal grants secret directly. A denial exists (recorded by Silva), but Hoffman holds an exemption issued by Gupta, and Gupta (director) outranks Silva (staff) — director → deputy_director → lab_head → researcher → staff (R6/R8). Denial overridden.

Moreau → d14 (confidential): No. Moreau's clearance (secret, via reviewer→auditor→principal) covers confidential, and she's the document's author so the embargo wouldn't block her — but the denial still applies. Her exemption was issued by Ueda, and Ueda (analyst) does not outrank Ibrahim (analyst) — same role, no inheritance edge between them. Unoverridden denial blocks regardless of authorship (R11a has no author exception — only R11b, the embargo clause, exempts authors).

Eriksson → d10 (confidential): Yes. senior_analyst grants confidential directly. d10 isn't embargoed. The denial (recorded by Zhao) is overridden: exemption issuer Farah (security_lead) outranks Zhao (staff) via security_lead → senior_analyst → analyst → staff.

Okafor → d18 (confidential): No. Okafor's clearance (internal, from researcher/analyst — neither inherits toward senior_analyst) doesn't even cover confidential, and independently the denial isn't overridden anyway: exemption issuer Silva (staff) doesn't outrank Duarte (staff) — identical role, not reflexive.

Rossi → d03 (confidential): Yes. lab_head grants confidential. Denial (recorded by Ito) is overridden: issuer Nakamura (deputy_director) outranks Ito (staff) via deputy_director → lab_head → researcher → staff.

Chen → d04 (secret): No. Chen's clearance does reach secret (via auditor → principal), so clearance isn't the issue. The denial (recorded by Bianchi) is not overridden: issuer Jansen holds only contractor, which inherits from visitor only — no path to analyst — so Jansen doesn't outrank Bianchi.

Adams → d06 (confidential): Yes. lab_head grants confidential. d06's embargo has lapsed (d10 supersedes it, d10 isn't embargoed). Adams is also its author, so even without the lapse she'd be exempt from the embargo clause.

Silva → d11 (top_secret): No. Silva holds only staff → internal. Nowhere near top_secret.

Gupta → d17 (secret): Yes. director grants secret directly. d17 is embargoed, but the chain d17 ← d21 ← d24 reaches d24, which isn't embargoed, so d17's embargo has lapsed (R9's transitive lapse rule). No denial recorded against Gupta for d17.

Jansen → d01 (public): Yes. contractor grants public, which covers public. No blocks.

16 & 17. Who can read d05 / d19? Both are top_secret with no denials recorded against anyone, and d19's embargo has lapsed (superseded by d20, which isn't embargoed) while d05 was never embargoed. So both reduce to "who has top_secret clearance": exactly the holders of the three top_secret-granting roles (Q19) — security_lead (Farah, Vasquez), deputy_director (Nakamura), director (Gupta).

Who can read d14? No one. d14 is the one embargo that's still active (nothing supersedes it, so R9's lapse condition never fires). R11b would exempt its author, Moreau — but Moreau is independently blocked by her un-overridden denial (see Q7), so R11a catches her anyway. Everyone else lacks the author exemption and is blocked by the active embargo.

Roles granting top_secret: security_lead (own level), and everything that inherits from it — deputy_director and director.

Who can read d22 (secret)? d22 isn't embargoed and has no denials, so it's purely a clearance question: everyone whose highest granted level is secret or top_secret. That's everyone holding one of the 7 secret‑or‑above roles: principal (Hoffman, Petrov), auditor (Chen, Yilmaz), reviewer (Moreau, Haddad), archivist (Kowalski, Tanaka), security_lead (Farah, Vasquez), deputy_director (Nakamura), director (Gupta) — 12 people. (Notably, no senior_analyst-line-only people qualify — senior_analyst tops out at confidential since it inherits from analyst, not principal.)

The full audit trail (every asserted clause with its rationale, and the proof tree behind every answer above) lives in logic.jsonl in this directory — logic history or logic inspect <predicate> will pull up any of it if the reviewers want to see the derivation for a specific case.