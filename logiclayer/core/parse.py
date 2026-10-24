"""Reads Prolog-style text into the clause structures in ast.py.

The agent writes Prolog notation at the command line, because that is the
notation language models have seen most of. This turns it into our own
structures on the way in.

A deliberately small part of Prolog is accepted: facts, rules, negation,
conjunction, and nested compound terms. Not accepted yet: lists, operators
such as = and <, arithmetic, disjunction with ; and cut. Those get added when
something actually needs them. Rejecting input we do not understand is much
safer than passing it through to the engine unexamined.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ast import Atom, Callable, Clause, Literal, Num, Struct, Term, Var


class ParseError(ValueError):
    """The text could not be read as a clause.

    Carries the position so the CLI can point at the offending character.
    """

    def __init__(self, message: str, text: str, position: int) -> None:
        self.text = text
        self.position = position
        super().__init__(f"{message} at position {position}: {text!r}")

    def caret(self) -> str:
        """The input with a caret under the problem, for terminal output."""
        return f"{self.text}\n{' ' * self.position}^"


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

_PUNCT = {"(", ")", ",", "."}
_SYMBOLIC = set("+-*/\\^<>=~:.?@#&")


@dataclass(frozen=True, slots=True)
class Token:
    kind: str  # name | var | num | punct | neck | naf
    text: str
    position: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i, n = 0, len(text)

    while i < n:
        ch = text[i]

        if ch.isspace():
            i += 1
            continue

        if ch == "%":  # comment to end of line
            while i < n and text[i] != "\n":
                i += 1
            continue

        start = i

        # Quoted atom: 'New York'.
        # A quote inside one is written either doubled ('it''s') which is the
        # ISO standard way, or backslash escaped ('it\'s') which SWI also
        # accepts. Both are handled.
        if ch == "'":
            i += 1
            chars: list[str] = []
            while i < n:
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":
                        chars.append("'")
                        i += 2
                        continue
                    break
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                chars.append(text[i])
                i += 1
            if i >= n:
                raise ParseError("unclosed quoted atom", text, start)
            i += 1  # closing quote
            tokens.append(Token("name", "".join(chars), start))
            continue

        if ch.isdigit():
            while i < n and (text[i].isdigit() or text[i] == "."):
                # A full stop is only part of a number if a digit follows it,
                # otherwise it ends the clause.
                if text[i] == "." and not (i + 1 < n and text[i + 1].isdigit()):
                    break
                i += 1
            tokens.append(Token("num", text[start:i], start))
            continue

        if ch.isalpha() or ch == "_":
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            word = text[start:i]
            kind = "var" if (word[0].isupper() or word[0] == "_") else "name"
            tokens.append(Token(kind, word, start))
            continue

        if ch in _PUNCT and not (ch == "." and text[start : start + 2] == ":-"):
            i += 1
            tokens.append(Token("punct", ch, start))
            continue

        if ch in _SYMBOLIC:
            while i < n and text[i] in _SYMBOLIC:
                i += 1
            symbol = text[start:i]
            if symbol == ":-":
                tokens.append(Token("neck", symbol, start))
            elif symbol in (r"\+", "not"):
                tokens.append(Token("naf", symbol, start))
            elif symbol == ".":
                tokens.append(Token("punct", ".", start))
            else:
                raise ParseError(f"unsupported operator {symbol!r}", text, start)
            continue

        raise ParseError(f"unexpected character {ch!r}", text, start)

    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = tokenize(text)
        self.i = 0

    # -- token helpers ------------------------------------------------------

    @property
    def current(self) -> Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _end_position(self) -> int:
        return len(self.text)

    def expect(self, kind: str, text: str | None = None) -> Token:
        token = self.current
        if token is None:
            want = text or kind
            raise ParseError(f"expected {want!r} but the input ended", self.text, self._end_position())
        if token.kind != kind or (text is not None and token.text != text):
            want = text or kind
            raise ParseError(f"expected {want!r}, found {token.text!r}", self.text, token.position)
        self.i += 1
        return token

    def accept(self, kind: str, text: str | None = None) -> Token | None:
        token = self.current
        if token and token.kind == kind and (text is None or token.text == text):
            self.i += 1
            return token
        return None

    # -- grammar ------------------------------------------------------------

    def parse_clause(self) -> Clause:
        head = self.parse_callable()

        body: tuple[Literal, ...] = ()
        if self.accept("neck"):
            body = self.parse_body()

        self.expect("punct", ".")
        if self.current is not None:
            raise ParseError(
                "unexpected text after the full stop; assert one clause at a time",
                self.text,
                self.current.position,
            )
        return Clause(head=head, body=body)

    def parse_body(self) -> tuple[Literal, ...]:
        literals = [self.parse_literal()]
        while self.accept("punct", ","):
            literals.append(self.parse_literal())
        return tuple(literals)

    def parse_literal(self) -> Literal:
        negated = self.accept("naf") is not None
        return Literal(goal=self.parse_callable(), negated=negated)

    def parse_callable(self) -> Callable:
        """A goal or a clause head. Must be an atom or a compound term."""
        token = self.current
        if token is None:
            raise ParseError("expected a goal but the input ended", self.text, self._end_position())
        if token.kind == "var":
            raise ParseError(
                f"{token.text!r} is a variable, which cannot be a goal on its own",
                self.text,
                token.position,
            )
        if token.kind != "name":
            raise ParseError(f"expected a predicate name, found {token.text!r}", self.text, token.position)

        term = self.parse_term()
        if not isinstance(term, (Atom, Struct)):
            raise ParseError(f"{token.text!r} cannot be a goal", self.text, token.position)
        return term

    def parse_term(self) -> Term:
        token = self.current
        if token is None:
            raise ParseError("expected a term but the input ended", self.text, self._end_position())

        if token.kind == "var":
            self.i += 1
            return Var(token.text)

        if token.kind == "num":
            self.i += 1
            text = token.text
            return Num(float(text) if "." in text else int(text))

        if token.kind == "name":
            self.i += 1
            # A compound term only if ( follows immediately, with no space.
            follows = self.current
            if follows and follows.kind == "punct" and follows.text == "(" and follows.position == token.position + len(token.text):
                self.i += 1
                args = [self.parse_term()]
                while self.accept("punct", ","):
                    args.append(self.parse_term())
                self.expect("punct", ")")
                return Struct(token.text, tuple(args))
            return Atom(token.text)

        raise ParseError(f"unexpected {token.text!r}", self.text, token.position)


def parse_clause(text: str) -> Clause:
    """Read exactly one clause. The closing full stop is required."""
    stripped = text.strip()
    if not stripped:
        raise ParseError("nothing to parse", text, 0)
    return _Parser(stripped).parse_clause()


def parse_goal(text: str) -> Literal:
    """Read a query goal. The full stop is optional here, since people omit it."""
    stripped = text.strip().rstrip(".").strip()
    if not stripped:
        raise ParseError("nothing to parse", text, 0)

    parser = _Parser(stripped)
    literal = parser.parse_literal()
    if parser.current is not None:
        raise ParseError(
            "unexpected text after the goal; query one goal at a time",
            stripped,
            parser.current.position,
        )
    return literal
