"""Texts and button labels for the bot UI.

## Traceability
Feature: F001, F002, F003
"""

# ── Command descriptions ──────────────────────────────────────────────
CMD_START = "start"
CMD_REVIEW = "review"
CMD_HELP = "help"

# ── Messages — Russian ───────────────────────────────────────────────
MSG_WELCOME = (
    "Привет! Я бот <b>Dataist Media</b>.\n\n"
    "Отправьте мне ссылку на статью arXiv, и я подготовлю "
    "редакционный обзор с обложкой и HTML-страницей.\n\n"
    "Просто отправьте ссылку или используйте /review"
)

MSG_HELP = (
    "<b>Доступные команды:</b>\n\n"
    "/start — приветствие\n"
    "/review — запустить пайплайн обзора\n"
    "/help — справка\n\n"
    "Или просто отправьте ссылку на arXiv."
)

MSG_ERROR = "❌ <b>Ошибка</b>\n\n{error}"

MSG_INVALID_URL = (
    "❌ Не удалось распознать ссылку на arXiv.\n"
    "Отправьте корректную ссылку, например:\n"
    "<code>https://arxiv.org/abs/2301.00001</code>"
)

MSG_SEND_URL = "Отправьте ссылку на статью arXiv:"

# ── Messages — English ───────────────────────────────────────────────
MSG_WELCOME_EN = (
    "Hello! I am the <b>Dataist Media</b> bot.\n\n"
    "Send me an arXiv paper link and I will prepare "
    "an editorial review with a cover and HTML page.\n\n"
    "Just send a link or use /review"
)

MSG_HELP_EN = (
    "<b>Available commands:</b>\n\n"
    "/start — welcome message\n"
    "/review — start the review pipeline\n"
    "/help — show this help\n\n"
    "Or just send an arXiv link."
)

MSG_ERROR_EN = "❌ <b>Error</b>\n\n{error}"

MSG_INVALID_URL_EN = (
    "❌ Could not recognise an arXiv URL.\n"
    "Please send a valid link, for example:\n"
    "<code>https://arxiv.org/abs/2301.00001</code>"
)

MSG_SEND_URL_EN = "Send an arXiv article link:"

# ── Interactive flow ──────────────────────────────────────────────────
MSG_PARSING = "⏳ Парсю статью..."
MSG_PARSING_EN = "⏳ Parsing article..."

MSG_CHOOSE_TITLE = (
    "📋 <b>Выберите заголовок</b> (кнопка) или напишите свой текст — "
    "он станет заголовком:"
)
MSG_CHOOSE_TITLE_EN = (
    "📋 <b>Choose a title</b> (button) or type your own — "
    "it will become the title:"
)

MSG_TITLE_SELECTED = '✅ <b>{title}</b>'
MSG_TITLE_SELECTED_EN = '✅ <b>{title}</b>'

MSG_COVER_DESCRIPTION = (
    "🎨 <b>Описание обложки:</b>\n\n"
    "<i>{description}</i>\n\n"
    "Напишите правки или свой промпт целиком, "
    "или нажмите 🖼 Сгенерировать"
)
MSG_COVER_DESCRIPTION_EN = (
    "🎨 <b>Cover description:</b>\n\n"
    "<i>{description}</i>\n\n"
    "Type edits or your own prompt, "
    "or press 🖼 Generate"
)

MSG_GENERATING_IMAGE = "🖼 Генерирую обложку..."
MSG_GENERATING_IMAGE_EN = "🖼 Generating cover image..."

MSG_BUILDING = "📝 Собираю статью и публикую..."
MSG_BUILDING_EN = "📝 Building article and publishing..."

# ── Button labels ─────────────────────────────────────────────────────
BTN_READ_RU = "🇷🇺 Читать (RU)"
BTN_READ_EN = "🇬🇧 Read (EN)"
BTN_LANG_TOGGLE = "🔄 EN / RU"
BTN_GENERATE_COVER = "🖼 Сгенерировать"
