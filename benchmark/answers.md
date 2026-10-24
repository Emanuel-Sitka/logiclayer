# Ground truth

Do not show either instance.

Computed by running `ground_truth.pl` through SWI-Prolog directly, not through
Logic Layer, so the answers do not depend on our tool being correct.

Regenerate everything with `python generate.py`.

|  | Question | Answer |
|---|---|---|
| 1 | Can Chen read d05? | **no** |
| 2 | Can Kowalski read d04? | **yes** |
| 3 | Can Moreau read d13? | **yes** |
| 4 | Can Nakamura read d05? | **yes** |
| 5 | Can Dubois read d02? | **no** |
| 6 | Can Hoffman read d13? | **yes** |
| 7 | Can Moreau read d14? | **no** |
| 8 | Can Eriksson read d10? | **yes** |
| 9 | Can Okafor read d18? | **no** |
| 10 | Can Rossi read d03? | **yes** |
| 11 | Can Chen read d04? | **no** |
| 12 | Can Adams read d06? | **yes** |
| 13 | Can Silva read d11? | **no** |
| 14 | Can Gupta read d17? | **yes** |
| 15 | Can Jansen read d01? | **yes** |
| 16 | Who can read d05? | **Farah, Gupta, Nakamura, Vasquez** |
| 17 | Who can read d19? | **Farah, Gupta, Nakamura, Vasquez** |
| 18 | Who can read d14? | **nobody** |
| 19 | Which roles grant top_secret clearance? | **Deputy Director, Director, Security Lead** |
| 20 | Who can read d22? | **Chen, Farah, Gupta, Haddad, Hoffman, Kowalski, Moreau, Nakamura, Petrov, Tanaka, Vasquez, Yilmaz** |

## Scoring

Twenty points, one per question. An enumeration scores only if the set is
exactly right.

Record for each instance: the score, whether the working actually supports the
answer, and — for the tool — whether a wrong answer came from a wrong clause or
from wrong deduction.
