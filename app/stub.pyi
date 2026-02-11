from decimal import Decimal
from typing import Literal

from fluent_compiler.types import FluentType
from typing_extensions import TypeAlias

PossibleValue: TypeAlias = str | int | float | Decimal | bool | FluentType

class TranslatorRunner:
    def get(self, path: str, **kwargs: PossibleValue) -> str: ...
    text: Text
    button: Button
    callback: Callback
    constant: Constant

class TextOther:
    @staticmethod
    def referral() -> Literal["""Тебя пригласил поселенец с ID:"""]: ...

class TextSettingsTimezoneError:
    @staticmethod
    def determine() -> Literal["""Не удалось определить часовой пояс. Попробуйте выбрать его вручную."""]: ...

class TextSettingsTimezone:
    error: TextSettingsTimezoneError

    @staticmethod
    def title(*, cooldown: PossibleValue, timezone: PossibleValue) -> Literal["""Текущий пояс: &lt;code&gt;{ $timezone }&lt;/code&gt;
Дневной сброс происходит в &lt;b&gt;00:00&lt;/b&gt; по этому времени.

⚠️ Менять пояс можно раз в &lt;b&gt;{ $cooldown } дней&lt;/b&gt;."""]: ...
    @staticmethod
    def determine() -> Literal["""&lt;b&gt;Нажми на кнопку ниже&lt;/b&gt;, чтобы определить часовой пояс автоматически."""]: ...
    @staticmethod
    def determined(*, timezone: PossibleValue) -> Literal["""Часовой пояс определён: &lt;b&gt;{ $timezone }&lt;/b&gt;"""]: ...
    @staticmethod
    def changed(*, tz_name: PossibleValue) -> Literal["""Часовой пояс установлен: &lt;b&gt;{ $tz_name }&lt;/b&gt;"""]: ...

class TextSettingsLanguage:
    @staticmethod
    def title(*, lang_name: PossibleValue) -> Literal["""Выберите язык интерфейса. Это не повлияет на язык сообщений от других игроков.

Текущий язык: &lt;b&gt;{ $lang_name }&lt;/b&gt;"""]: ...

class TextSettings:
    timezone: TextSettingsTimezone
    language: TextSettingsLanguage

    @staticmethod
    def title() -> Literal["""Настройки"""]: ...
    @staticmethod
    def subtitle() -> Literal["""Вы можете настроить поведение бота под себя, изменив следующие параметры:"""]: ...

class Text:
    other: TextOther
    settings: TextSettings

class ButtonCommon:
    @staticmethod
    def back() -> Literal["""Назад"""]: ...

class ButtonSettingsTimezone:
    @staticmethod
    def determine() -> Literal["""Определить"""]: ...
    @staticmethod
    def share_location() -> Literal["""Поделиться геопозицией"""]: ...
    @staticmethod
    def set() -> Literal["""Установить!"""]: ...

class ButtonSettings:
    timezone: ButtonSettingsTimezone

class Button:
    common: ButtonCommon
    settings: ButtonSettings

class CallbackCommon:
    @staticmethod
    def dont_touch() -> Literal["""Не тронь чужой снасти!"""]: ...

class CallbackSettingsLanguage:
    @staticmethod
    def changed(*, lang_name: PossibleValue) -> Literal["""Язык успешно изменён на { $lang_name }!"""]: ...

class CallbackSettingsTimezoneError:
    @staticmethod
    def locked(*, time_left: PossibleValue) -> Literal["""Сменить пояс можно { $time_left }"""]: ...

class CallbackSettingsTimezone:
    error: CallbackSettingsTimezoneError

    @staticmethod
    def changed() -> Literal["""Часовой пояс сохранен!"""]: ...

class CallbackSettings:
    language: CallbackSettingsLanguage
    timezone: CallbackSettingsTimezone

class CallbackCraft:
    @staticmethod
    def craft() -> Literal["""Трудиться"""]: ...

class Callback:
    common: CallbackCommon
    settings: CallbackSettings
    craft: CallbackCraft

class ConstantSettingsCommon:
    @staticmethod
    def on() -> Literal["""Включено"""]: ...
    @staticmethod
    def off() -> Literal["""Выключено"""]: ...
    @staticmethod
    def enabled() -> Literal["""Включены"""]: ...
    @staticmethod
    def disabled() -> Literal["""Выключены"""]: ...
    @staticmethod
    def account() -> Literal["""Учитывать"""]: ...
    @staticmethod
    def ignore() -> Literal["""Не учитывать"""]: ...

class ConstantSettingsStyle:
    @staticmethod
    def compact() -> Literal["""Компактный"""]: ...
    @staticmethod
    def full() -> Literal["""Развёрнутый"""]: ...

class ConstantSettingsLabel:
    @staticmethod
    def style() -> Literal["""Стиль"""]: ...
    @staticmethod
    def hints() -> Literal["""Подсказки"""]: ...
    @staticmethod
    def typos() -> Literal["""Опечатки"""]: ...
    @staticmethod
    def timezone() -> Literal["""Часовой пояс"""]: ...
    @staticmethod
    def language() -> Literal["""Язык"""]: ...

class ConstantSettings:
    common: ConstantSettingsCommon
    style: ConstantSettingsStyle
    label: ConstantSettingsLabel

class Constant:
    settings: ConstantSettings
