% A playground for getting a feel for Prolog.
% Load it with:  scripts\repl.cmd
%
% Lines starting with % are comments.

% ---------------------------------------------------------------------------
% Facts. Plain statements. Lowercase names are specific things.
%
% The dynamic declarations come first. Prolog refuses to add or remove
% clauses of a predicate that was loaded from a file, unless that predicate
% was declared dynamic. Without these three lines, assert(rough(anne)) at
% the prompt is rejected with "No permission to modify static procedure".
% ---------------------------------------------------------------------------

:- dynamic person/1.
:- dynamic kind/1.
:- dynamic rough/1.
:- dynamic parent/2.

% Who exists. Prolog has no notion of what things there are - any word you
% type is a valid term, whether or not anything mentions it. So if you want to
% ask "who is not rough?", something has to say who the candidates are.
%
% Note that kind/1 and rough/1 will not do. They say what someone is LIKE.
% person/1 says what someone IS. Only the second is a domain.
person(anne).
person(bob).
person(carol).
person(alice).
person(dave).

kind(anne).
kind(carol).
rough(bob).
rough(carol).

% Two arguments. Argument order is a decision you have to make and then
% remember: this reads "the first one is a parent of the second one".
parent(alice, bob).
parent(bob, carol).
parent(carol, dave).

% ---------------------------------------------------------------------------
% Rules. Capital letters are variables, so these apply to everyone.
%   :-  means "if"
%   ,   means "and"
%   \+  means "cannot be proved"
% ---------------------------------------------------------------------------

quiet(X)   :- kind(X), \+ rough(X).
careful(X) :- quiet(X).
trusted(X) :- careful(X).

% "Someone is gentle if they are not rough."
%
% person(X) has to come first, and for two reasons.
%
% It says what X ranges over. Without it there is nothing to enumerate, so
% asking gentle(Who) has no answer to give.
%
% And it binds X. Prolog works through a rule left to right, and only a
% positive goal can bind anything - \+ never can, because it succeeds when its
% inner goal fails and a failed goal leaves nothing bound. So writing
%
%     gentle(X) :- \+ rough(X), person(X).
%
% leaves X loose when the negation runs. There it asks "is anyone at all
% rough?" rather than "is this X rough?", and since bob is rough it fails for
% everybody. Try it at the prompt and see.
gentle(X) :- person(X), \+ rough(X).

% ---------------------------------------------------------------------------
% Recursion. A rule that refers to itself.
%
% "X is an ancestor of Y if X is a parent of Y, OR if X is a parent of
% someone who is an ancestor of Y."
%
% Two clauses with the same head means "or" - Prolog tries the first, and
% on failure tries the second.
%
% The order inside the second rule matters enormously. Written as it is
% here it terminates. Swap the two conditions around and it loops forever,
% because Prolog would try to prove ancestor by first proving ancestor.
% ---------------------------------------------------------------------------

ancestor(X, Y) :- parent(X, Y).
ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).

% ---------------------------------------------------------------------------
% Things worth trying at the prompt. Remember the full stop at the end.
%
%   trusted(anne).        proved - anne is kind and not rough
%   trusted(carol).       not proved - carol is kind but also rough
%   trusted(zoe).         not proved - zoe is not mentioned anywhere
%
%   kind(Who).            ask for values, not yes/no. Press ; for more
%   trusted(Who).
%
%   ancestor(alice, dave).      three steps down the chain
%   ancestor(alice, Who).       everyone alice is an ancestor of
%   ancestor(Who, dave).        everyone who is an ancestor of dave
%
%   gentle(Who).          everyone not known to be rough
%
% Then see the ordering trap for yourself. Type this at the prompt:
%
%   assert((careless(X) :- \+ rough(X), person(X))).
%   careless(anne).       proved  - you named her, so X was already bound
%   careless(Who).        fails   - X was loose, so it asked "is ANYONE rough?"
%
% Same conditions, opposite order, different answer. The closed question hides
% the bug and the open one exposes it. Logic Layer refuses to store rules
% written this way.
%
%   \+ rough(zoe).        succeeds. Read it carefully - it does NOT mean
%                         zoe is gentle. It means nothing here proves zoe
%                         is rough. Prolog assumes anything it cannot
%                         derive is false.
%
% Then change something and see what happens. This only works because of
% the dynamic declarations at the top of the file.
%
%   assert(rough(anne)).  add a fact while running
%   trusted(anne).        no longer proved
%   retract(rough(anne)). take it away again
%   trusted(anne).        proved again
%
% Note that assert only changes the running session. The file on disk is
% untouched, so restarting the prompt gets you back to the original.
% ---------------------------------------------------------------------------
