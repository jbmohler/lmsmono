import secrets
from dataclasses import dataclass

from litestar import Controller, get
from litestar.params import Parameter

from .wordlist import WORD_LIST

ALPHA = "abcdefghijklmnopqrstuvwxyz"
VOWELS = "aeiouy"
CONSONANTS = "".join(c for c in ALPHA if c not in "aeiou")
NUMBERS = "0123456789"
SYMBOLS = "`~!@#$%^&*()[]{}:;/.,<>?"

DIGRAPHS = ["th", "sh", "ch", "st", "kn", "wh"]


def _secure_shuffle(lst: list[str]) -> None:
    """Fisher-Yates shuffle using secrets.randbelow."""
    for i in range(len(lst) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        lst[i], lst[j] = lst[j], lst[i]


def _triplet() -> str:
    """Generate a short pronounciable syllable."""
    ends = DIGRAPHS + list(CONSONANTS)
    spaces = [ends, list(VOWELS), ends]
    bit = "".join(secrets.choice(x) for x in spaces)
    if secrets.randbelow(2) == 1:
        bit = bit.title()
    return bit


def _pronounciable(bits: int) -> str:
    tripbits = 13  # each triplet ~13 bits of entropy

    triplet_count = (bits - 1) // tripbits + 1
    minlen = triplet_count * 4 - 3
    maxlen = triplet_count * 4 + 3

    trips = [_triplet() for _ in range(triplet_count)]
    while len("".join(trips)) > (minlen + maxlen) // 2:
        trips = trips[:-1]

    tip_space = NUMBERS
    trip_count = len("".join(trips))
    tip_count = secrets.randbelow(maxlen - max(0, minlen - trip_count) + 1) + max(
        0, minlen - trip_count
    )
    tips = [secrets.choice(tip_space) for _ in range(tip_count)]

    total: list[str] = trips + tips
    _secure_shuffle(total)
    return "".join(total)


def _random_from_charset(bits: int, charset: str) -> str:
    middle_bits = bits - 11
    per_char = len(charset).bit_length() - 1
    char_count = (middle_bits - 1) // per_char + 1

    chosen = [secrets.choice(charset) for _ in range(char_count)]
    alpha_both = ALPHA + ALPHA.upper()
    start = secrets.choice(alpha_both)
    end = secrets.choice(alpha_both)
    return start + "".join(chosen) + end


def _random_password(bits: int) -> str:
    charset = ALPHA + ALPHA.upper() + NUMBERS + SYMBOLS
    return _random_from_charset(bits, charset)


def _alphanumeric(bits: int) -> str:
    charset = ALPHA + ALPHA.upper() + NUMBERS
    return _random_from_charset(bits, charset)


def _words(bits: int) -> str:
    per_word = len(WORD_LIST).bit_length() - 1
    word_count = (bits - 1) // per_word + 1

    chosen = [secrets.choice(WORD_LIST) for _ in range(word_count)]
    return " ".join(chosen)


GENERATORS = {
    "pronounciable": _pronounciable,
    "words": _words,
    "random": _random_password,
    "alphanumeric": _alphanumeric,
}


@dataclass
class GeneratePasswordResponse:
    password: str
    mode: str
    bits: int


class PasswordGeneratorController(Controller):
    path = "/api/password/generate"
    tags = ["passwords"]

    @get()
    async def generate_password(
        self,
        mode: str = Parameter(default="alphanumeric"),
        bits: int = Parameter(default=50, ge=10, le=256),
    ) -> GeneratePasswordResponse:
        generator = GENERATORS.get(mode)
        if generator is None:
            from litestar.exceptions import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"Unknown mode '{mode}'. Valid modes: {', '.join(GENERATORS)}",
            )

        password = generator(bits)
        return GeneratePasswordResponse(password=password, mode=mode, bits=bits)
