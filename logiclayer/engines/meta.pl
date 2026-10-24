% Logic Layer meta-interpreter for SWI-Prolog.
%
% Plain Prolog answers yes or no and throws the reasoning away. This runs a
% goal the same way Prolog would, but records every clause it used along the
% way, so an answer arrives with a proof attached rather than on trust.
%
% It is driven by a JSON request file and writes a JSON result to standard
% output, so no query text has to survive the command line.

:- use_module(library(http/json)).
:- use_module(library(lists)).

:- dynamic ll_src/3.

% ---------------------------------------------------------------------------
% The interpreter.
%
% ll_solve(+Goal, -Proof) proves Goal and builds a term describing how.
%
% Clauses are looked up in the ll_src/3 table that the generated program
% carries, rather than with clause/2. That table pairs each clause with the
% ledger entry it came from, so the ledger id ends up in the proof and a
% conclusion can be traced back to the sentence that produced it.
% ---------------------------------------------------------------------------

ll_solve(true, true) :- !.

ll_solve((A, B), (PA, PB)) :- !,
    ll_solve(A, PA),
    ll_solve(B, PB).

% Negation as failure. The goal succeeds precisely because the inner goal
% could not be proved, so there is no sub-proof to record -- the absence of
% one is the whole justification. What we record instead is the goal that was
% taken to be false, which is the assumption the answer rests on.
%
% Groundness is checked here, at the moment of the call, because that is the
% one thing no amount of reading the rule beforehand can tell you. A term with
% a variable still in it makes the negation ask about a whole family of things
% rather than one thing: \+ damaged(book(orwell, Title)) asks whether any
% Orwell book is damaged, not whether this one is.
ll_solve(\+ G, naf(G, Ground)) :- !,
    ( ground(G) -> Ground = true ; Ground = false ),
    \+ ll_solve(G, _).

ll_solve(G, node(G, Id, Proof)) :-
    ll_src(G, Body, Id),
    ll_solve(Body, Proof).

% ---------------------------------------------------------------------------
% Turning a proof term into JSON.
% ---------------------------------------------------------------------------

% A rule body is a nested conjunction. Flatten it so the children of a node
% are a plain list.
conj_list(true, []) :- !.
conj_list((A, B), L) :- !,
    conj_list(A, LA),
    conj_list(B, LB),
    append(LA, LB, L).
conj_list(P, [P]).

% Terms are written with a space after each argument separator, so that what
% the engine prints matches what our own printer produces. Prolog's ~q writes
% book(orwell,animal_farm); we want book(orwell, animal_farm).
term_text(Term, Text) :-
    with_output_to(string(Text),
                   write_term(Term, [quoted(true), spacing(next_argument)])).

% The goal recorded here is the bare positive one, not the negated form. The
% assumption is about that goal being false, and whatever displays it can put
% the \+ back.
proof_json(naf(G, Ground), json{kind: "naf", goal: S, ground: Ground, children: []}) :- !,
    term_text(G, S).

proof_json(node(G, Id, Sub), Dict) :- !,
    term_text(G, S),
    conj_list(Sub, Parts),
    maplist(proof_json, Parts, Children),
    ( Children == [] -> Kind = "fact" ; Kind = "rule" ),
    Dict = json{kind: Kind, goal: S, id: Id, children: Children}.

proof_json(Other, json{kind: "opaque", goal: S, children: []}) :-
    term_text(Other, S).

% ---------------------------------------------------------------------------
% Bindings.
%
% variable_names gives back the names the caller actually wrote, so the answer
% can say "Who = anne" rather than naming an internal variable.
% ---------------------------------------------------------------------------

bindings_json(Names, Dict) :-
    findall(K-V,
            ( member(K = Value, Names),
              term_text(Value, V) ),
            Pairs),
    dict_pairs(Dict, json, Pairs).

% ---------------------------------------------------------------------------
% Running one request.
% ---------------------------------------------------------------------------

read_json_file(Path, Dict) :-
    setup_call_cleanup(
        open(Path, read, In, [encoding(utf8)]),
        json_read_dict(In, Dict),
        close(In)).

one_answer(Goal, Names, WantProof, json{bindings: B, proof: P}) :-
    (   WantProof == true
    ->  ll_solve(Goal, ProofTerm),
        proof_json(ProofTerm, P)
    ;   call(Goal),
        P = null
    ),
    bindings_json(Names, B).

ll_run(RequestPath) :-
    read_json_file(RequestPath, Req),

    % The generated program defines both the real clauses and the ll_src
    % table. Warnings about clause layout are expected: the ledger stores
    % clauses in the order they arrived, not grouped by predicate.
    style_check(-singleton),
    style_check(-discontiguous),
    atom_string(KbFile, Req.kb),
    consult(KbFile),

    term_string(Goal, Req.goal, [variable_names(Names)]),
    Limit = Req.limit,
    WantProof = Req.proof,

    findall(A, one_answer(Goal, Names, WantProof, A), Found),
    length(Found, Count),
    (   Count > Limit
    ->  length(Kept, Limit),
        append(Kept, _, Found),
        Truncated = true
    ;   Kept = Found,
        Truncated = false
    ),

    ( Kept == [] -> Status = "unknown" ; Status = "proved" ),
    json_write_dict(current_output,
                    json{status: Status, answers: Kept, truncated: Truncated}),
    nl.

ll_main(RequestPath) :-
    catch(ll_run(RequestPath), Error, report_error(Error)).

report_error(Error) :-
    format(string(Message), "~w", [Error]),
    json_write_dict(current_output,
                    json{status: "error", message: Message,
                         answers: [], truncated: false}),
    nl.
