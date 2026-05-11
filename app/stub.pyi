from decimal import Decimal
from typing import Literal

from fluent_compiler.types import FluentType
from typing_extensions import TypeAlias

PossibleValue: TypeAlias = str | int | float | Decimal | bool | FluentType

class TranslatorRunner:
    def get(self, path: str, **kwargs: PossibleValue) -> str: ...
    text: Text
    callback: Callback
    button: Button
    constant: Constant

class TextCraftChoose:
    @staticmethod
    def title() -> Literal["""Выбор ремесла"""]: ...
    @staticmethod
    def cooldown() -> Literal["""Сменить ремесло можно через"""]: ...

class TextCraftStatus:
    @staticmethod
    def selected() -> Literal["""Выбрано"""]: ...
    @staticmethod
    def available() -> Literal["""Доступно"""]: ...
    @staticmethod
    def locked() -> Literal["""Недоступно"""]: ...

class TextCraftSelected:
    @staticmethod
    def success(*, profession_name: PossibleValue, user_name: PossibleValue) -> Literal["""&lt;b&gt;{ $user_name }&lt;/b&gt; избрал своё ремесло: &lt;b&gt;{ $profession_name }!&lt;/b&gt;"""]: ...

class TextCraft:
    choose: TextCraftChoose
    status: TextCraftStatus
    selected: TextCraftSelected

    @staticmethod
    def no_professions() -> Literal["""Нет доступных ремесел. Обратитесь к &lt;a href=&#34;https://t.me/megatocha&#34;&gt;создателю.&lt;/a&gt;"""]: ...
    @staticmethod
    def no_profession() -> Literal["""Ты ещё ремесла не избрал."""]: ...
    @staticmethod
    def no_works() -> Literal["""Твоё ремесло пока не имеет доступных трудов. Жди вестей новых!"""]: ...

class TextOtherPrivate:
    @staticmethod
    def greeting() -> Literal["""&lt;b&gt;Здрав будь!&lt;/b&gt; Я вестник для игры в &lt;b&gt;Поселения&lt;/b&gt;.
Чтоб в сходку свою меня позвать, &lt;b&gt;на знак ниже ткни:&lt;/b&gt;"""]: ...

class TextOtherBotAdded:
    @staticmethod
    def __call__() -> Literal["""&lt;b&gt;Добро пожаловать в игру «Поселения»!&lt;/b&gt;

Для начала игры используйте команду /start"""]: ...
    @staticmethod
    def no_admin() -> Literal["""Пожалуйста, &lt;b&gt;назначьте меня администратором&lt;/b&gt; с правами на &lt;i&gt;закрепление&lt;/i&gt; и &lt;i&gt;удаление&lt;/i&gt; сообщений, &lt;b&gt;чтобы я мог полноценно функционировать!&lt;/b&gt;"""]: ...

class TextOtherBot:
    added: TextOtherBotAdded

    @staticmethod
    def left(*, chat_title: PossibleValue) -> Literal["""&lt;b&gt;Я покинул стены поселения «{ $chat_title }»...&lt;/b&gt;
Буду признателен, если расскажешь, что пошло не так.
Это поможет мне стать лучше для других правителей."""]: ...
    @staticmethod
    def promoted() -> Literal["""&lt;b&gt;Спасибо&lt;/b&gt;, что назначили меня администратором!"""]: ...

class TextOtherEffects:
    @staticmethod
    def title(*, name: PossibleValue) -> Literal["""&lt;b&gt;Эффекты { $name }&lt;/b&gt;"""]: ...
    @staticmethod
    def empty() -> Literal["""Нет активных эффектов."""]: ...
    @staticmethod
    def hint() -> Literal["""Бонусы можно получить от личных или городских построек!"""]: ...

