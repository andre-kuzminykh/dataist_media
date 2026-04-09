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
    "Используйте /review &lt;url&gt; или просто отправьте ссылку."
)

MSG_HELP = (
    "<b>Доступные команды:</b>\n\n"
    "/start — приветствие\n"
    "/review &lt;arxiv_url&gt; — запустить пайплайн обзора\n"
    "/help — справка\n\n"
    "Вы также можете просто отправить ссылку на arXiv после команды /review."
)

MSG_PROCESSING = "\u2699\ufe0f Обрабатываю статью, это может занять пару минут..."

MSG_SUCCESS = (
    "<b>{title}</b>\n\n"
    "Обзор готов!\n\n"
    "{links}"
)

MSG_ERROR = (
    "\u274c <b>Ошибка</b>\n\n"
    "{error}"
)

MSG_INVALID_URL = (
    "\u274c Не удалось распознать ссылку на arXiv.\n"
    "Пожалуйста, отправьте корректную ссылку, например:\n"
    "<code>https://arxiv.org/abs/2301.00001</code>"
)

MSG_SEND_URL = "Отправьте ссылку на статью arXiv:"

# ── Messages — English ───────────────────────────────────────────────
MSG_WELCOME_EN = (
    "Hello! I am the <b>Dataist Media</b> bot.\n\n"
    "Send me an arXiv paper link and I will prepare "
    "an editorial review with a cover and HTML page.\n\n"
    "Use /review &lt;url&gt; or simply send a link."
)

MSG_HELP_EN = (
    "<b>Available commands:</b>\n\n"
    "/start — welcome message\n"
    "/review &lt;arxiv_url&gt; — start the review pipeline\n"
    "/help — show this help\n\n"
    "You can also just send an arXiv link after the /review command."
)

MSG_PROCESSING_EN = "\u2699\ufe0f Processing the article, this may take a couple of minutes..."

MSG_SUCCESS_EN = (
    "<b>{title}</b>\n\n"
    "Review is ready!\n\n"
    "{links}"
)

MSG_ERROR_EN = (
    "\u274c <b>Error</b>\n\n"
    "{error}"
)

MSG_INVALID_URL_EN = (
    "\u274c Could not recognise an arXiv URL.\n"
    "Please send a valid link, for example:\n"
    "<code>https://arxiv.org/abs/2301.00001</code>"
)

MSG_SEND_URL_EN = "Send an arXiv article link:"

# ── Button labels ─────────────────────────────────────────────────────
BTN_READ_RU = "\U0001f1f7\U0001f1fa Читать (RU)"
BTN_READ_EN = "\U0001f1ec\U0001f1e7 Read (EN)"
BTN_CHANNEL = "\U0001f4e2 Канал / Channel"

# ── Interactive flow messages ──────────────────────────────────────
MSG_PARSING = "⏳ Парсю статью..."
MSG_PARSING_EN = "⏳ Parsing article..."

MSG_CHOOSE_TITLE = "📋 <b>Выберите заголовок</b> (нажмите кнопку) или напишите свой:"
MSG_CHOOSE_TITLE_EN = "📋 <b>Choose a title</b> (press a button) or write your own:"

MSG_TITLE_SELECTED = '✅ Заголовок выбран: <b>"{title}"</b>'
MSG_TITLE_SELECTED_EN = '✅ Title selected: <b>"{title}"</b>'

MSG_COVER_DESCRIPTION = "🎨 <b>Описание обложки:</b>\n\n<i>{description}</i>"
MSG_COVER_DESCRIPTION_EN = "🎨 <b>Cover description:</b>\n\n<i>{description}</i>"

MSG_SEND_COVER_EDIT = "✏️ Напишите, что изменить в описании обложки:"
MSG_SEND_COVER_EDIT_EN = "✏️ Describe what to change in the cover description:"

MSG_GENERATING_IMAGE = "🖼 Генерирую обложку..."
MSG_GENERATING_IMAGE_EN = "🖼 Generating cover image..."

MSG_BUILDING = "📝 Собираю статью и публикую..."
MSG_BUILDING_EN = "📝 Building article and publishing..."

MSG_SEND_CUSTOM_TITLE = "✏️ Напишите свой вариант заголовка:"
MSG_SEND_CUSTOM_TITLE_EN = "✏️ Write your own title variant:"

MSG_REGENERATING_TITLES = "🔄 Генерирую новые заголовки на основе вашего варианта..."
MSG_REGENERATING_TITLES_EN = "🔄 Generating new titles based on your input..."

# ── Button labels for interactive flow ─────────────────────────────
BTN_CUSTOM_TITLE = "✏️ Свой заголовок"
BTN_EDIT_COVER = "✏️ Редактировать"
BTN_GENERATE_COVER = "🖼 Сгенерировать"
