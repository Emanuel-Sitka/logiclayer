# Data access review — Meridian Research Group

You are auditing the data access rules before an external review. The rules are
reproduced from the policy document, followed by the current state of the
system.

Answer the twenty questions at the end. For each, give the answer and show how
you reached it.

---

## The rules

**R1.** Clearance levels, lowest to highest: **public**, **internal**,
**confidential**, **secret**, **top_secret**.

**R2.** A role may inherit from one or more other roles. Inheritance is
transitive: if A inherits from B and B inherits from C, then A inherits from C.

**R3.** A role grants its own clearance level, and every clearance level
granted by any role it inherits from, directly or indirectly. A role's own
listed level is not necessarily the highest level it grants.

**R4.** A person may hold more than one role. A person's clearance is the
highest level granted by any role they hold.

**R5.** A clearance level covers its own level and every level below it.

**R6.** Role A **outranks** role B if A inherits from B, directly or
indirectly. Person A outranks person B if A holds some role that outranks some
role held by B.

**R7.** A denial is recorded against a person for a document, by a named
member of staff. A denial blocks that person from that document unless it has
been overridden.

**R8.** A denial is **overridden** if the person holds an exemption for that
same document, and the person who issued the exemption outranks the person who
recorded the denial.

**R9.** Succession: a document may supersede another, and succession is
transitive. An embargo on a document has **lapsed** if some document that
supersedes it, directly or indirectly, is not itself embargoed.

**R10.** An embargo is **active** if the document is embargoed and its embargo
has not lapsed.

**R11.** A person is **blocked** from a document if either:

  a. a denial is recorded against them for it that has not been overridden, or
  b. the document's embargo is active and they are not one of its authors.

**R12.** A person may read a document if their clearance covers the document's
classification **and** they are not blocked from it.

---

## Roles

| Role | Own clearance | Inherits from |
|---|---|---|
| visitor | public | — |
| contractor | public | visitor |
| staff | internal | visitor |
| analyst | internal | staff |
| researcher | internal | staff |
| senior_analyst | confidential | analyst |
| principal | secret | senior_analyst |
| auditor | public | principal |
| reviewer | internal | auditor |
| archivist | public | reviewer |
| lab_head | confidential | researcher |
| security_lead | top_secret | senior_analyst |
| deputy_director | internal | lab_head, security_lead |
| director | secret | deputy_director |

## People and the roles they hold

| Person | Roles |
|---|---|
| Adams | lab_head |
| Barnes | researcher |
| Chen | auditor |
| Dubois | visitor |
| Eriksson | senior_analyst |
| Farah | security_lead |
| Gupta | director |
| Hoffman | staff, principal |
| Ibrahim | analyst |
| Jansen | contractor |
| Kowalski | archivist |
| Lindqvist | senior_analyst, staff |
| Moreau | reviewer |
| Nakamura | deputy_director |
| Okafor | researcher, analyst |
| Petrov | principal |
| Quinn | visitor, contractor |
| Rossi | lab_head, senior_analyst |
| Silva | staff |
| Tanaka | archivist, researcher |
| Ueda | analyst |
| Vasquez | security_lead |
| Wang | researcher |
| Xu | contractor |
| Yilmaz | auditor, visitor |
| Zhao | staff |
| Abara | visitor |
| Bianchi | analyst |
| Costa | researcher |
| Duarte | staff |
| Elmi | contractor |
| Fischer | senior_analyst |
| Gallo | visitor |
| Haddad | reviewer |
| Ito | staff |
| Jung | analyst |

## Documents

| Document | Classification |
|---|---|
| d01 | public |
| d02 | internal |
| d03 | confidential |
| d04 | secret |
| d05 | top_secret |
| d06 | confidential |
| d07 | internal |
| d08 | secret |
| d09 | public |
| d10 | confidential |
| d11 | top_secret |
| d12 | internal |
| d13 | secret |
| d14 | confidential |
| d15 | public |
| d16 | internal |
| d17 | secret |
| d18 | confidential |
| d19 | top_secret |
| d20 | internal |
| d21 | confidential |
| d22 | secret |
| d23 | public |
| d24 | internal |

## Authorship

| Document | Authors |
|---|---|
| d03 | Adams |
| d04 | Chen |
| d05 | Farah |
| d06 | Adams |
| d07 | Barnes |
| d08 | Petrov |
| d10 | Eriksson |
| d11 | Gupta |
| d13 | Hoffman |
| d14 | Moreau |
| d16 | Wang |
| d17 | Fischer |
| d18 | Okafor |
| d19 | Gupta |
| d21 | Rossi |
| d22 | Tanaka |

Documents not listed have no recorded author.

## Embargoes

Embargoed: **d04**, **d06**, **d11**, **d14**, **d17**, **d19**, **d21**.

## Succession

| Supersedes | The earlier document |
|---|---|
| d09 | d04 |
| d10 | d06 |
| d19 | d11 |
| d20 | d19 |
| d21 | d17 |
| d24 | d21 |

## Denials

| Person | Document | Recorded by |
|---|---|---|
| Hoffman | d13 | Silva |
| Moreau | d14 | Ibrahim |
| Eriksson | d10 | Zhao |
| Okafor | d18 | Duarte |
| Rossi | d03 | Ito |
| Petrov | d08 | Jung |
| Chen | d04 | Bianchi |
| Wang | d16 | Silva |

## Exemptions

| Person | Document | Issued by |
|---|---|---|
| Hoffman | d13 | Gupta |
| Moreau | d14 | Ueda |
| Eriksson | d10 | Farah |
| Okafor | d18 | Silva |
| Rossi | d03 | Nakamura |
| Chen | d04 | Jansen |

---

## Questions

1. Can Chen read d05?
2. Can Kowalski read d04?
3. Can Moreau read d13?
4. Can Nakamura read d05?
5. Can Dubois read d02?
6. Can Hoffman read d13?
7. Can Moreau read d14?
8. Can Eriksson read d10?
9. Can Okafor read d18?
10. Can Rossi read d03?
11. Can Chen read d04?
12. Can Adams read d06?
13. Can Silva read d11?
14. Can Gupta read d17?
15. Can Jansen read d01?
16. Who can read d05?
17. Who can read d19?
18. Who can read d14?
19. Which roles grant top_secret clearance?
20. Who can read d22?