class TextOtherPromo:
    @staticmethod
    def not_developer() -> Literal["""Только разработчики могут выдавать ресурсы."""]: ...
    @staticmethod
    def bad_format() -> Literal["""Неверный формат команды.
&lt;code&gt;!дать эмодзи количество&lt;/code&gt; (в ответ или себе)"""]: ...
    @staticmethod
    def received(*, name: PossibleValue) -> Literal["""&lt;b&gt;{ $name } получил(а):&lt;/b&gt;"""]: ...

class TextOther:
    private: TextOtherPrivate
    bot: TextOtherBot
    effects: TextOtherEffects
    promo: TextOtherPromo

    @staticmethod
    def referral() -> Literal["""Тебя пригласил поселенец с ID:"""]: ...
    @staticmethod
    def cancel() -> Literal["""Отменено."""]: ...
    @staticmethod
    def help() -> Literal["""&lt;b&gt;Моё Поселение!&lt;/b&gt; — текстовая MMORPG о жизни общины.
Ты выбираешь ремесло, трудишься в мини-играх и развиваешь поселенца.

&lt;b&gt;Как играть&lt;/b&gt;
• /start — начать и осмотреть поселение
• /me — профиль и действия
• /choose_craft — выбрать ремесло
• /craft — начать работу

&lt;a href=&#34;https://docs.fiwu.uno/&#34;&gt;Полные гайды&lt;/a&gt;"""]: ...

class TextSettlementViewOwner:
    @staticmethod
    def missing() -> Literal["""Отсутствует"""]: ...
    @staticmethod
    def fallback(*, telegram_id: PossibleValue) -> Literal["""Пользователь { $telegram_id }"""]: ...

class TextSettlementView:
    owner: TextSettlementViewOwner

class TextSettlementRename:
    @staticmethod
    def empty() -> Literal["""Укажите название!
Пример: &lt;code&gt;/name_settlement Новый Град&lt;/code&gt;"""]: ...
    @staticmethod
    def length() -> Literal["""Название должно быть от 3 до 30 символов."""]: ...
    @staticmethod
    def not_owner() -> Literal["""Управлять именем поселения токмо &lt;b&gt;правитель&lt;/b&gt; может! Иди своим путём, простолюдин."""]: ...
    @staticmethod
    def cooldown(*, time_left: PossibleValue) -> Literal["""&lt;b&gt;Не спеши, правитель.&lt;/b&gt;
Чернила на прошлом указе ещё не высохли. Негоже так часто имена менять.

Новую грамоту сможешь подать &lt;b&gt;{ $time_left }&lt;/b&gt;."""]: ...
    @staticmethod
    def same(*, new_name: PossibleValue, old_name: PossibleValue) -> Literal["""&lt;b&gt;К чему тратить чернила?&lt;/b&gt;
Писарь не станет марать пергамент понапрасну.

Ты меняешь &lt;b&gt;{ $old_name }&lt;/b&gt; на &lt;b&gt;{ $new_name }&lt;/b&gt;. Суть едина."""]: ...
    @staticmethod
    def success(*, new_name: PossibleValue, old_name: PossibleValue) -> Literal["""&lt;b&gt;Быть по сему!&lt;/b&gt;

Имя &lt;b&gt;{ $old_name }&lt;/b&gt; уходит в легенды. Отныне и впредь владения сии величаются &lt;b&gt;{ $new_name }&lt;/b&gt;!

&lt;b&gt;Да здравствует { $new_name }!&lt;/b&gt;"""]: ...

class TextSettlement:
    view: TextSettlementView
    rename: TextSettlementRename

class TextSettlerId:
    @staticmethod
    def internal() -> Literal["""Внутренний ID"""]: ...

class TextSettlerProfileCraft:
    @staticmethod
    def none() -> Literal["""Лодырь"""]: ...

class TextSettlerProfileFull:
    @staticmethod
    def craft() -> Literal["""Ремесло"""]: ...
    @staticmethod
    def level() -> Literal["""Ступень"""]: ...
    @staticmethod
    def exp() -> Literal["""Опыт"""]: ...
    @staticmethod
    def rank() -> Literal["""Титул"""]: ...
    @staticmethod
    def quote() -> Literal["""Мера"""]: ...
    @staticmethod
    def balance() -> Literal["""Мошна"""]: ...

