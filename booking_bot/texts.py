"""All user-facing strings. Placeholders use str.format; HTML parse mode is on, so user input is escaped."""

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "welcome": "👋 Hi, {name}!\n\nI can book you in at <b>{business}</b>. Choose an option below.",
        "btn_book": "📅 Book",
        "btn_my": "🗂 My bookings",
        "btn_contacts": "📍 Contacts",
        "choose_service": "What would you like to book?",
        "service_line": "{name} · {minutes} min · {price}",
        "choose_day": "<b>{service}</b>\nChoose a day:",
        "no_days": "Sorry, there are no free slots in the next {days} days. Please check back later.",
        "choose_time": "<b>{service}</b>, {day}\nChoose a time:",
        "no_times": "That day just filled up. Please pick another one.",
        "confirm": "Please confirm your booking:\n\n<b>{service}</b>\n🗓 {day}, {time}\n⏱ {minutes} min\n💳 {price}",
        "btn_confirm": "✅ Confirm",
        "btn_back": "← Back",
        "booked": "✅ You're booked!\n\n<b>{service}</b>\n🗓 {day}, {time}\n\nI'll remind you beforehand. See you soon!",
        "slot_taken": "😔 Someone has just taken that time. Please choose another one.",
        "too_many": "You already have {max} upcoming bookings. Cancel one to book another.",
        "too_late": "That time is no longer available. Please choose another one.",
        "my_empty": "You have no upcoming bookings.",
        "my_header": "Your upcoming bookings:",
        "my_line": "• <b>{service}</b> — {day}, {time}",
        "btn_cancel": "✖ Cancel {day} {time}",
        "cancelled": "Booking for {day}, {time} cancelled.",
        "cancel_failed": "This booking is already cancelled or doesn't exist.",
        "contacts": "<b>{business}</b>\n📍 {address}\n📞 {phone}",
        "reminder": "⏰ Reminder: <b>{service}</b> today at {time}.\n📍 {address}",
        "admin_new": "🆕 New booking #{id}\n<b>{service}</b>\n🗓 {day}, {time}\n👤 {user}",
        "admin_cancelled": "❌ Booking #{id} cancelled by the client\n{service} — {day}, {time}\n👤 {user}",
        "admin_cancelled_by_you": "Booking #{id} cancelled; the client has been notified.",
        "client_cancelled_by_admin": "Unfortunately your booking for {day}, {time} was cancelled. Please choose another time.",
        "agenda_empty": "No bookings for {period}.",
        "agenda_header": "📋 Bookings for {period}:",
        "agenda_line": "#{id} {time} — {service} — {user}",
        "admin_help": "Admin commands:\n/today · /tomorrow · /week — agenda\n/export — all bookings as CSV\n/cancel ID — cancel a booking",
        "admin_cancel_usage": "Usage: /cancel 42",
        "period_today": "today",
        "period_tomorrow": "tomorrow",
        "period_week": "the next 7 days",
        "unknown": "I didn't get that. Use the buttons below 👇",
    },
    "ru": {
        "welcome": "👋 Здравствуйте, {name}!\n\nЯ помогу записаться в <b>{business}</b>. Выберите действие ниже.",
        "btn_book": "📅 Записаться",
        "btn_my": "🗂 Мои записи",
        "btn_contacts": "📍 Контакты",
        "choose_service": "На какую услугу записать?",
        "service_line": "{name} · {minutes} мин · {price}",
        "choose_day": "<b>{service}</b>\nВыберите день:",
        "no_days": "К сожалению, в ближайшие {days} дн. свободных окон нет. Загляните позже.",
        "choose_time": "<b>{service}</b>, {day}\nВыберите время:",
        "no_times": "Этот день только что заняли. Выберите другой.",
        "confirm": "Подтвердите запись:\n\n<b>{service}</b>\n🗓 {day}, {time}\n⏱ {minutes} мин\n💳 {price}",
        "btn_confirm": "✅ Подтвердить",
        "btn_back": "← Назад",
        "booked": "✅ Вы записаны!\n\n<b>{service}</b>\n🗓 {day}, {time}\n\nЯ напомню заранее. До встречи!",
        "slot_taken": "😔 Это время только что заняли. Выберите другое.",
        "too_many": "У вас уже {max} предстоящих записи. Отмените одну, чтобы записаться снова.",
        "too_late": "Это время уже недоступно. Выберите другое.",
        "my_empty": "У вас нет предстоящих записей.",
        "my_header": "Ваши предстоящие записи:",
        "my_line": "• <b>{service}</b> — {day}, {time}",
        "btn_cancel": "✖ Отменить {day} {time}",
        "cancelled": "Запись на {day}, {time} отменена.",
        "cancel_failed": "Эта запись уже отменена или не существует.",
        "contacts": "<b>{business}</b>\n📍 {address}\n📞 {phone}",
        "reminder": "⏰ Напоминание: <b>{service}</b> сегодня в {time}.\n📍 {address}",
        "admin_new": "🆕 Новая запись #{id}\n<b>{service}</b>\n🗓 {day}, {time}\n👤 {user}",
        "admin_cancelled": "❌ Клиент отменил запись #{id}\n{service} — {day}, {time}\n👤 {user}",
        "admin_cancelled_by_you": "Запись #{id} отменена, клиент уведомлён.",
        "client_cancelled_by_admin": "К сожалению, ваша запись на {day}, {time} отменена. Выберите другое время.",
        "agenda_empty": "Записей на {period} нет.",
        "agenda_header": "📋 Записи на {period}:",
        "agenda_line": "#{id} {time} — {service} — {user}",
        "admin_help": "Команды администратора:\n/today · /tomorrow · /week — расписание\n/export — все записи в CSV\n/cancel ID — отменить запись",
        "admin_cancel_usage": "Использование: /cancel 42",
        "period_today": "сегодня",
        "period_tomorrow": "завтра",
        "period_week": "ближайшие 7 дней",
        "unknown": "Не понял. Воспользуйтесь кнопками ниже 👇",
    },
}

WEEKDAYS_SHORT = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
}


class T:
    """Tiny translator: T('ru')('booked', service=...)."""

    def __init__(self, lang: str):
        self.lang = lang
        self.strings = TEXTS[lang]

    def __call__(self, key: str, **kwargs) -> str:
        return self.strings[key].format(**kwargs)

    def day(self, d) -> str:
        return f"{WEEKDAYS_SHORT[self.lang][d.weekday()]} {d:%d.%m}"


assert TEXTS["en"].keys() == TEXTS["ru"].keys(), "translations out of sync"
