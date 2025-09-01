# keyboards.py
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🎮 Создать игру", callback_data="create_game")
    )
    keyboard.add(
        InlineKeyboardButton("📋 Правила", callback_data="rules"),
        InlineKeyboardButton("ℹ️ О боте", callback_data="about")
    )
    return keyboard

def get_admin_menu() -> InlineKeyboardMarkup:
    """Меню администратора"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🃏 Управление карточками", callback_data="admin_cards"),
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    )
    return keyboard


def get_game_lobby_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура лобби игры"""
    keyboard = InlineKeyboardMarkup(row_width=2)

    # ДОБАВЛЕНО: кнопка присоединения для всех
    keyboard.add(InlineKeyboardButton("🚪 Присоединиться", callback_data="join_game"))

    if is_admin:
        keyboard.add(
            InlineKeyboardButton("▶️ Начать игру", callback_data="start_game"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="game_settings")
        )

    keyboard.add(
        InlineKeyboardButton("👥 Игроки", callback_data="show_players"),
        InlineKeyboardButton("🚪 Покинуть", callback_data="leave_game")
    )
    return keyboard


def get_character_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для управления персонажем"""
    keyboard = InlineKeyboardMarkup(row_width=2)

    cards = [
        ("💼 Профессия", "reveal_profession"),
        ("👤 Биология", "reveal_biology"),
        ("🫁 Здоровье", "reveal_health"),
        ("🗣 Фобия", "reveal_phobia"),
        ("🎮 Хобби", "reveal_hobby"),
        ("🔎 Факт", "reveal_fact"),
        ("📦 Багаж", "reveal_baggage")
    ]

    for text, callback in cards:
        keyboard.add(InlineKeyboardButton(text, callback_data=callback))

    keyboard.add(InlineKeyboardButton("🃏 Спец. карточка", callback_data="reveal_special_card"))
    keyboard.add(InlineKeyboardButton("⚡ Использовать спец. карточку", callback_data="use_special_card"))
    keyboard.add(InlineKeyboardButton("📋 Мой персонаж", callback_data="show_my_character"))
    return keyboard

    if player.character and player.character.special_card_id and not player.special_card_used: #new
        keyboard.add(InlineKeyboardButton("⚡ Использовать спец. карточку", callback_data="use_special_card")) #new


def get_card_reveal_phase_keyboard(phase: str) -> InlineKeyboardMarkup:
    """Клавиатура для фаз раскрытия карточек"""
    keyboard = InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        InlineKeyboardButton("🃏 Мои карточки", callback_data="manage_cards"),
        InlineKeyboardButton("👥 Игроки", callback_data="show_game_players")
    )
    keyboard.add(InlineKeyboardButton("📋 Мой персонаж", callback_data="show_my_character"))

    return keyboard

def get_voting_keyboard(players: List, current_user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для голосования"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем кнопки для голосования за каждого живого игрока (кроме текущего)
    for player in players:
        if hasattr(player, 'is_alive') and player.is_alive and hasattr(player, 'user_id') and player.user_id != current_user_id:
            text = f"🗳️ {player.get_display_name()}"
            keyboard.add(InlineKeyboardButton(text, callback_data=f"vote_{player.user_id}"))
    
    # Добавляем кнопку воздержания
    keyboard.add(InlineKeyboardButton("🤐 Воздержаться", callback_data="abstain"))
    return keyboard


def __init__(self, chat_id: int, admin_id: int):
    # ... существующие поля ...
    self.first_voting_completed = False  # Новое поле


def get_cards_menu_inline_keyboard(chat_id: int, game_manager=None) -> InlineKeyboardMarkup:
    """Клавиатура для перехода в бота для управления карточками"""
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Проверяем завершено ли первое голосование
    if game_manager and chat_id in game_manager.games:
        game = game_manager.games[chat_id]
        if getattr(game, 'first_voting_completed', False):
            # После первого голосования - только переход в бота
            bot_username = "bunker_nnkf_bot"  # Замените на username вашего бота
            url = f"https://t.me/{bot_username}"
            keyboard.add(InlineKeyboardButton("🃏 Перейти в бота", url=url))
        else:
            # До первого голосования - переход с параметрами
            bot_username = "bunker_nnkf_bot"
            url = f"https://t.me/{bot_username}?start=cards_{chat_id}"
            keyboard.add(InlineKeyboardButton("🃏 Управлять карточками", url=url))
    else:
        # Fallback
        bot_username = "bunker_nnkf_bot"
        url = f"https://t.me/{bot_username}?start=cards_{chat_id}"
        keyboard.add(InlineKeyboardButton("🃏 Управлять карточками", url=url))

    return keyboard

def get_admin_cards_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления карточками"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    categories = [
        ("💼 Профессии", "edit_professions"),
        ("👤 Биология", "edit_biology"),
        ("🫁 Тело", "edit_health_body"),
        ("🦠 Заболевания", "edit_health_disease"),
        ("🗣 Фобии", "edit_phobias"),
        ("🎮 Хобби", "edit_hobbies"),
        ("🔎 Факты", "edit_facts"),
        ("📦 Багаж", "edit_baggage"),
        ("🃏 Спец. карточки", "edit_special_cards"),
        ("🎲 Сценарии", "edit_scenarios")
    ]
    
    for text, callback in categories:
        keyboard.add(InlineKeyboardButton(text, callback_data=callback))
    
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_back"))
    return keyboard

def get_card_edit_keyboard(category: str) -> InlineKeyboardMarkup:
    """Клавиатура редактирования категории карточек"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton("➕ Добавить", callback_data=f"add_{category}"),
        InlineKeyboardButton("❌ Удалить", callback_data=f"remove_{category}")
    )
    keyboard.add(
        InlineKeyboardButton("📋 Показать все", callback_data=f"show_{category}"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_cards")
    )
    
    return keyboard


def get_game_phase_keyboard(phase: str) -> InlineKeyboardMarkup:
    """Клавиатура для текущей фазы игры"""
    keyboard = InlineKeyboardMarkup(row_width=1)

    if phase in ["role_study", "card_reveal_1", "card_reveal_2", "card_reveal_3",
                 "card_reveal_4", "card_reveal_5", "card_reveal_6", "card_reveal_7"]:
        keyboard.add(InlineKeyboardButton("🃏 Управлять карточками в ЛС", callback_data="manage_cards"))

    elif phase == "voting":
        keyboard.add(InlineKeyboardButton("🗳️ Голосовать в ЛС", callback_data="start_voting"))

    return keyboard

def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да", callback_data=f"confirm_{action}"),
        InlineKeyboardButton("❌ Нет", callback_data=f"cancel_{action}")
    )
    return keyboard

