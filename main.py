import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ConversationHandler, CallbackQueryHandler,
)

import config
from db.models import init_db
from bot.scheduler import init_scheduler
from bot.handlers import (
    handle_message, cmd_list, cmd_cancel, cmd_start, cmd_clearjobs,
    handle_done_callback, handle_snooze_callback,
    handle_custom_start, handle_custom_time_input,
    WAITING_CUSTOM_TIME,
)

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
    app.add_handler(CommandHandler("clearjobs", cmd_clearjobs))

    # Inline button callbacks (non-conversation)
    app.add_handler(CallbackQueryHandler(handle_done_callback, pattern=r"^done:"))
    app.add_handler(CallbackQueryHandler(handle_snooze_callback, pattern=r"^snooze:"))

    # ConversationHandler for custom time (must be before catch-all MessageHandler)
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_custom_start, pattern=r"^custom:")],
        states={WAITING_CUSTOM_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_time_input)]},
        fallbacks=[],
        per_message=False,
    ))

    # Catch-all text handler (last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (polling)…")
    app.run_polling()


if __name__ == "__main__":
    main()