class TextSettlerProfileWork:
    @staticmethod
    def cooldown(*, countdown: PossibleValue) -> Literal["""Труд доступен &lt;b&gt;{ $countdown }&lt;/b&gt;"""]: ...
    @staticmethod
    def ready() -> Literal["""Доступен труд!"""]: ...

class TextSettlerProfileOvertime:
    @staticmethod
    def hint() -> Literal["""Страда взята"""]: ...

class TextSettlerProfile:
    craft: TextSettlerProfileCraft
    full: TextSettlerProfileFull
    work: TextSettlerProfileWork
    overtime: TextSettlerProfileOvertime

class TextSettlerError:
    @staticmethod
    def not_found() -> Literal["""Беда приключилась, вести о тебе не сысканы. Погоди малость, опосля пытай снова."""]: ...

class TextSettlerCosmetics:
    @staticmethod
    def title() -> Literal["""Доступные обличья"""]: ...
    @staticmethod
    def current() -> Literal["""Текущий эмодзи"""]: ...
    @staticmethod
    def none() -> Literal["""Нет доступных эмодзи"""]: ...
    @staticmethod
    def accepted(*, emoji: PossibleValue) -> Literal["""Облик принят: { $emoji }"""]: ...

class TextSettlerOvertimeStatus:
    @staticmethod
    def active(*, overtime_count: PossibleValue, quote: PossibleValue, reset_countdown: PossibleValue, target_quote: PossibleValue) -> Literal["""Состояние страды: &lt;b&gt;Активна&lt;/b&gt;
Сколько страды взято: { $overtime_count } (&lt;b&gt;{ $reset_countdown }&lt;/b&gt; до новой страды)
📄 Мера: &lt;b&gt;{ $quote }/{ $target_quote }&lt;/b&gt;"""]: ...
    @staticmethod
    def need_quota() -> Literal["""Страду брать можно, токмо основную 📄 меру свершив!"""]: ...
    @staticmethod
    def inactive(*, overtime_count: PossibleValue) -> Literal["""Состояние страды: 🔘 &lt;b&gt;Неактивна&lt;/b&gt;
Сколько страды взято: { $overtime_count }"""]: ...

class TextSettlerOvertime:
    status: TextSettlerOvertimeStatus

    @staticmethod
    def title() -> Literal["""Страда"""]: ...
    @staticmethod
    def hint(*, reset_countdown: PossibleValue) -> Literal["""Коль добра тебе мало, можешь &lt;b&gt;страду&lt;/b&gt; взять. С каждой страдой работа тяжелеет, мудрости меньше наберёшь, но грошей столько же получишь. Коль &lt;b&gt;не поспеешь труд свершить&lt;/b&gt; до нового дня ({ $reset_countdown }), на тебя &lt;b&gt;виру&lt;/b&gt; наложат."""]: ...
    @staticmethod
    def taken(*, new_quote: PossibleValue, reset_countdown: PossibleValue) -> Literal["""&lt;b&gt;Страда взята!&lt;/b&gt; (📄 0/{ $new_quote })
Новая мера должна быть исполнена 🕒 &lt;b&gt;{ $reset_countdown }&lt;/b&gt;!"""]: ...

class TextSettlerInventory:
    @staticmethod
    def title() -> Literal["""Скарбы"""]: ...
    @staticmethod
    def empty() -> Literal["""Пусто"""]: ...
    @staticmethod
    def hint() -> Literal["""Ресурсы могут добывать разные специалисты, а также их можно получить в награду за выполнение событий."""]: ...

class TextSettler:
    id: TextSettlerId
    profile: TextSettlerProfile
    error: TextSettlerError
    cosmetics: TextSettlerCosmetics
    overtime: TextSettlerOvertime
    inventory: TextSettlerInventory

