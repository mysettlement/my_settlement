from decimal import Decimal
from typing import Literal

from fluent_compiler.types import FluentType
from typing_extensions import TypeAlias

PossibleValue: TypeAlias = str | int | float | Decimal | bool | FluentType

class TranslatorRunner:
    def get(self, path: str, **kwargs: PossibleValue) -> str: ...
    language: Language

class Language:
    @staticmethod
    def changed(*, lang_name: PossibleValue) -> Literal["""&#34;✅ Язык успешно изменён на { $lang_name }!&#34;"""]: ...
