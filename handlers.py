# handlers.py
import logging
from typing import Dict, Any
from telebot.types import Message, CallbackQuery
from game_manager import GamePhase
import time
import os

from keyboards import *
from config import ADMIN_IDS, ALLOWED_CHAT_ID, MESSAGE_DELAY, BOT_IMAGES
from config import GAME_SETTINGS
from special_cards import get_special_cards, add_special_card, remove_special_card, save_special_cards  # new
from config import ALLOWED_CHAT_ID
import game_manager

logger = logging.getLogger(__name__)


class BotHandlers:
    """Обработчики команд и колбэков бота"""

    def __init__(self, bot, game_manager):
        self.bot = bot
        self.game_manager = game_manager
        self.user_states: Dict[int, Dict[str, Any]] = {}  # Состояния пользователей

    def _send_message_with_image(self, chat_id: int, text: str, image_key: str = None, **kwargs):
        """Отправляет сообщение с возможным изображением БЕЗ задержки (для команд)"""

        try:
            image_path = BOT_IMAGES.get(image_key, '') if image_key else ''

            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as photo:
                    self.bot.send_photo(
                        chat_id,
                        photo=photo,
                        caption=text,
                        **kwargs
                    )
            else:
                self.bot.send_message(chat_id, text, **kwargs)

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            try:
                self.bot.send_message(chat_id, text, **kwargs)
            except Exception as e2:
                logger.error(f"Ошибка отправки fallback сообщения: {e2}")

    def register_handlers(self):
        """Регистрирует обработчики"""

        # Команды
        self.bot.message_handler(commands=['start'])(self.start_command)
        self.bot.message_handler(commands=['help'])(self.help_command)
        self.bot.message_handler(commands=['game'])(self.game_command)
        self.bot.message_handler(commands=['admin'])(self.admin_command)
        self.bot.message_handler(commands=['stop'])(self.stop_command)

        # НОВЫЕ КОМАНДЫ:
        self.bot.message_handler(commands=['begin', 'startgame'])(self.begin_game_command)
        self.bot.message_handler(commands=['end', 'endgame'])(self.end_game_command)
        self.bot.message_handler(commands=['leave'])(self.leave_game_command)

        # Колбэки
        self.bot.callback_query_handler(func=lambda call: True)(self.callback_handler)

        # Текстовые сообщения
        self.bot.message_handler(content_types=['text'])(self.text_handler)

    def begin_game_command(self, message: Message):
        """Обработчик команды /begin (начать игру)"""
        try:
            if message.chat.type not in ['group', 'supergroup']:
                self.bot.send_message(message.chat.id, "❌ Команда доступна только в группах!")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            if chat_id not in self.game_manager.games:
                self.bot.send_message(chat_id, "❌ Нет созданной игры. Используйте /game для создания.")
                return

            game = self.game_manager.games[chat_id]

            # Проверяем права админа
            if user_id != game.admin_id:
                self.bot.send_message(chat_id, "❌ Только админ игры может её начать.")
                return

            # Начинаем игру
            if self.game_manager.start_game(chat_id, user_id):
                self._send_message_with_image(chat_id, "🎭 Игра началась! Изучайте ваших персонажей." 'game_start')
            else:
                self.bot.send_message(
                    chat_id,
                    f"❌ Не удалось начать игру. Нужно {GAME_SETTINGS['MIN_PLAYERS']}-{GAME_SETTINGS['MAX_PLAYERS']} игроков."
                )

        except Exception as e:
            logger.error(f"Ошибка в begin_game_command: {e}")
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при запуске игры.")

    def _check_chat_allowed(self, chat_id: int) -> bool:
        """Проверяет разрешен ли чат"""
        if ALLOWED_CHAT_ID is None:
            return True
        return chat_id == ALLOWED_CHAT_ID

    def end_game_command(self, message: Message):
        """Обработчик команды /end (завершить игру досрочно)"""
        try:
            if message.chat.type not in ['group', 'supergroup']:
                self.bot.send_message(message.chat.id, "❌ Команда доступна только в группах!")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            if chat_id not in self.game_manager.games:
                self.bot.send_message(chat_id, "❌ Нет активной игры.")
                return

            game = self.game_manager.games[chat_id]

            # Проверяем права (админ игры или бота)
            if user_id != game.admin_id and user_id not in ADMIN_IDS:
                self.bot.send_message(chat_id, "❌ Только админ игры может её завершить.")
                return

            # Останавливаем таймеры
            self.game_manager.phase_timer.stop_phase_timer(chat_id)

            # Удаляем игру
            del self.game_manager.games[chat_id]

            self.bot.send_message(chat_id, "⛔ Игра досрочно завершена администратором.")

        except Exception as e:
            logger.error(f"Ошибка в end_game_command: {e}")
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при завершении игры.")

    def leave_game_command(self, message: Message):
        """Обработчик команды /leave (покинуть игру)"""
        try:
            if message.chat.type not in ['group', 'supergroup']:
                self.bot.send_message(message.chat.id, "❌ Команда доступна только в группах!")
                return

            chat_id = message.chat.id
            user_id = message.from_user.id

            if chat_id not in self.game_manager.games:
                self.bot.send_message(chat_id, "❌ Нет активной игры.")
                return

            game = self.game_manager.games[chat_id]

            if user_id not in game.players:
                self.bot.send_message(chat_id, "❌ Вы не участвуете в игре.")
                return

            # Проверяем фазу игры - можно выйти только в лобби
            if game.phase != GamePhase.LOBBY:
                self.bot.send_message(
                    chat_id,
                    "❌ Нельзя покинуть игру после её начала. Игра уже запущена."
                )
                return

            # Получаем имя игрока для уведомления
            player_name = game.players[user_id].get_display_name()

            # Удаляем игрока
            if self.game_manager.leave_game(chat_id, user_id):
                self.bot.send_message(chat_id, f"👋 {player_name} покинул игру")

                # Если это был админ или осталось мало игроков
                if user_id == game.admin_id or len(game.players) < GAME_SETTINGS['MIN_PLAYERS']:
                    # Останавливаем игру
                    self.game_manager.phase_timer.stop_phase_timer(chat_id)
                    del self.game_manager.games[chat_id]
                    self._send_message_with_image(chat_id, "❌ Игра завершена из-за выхода ключевых игроков." 'game_end')
                else:
                    # ИСПРАВЛЕНО: обновляем только если есть сохраненный ID
                    if hasattr(game, 'lobby_message_id') and game.lobby_message_id:
                        self._send_lobby_status(chat_id, game.lobby_message_id)
            else:
                self.bot.send_message(chat_id, "❌ Ошибка при выходе из игры.")

        except Exception as e:
            logger.error(f"Ошибка в leave_game_command: {e}")
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при выходе из игры.")

    def start_command(self, message: Message):
        """Обработчик команды /start"""
        try:
            # Проверяем параметры команды
            if len(message.text.split()) > 1:
                param = message.text.split()[1]
                if param.startswith('vote_'):
                    chat_id = int(param.replace('vote_', ''))
                    # Проверяем разрешенный чат
                    if not self._check_chat_allowed(chat_id):
                        self.bot.send_message(message.chat.id, "❌ Игра недоступна.")
                        return
                    self._handle_voting_start_param(message, chat_id)
                    return
                elif param.startswith('cards_'):
                    chat_id = int(param.replace('cards_', ''))
                    # Проверяем разрешенный чат
                    if not self._check_chat_allowed(chat_id):
                        self.bot.send_message(message.chat.id, "❌ Игра недоступна.")
                        return
                    self._handle_cards_start_param(message, chat_id)
                    return

            welcome_text = "🎮 **Добро пожаловать в Bunker RP!**\n\n"
            welcome_text += "Это игра на выживание, где вам нужно решить, "
            welcome_text += "кто достоин попасть в бункер после апокалипсиса.\n\n"
            welcome_text += "Выберите действие:"

            keyboard = get_main_menu()

            if message.from_user.id in ADMIN_IDS:
                keyboard.add(InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel"))

            self._send_message_with_image(
                message.chat.id,
                welcome_text,
                image_key='lobby',
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Ошибка в start_command: {e}")
            self.bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте позже.")

    def _handle_cards_start_param(self, message: Message, chat_id: int):
        """Обработка перехода для управления карточками через параметр /start"""
        user_id = message.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.send_message(
                message.chat.id,
                "❌ Игра не найдена или уже завершена."
            )
            return

        game = self.game_manager.games[chat_id]

        # Проверяем, что игрок участвует в игре
        if user_id not in game.players:
            self.bot.send_message(
                message.chat.id,
                "❌ Вы не участвуете в этой игре."
            )
            return

        # ИСПРАВЛЕНО: проверяем очередь игрока перед отправкой меню
        is_current_turn = (hasattr(game, 'current_turn_player_id') and
                           game.current_turn_player_id == user_id)

        if not is_current_turn and hasattr(game, 'current_turn_player_id') and game.current_turn_player_id:
            # Не очередь этого игрока
            current_player = game.players.get(game.current_turn_player_id)
            current_name = current_player.get_display_name() if current_player else "другого игрока"

            self.bot.send_message(
                user_id,
                f"⏳ **Ожидание очереди**\n\nСейчас ходит: {current_name}\nДождитесь своей очереди.",
                parse_mode='Markdown'
            )
            return

        # Отправляем меню карточек только если очередь игрока
        self._send_cards_menu_to_private(user_id, chat_id)

    def _handle_card_reveal_timeout(self, chat_id: int, card_number: int):
        """Обрабатывает истечение времени на раскрытие карты"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        # Переходим к следующему игроку
        game.current_player_index += 1

        if game.current_player_index >= len(game.players_order):
            # Все игроки прошли - завершаем фазу
            self._handle_card_phase_end(chat_id, card_number)
        else:
            # Продолжаем с следующим игроком
            self._start_card_reveal_phase(chat_id, card_number)

    def _send_cards_menu_to_private(self, user_id: int, chat_id: int):
        """Отправляет меню управления карточками в ЛС"""
        if chat_id not in self.game_manager.games:
            return

        game = self.game_manager.games[chat_id]
        player = game.players.get(user_id)

        if not player:
            return

        # Передаем текущую фазу
        current_phase = game.phase.value if hasattr(game, 'phase') else None
        keyboard = get_private_character_keyboard(player, current_phase)

        if current_phase == "card_reveal_1":
            cards_text = "🎴 **Ваша очередь! Фаза раскрытия профессий**\n\n"
            cards_text += "В первой фазе можно раскрыть только профессию."
        else:
            cards_text = "🃏 **Ваша очередь! Управление карточками**\n\n"
            cards_text += "Выберите карточку для раскрытия в игре:"

        # Сохраняем информацию о чате
        if not hasattr(self, 'user_states'):
            self.user_states = {}

        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        self.user_states[user_id]['cards_chat'] = chat_id

        self.bot.send_message(
            user_id,
            cards_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_voting_start_param(self, message: Message, chat_id: int):
        """Обработка перехода для голосования через параметр /start"""
        user_id = message.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.send_message(
                message.chat.id,
                "❌ Игра не найдена или уже завершена."
            )
            return

        game = self.game_manager.games[chat_id]

        # Проверяем, что игрок участвует в игре
        if user_id not in game.players:
            self.bot.send_message(
                message.chat.id,
                "❌ Вы не участвуете в этой игре."
            )
            return

        # Проверяем фазу игры
        if game.phase.value != "voting":
            self.bot.send_message(
                message.chat.id,
                "❌ Сейчас не время голосования."
            )
            return

        # Проверяем, что игрок жив
        if not game.players[user_id].is_alive:
            self.bot.send_message(
                message.chat.id,
                "❌ Вы не можете голосовать."
            )
            return

        # Проверяем, уже проголосовал ли игрок
        if game.players[user_id].has_voted:
            self.bot.send_message(
                message.chat.id,
                "✅ Вы уже проголосовали в этом раунде."
            )
            return

        # Отправляем голосование
        self._send_private_voting(user_id, chat_id)

    def _send_private_voting(self, user_id: int, chat_id: int):
        """Отправляет голосование в личные сообщения"""
        if chat_id not in self.game_manager.games:
            return

        game = self.game_manager.games[chat_id]

        # Создаем список живых игроков (кроме самого голосующего)
        alive_players = [p for p in game.get_alive_players() if p.user_id != user_id]

        if not alive_players:
            self.bot.send_message(user_id, "❌ Нет игроков для голосования")
            return

        from keyboards import get_private_voting_keyboard  # Добавить импорт
        keyboard = get_private_voting_keyboard(alive_players, user_id)

        voting_text = f"🗳️ **ГОЛОСОВАНИЕ**\n\n"
        voting_text += f"Выберите игрока, которого хотите **ИСКЛЮЧИТЬ** из бункера:\n\n"

        for player in alive_players:
            voting_text += f"👤 {player.get_display_name()}\n"

        # Сохраняем информацию о голосовании
        if not hasattr(self, 'user_states'):
            self.user_states = {}

        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        self.user_states[user_id]['voting_chat'] = chat_id

        self.bot.send_message(
            user_id,
            voting_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def help_command(self, message: Message):
        """Обработчик команды /help"""
        try:
            help_text = """🆘 **Справка по командам:**

    /start - Главное меню
    /game - Создать игру/присоединиться к игре
    /begin - Начать созданную игру (админ)
    /end - Досрочно завершить игру (админ)
    /leave - Покинуть игру (только до начала)
    /help - Эта справка
    /admin - Панель администратора (только для админа бота)

    🎯 **Как играть:**
    1. Создайте игру командой /game в группе
    2. Наберите нужное количество игроков
    3. Начните игру командой /begin
    4. Изучите своего персонажа
    5. Раскрывайте карточки и обсуждайте
    6. Голосуйте за исключение
    7. Побеждают те, кто попадает в бункер!

    📝 **Фазы игры:**
    🎭 Изучение ролей
    🎴 Раскрытие карточек (7 раундов)
    🗳️ Голосование
    📊 Результаты"""

            self.bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Ошибка в help_command: {e}")

    def game_command(self, message: Message):
        """Обработчик команды /game"""
        try:
            # Проверяем разрешенный чат
            if not self._check_chat_allowed(message.chat.id):
                if message.chat.id < 0:  # Групповой чат
                    self.bot.send_message(message.chat.id, "❌ Бот не работает в этом чате.")
                    try:
                        self.bot.leave_chat(message.chat.id)
                    except:
                        pass
                return

            # Проверяем, что команда в группе
            if message.chat.type not in ['group', 'supergroup']:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Игра доступна только в группах!"
                )
                return

            chat_id = message.chat.id
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name

            # Проверяем существующую игру
            if chat_id in self.game_manager.games:
                # Пытаемся присоединиться
                if self.game_manager.join_game(chat_id, user_id, username, first_name):
                    self.bot.send_message(
                        chat_id,
                        f"✅ {first_name} присоединился к игре!"
                    )
                    # ИСПРАВЛЕНО: редактируем существующее сообщение лобби
                    game = self.game_manager.games[chat_id]
                    if hasattr(game, 'lobby_message_id') and game.lobby_message_id:
                        self._send_lobby_status(chat_id, game.lobby_message_id)
                else:
                    self.bot.send_message(
                        chat_id,
                        "❌ Не удалось присоединиться к игре."
                    )
            else:
                # Создаем новую игру
                if self.game_manager.create_game(chat_id, user_id):
                    self.game_manager.join_game(chat_id, user_id, username, first_name)

                    game_text = f"🎮 **Новая игра создана!**\n\n"
                    game_text += f"👑 Админ: {first_name}\n"
                    game_text += f"👥 Игроков: 1/{GAME_SETTINGS['MAX_PLAYERS']}\n\n"
                    game_text += "Ждем остальных игроков..."

                    keyboard = get_game_lobby_keyboard(is_admin=True)

                    message = self.bot.send_message(
                        chat_id,
                        game_text,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )

                    # ИСПРАВЛЕНО: сохраняем ID сообщения
                    game = self.game_manager.games[chat_id]
                    game.lobby_message_id = message.message_id
                else:
                    self.bot.send_message(
                        chat_id,
                        "❌ Ошибка создания игры."
                    )

        except Exception as e:
            logger.error(f"Ошибка в game_command: {e}")

    def admin_command(self, message: Message):
        """Обработчик команды /admin"""
        try:
            if message.from_user.id not in ADMIN_IDS:
                self.bot.send_message(message.chat.id, "❌ У вас нет прав администратора.")
                return

            admin_text = "👑 **Панель администратора**\n\nВыберите действие:"
            keyboard = get_admin_menu()

            self.bot.send_message(
                message.chat.id,
                admin_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Ошибка в admin_command: {e}")

    def stop_command(self, message: Message):
        """Обработчик команды /stop"""
        try:
            chat_id = message.chat.id
            user_id = message.from_user.id

            if chat_id not in self.game_manager.games:
                self.bot.send_message(chat_id, "❌ Нет активной игры в этом чате.")
                return

            game = self.game_manager.games[chat_id]

            # Проверяем права (админ игры или бота)
            if user_id != game.admin_id and user_id not in ADMIN_IDS:
                self.bot.send_message(chat_id, "❌ Только админ игры может её завершить.")
                return

            # Останавливаем таймеры
            self.game_manager.phase_timer.stop_phase_timer(chat_id)

            # Удаляем игру
            del self.game_manager.games[chat_id]

            self._send_message_with_image(chat_id, "⛔ Игра принудительно завершена.", 'game_end')

        except Exception as e:
            logger.error(f"Ошибка в stop_command: {e}")

    def callback_handler(self, call: CallbackQuery):
        """Основной обработчик колбэков"""
        try:
            callback_data = call.data
            user_id = call.from_user.id
            chat_id = call.message.chat.id
            message_id = call.message.message_id

            # Основное меню
            if callback_data == "create_game":
                self._handle_create_game(call)
            elif callback_data == "join_game":
                self._handle_join_game(call)
            elif callback_data == "rules":
                self._handle_rules(call)
            elif callback_data == "about":
                self._handle_about(call)
            elif callback_data == "manage_cards":
                self._handle_manage_cards(call)

            # Админ панель
            elif callback_data == "admin_panel":
                self._handle_admin_panel(call)
            elif callback_data == "admin_cards":
                self._handle_admin_cards(call)
            elif callback_data == "edit_special":
                self._handle_edit_special_cards(call)
            elif callback_data == "admin_stats":
                self._handle_admin_stats(call)
            elif callback_data == "admin_back":
                self._handle_admin_panel(call)

            # Управление карточками
            elif callback_data.startswith("edit_"):
                self._handle_edit_cards(call)
            elif callback_data.startswith("add_"):
                self._handle_add_card(call)
            elif callback_data.startswith("remove_"):
                self._handle_remove_card(call)
            elif callback_data.startswith("show_"):
                self._handle_show_cards(call)

            # Игровые действия
            elif callback_data == "start_game":
                self._handle_start_game(call)
            elif callback_data == "leave_game":
                self._handle_leave_game(call)
            elif callback_data == "show_players":
                self._handle_show_players(call)
            elif callback_data == "game_settings":
                self._handle_game_settings(call)

            # Управление персонажем
            elif callback_data.startswith("reveal_"):
                if callback_data == "reveal_special_card":
                    self._safe_answer_callback(call, "❌ Специальные карточки нельзя раскрывать", show_alert=True)
                else:
                    self._handle_reveal_card(call)
            elif callback_data == "use_special_card":
                self._handle_use_special_card(call)
            elif callback_data == "show_my_character":
                self._handle_show_character(call)
            elif callback_data == "show_game_players":
                self._handle_show_game_players(call)

            # Голосование
            elif callback_data == "start_voting":
                self._handle_start_voting(call)
            elif callback_data.startswith("vote_"):
                if callback_data == "vote_abstain":
                    self._handle_abstain(call)
                else:
                    self._handle_vote(call)

            # Подтверждения
            elif callback_data.startswith("confirm_"):
                self._handle_confirm(call)
            elif callback_data.startswith("cancel_"):
                self._handle_cancel(call)

            # Назад
            elif callback_data == "back":
                self._handle_back(call)

            # Отвечаем на колбэк безопасно
            self._safe_answer_callback(call)

        except Exception as e:
            logger.error(f"Ошибка в callback_handler: {e}")
            self._safe_answer_callback(call, "❌ Произошла ошибка")

    def _safe_answer_callback(self, call: CallbackQuery, text: str = None, show_alert: bool = False):
        """Безопасная отправка ответа на callback"""
        try:
            self.bot.answer_callback_query(call.id, text, show_alert)
        except Exception as e:
            logger.debug(f"Ошибка ответа на callback (игнорируется): {e}")

    def _safe_edit_message(self, chat_id: int, message_id: int, text: str, reply_markup=None, **kwargs):
        """Безопасное редактирование сообщения"""
        try:
            self.bot.edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=reply_markup,
                **kwargs
            )
            return True
        except Exception as e:
            if "message is not modified" not in str(e):
                logger.error(f"Ошибка редактирования сообщения: {e}")
            return False

    def text_handler(self, message: Message):
        """Обработчик текстовых сообщений"""
        try:
            user_id = message.from_user.id

            # Проверяем состояние пользователя
            if user_id in self.user_states:
                state = self.user_states[user_id]

                if state.get('action') == 'add_card':
                    self._process_add_card(message, state)
                elif state.get('action') == 'remove_card':
                    self._process_remove_card(message, state)
                else:
                    # Очищаем неизвестное состояние
                    del self.user_states[user_id]

        except Exception as e:
            logger.error(f"Ошибка в text_handler: {e}")

    def _handle_abstain_vote(self, call: CallbackQuery):
        """Обработка воздержания от голосования"""
        user_id = call.from_user.id

        if not hasattr(self, 'user_states') or user_id not in self.user_states or 'voting_chat' not in self.user_states[
            user_id]:
            self.bot.answer_callback_query(call.id, "❌ Ошибка голосования", show_alert=True)
            return

        chat_id = self.user_states[user_id]['voting_chat']

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Игра не найдена", show_alert=True)
            return

        game = self.game_manager.games[chat_id]
        player = game.players.get(user_id)

        if not player or not player.is_alive or player.has_voted:
            self.bot.answer_callback_query(call.id, "❌ Не можете голосовать", show_alert=True)
            return

        # Отмечаем как проголосовавшего без цели
        player.has_voted = True
        player.vote_target = None

        # Уведомляем пользователя
        self.bot.edit_message_text(
            "✅ **Воздержание принято!**\n\nВы воздержались от голосования.",
            user_id,
            call.message.message_id,
            parse_mode='Markdown'
        )

        # Уведомляем в группе
        try:
            alive_players = game.get_alive_players()
            voted_count = sum(1 for p in alive_players if p.has_voted)
            voter_name = player.get_display_name()

            self.bot.send_message(
                chat_id,
                f"🤐 {voter_name} воздержался ({voted_count}/{len(alive_players)})"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления в группе: {e}")

        # Очищаем состояние
        if 'voting_chat' in self.user_states[user_id]:
            del self.user_states[user_id]['voting_chat']
            if not self.user_states[user_id]:
                del self.user_states[user_id]

        self.bot.answer_callback_query(call.id)

    # Обработчики конкретных действий

    def _handle_create_game(self, call: CallbackQuery):
        """Обработка создания игры"""
        create_text = "🎮 **Создание игры**\n\nДля создания игры используйте команду /game в группе.\n\nИгра доступна только в групповых чатах."

        keyboard = get_back_keyboard()

        self._safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            create_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

        chat_id = call.message.chat.id
        user_id = call.from_user.id
        username = call.from_user.username
        first_name = call.from_user.first_name

        if chat_id in self.game_manager.games:
            self.bot.edit_message_text(
                "❌ В этом чате уже есть активная игра!",
                call.message.chat.id,
                call.message.message_id
            )
            return

        if self.game_manager.create_game(chat_id, user_id):
            self.game_manager.join_game(chat_id, user_id, username, first_name)

            # ИСПРАВЛЕНО: сохраняем ID сообщения и редактируем его
            game = self.game_manager.games[chat_id]
            game.lobby_message_id = call.message.message_id

            self._send_lobby_status(chat_id, call.message.message_id)
        else:
            self.bot.edit_message_text(
                "❌ Ошибка создания игры.",
                call.message.chat.id,
                call.message.message_id
            )

    def _handle_join_game(self, call: CallbackQuery):
        """Обработка присоединения к игре"""
        if call.message.chat.type not in ['group', 'supergroup']:
            self.bot.edit_message_text(
                "❌ Нет активной игры в этом чате!",
                call.message.chat.id,
                call.message.message_id
            )
            return

        chat_id = call.message.chat.id
        user_id = call.from_user.id
        username = call.from_user.username
        first_name = call.from_user.first_name

        if chat_id not in self.game_manager.games:
            self.bot.edit_message_text(
                "❌ Нет активной игры в этом чате!",
                call.message.chat.id,
                call.message.message_id
            )
            return

        try:
            self.bot.send_message(
                user_id,
                "🎮 Для участия в игре напишите /start боту в личных сообщениях, если еще не делали этого."
            )
        except Exception:
            self.bot.answer_callback_query(
                call.id,
                "❌ Напишите боту /start в личных сообщениях для участия в игре",
                show_alert=True
            )
            return

        if self.game_manager.join_game(chat_id, user_id, username, first_name):
            game = self.game_manager.games[chat_id]
            # ИСПРАВЛЕНО: всегда используем lobby_message_id для редактирования
            if hasattr(game, 'lobby_message_id') and game.lobby_message_id:
                self._send_lobby_status(chat_id, game.lobby_message_id)
            else:
                # Если нет сохраненного ID, редактируем текущее сообщение
                game.lobby_message_id = call.message.message_id
                self._send_lobby_status(chat_id, call.message.message_id)
        else:
            self.bot.answer_callback_query(
                call.id,
                "❌ Не удалось присоединиться к игре",
                show_alert=True
            )

    def _handle_rules(self, call: CallbackQuery):
        """Показ правил игры"""
        rules_text = """📋 **Правила игры Bunker RP:**

🎯 **Цель:** Попасть в бункер после апокалипсиса

🎭 **Ход игры:**
1. **Лобби** - набор игроков (3-8 человек)
2. **Изучение ролей** (3 мин) - изучите своего персонажа
3. **Обсуждение** (10 мин) - убеждайте других в своей полезности
4. **Голосование** (2 мин) - голосуйте против тех, кто не должен попасть в бункер
5. **Результаты** (1 мин) - узнайте, кого исключили

🎴 **Персонажи:**
У каждого есть профессия, возраст, здоровье, хобби, фобия и предмет. Раскрывайте карточки стратегически!

🏆 **Победа:**
Побеждают те, кто остается после всех голосований и помещается в бункер.

💡 **Советы:**
- Раскрывайте полезные карточки
- Скрывайте недостатки
- Убеждайте в своей необходимости
- Объединяйтесь против угроз"""

        keyboard = get_back_keyboard()

        self.bot.edit_message_text(
            rules_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_about(self, call: CallbackQuery):
        """Информация о боте"""
        about_text = """ℹ️ **О боте Bunker RP**

🤖 Версия: 1.0
👨‍💻 Разработано для увлекательной игры в выживание

⚙️ **Возможности:**
• Автоматические таймеры фаз
• Генерация персонажей и сценариев  
• Система голосования
• Поддержка групп 3-8 игроков
• Админ-панель для настройки карточек

📞 **Поддержка:**
Если нашли баг или есть предложения, свяжитесь с администратором.

🎮 Приятной игры!"""

        keyboard = get_back_keyboard()

        self.bot.edit_message_text(
            about_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_admin_panel(self, call: CallbackQuery):
        """Админ панель"""
        if call.from_user.id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        admin_text = "👑 **Панель администратора**\n\nВыберите действие:"
        keyboard = get_admin_menu()

        self.bot.edit_message_text(
            admin_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_admin_cards(self, call: CallbackQuery):
        """Управление карточками"""
        if call.from_user.id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        cards_text = "🃏 **Управление карточками**\n\nВыберите категорию для редактирования:"
        keyboard = get_admin_cards_keyboard()

        self.bot.edit_message_text(
            cards_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_admin_stats(self, call: CallbackQuery):
        """Статистика бота"""
        if call.from_user.id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        active_games = len(self.game_manager.games)
        total_players = sum(len(game.players) for game in self.game_manager.games.values())

        stats_text = f"""📊 **Статистика бота**

🎮 Активных игр: {active_games}
👥 Всего игроков онлайн: {total_players}

📝 **Карточек в базе:**"""

        for category, cards in self.game_manager.cards_data.items():
            category_names = {
                'professions': 'Профессий',
                'health': 'Здоровье',
                'hobbies': 'Хобби',
                'phobias': 'Фобий',
                'items': 'Предметов',
                'additional': 'Доп. информация',
                'scenarios': 'Сценариев'
            }

            name = category_names.get(category, category.title())
            stats_text += f"\n• {name}: {len(cards)}"

        keyboard = get_back_keyboard()

        self.bot.edit_message_text(
            stats_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_start_game(self, call: CallbackQuery):
        """Запуск игры"""
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if self.game_manager.start_game(chat_id, user_id):
            self.bot.edit_message_text(
                "🎭 Игра началась! Фаза изучения ролей...",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            self.bot.answer_callback_query(
                call.id,
                "❌ Не удалось начать игру. Проверьте количество игроков.",
                show_alert=True
            )

    def _handle_reveal_card(self, call: CallbackQuery):
        """Раскрытие карточки персонажа"""
        user_id = call.from_user.id

        if (not hasattr(self, 'user_states') or
                user_id not in self.user_states or
                'cards_chat' not in self.user_states[user_id]):
            self._safe_answer_callback(call, "❌ Ошибка: чат игры не найден", show_alert=True)
            return

        chat_id = self.user_states[user_id]['cards_chat']
        card_type = call.data.replace("reveal_", "")

        if chat_id not in self.game_manager.games:
            self._safe_answer_callback(call, "❌ Игра не найдена", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        # Проверка очереди
        if hasattr(game,
                   'current_turn_player_id') and game.current_turn_player_id and game.current_turn_player_id != user_id:
            current_player = game.players.get(game.current_turn_player_id)
            current_name = current_player.get_display_name() if current_player else "другого игрока"
            self._safe_answer_callback(
                call,
                f"❌ Сейчас очередь {current_name}. Дождитесь своего хода!",
                show_alert=True
            )
            return

        # Ограничение только для первой фазы
        if game.phase.value == "card_reveal_1" and card_type != "profession":
            self._safe_answer_callback(
                call,
                "❌ В первой фазе можно раскрыть только профессию",
                show_alert=True
            )
            return

        if self.game_manager.reveal_card(chat_id, user_id, card_type):
            # Удаляем уведомление об очереди из ЛС
            if hasattr(game, 'current_turn_message_id') and game.current_turn_message_id:
                try:
                    self.bot.delete_message(user_id, game.current_turn_message_id)
                    game.current_turn_message_id = None
                except Exception as e:
                    logger.debug(f"Не удалось удалить сообщение очереди: {e}")

            # Получаем информацию о карточке и отправляем в игровой чат
            if chat_id in self.game_manager.games:
                game = self.game_manager.games[chat_id]
                if user_id in game.players:
                    player = game.players[user_id]
                    character = player.character

                    card_names = {
                        'profession': '💼 Профессия',
                        'biology': '👤 Биология',
                        'health': '🫁 Здоровье',
                        'phobia': '🗣 Фобия',
                        'hobby': '🎮 Хобби',
                        'fact': '🔎 Факт',
                        'baggage': '📦 Багаж'
                    }

                    card_values = {
                        'profession': character.profession,
                        'biology': f"{character.gender} {character.age} лет",
                        'health': f"{character.body_type}, {character.disease}",
                        'phobia': character.phobia,
                        'hobby': character.hobby,
                        'fact': character.fact,
                        'baggage': character.baggage
                    }

                    card_name = card_names.get(card_type, card_type)
                    card_value = card_values.get(card_type, "Неизвестно")

                    reveal_text = f"🎴 {player.get_display_name()} раскрыл карточку:\n"
                    reveal_text += f"**{card_name}**: {card_value}"

                    # Отправляем в чат с задержкой
                    self.game_manager._send_message_with_delay_and_image(
                        chat_id, reveal_text, 'card_reveal', parse_mode='Markdown'
                    )

            # ИЗМЕНЕНО: обновляем существующую клавиатуру
            current_phase = game.phase.value
            keyboard = get_private_character_keyboard(game.players[user_id], current_phase)

            success = self._safe_edit_message(
                user_id,
                call.message.message_id,
                "🃏 **Управление карточками**\n\nВыберите карточку для раскрытия:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

            if not success:
                # Если редактирование не удалось, отправляем новое сообщение
                try:
                    self.bot.send_message(
                        user_id,
                        "🃏 **Управление карточками**\n\nВыберите карточку для раскрытия:",
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки нового меню: {e}")

            self._safe_answer_callback(call, "✅ Карточка раскрыта!")
        else:
            self._safe_answer_callback(call, "❌ Не удалось раскрыть карточку")

    def _handle_use_special_card(self, call: CallbackQuery):
        """Обработка использования специальной карточки"""
        user_id = call.from_user.id

        # Получаем chat_id из состояния пользователя
        if (not hasattr(self, 'user_states') or
                user_id not in self.user_states or
                'cards_chat' not in self.user_states[user_id]):
            self.bot.answer_callback_query(call.id, "❌ Ошибка: чат игры не найден", show_alert=True)
            return

        chat_id = self.user_states[user_id]['cards_chat']

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Игра не найдена", show_alert=True)
            return

        game = self.game_manager.games[chat_id]
        if user_id not in game.players:
            self.bot.answer_callback_query(call.id, "❌ Вы не участвуете в игре", show_alert=True)
            return

        player = game.players[user_id]

        # Используем специальную карточку
        result = self.game_manager.use_special_card(chat_id, user_id)

        if result["success"]:
            # Уведомляем в ЛС
            self.bot.edit_message_text(
                f"✅ {result['message']}",
                user_id,
                call.message.message_id,
                parse_mode='Markdown'
            )

            # Отправляем публичное сообщение если есть
            if "public_message" in result:
                try:
                    self.bot.send_message(chat_id, result["public_message"], parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Ошибка отправки публичного сообщения: {e}")

            self.bot.answer_callback_query(call.id, "✅ Специальная карточка использована!")
        else:
            self.bot.answer_callback_query(call.id, f"❌ {result['message']}", show_alert=True)

    def _handle_vote(self, call: CallbackQuery):
        """Обработка голосования"""
        user_id = call.from_user.id

        # Получаем chat_id из состояния пользователя
        if user_id not in self.user_states or 'voting_chat' not in self.user_states[user_id]:
            self.bot.answer_callback_query(call.id, "❌ Ошибка голосования", show_alert=True)
            return

        chat_id = self.user_states[user_id]['voting_chat']
        target_id = int(call.data.replace("vote_", ""))

        if self.game_manager.vote_player(chat_id, user_id, target_id):
            # Получаем имя цели
            target_name = "игрока"
            if chat_id in self.game_manager.games:
                game = self.game_manager.games[chat_id]
                if target_id in game.players:
                    target_name = game.players[target_id].get_display_name()

            # Уведомляем в ЛС
            self.bot.edit_message_text(
                f"✅ **Голос принят!**\n\nВы проголосовали против: {target_name}\n\nВернитесь в группу и дождитесь окончания голосования.",
                user_id,
                call.message.message_id,
                parse_mode='Markdown'
            )

            # Уведомляем в группе
            try:
                game = self.game_manager.games[chat_id]
                alive_players = game.get_alive_players()
                voted_count = sum(1 for p in alive_players if p.has_voted)

                voter_name = game.players[user_id].get_display_name()

                self.bot.send_message(
                    chat_id,
                    f"✅ {voter_name} проголосовал ({voted_count}/{len(alive_players)})"
                )
            except:
                pass

            # Очищаем состояние
            if 'voting_chat' in self.user_states[user_id]:
                del self.user_states[user_id]['voting_chat']

            self.bot.answer_callback_query(call.id)
        else:
            self.bot.answer_callback_query(
                call.id,
                "❌ Не удалось проголосовать",
                show_alert=True
            )

    def _update_voting_message(self, message):
        """Обновляет сообщение голосования"""
        try:
            chat_id = message.chat.id

            if chat_id not in self.game_manager.games:
                return

            game = self.game_manager.games[chat_id]

            if game.phase.value != "voting":
                return

            alive_players = game.get_alive_players()
            voted_count = sum(1 for p in alive_players if p.has_voted)

            voting_text = "🗳️ **Голосование в процессе...**\n\n"
            voting_text += f"Проголосовало: {voted_count}/{len(alive_players)}\n\n"
            voting_text += "Используйте кнопки для голосования против игроков."

            self.bot.edit_message_text(
                voting_text,
                chat_id,
                message.message_id,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Ошибка обновления сообщения голосования: {e}")

    def _handle_back(self, call: CallbackQuery):
        """Обработка кнопки назад"""
        welcome_text = "🎮 **Добро пожаловать в Bunker RP!**\n\n"
        welcome_text += "Это игра на выживание, где вам нужно решить, "
        welcome_text += "кто достоин попасть в бункер после апокалипсиса.\n\n"
        welcome_text += "Выберите действие:"

        keyboard = get_main_menu()

        if call.from_user.id in ADMIN_IDS:
            keyboard.add(InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel"))

        self.bot.edit_message_text(
            welcome_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_leave_game(self, call: CallbackQuery):
        """Обработка выхода из игры"""
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        if user_id not in game.players:
            self.bot.answer_callback_query(call.id, "❌ Вы не участвуете в игре", show_alert=True)
            return

        # Удаляем игрока
        if self.game_manager.leave_game(chat_id, user_id):
            player_name = game.players[user_id].get_display_name() if user_id in game.players else "Игрок"

            self.bot.answer_callback_query(call.id, "✅ Вы покинули игру")

            # Если это был админ или осталось мало игроков
            if user_id == game.admin_id or len(game.players) < GAME_SETTINGS['MIN_PLAYERS']:
                # Останавливаем игру
                self.game_manager.phase_timer.stop_phase_timer(chat_id)
                del self.game_manager.games[chat_id]
                self._send_message_with_image(chat_id, "❌ Игра завершена из-за выхода игроков." 'game_end')
            else:
                self.bot.send_message(chat_id, f"👋 {player_name} покинул игру")
                self._send_lobby_status(chat_id)
        else:
            self.bot.answer_callback_query(call.id, "❌ Ошибка при выходе из игры")

    def _handle_show_players(self, call: CallbackQuery):
        """Показ списка игроков"""
        chat_id = call.message.chat.id

        players_info = self.game_manager.get_players_list(chat_id)

        if players_info:
            self.bot.answer_callback_query(call.id, players_info, show_alert=True)
        else:
            self.bot.answer_callback_query(call.id, "❌ Нет информации об игроках", show_alert=True)

    def _handle_game_settings(self, call: CallbackQuery):
        """Настройки игры"""
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        if user_id != game.admin_id:  # Изменено с game.ADMIN_IDS на game.admin_id
            self.bot.answer_callback_query(call.id, "❌ Только админ может изменять настройки", show_alert=True)
            return

        settings_text = f"""⚙️ **Настройки игры:**
            
                ⏱️ Время изучения ролей: {GAME_SETTINGS['ROLE_STUDY_TIME']}с
                💬 Время обсуждения: {GAME_SETTINGS['DISCUSSION_TIME']}с  
                🗳️ Время голосования: {GAME_SETTINGS['VOTING_TIME']}с
                📊 Время результатов: {GAME_SETTINGS['RESULTS_TIME']}с
            
                👥 Мин. игроков: {GAME_SETTINGS['MIN_PLAYERS']}
                👥 Макс. игроков: {GAME_SETTINGS['MAX_PLAYERS']}"""

        self.bot.answer_callback_query(call.id, settings_text, show_alert=True)

    def _handle_show_character(self, call: CallbackQuery):
        """Показ своего персонажа"""
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        if user_id not in game.players:
            self.bot.answer_callback_query(call.id, "❌ Вы не участвуете в игре", show_alert=True)
            return

        player = game.players[user_id]
        character_info = player.get_character_info(show_all=True)

        if character_info:
            self.bot.answer_callback_query(call.id, f"👤 Ваш персонаж:\n\n{character_info}", show_alert=True)
        else:
            self.bot.answer_callback_query(call.id, "❌ Персонаж еще не создан", show_alert=True)

    def _handle_manage_cards(self, call: CallbackQuery):
        """Управление карточками персонажа - переход в ЛС"""
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        if user_id not in game.players:
            self.bot.answer_callback_query(call.id, "❌ Вы не участвуете в игре", show_alert=True)
            return

        # Отправляем в ЛС
        try:
            self._send_cards_menu_to_private(user_id, chat_id)
            self.bot.answer_callback_query(call.id, "✅ Проверьте личные сообщения для управления карточками")
        except Exception as e:
            logger.error(f"Ошибка отправки меню карточек в ЛС: {e}")
            self.bot.answer_callback_query(call.id, "❌ Не могу отправить в ЛС. Напишите боту /start")

    def _handle_show_game_players(self, call: CallbackQuery):
        """Показ игроков в игре с их раскрытыми карточками"""
        chat_id = call.message.chat.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        players_text = "👥 **Игроки и их карточки:**\n\n"

        for player in game.players.values():
            status = "💚" if player.is_alive else "💀"
            admin_mark = "👑" if player.is_admin else "👤"

            players_text += f"{admin_mark} {status} **{player.get_display_name()}**\n"
            players_text += player.get_character_info(show_all=False) + "\n\n"

        self.bot.answer_callback_query(call.id, players_text, show_alert=True)

    def _handle_start_voting(self, call: CallbackQuery):
        """Начало голосования - отправка в ЛС"""
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Игра не найдена", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        # Проверяем фазу игры
        if game.phase.value != "voting":
            self.bot.answer_callback_query(call.id, "❌ Сейчас не время голосования", show_alert=True)
            return

        # Проверяем, что игрок жив
        if user_id not in game.players or not game.players[user_id].is_alive:
            self.bot.answer_callback_query(call.id, "❌ Вы не можете голосовать", show_alert=True)
            return

        # Проверяем, уже проголосовал ли игрок
        if game.players[user_id].has_voted:
            self.bot.answer_callback_query(call.id, "❌ Вы уже проголосовали", show_alert=True)
            return

        # Отправляем голосование в ЛС
        try:
            self._send_voting_to_private(user_id, chat_id)
            self.bot.answer_callback_query(call.id, "✅ Проверьте личные сообщения для голосования")
        except Exception as e:
            # Если не удается отправить в ЛС, голосуем в группе
            logger.error(f"Ошибка отправки голосования в ЛС: {e}")
            self.bot.answer_callback_query(call.id, "❌ Не могу отправить в ЛС. Напишите боту /start")

    def _send_voting_to_private(self, user_id: int, chat_id: int):
        """Отправляет голосование в ЛС"""
        if chat_id not in self.game_manager.games:
            return

        game = self.game_manager.games[chat_id]

        # Создаем клавиатуру с живыми игроками (кроме самого голосующего)
        alive_players = [p for p in game.get_alive_players() if p.user_id != user_id]

        if not alive_players:
            self.bot.send_message(user_id, "❌ Нет игроков для голосования")
            return

        keyboard = get_voting_keyboard(alive_players, user_id)

        voting_text = f"🗳️ **ГОЛОСОВАНИЕ** (Чат: {chat_id})\n\n"
        voting_text += f"Выберите игрока, которого хотите **ИСКЛЮЧИТЬ** из бункера:\n\n"

        for player in alive_players:
            voting_text += f"👤 {player.get_display_name()}\n"

        # Инициализируем user_states если его нет
        if not hasattr(self, 'user_states'):
            self.user_states = {}

        # Сохраняем информацию о голосовании
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        self.user_states[user_id]['voting_chat'] = chat_id

        self.bot.send_message(
            user_id,
            voting_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_abstain(self, call: CallbackQuery):
        """Обработка воздержания от голосования"""
        user_id = call.from_user.id

        # Инициализируем user_states если его нет
        if not hasattr(self, 'user_states'):
            self.user_states = {}

        # Получаем chat_id из состояния пользователя
        if user_id not in self.user_states or 'voting_chat' not in self.user_states[user_id]:
            self.bot.answer_callback_query(call.id, "❌ Ошибка голосования", show_alert=True)
            return

        chat_id = self.user_states[user_id]['voting_chat']

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        if user_id not in game.players:
            self.bot.answer_callback_query(call.id, "❌ Вы не участвуете в игре", show_alert=True)
            return

        player = game.players[user_id]

        if not player.is_alive:
            self.bot.answer_callback_query(call.id, "❌ Вы не можете голосовать", show_alert=True)
            return

        if player.has_voted:
            self.bot.answer_callback_query(call.id, "❌ Вы уже проголосовали", show_alert=True)
            return

        # Отмечаем как проголосовавшего, но без цели
        player.has_voted = True
        player.vote_target = None

        # Уведомляем в ЛС
        self.bot.edit_message_text(
            f"✅ **Воздержание принято!**\n\nВы воздержались от голосования.\n\nВернитесь в группу и дождитесь окончания голосования.",
            user_id,
            call.message.message_id,
            parse_mode='Markdown'
        )

        # Уведомляем в группе
        try:
            alive_players = game.get_alive_players()
            voted_count = sum(1 for p in alive_players if p.has_voted)
            voter_name = player.get_display_name()

            self.bot.send_message(
                chat_id,
                f"🤐 {voter_name} воздержался ({voted_count}/{len(alive_players)})"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления в группе: {e}")

        # Очищаем состояние
        if user_id in self.user_states and 'voting_chat' in self.user_states[user_id]:
            del self.user_states[user_id]['voting_chat']
            # Удаляем пустой словарь
            if not self.user_states[user_id]:
                del self.user_states[user_id]

        self.bot.answer_callback_query(call.id)

    def _handle_confirm(self, call: CallbackQuery):
        """Обработка подтверждения действия"""
        action = call.data.replace("confirm_", "")

        if action == "leave_game":
            self._handle_leave_game(call)
        elif action == "stop_game":
            self._handle_stop_game_confirm(call)
        else:
            self.bot.answer_callback_query(call.id, "❌ Неизвестное действие")

    def _handle_cancel(self, call: CallbackQuery):
        """Обработка отмены действия"""
        self.bot.answer_callback_query(call.id, "❌ Действие отменено")

        # Возвращаемся к предыдущему меню
        chat_id = call.message.chat.id

        if chat_id in self.game_manager.games:
            game = self.game_manager.games[chat_id]
            keyboard = get_game_phase_keyboard(game.phase.value)

            try:
                self.bot.edit_message_text(
                    "🎮 Игра в процессе...",
                    chat_id,
                    call.message.message_id,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                # Если не удается редактировать, отправляем новое
                self.bot.send_message(
                    chat_id,
                    "🎮 Игра в процессе...",
                    reply_markup=keyboard
                )
        else:
            self._handle_back(call)

    def _handle_edit_cards(self, call: CallbackQuery):
        """Редактирование категории карточек"""
        if call.from_user.id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        category = call.data.replace("edit_", "")

        category_names = {
            'professions': 'Профессии',
            'biology': 'Биология',
            'health_body': 'Телосложение',
            'health_disease': 'Заболевания',
            'phobias': 'Фобии',
            'hobbies': 'Хобби',
            'facts': 'Факты',
            'baggage': 'Багаж',
            'special_cards': 'Специальные карточки',
            'scenarios': 'Сценарии'
        }

        category_name = category_names.get(category, category)
        cards_count = len(self.game_manager.cards_data.get(category, []))

        edit_text = f"🃏 **Редактирование: {category_name}**\n\n"
        edit_text += f"Всего карточек: {cards_count}\n\n"

        if category in ['biology', 'health_body', 'health_disease']:
            edit_text += "⚠️ Карточки с весами (формат: текст, вес)\n\n"

        edit_text += "Выберите действие:"

        keyboard = get_card_edit_keyboard(category)

        try:
            self.bot.edit_message_text(
                edit_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка редактирования меню")

    def _handle_add_card(self, call: CallbackQuery):
        """Начало добавления карточки"""
        if call.from_user.id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        category = call.data.replace("add_", "")

        # Инициализируем user_states если его нет
        if not hasattr(self, 'user_states'):
            self.user_states = {}

        # Сохраняем состояние пользователя
        self.user_states[call.from_user.id] = {
            'action': 'add_card',
            'category': category,
            'message_id': call.message.message_id,
            'chat_id': call.message.chat.id
        }

        category_names = {
            'professions': 'профессию',
            'health': 'состояние здоровья',
            'hobbies': 'хобби',
            'phobias': 'фобию',
            'items': 'предмет',
            'additional': 'дополнительную информацию',
            'scenarios': 'сценарий'
        }

        category_name = category_names.get(category, category)

        try:
            self.bot.edit_message_text(
                f"✏️ **Добавление карточки**\n\nНапишите {category_name}, которую хотите добавить:",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id, f"Напишите {category_name} в чат")
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка редактирования меню")

    def _handle_edit_special_cards(self, call: CallbackQuery):  # new
        """Редактирование специальных карточек"""
        if call.from_user.id != ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        special_cards = get_special_cards()

        edit_text = f"🃏 **Специальные карточки** ({len(special_cards)} шт.)\n\n"
        edit_text += "⚠️ Будьте осторожны! Здесь выполняется код.\n\n"
        edit_text += "Выберите действие:"

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("➕ Добавить", callback_data="add_special"),
            InlineKeyboardButton("❌ Удалить", callback_data="remove_special")
        )
        keyboard.add(InlineKeyboardButton("📋 Показать все", callback_data="show_special"))
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_cards"))

        self.bot.edit_message_text(
            edit_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    def _handle_add_special_card(self, call: CallbackQuery):  # new
        """Начало добавления специальной карточки"""
        # Сохраняем состояние для многоэтапного ввода
        self.user_states[call.from_user.id] = {
            'action': 'add_special_card',
            'stage': 'name',  # name -> description -> code
            'chat_id': call.message.chat.id,
            'message_id': call.message.message_id
        }

        self.bot.edit_message_text(
            "✏️ **Добавление специальной карточки**\n\nВведите название карточки:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

    def _handle_remove_card(self, call: CallbackQuery):
        """Начало удаления карточки"""
        if call.from_user.id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        category = call.data.replace("remove_", "")
        cards = self.game_manager.cards_data.get(category, [])

        if not cards:
            self.bot.answer_callback_query(call.id, "❌ Нет карточек для удаления", show_alert=True)
            return

        # Инициализируем user_states если его нет
        if not hasattr(self, 'user_states'):
            self.user_states = {}

        # Сохраняем состояние пользователя
        self.user_states[call.from_user.id] = {
            'action': 'remove_card',
            'category': category,
            'message_id': call.message.message_id,
            'chat_id': call.message.chat.id
        }

        cards_text = f"❌ **Удаление карточки**\n\nТекущие карточки:\n\n"
        for i, card in enumerate(cards[:20], 1):  # Показываем первые 20
            cards_text += f"{i}. {card}\n"

        if len(cards) > 20:
            cards_text += f"\n... и еще {len(cards) - 20} карточек"

        cards_text += f"\n\nНапишите точный текст карточки для удаления:"

        try:
            self.bot.edit_message_text(
                cards_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            self.bot.answer_callback_query(call.id, "Напишите текст карточки для удаления")
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка редактирования меню")

    def _handle_show_cards(self, call: CallbackQuery):
        """Показ всех карточек категории"""
        if call.from_user.id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав доступа", show_alert=True)
            return

        category = call.data.replace("show_", "")
        cards = self.game_manager.cards_data.get(category, [])

        category_names = {
            'professions': 'Профессии',
            'health': 'Здоровье',
            'hobbies': 'Хобби',
            'phobias': 'Фобии',
            'items': 'Предметы',
            'additional': 'Доп. информация',
            'scenarios': 'Сценарии'
        }

        category_name = category_names.get(category, category)

        if not cards:
            self.bot.answer_callback_query(call.id, f"❌ Нет карточек в категории {category_name}", show_alert=True)
            return

        cards_text = f"🃏 **{category_name}** ({len(cards)} шт.)\n\n"

        # Показываем первые 30 карточек
        for i, card in enumerate(cards[:30], 1):
            cards_text += f"{i}. {card}\n"

        if len(cards) > 30:
            cards_text += f"\n... и еще {len(cards) - 30} карточек"

        # Ограничиваем длину сообщения для callback answer
        if len(cards_text) > 200:
            cards_text = cards_text[:200] + "..."

        self.bot.answer_callback_query(call.id, cards_text, show_alert=True)

    def _process_add_card(self, message: Message, state: dict):
        """Обработка добавления карточки"""
        try:
            category = state['category']
            card_text = message.text.strip()

            if len(card_text) < 2:
                self.bot.send_message(message.chat.id, "❌ Слишком короткий текст карточки")
                return

            if len(card_text) > 100:
                self.bot.send_message(message.chat.id, "❌ Слишком длинный текст карточки (максимум 100 символов)")
                return

            # Добавляем карточку
            if self.game_manager.add_card(category, card_text):
                self.bot.send_message(message.chat.id, f"✅ Карточка '{card_text}' добавлена!")

                # Возвращаемся к редактированию категории
                self._return_to_card_edit_menu(state, category)
            else:
                self.bot.send_message(message.chat.id, "❌ Карточка уже существует или произошла ошибка")

            # Очищаем состояние
            if message.from_user.id in self.user_states:
                del self.user_states[message.from_user.id]

        except Exception as e:
            logger.error(f"Ошибка добавления карточки: {e}")
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при добавлении карточки")

    def _process_remove_card(self, message: Message, state: dict):
        """Обработка удаления карточки"""
        try:
            category = state['category']
            card_text = message.text.strip()

            # Удаляем карточку
            if self.game_manager.remove_card(category, card_text):
                self.bot.send_message(message.chat.id, f"✅ Карточка '{card_text}' удалена!")
            else:
                self.bot.send_message(message.chat.id, f"❌ Карточка '{card_text}' не найдена")

            # Возвращаемся к редактированию категории
            self._return_to_card_edit_menu(state, category)

            # Очищаем состояние
            if message.from_user.id in self.user_states:
                del self.user_states[message.from_user.id]

        except Exception as e:
            logger.error(f"Ошибка удаления карточки: {e}")
            self.bot.send_message(message.chat.id, "❌ Произошла ошибка при удалении карточки")

    def _return_to_card_edit_menu(self, state: dict, category: str):
        """Возвращает к меню редактирования карточек"""
        try:
            category_names = {
                'professions': 'Профессии',
                'health': 'Здоровье',
                'hobbies': 'Хобби',
                'phobias': 'Фобии',
                'items': 'Предметы',
                'additional': 'Доп. информация',
                'scenarios': 'Сценарии'
            }

            category_name = category_names.get(category, category)
            cards_count = len(self.game_manager.cards_data.get(category, []))

            edit_text = f"🃏 **Редактирование: {category_name}**\n\n"
            edit_text += f"Всего карточек: {cards_count}\n\n"
            edit_text += "Выберите действие:"

            keyboard = get_card_edit_keyboard(category)

            self.bot.edit_message_text(
                edit_text,
                state['chat_id'],
                state['message_id'],
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка возврата к меню редактирования: {e}")

    def _handle_stop_game_confirm(self, call: CallbackQuery):
        """Подтверждение остановки игры"""
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        # Проверяем права (админ игры или бота)
        if user_id != game.admin_id and user_id not in ADMIN_IDS:
            self.bot.answer_callback_query(call.id, "❌ Нет прав для остановки игры", show_alert=True)
            return

        # Останавливаем таймеры
        if hasattr(self.game_manager, 'phase_timer'):
            self.game_manager.phase_timer.stop_phase_timer(chat_id)

        # Удаляем игру
        del self.game_manager.games[chat_id]

        try:
            self.bot.edit_message_text(
                "⛔ Игра принудительно завершена администратором.",
                chat_id,
                call.message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            self._send_message_with_image(chat_id, "⛔ Игра принудительно завершена администратором." 'game_end')

        self.bot.answer_callback_query(call.id, "✅ Игра остановлена")

    def _handle_show_vote_results(self, call: CallbackQuery):
        """Показ результатов голосования"""
        chat_id = call.message.chat.id

        if chat_id not in self.game_manager.games:
            self.bot.answer_callback_query(call.id, "❌ Нет активной игры", show_alert=True)
            return

        game = self.game_manager.games[chat_id]

        if game.phase.value != "voting" and game.phase.value != "results":
            self.bot.answer_callback_query(call.id, "❌ Результаты пока недоступны", show_alert=True)
            return

        alive_players = game.get_alive_players()
        voted_count = sum(1 for p in alive_players if p.has_voted)

        results_text = f"📊 **Текущие результаты голосования:**\n\n"
        results_text += f"Проголосовало: {voted_count}/{len(alive_players)}\n\n"

        # Показываем кто за кого голосовал (если голосование завершено)
        if game.phase.value == "results":
            vote_counts = {}
            for player in alive_players:
                if player.vote_target and player.vote_target in game.players:
                    target = game.players[player.vote_target]
                    if target.user_id not in vote_counts:
                        vote_counts[target.user_id] = 0
                    vote_counts[target.user_id] += 1

            results_text += "**Голоса против:**\n"
            for user_id, votes in sorted(vote_counts.items(), key=lambda x: x[1], reverse=True):
                player = game.players[user_id]
                results_text += f"• {player.get_display_name()}: {votes} голос(ов)\n"
        else:
            results_text += "Голосование еще не завершено."

        # Ограничиваем длину для callback answer
        if len(results_text) > 200:
            results_text = results_text[:200] + "..."

        self.bot.answer_callback_query(call.id, results_text, show_alert=True)

    def _send_lobby_status(self, chat_id: int, edit_message_id: int = None):
        """Отправляет или редактирует статус лобби"""
        try:
            if chat_id not in self.game_manager.games:
                return

            game = self.game_manager.games[chat_id]

            lobby_text = "🎮 **Лобби игры**\n\n"
            lobby_text += f"👑 Админ: {game.players[game.admin_id].get_display_name()}\n"
            lobby_text += f"👥 Игроков: {len(game.players)}/{GAME_SETTINGS['MAX_PLAYERS']}\n\n"

            lobby_text += "**Игроки:**\n"
            for i, player in enumerate(game.players.values(), 1):
                status = "👑" if player.is_admin else "👤"
                lobby_text += f"{i}. {status} {player.get_display_name()}\n"

            if game.can_start():
                lobby_text += f"\n✅ Можно начинать игру!"
            else:
                min_players = GAME_SETTINGS['MIN_PLAYERS']
                lobby_text += f"\n⏳ Нужно минимум {min_players} игроков"

            is_admin = game.admin_id in game.players  # Исправлено
            keyboard = get_game_lobby_keyboard(is_admin=is_admin)

            # Если указан message_id, редактируем сообщение, иначе отправляем новое
            if edit_message_id:
                try:
                    self.bot.edit_message_text(
                        lobby_text,
                        chat_id,
                        edit_message_id,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                    return edit_message_id
                except Exception as e:
                    logger.error(f"Ошибка редактирования сообщения лобби: {e}")
                    # Если не удалось отредактировать, отправляем новое

            # Отправляем новое сообщение
            message = self.bot.send_message(
                chat_id,
                lobby_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

            # Сохраняем ID сообщения в игре
            game.lobby_message_id = message.message_id
            return message.message_id

        except Exception as e:
            logger.error(f"Ошибка отправки статуса лобби: {e}")

    # В основном обработчике callback'ов добавьте:
    # elif callback_data == "show_vote_results":
    #     self._handle_show_vote_results(call)