class TextCommonWork:
    @staticmethod
    def expired() -> Literal["""Долго ты без дела стоял! Труд отложен."""]: ...

class TextCommon:
    work: TextCommonWork

    @staticmethod
    def received() -> Literal["""Получено"""]: ...
    @staticmethod
    def none() -> Literal["""Неизвестно"""]: ...

class TextBuildingsTown:
    @staticmethod
    def title() -> Literal["""Городские постройки"""]: ...

class TextBuildingsMy:
    @staticmethod
    def title() -> Literal["""Мои постройки"""]: ...

class TextBuildingsStatus:
    @staticmethod
    def active() -> Literal["""Активно"""]: ...
    @staticmethod
    def construction(*, time_left: PossibleValue) -> Literal["""Построится { $time_left }"""]: ...

class TextBuildingsView:
    @staticmethod
    def active() -> Literal["""В обороте!"""]: ...
    @staticmethod
    def construction(*, time_left: PossibleValue) -> Literal["""Стройка закончится &lt;b&gt;{ $time_left }&lt;/b&gt;"""]: ...
    @staticmethod
    def bonuses() -> Literal["""Бонусы:"""]: ...

class TextBuildingsCatalogScope:
    @staticmethod
    def town() -> Literal["""Городские"""]: ...
    @staticmethod
    def my() -> Literal["""Личные"""]: ...

class TextBuildingsCatalog:
    scope: TextBuildingsCatalogScope

    @staticmethod
    def title() -> Literal["""Каталог чертежей"""]: ...

class TextBuildingsPreview:
    @staticmethod
    def requirements() -> Literal["""Требуется для постройки:"""]: ...
    @staticmethod
    def time(*, time: PossibleValue) -> Literal["""&lt;b&gt;Время строительства:&lt;/b&gt; { $time } секунд"""]: ...

class TextBuildings:
    town: TextBuildingsTown
    my: TextBuildingsMy
    status: TextBuildingsStatus
    view: TextBuildingsView
    catalog: TextBuildingsCatalog
    preview: TextBuildingsPreview

    @staticmethod
    def empty() -> Literal["""Пока здесь пусто."""]: ...
    @staticmethod
    def not_found() -> Literal["""Здание уже снесено или не существует."""]: ...

class TextSettingsTimezoneError:
    @staticmethod
    def determine() -> Literal["""Не удалось определить часовой пояс. Попробуй выбрать его вручную."""]: ...

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
    def title(*, lang_name: PossibleValue) -> Literal["""Выбери язык интерфейса. Это не повлияет на язык сообщений от других игроков.

Текущий язык: &lt;b&gt;{ $lang_name }&lt;/b&gt;"""]: ...

class TextSettings:
    timezone: TextSettingsTimezone
    language: TextSettingsLanguage

    @staticmethod
    def title() -> Literal["""Настройки"""]: ...
    @staticmethod
    def subtitle() -> Literal["""Вы можете настроить поведение бота под себя, изменив следующие параметры:"""]: ...

class Text:
    craft: TextCraft
    other: TextOther
    settlement: TextSettlement
    settler: TextSettler
    common: TextCommon
    buildings: TextBuildings
    settings: TextSettings

class CallbackCraft:
    @staticmethod
    def craft() -> Literal["""Трудиться"""]: ...
    @staticmethod
    def already_selected() -> Literal["""Ты сие ремесло уже избрал!"""]: ...
    @staticmethod
    def level_too_low() -> Literal["""Ремесло сие тебе не по плечу!"""]: ...
    @staticmethod
    def cooldown(*, when: PossibleValue) -> Literal["""Недавно ты ремесло своё сменил, человече! Новое взять можно, как &lt;b&gt;{ $when }&lt;/b&gt; пройдёт."""]: ...
    @staticmethod
    def work_not_found() -> Literal["""Труд не сыскан!"""]: ...
    @staticmethod
    def wrong_profession() -> Literal["""Сие дело твоему ремеслу не по плечу!"""]: ...

