Setting up the foundations
Before answering, I derived three reusable tables from the rules.

Role → effective (highest) clearance granted (R2/R3: own level + everything inherited, transitively; only the max matters since R5 makes a level cover everything below it):

Role	Own	Effective max
visitor	public	public
contractor	public	public
staff	internal	internal
analyst	internal	internal
researcher	internal	internal
senior_analyst	confidential	confidential
principal	secret	secret
auditor	public	secret (via principal)
reviewer	internal	secret (via auditor)
archivist	public	secret (via reviewer)
lab_head	confidential	confidential
security_lead	top_secret	top_secret
deputy_director	internal	top_secret (via security_lead)
director	secret	top_secret (via deputy_director)
This is the R3 "gotcha": auditor/reviewer/archivist look low-clearance but actually grant secret through the principal→...chain.

Embargo status (R9/R10 — active only if embargoed and no superseding document, direct or transitive, is unembargoed):

Doc	Supersessors (transitive)	Any unembargoed?	Status
d04	d09	yes (d09)	lapsed
d06	d10	yes (d10)	lapsed
d11	d19, d20	yes (d20)	lapsed
d14	none	—	active
d17	d21, d24	yes (d24)	lapsed
d19	d20	yes (d20)	lapsed
d21	d24	yes (d24)	lapsed
So d14 is the only document with a live embargo. That drives several answers below.

Person → clearance (R4, max over held roles) — computed once, used throughout: Farah/Gupta/Nakamura/Vasquez = top_secret; Chen/Hoffman/Kowalski/Moreau/Petrov/Tanaka/Yilmaz/Haddad = secret; Adams/Eriksson/Lindqvist/Rossi/Fischer = confidential; Barnes/Ibrahim/Okafor/Silva/Wang/Zhao/Bianchi/Costa/Duarte/Ito/Jung = internal; Dubois/Jansen/Quinn/Xu/Abara/Elmi/Gallo = public.

Answers
1. Can Chen read d05? — No.
Chen holds auditor → secret clearance. d05 is top_secret. Secret doesn't cover top_secret (R5), so R12 already fails.

2. Can Kowalski read d04? — Yes.
Kowalski holds archivist → secret, which covers d04 (secret). No denial recorded against Kowalski. d04's embargo has lapsed (d09 supersedes it and d09 isn't embargoed), so R11(b) doesn't apply. Not blocked.

3. Can Moreau read d13? — Yes.
Moreau (reviewer) → secret clearance, covers d13 (secret). No denial against Moreau for d13 (their denial is for d14, a different document), and d13 isn't embargoed.

4. Can Nakamura read d05? — Yes.
Nakamura (deputy_director) → top_secret, covers d05. No denial, no embargo on d05.

5. Can Dubois read d02? — No.
Dubois (visitor) → public clearance. d02 is internal, which public doesn't cover.

6. Can Hoffman read d13? — Yes.
Hoffman (staff, principal) → secret, covers d13. Silva recorded a denial, but Hoffman holds an exemption for d13 issued by Gupta. Gupta holds director, whose inheritance closure reaches staff (director→deputy_director→lab_head→researcher→staff, and via security_lead too), so Gupta outranks Silva (R6). The denial is overridden (R8). Not blocked.

7. Can Moreau read d14? — No.
Clearance is fine (secret ≥ confidential). But: Ibrahim recorded a denial against Moreau for d14, and Moreau's exemption was issued by Ueda — both Ueda and Ibrahim hold analyst, and a role doesn't outrank an identical role (R6 requires actual inheritance), so Ueda does not outrank Ibrahim. The denial is not overridden → blocked under R11(a).

8. Can Eriksson read d10? — Yes.
Eriksson (senior_analyst) → confidential, covers d10. Zhao recorded a denial, but the exemption issuer Farah (security_lead) outranks Zhao (staff) — security_lead's closure includes staff. Overridden. d10 isn't embargoed.

9. Can Okafor read d18? — No.
Okafor holds researcher and analyst, both capping at internal. d18 is confidential — clearance already fails, so the denial/exemption on d18 is moot.

10. Can Rossi read d03? — Yes.
Rossi (lab_head, senior_analyst) → confidential, covers d03. Ito recorded a denial, but the exemption issuer Nakamura (deputy_director) outranks Ito (staff) — deputy_director's closure includes staff. Overridden. d03 isn't embargoed.

11. Can Chen read d04? — No.
Clearance covers it (secret), and the embargo has lapsed, but Bianchi recorded a denial against Chen for d04. Chen's exemption was issued by Jansen (contractor), whose closure is only {visitor} — contractor does not outrank Bianchi's analyst. Not overridden → blocked under R11(a).

12. Can Adams read d06? — Yes.
Adams (lab_head) → confidential, covers d06. No denial against Adams. d06's embargo has lapsed (superseded by unembargoed d10). Not blocked (and Adams is also an author, which would have exempted them from (b) anyway).

13. Can Silva read d11? — No.
Silva (staff) → internal clearance; d11 is top_secret. Fails clearance outright (the fact that d11's embargo has lapsed is irrelevant here).

14. Can Gupta read d17? — Yes.
Gupta (director) → top_secret, covers d17 (secret). No denial against Gupta. d17's embargo has lapsed transitively (d24 supersedes d21 supersedes d17, and d24 isn't embargoed). Not blocked.

15. Can Jansen read d01? — Yes.
Jansen (contractor) → public, covers d01 (public). No denial, no embargo.

16. Who can read d05? — Farah, Gupta, Nakamura, Vasquez.
d05 is top_secret, so only the four people whose clearance reaches top_secret qualify (Farah/security_lead, Gupta/director, Nakamura/deputy_director, Vasquez/security_lead). No denials or embargo touch d05, so none are blocked.

17. Who can read d19? — Farah, Gupta, Nakamura, Vasquez.
Same top_secret-clearance group as above (d19 is top_secret). d19's embargo has lapsed (superseded by unembargoed d20), and no denials target d19, so nobody in that group is blocked.

18. Who can read d14? — Nobody.
d14 is confidential, so 17 people meet the clearance bar. But d14's embargo is the one active embargo in the system, and R11(b) blocks everyone who is not an author. The only author is Moreau — and Moreau is separately blocked anyway, because Ibrahim's denial against them is not overridden (see Q7: Ueda doesn't outrank Ibrahim). So every candidate is blocked, one way or another.

19. Which roles grant top_secret clearance? — security_lead, deputy_director, director.
security_lead has it directly; deputy_director inherits it from security_lead; director inherits it from deputy_director. No other role's inheritance chain reaches security_lead (the auditor/reviewer/archivist chain tops out at principal's secret).

20. Who can read d22? — Chen, Farah, Gupta, Hoffman, Kowalski, Moreau, Nakamura, Petrov, Tanaka, Vasquez, Yilmaz, Haddad.
d22 is secret, so everyone with secret or top_secret clearance qualifies (that's exactly this list of 12). No denials mention d22 and it isn't embargoed at all, so nobody is blocked.