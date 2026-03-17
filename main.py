import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

import config
from db.models import init_db
from bot.scheduler import init_scheduler
from bot.handlers import handle_message, cmd_list, cmd_cancel, cmd_start

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point: initialise DB + scheduler, then start the Telegram bot."""
    init_db()
    init_scheduler()

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)…")
    app.run_polling()


if __name__ == "__main__":
    main()