class CallbackOtherLang:
    @staticmethod
    def not_found(*, lang_code: PossibleValue) -> Literal["""Язык { $lang_code } не найден"""]: ...

class CallbackOther:
    lang: CallbackOtherLang

class CallbackSettlerOvertime:
    @staticmethod
    def already() -> Literal["""Страда уже взята!"""]: ...

class CallbackSettler:
    overtime: CallbackSettlerOvertime

class CallbackCommonWorkExpired:
    @staticmethod
    def toast() -> Literal["""Пора труда миновала! Дело отложено."""]: ...

class CallbackCommonWork:
    expired: CallbackCommonWorkExpired

    @staticmethod
    def not_found() -> Literal["""Дело не сыскано. Может, ты уж его свершил, али вовсе не твоё то дело?"""]: ...

class CallbackCommon:
    work: CallbackCommonWork

    @staticmethod
    def dont_touch() -> Literal["""Не тронь чужой снасти!"""]: ...
    @staticmethod
    def wait() -> Literal["""Погоди миг единый!"""]: ...
    @staticmethod
    def invalid_action() -> Literal["""Неверный ход!"""]: ...
    @staticmethod
    def invalid_step() -> Literal["""Неверный шаг!"""]: ...

class CallbackBuildingsBuild:
    @staticmethod
    def success() -> Literal["""Работа закипела!"""]: ...
    @staticmethod
    def only_mayor() -> Literal["""Только правитель может строить городские здания."""]: ...

class CallbackBuildings:
    build: CallbackBuildingsBuild

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

class Callback:
    craft: CallbackCraft
    other: CallbackOther
    settler: CallbackSettler
    common: CallbackCommon
    buildings: CallbackBuildings
    settings: CallbackSettings

class ButtonOtherBotLeft:
    @staticmethod
    def survey() -> Literal["""Пройти опрос (1 мин)"""]: ...

class ButtonOtherBot:
    left: ButtonOtherBotLeft

    @staticmethod
    def help() -> Literal["""Помощь"""]: ...
    @staticmethod
    def inspect() -> Literal["""Осмотреть поселение"""]: ...
    @staticmethod
    def cancel() -> Literal["""Отмена"""]: ...

class ButtonOther:
    bot: ButtonOtherBot

    @staticmethod
    def add() -> Literal["""Добавить"""]: ...

class ButtonSettlement:
    @staticmethod
    def profile() -> Literal["""Лик"""]: ...
    @staticmethod
    def rename() -> Literal["""Переименовать"""]: ...
    @staticmethod
    def buildings() -> Literal["""Постройки"""]: ...

class ButtonSettlerOvertime:
    @staticmethod
    def __call__() -> Literal["""Страда"""]: ...
    @staticmethod
    def take() -> Literal["""Взять страду"""]: ...

class ButtonSettler:
    overtime: ButtonSettlerOvertime

    @staticmethod
    def cosmetics() -> Literal["""Обличья"""]: ...
    @staticmethod
    def inventory() -> Literal["""Скарб"""]: ...
    @staticmethod
    def work() -> Literal["""Трудиться"""]: ...
    @staticmethod
    def choose_craft() -> Literal["""Выбрать ремесло"""]: ...

class ButtonCommon:
    @staticmethod
    def back() -> Literal["""Назад"""]: ...

class ButtonBuildings:
    @staticmethod
    def blueprints() -> Literal["""Чертежи"""]: ...
    @staticmethod
    def build() -> Literal["""Построить!"""]: ...
    @staticmethod
    def back_blueprints() -> Literal["""К чертежам"""]: ...

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
    other: ButtonOther
    settlement: ButtonSettlement
    settler: ButtonSettler
    common: ButtonCommon
    buildings: ButtonBuildings
    settings: ButtonSettings

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