def get_back_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура возврата"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard


def get_voting_inline_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для перехода в бота для голосования"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # URL для перехода в бота с параметром для голосования
    bot_username = "bunker_nnkf_bot"  # Замените на username вашего бота
    url = f"https://t.me/{bot_username}?start=vote_{chat_id}"
    
    keyboard.add(InlineKeyboardButton("🗳️ Голосовать в личных сообщениях", url=url))
    return keyboard

def get_private_voting_keyboard(players: List, current_user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для голосования в личных сообщениях"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем кнопки для голосования за каждого живого игрока (кроме текущего)
    for player in players:
        if hasattr(player, 'is_alive') and player.is_alive and hasattr(player, 'user_id') and player.user_id != current_user_id:
            text = f"🗳️ Голосовать против {player.get_display_name()}"
            keyboard.add(InlineKeyboardButton(text, callback_data=f"vote_{player.user_id}"))
    
    # Добавляем кнопку воздержания
    keyboard.add(InlineKeyboardButton("🤐 Воздержаться", callback_data="vote_abstain"))
    return keyboard


def get_private_character_keyboard(player, current_phase=None) -> InlineKeyboardMarkup:
    """Клавиатура для управления персонажем в ЛС"""
    keyboard = InlineKeyboardMarkup(row_width=3)

    if not player.character:
        return keyboard

    cards = []

    # Ограничения только для первой фазы
    if current_phase == "card_reveal_1":
        # В первой фазе только профессия
        card_info = [("💼", "reveal_profession", "profession")]
    else:
        # В остальных фазах все карточки
        card_info = [
            ("💼", "reveal_profession", "profession"),
            ("👤", "reveal_biology", "biology"),
            ("🫁", "reveal_health", "health"),
            ("🗣", "reveal_phobia", "phobia"),
            ("🎮", "reveal_hobby", "hobby"),
            ("🔎", "reveal_fact", "fact"),
            ("📦", "reveal_baggage", "baggage")
        ]

    for emoji, callback, card_type in card_info:
        # Проверяем не раскрыта ли карта и не воздержался ли игрок
        not_revealed = not player.character.revealed_cards.get(card_type, False)
        not_abstained = not getattr(player, f'abstained_card_{card_type}', False)

        if not_revealed and not_abstained:
            cards.append(InlineKeyboardButton(emoji, callback_data=callback))

    # Добавляем кнопки по 3 в ряд
    for i in range(0, len(cards), 3):
        row = cards[i:i + 3]
        keyboard.row(*row)

    # Кнопка воздержания (всегда доступна)
    # keyboard.row(InlineKeyboardButton("🤐 Воздержаться", callback_data="abstain_card"))

    # Кнопка использования специальной карточки
    if (player.character.special_card and
            hasattr(player, 'special_card_used') and
            not player.special_card_used):
        keyboard.row(InlineKeyboardButton("⚡ Использовать спецкарточку", callback_data="use_special_card"))

    # НОВОЕ: кнопка возврата в группу
    from config import GROUP_CHAT_ID
    if GROUP_CHAT_ID:
        keyboard.row(InlineKeyboardButton("🔙 Вернуться в группу", url=f"https://t.me/c/{abs(GROUP_CHAT_ID)}/1"))

    return keyboard

def get_cards_menu_inline_keyboard(chat_id: int, game_manager=None) -> InlineKeyboardMarkup:
    """Клавиатура для перехода в бота для управления карточками"""
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Проверяем завершено ли первое голосование
    if game_manager and chat_id in game_manager.games:
        game = game_manager.games[chat_id]
        if getattr(game, 'first_voting_completed', False):
            # После первого голосования - только переход в бота
            bot_username = "bunker_nnkf_bot"  # Замените на username вашего бота
            url = f"https://t.me/{bot_username}"
            keyboard.add(InlineKeyboardButton("🃏 Перейти в бота", url=url))
        else:
            # До первого голосования - переход с параметрами
            bot_username = "bunker_nnkf_bot"
            url = f"https://t.me/{bot_username}?start=cards_{chat_id}"
            keyboard.add(InlineKeyboardButton("🃏 Управлять карточками", url=url))
    else:
        # Fallback
        bot_username = "bunker_nnkf_bot"
        url = f"https://t.me/{bot_username}?start=cards_{chat_id}"
        keyboard.add(InlineKeyboardButton("🃏 Управлять карточками", url=url))

    return keyboard