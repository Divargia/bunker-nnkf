# bot.py
import logging
import telebot
from telebot import types
from telebot import apihelper
import threading
import time

from config import BOT_TOKEN, LOGGING_CONFIG
from game_manager import GameManager
from handlers import BotHandlers

apihelper.ENABLE_MIDDLEWARE = True

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format'],
    handlers=[
        logging.FileHandler(LOGGING_CONFIG['file'], encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BunkerBot:
    """Основной класс бота"""
    
    def __init__(self):
        """Инициализация бота"""
        self.bot = telebot.TeleBot(BOT_TOKEN, parse_mode='Markdown')
        self.game_manager = GameManager(self.bot)
        self.handlers = BotHandlers(self.bot, self.game_manager)
        
        # Настройка бота
        self._setup_bot()
        
        logger.info("Бот инициализирован")

    def _setup_bot(self):
        """Настройка параметров бота"""
        # Включаем треды для обработки сообщений
        self.bot.threaded = True

        # Регистрируем обработчики
        self.handlers.register_handlers()

        # ДОБАВЬТЕ ЭТОТ КОД ЗДЕСЬ:
        # Middleware для ограничения чатов
        @self.bot.middleware_handler(update_types=['message', 'callback_query'])
        def chat_restriction_middleware(bot_instance, update):
            """Middleware для ограничения чатов"""
            try:
                from config import ALLOWED_CHAT_ID

                if ALLOWED_CHAT_ID is None:
                    # Ограничения нет, работаем везде
                    return

                chat_id = None

                if hasattr(update, 'message') and update.message:
                    chat_id = update.message.chat.id
                elif hasattr(update, 'callback_query') and update.callback_query:
                    chat_id = update.callback_query.message.chat.id

                if chat_id and chat_id != ALLOWED_CHAT_ID:
                    # Не разрешенный чат
                    if chat_id < 0:  # Групповой чат
                        try:
                            bot_instance.send_message(
                                chat_id,
                                "❌ Бот работает только в определенном чате. До свидания!"
                            )
                            # Покидаем чат
                            bot_instance.leave_chat(chat_id)
                            logger.info(f"Покинул неразрешенный чат {chat_id}")
                        except Exception as e:
                            logger.error(f"Ошибка выхода из чата {chat_id}: {e}")
                    else:
                        # Личное сообщение - просто игнорируем
                        try:
                            bot_instance.send_message(
                                chat_id,
                                "❌ Бот временно недоступен в личных сообщениях."
                            )
                        except:
                            pass

                    # Прерываем обработку
                    return False

            except Exception as e:
                logger.error(f"Ошибка в chat_restriction_middleware: {e}")

        # Настройка обработки ошибок (существующий код)
        @self.bot.middleware_handler(update_types=['message', 'callback_query'])
        def log_middleware(bot_instance, update):
            """Middleware для логирования"""
            try:
                if hasattr(update, 'message') and update.message:
                    user_info = f"User {update.message.from_user.id}"
                    if update.message.from_user.username:
                        user_info += f" (@{update.message.from_user.username})"

                    chat_info = f"Chat {update.message.chat.id} ({update.message.chat.type})"
                    logger.debug(f"Message from {user_info} in {chat_info}: {update.message.text}")

                elif hasattr(update, 'callback_query') and update.callback_query:
                    user_info = f"User {update.callback_query.from_user.id}"
                    if update.callback_query.from_user.username:
                        user_info += f" (@{update.callback_query.from_user.username})"

                    logger.debug(f"Callback from {user_info}: {update.callback_query.data}")

            except Exception as e:
                logger.error(f"Ошибка в middleware: {e}")
    
    def start_polling(self):
        """Запуск бота в режиме polling"""
        try:
            logger.info("Запуск бота...")
            
            # Проверяем токен
            bot_info = self.bot.get_me()
            logger.info(f"Бот запущен: @{bot_info.username} ({bot_info.first_name})")
            
            # Запускаем polling с обработкой ошибок
            self.bot.polling(
                non_stop=True,
                interval=1,
                timeout=60,
                long_polling_timeout=60,
                logger_level=logging.INFO
            )
            
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise
    
    def stop(self):
        """Остановка бота"""
        try:
            logger.info("Остановка бота...")
            
            # Останавливаем все таймеры игр
            for game in self.game_manager.games.values():
                self.game_manager.phase_timer.stop_phase_timer(game.chat_id)
            
            # Останавливаем polling
            self.bot.stop_polling()
            
            logger.info("Бот остановлен")
            
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")
    
    def send_message_safe(self, chat_id: int, text: str, **kwargs):
        """Безопасная отправка сообщения с обработкой ошибок"""
        try:
            return self.bot.send_message(chat_id, text, **kwargs)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 403:
                logger.warning(f"Бот заблокирован пользователем {chat_id}")
            elif e.error_code == 400:
                logger.warning(f"Неверный chat_id {chat_id} или сообщение")
            else:
                logger.error(f"Telegram API ошибка при отправке в {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в {chat_id}: {e}")
        return None
    
    def edit_message_safe(self, chat_id: int, message_id: int, text: str, **kwargs):
        """Безопасное редактирование сообщения"""
        try:
            return self.bot.edit_message_text(text, chat_id, message_id, **kwargs)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 400 and "message is not modified" in e.description.lower():
                # Сообщение не изменилось - это нормально
                pass
            else:
                logger.error(f"Ошибка редактирования сообщения: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка редактирования: {e}")
        return None
    
    def get_chat_administrators_safe(self, chat_id: int):
        """Безопасное получение списка администраторов чата"""
        try:
            return self.bot.get_chat_administrators(chat_id)
        except Exception as e:
            logger.error(f"Ошибка получения админов чата {chat_id}: {e}")
            return []
    
    def get_chat_member_safe(self, chat_id: int, user_id: int):
        """Безопасное получение информации о участнике чата"""
        try:
            return self.bot.get_chat_member(chat_id, user_id)
        except Exception as e:
            logger.error(f"Ошибка получения участника {user_id} в чате {chat_id}: {e}")
            return None

def create_bot():
    """Фабрика для создания экземпляра бота"""
    return BunkerBot()

# Глобальная переменная для хранения экземпляра бота
_bot_instance = None

def get_bot():
    """Получение глобального экземпляра бота (синглтон)"""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = create_bot()
    return _bot_instance

# Обработчик для graceful shutdown
def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"Получен сигнал {signum}, завершение работы...")
    global _bot_instance
    if _bot_instance:
        _bot_instance.stop()
    exit(0)

# Регистрируем обработчики сигналов
import signal
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


#@self.bot.middleware_handler(update_types=['message', 'callback_query'])
#def chat_restriction_middleware(bot_instance, update):
#    """Middleware для ограничения чатов"""
#    try:
#        from config import ALLOWED_CHAT_ID
#
#        if ALLOWED_CHAT_ID is None:
#            # Ограничения нет, работаем везде
#            return
#
#        chat_id = None
#
#        if hasattr(update, 'message') and update.message:
#            chat_id = update.message.chat.id
#        elif hasattr(update, 'callback_query') and update.callback_query:
#            chat_id = update.callback_query.message.chat.id
#
#        if chat_id and chat_id != ALLOWED_CHAT_ID:
#            # Не разрешенный чат
#            if chat_id < 0:  # Групповой чат
#                try:
#                    bot_instance.send_message(
#                        chat_id,
#                        "❌ Бот работает только в определенном чате. До свидания!"
#                    )
#                    # Покидаем чат
#                    bot_instance.leave_chat(chat_id)
#                    logger.info(f"Покинул неразрешенный чат {chat_id}")
#                except Exception as e:
#                    logger.error(f"Ошибка выхода из чата {chat_id}: {e}")
#            else:
#                # Личное сообщение - просто игнорируем
#                try:
#                    bot_instance.send_message(
#                        chat_id,
#                        "❌ Бот временно недоступен в личных сообщениях."
#                    )
#                except:
#                    pass
#
#            # Прерываем обработку
#            return False
#
#    except Exception as e:
#        logger.error(f"Ошибка в chat_restriction_middleware: {e}")
