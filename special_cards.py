# special_cards.py
# Файл для хранения специальных карточек с исполняемым кодом
# ВНИМАНИЕ: Этот файл может быть изменен ботом автоматически

import random
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class SpecialCard:
    """Класс специальной карточки"""
    
    def __init__(self, name: str, description: str, code: str, usage_count: int = 1):
        self.name = name
        self.description = description
        self.code = code
        self.usage_count = usage_count
        self.used = False
    
    def execute(self, game, player, bot, target_player=None, **kwargs) -> Dict[str, Any]:
        """Выполняет код специальной карточки"""
        if self.used and self.usage_count <= 0:
            return {"success": False, "message": "Карточка уже использована"}
        
        try:
            # Создаем безопасный контекст выполнения
            context = {
                'game': game,
                'player': player,
                'target_player': target_player,
                'bot': bot,
                'random': random,
                'logger': logger,
                'result': {"success": True, "message": "Карточка использована"}
            }
            
            # Выполняем код карточки
            exec(self.code, context)
            
            # Отмечаем использование
            if self.usage_count > 0:
                self.usage_count -= 1
                if self.usage_count <= 0:
                    self.used = True
            
            return context.get('result', {"success": True, "message": "Карточка выполнена"})
            
        except Exception as e:
            logger.error(f"Ошибка выполнения специальной карточки {self.name}: {e}")
            return {"success": False, "message": f"Ошибка выполнения: {e}"}

# Предустановленные специальные карточки
SPECIAL_CARDS = {
    "swap_facts": SpecialCard(
        name="Обмен фактами",
        description="Поменяйтесь карточками фактов с любым неизгнанным игроком с открытой картой факта",
        code="""
# Находим игроков с открытыми фактами
available_targets = []
for p in game.get_alive_players():
    if p.user_id != player.user_id and p.character and p.character.revealed_cards.get('fact', False):
        available_targets.append(p)

if not available_targets:
    result = {"success": False, "message": "Нет игроков с открытыми фактами для обмена"}
else:
    if target_player and target_player in available_targets:
        # Меняем факты местами
        player_fact = player.character.fact
        target_fact = target_player.character.fact
        
        player.character.fact = target_fact
        target_player.character.fact = player_fact
        
        result = {
            "success": True, 
            "message": f"Факты обменены с {target_player.get_display_name()}!",
            "public_message": f"🔄 {player.get_display_name()} обменялся фактами с {target_player.get_display_name()}!"
        }
    else:
        result = {
            "success": False, 
            "message": f"Доступные цели: {', '.join([p.get_display_name() for p in available_targets])}"
        }
""",
        usage_count=1
    ),

    "shuffle_professions": SpecialCard(
        name="Перемешать профессии",
        description="Собери все открытые карты профессий у неизгнанных игроков, перемешай и перераздай",
        code="""
# Собираем открытые профессии
open_professions = []
affected_players = []

for p in game.get_alive_players():
    if p.character and p.character.revealed_cards.get('profession', False):
        open_professions.append(p.character.profession)
        affected_players.append(p)

if len(open_professions) < 2:
    result = {"success": False, "message": "Недостаточно открытых профессий для перемешивания"}
else:
    import random
    random.shuffle(open_professions)

    # Перераздаем профессии
    for i, p in enumerate(affected_players):
        p.character.profession = open_professions[i]

    affected_names = [p.get_display_name() for p in affected_players]
    result = {
        "success": True,
        "message": f"Профессии перемешаны среди {len(affected_players)} игроков!",
        "public_message": f"🔀 {player.get_display_name()} перемешал профессии игроков: {', '.join(affected_names)}"
    }
""",
        usage_count=1
    ),

    "swap_professions": SpecialCard(
        name="Обмен профессиями",
        description="Поменяйся карточками профессий с любым неизгнанным игроком с открытой картой профессии",
        code="""
available_targets = []
for p in game.get_alive_players():
    if p.user_id != player.user_id and p.character and p.character.revealed_cards.get('profession', False):
        available_targets.append(p)

if not available_targets:
    result = {"success": False, "message": "Нет игроков с открытыми профессиями для обмена"}
else:
    if target_player and target_player in available_targets:
        player_prof = player.character.profession
        target_prof = target_player.character.profession

        player.character.profession = target_prof
        target_player.character.profession = player_prof

        result = {
            "success": True, 
            "message": f"Профессии обменены с {target_player.get_display_name()}!",
            "public_message": f"🔄 {player.get_display_name()} обменялся профессиями с {target_player.get_display_name()}!"
        }
    else:
        result = {
            "success": False, 
            "message": f"Доступные цели: {', '.join([p.get_display_name() for p in available_targets])}"
        }
""",
        usage_count=1
    ),

    "double_vote": SpecialCard(
        name="Двойной голос",
        description="Твой голос считается за два в этом голосовании",
        code="""
if not hasattr(player, 'double_vote_active'):
    player.double_vote_active = True
    result = {
        "success": True,
        "message": "Ваш голос теперь считается за два!",
        "public_message": f"🗳️🗳️ {player.get_display_name()} получил двойной голос!"
    }
else:
    result = {"success": False, "message": "У вас уже есть двойной голос"}
""",
        usage_count=1
    ),

    "pig_transformation": SpecialCard(
        name="Превращение в свинью",
        description="Ты становишься свиньёй до конца раунда. Тебя не могут изгнать, однако ты не можешь открывать карты до следующего раунда",
        code="""
if not hasattr(player, 'is_pig'):
    player.is_pig = True
    player.pig_immunity = True  # Иммунитет от изгнания
    player.cannot_reveal = True  # Не может раскрывать карты

    result = {
        "success": True,
        "message": "Вы превратились в свинью! Вас нельзя изгнать, но вы не можете раскрывать карты этот раунд.",
        "public_message": f"🐷 {player.get_display_name()} превратился в свинью и получил иммунитет!"
    }
else:
    result = {"success": False, "message": "Вы уже свинья!"}
""",
        usage_count=1
    ),

    "revenge_exile": SpecialCard(
        name="Месть при изгнании",
        description="Если тебя изгнали, забери с собой любого игрока",
        code="""
if not hasattr(player, 'revenge_active'):
    player.revenge_active = True
    result = {
        "success": True,
        "message": "Если вас изгонят, вы сможете забрать с собой одного игрока!",
        "public_message": f"💀 {player.get_display_name()} активировал месть при изгнании!"
    }
else:
    result = {"success": False, "message": "Месть уже активирована"}
""",
        usage_count=1
    ),

    "block_vote": SpecialCard(
        name="Блокировка голосования",
        description="Выбери неизгнанного игрока, который не сможет голосовать в этом раунде",
        code="""
alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]

if not alive_players:
    result = {"success": False, "message": "Нет других игроков"}
else:
    if target_player and target_player in alive_players:
        target_player.blocked_from_voting = True
        result = {
            "success": True,
            "message": f"{target_player.get_display_name()} не сможет голосовать в этом раунде!",
            "public_message": f"🚫 {player.get_display_name()} заблокировал голосование для {target_player.get_display_name()}!"
        }
    else:
        available_targets = [p.get_display_name() for p in alive_players]
        result = {
            "success": False,
            "message": f"Выберите цель: {', '.join(available_targets)}"
        }
""",
        usage_count=1
    ),

    "reveal_random": SpecialCard(
        name="Случайное раскрытие",
        description="Раскрывает случайную нераскрытую карточку любого игрока",
        code="""
# Собираем всех живых игроков кроме текущего
alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]

if not alive_players:
    result = {"success": False, "message": "Нет других игроков"}
else:
    # Выбираем случайного игрока
    target = random.choice(alive_players)
    
    # Находим нераскрытые карточки
    unrevealed_cards = []
    for card_type, revealed in target.character.revealed_cards.items():
        if not revealed:
            unrevealed_cards.append(card_type)
    
    if not unrevealed_cards:
        result = {"success": False, "message": f"У {target.get_display_name()} все карточки уже раскрыты"}
    else:
        # Раскрываем случайную карточку
        card_to_reveal = random.choice(unrevealed_cards)
        target.character.revealed_cards[card_to_reveal] = True
        
        # Получаем информацию о раскрытой карточке
        card_names = {
            'profession': 'Профессия',
            'biology': 'Биология', 
            'health': 'Здоровье',
            'phobia': 'Фобия',
            'hobby': 'Хобби',
            'fact': 'Факт',
            'baggage': 'Багаж'
        }
        
        card_values = {
            'profession': target.character.profession,
            'biology': f"{target.character.gender} {target.character.age} лет",
            'health': f"{target.character.body_type}, {target.character.disease}",
            'phobia': target.character.phobia,
            'hobby': target.character.hobby,
            'fact': target.character.fact,
            'baggage': target.character.baggage
        }
        
        card_name = card_names.get(card_to_reveal, card_to_reveal)
        card_value = card_values.get(card_to_reveal, "Неизвестно")
        
        result = {
            "success": True,
            "message": f"Раскрыта карточка {card_name} игрока {target.get_display_name()}: {card_value}",
            "public_message": f"🎴 {player.get_display_name()} принудительно раскрыл карточку {card_name} игрока {target.get_display_name()}: {card_value}"
        }
""",
        usage_count=1
    ),
    
    "immunity": SpecialCard(
        name="Иммунитет",
        description="Защищает от исключения в следующем раунде голосования",
        code="""
# Устанавливаем флаг иммунитета
if not hasattr(player, 'has_immunity'):
    player.has_immunity = True
    
    result = {
        "success": True,
        "message": "Вы получили иммунитет от исключения в следующем раунде!",
        "public_message": f"🛡️ {player.get_display_name()} использовал карточку иммунитета!"
    }
else:
    result = {"success": False, "message": "У вас уже есть иммунитет"}
""",
        usage_count=1
    ),
    
    "vote_steal": SpecialCard(
        name="Кража голоса",
        description="Отменяет голос любого игрока и добавляет его себе",
        code="""
# Находим игроков, которые уже проголосовали
voted_players = [p for p in game.get_alive_players() if p.has_voted and p.user_id != player.user_id]

if not voted_players:
    result = {"success": False, "message": "Никто еще не проголосовал"}
else:
    if target_player and target_player in voted_players:
        # Отменяем голос цели
        if target_player.vote_target:
            # Уменьшаем счетчик голосов у цели голосования
            if target_player.vote_target in game.players:
                game.players[target_player.vote_target].votes_received = max(0, 
                    game.players[target_player.vote_target].votes_received - 1)
        
        # Сбрасываем голос
        target_player.has_voted = False
        target_player.vote_target = None
        
        result = {
            "success": True,
            "message": f"Голос {target_player.get_display_name()} отменен!",
            "public_message": f"🗳️ {player.get_display_name()} отменил голос игрока {target_player.get_display_name()}!"
        }
    else:
        available_targets = [p.get_display_name() for p in voted_players]
        result = {
            "success": False,
            "message": f"Доступные цели: {', '.join(available_targets)}"
        }
""",
        usage_count=1
    ),
    
    "card_peek": SpecialCard(
        name="Подглядывание",
        description="Узнайте одну нераскрытую карточку любого игрока (только вы увидите)",
        code="""
alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]

if not alive_players:
    result = {"success": False, "message": "Нет других игроков"}
else:
    if target_player and target_player in alive_players:
        # Находим нераскрытые карточки
        unrevealed_cards = []
        for card_type, revealed in target_player.character.revealed_cards.items():
            if not revealed:
                unrevealed_cards.append(card_type)
        
        if not unrevealed_cards:
            result = {"success": False, "message": f"У {target_player.get_display_name()} все карточки раскрыты"}
        else:
            # Показываем случайную нераскрытую карточку
            card_to_peek = random.choice(unrevealed_cards)
            
            card_names = {
                'profession': 'Профессия',
                'biology': 'Биология',
                'health': 'Здоровье', 
                'phobia': 'Фобия',
                'hobby': 'Хобби',
                'fact': 'Факт',
                'baggage': 'Багаж'
            }
            
            card_values = {
                'profession': target_player.character.profession,
                'biology': f"{target_player.character.gender} {target_player.character.age} лет",
                'health': f"{target_player.character.body_type}, {target_player.character.disease}",
                'phobia': target_player.character.phobia,
                'hobby': target_player.character.hobby,
                'fact': target_player.character.fact,
                'baggage': target_player.character.baggage
            }
            
            card_name = card_names.get(card_to_peek, card_to_peek)
            card_value = card_values.get(card_to_peek, "Неизвестно")
            
            result = {
                "success": True,
                "message": f"Скрытая карточка {target_player.get_display_name()}: {card_name} - {card_value}",
                "public_message": f"🔍 {player.get_display_name()} подглядел карточку игрока {target_player.get_display_name()}"
            }
    else:
        available_targets = [p.get_display_name() for p in alive_players]
        result = {
            "success": False,
            "message": f"Выберите цель: {', '.join(available_targets)}"
        }
""",
        usage_count=1
    ),

    "steal_profession": SpecialCard(
        name="Кража профессии",
        description="Забери профессию любого игрока с открытой профессией",
        code="""
# Находим игроков с открытыми профессиями
available_targets = []
for p in game.get_alive_players():
    if p.user_id != player.user_id and p.character and p.character.revealed_cards.get('profession', False):
        available_targets.append(p)

if not available_targets:
    result = {"success": False, "message": "Нет игроков с открытыми профессиями для кражи"}
else:
    if target_player and target_player in available_targets:
        # Крадем профессию
        stolen_profession = target_player.character.profession
        target_player.character.profession = player.character.profession
        player.character.profession = stolen_profession

        # Сохраняем изменения
        if hasattr(game, 'game_manager') and hasattr(game.game_manager, 'save_player_cards'):
            game.game_manager.save_player_cards(game.chat_id)

        result = {
            "success": True,
            "message": f"Профессия украдена у {target_player.get_display_name()}!",
            "public_message": f"💰 {player.get_display_name()} украл профессию у {target_player.get_display_name()}!"
        }
    else:
        available_names = [p.get_display_name() for p in available_targets]
        result = {
            "success": False,
            "message": f"Выберите цель: {', '.join(available_names)}"
        }
""",
        usage_count=1
    ),

    "change_fact": SpecialCard(
        name="Смена факта",
        description="Смени свой факт на любой другой из колоды",
        code="""
import random

# Получаем список всех фактов
facts_list = game.game_manager.cards_data.get('facts', [])

if not facts_list:
    result = {"success": False, "message": "Нет доступных фактов для смены"}
else:
    # Исключаем текущий факт
    available_facts = [f for f in facts_list if f != player.character.fact]

    if not available_facts:
        result = {"success": False, "message": "Нет других фактов для смены"}
    else:
        old_fact = player.character.fact
        new_fact = random.choice(available_facts)
        player.character.fact = new_fact

        # Сохраняем изменения
        if hasattr(game, 'game_manager') and hasattr(game.game_manager, 'save_player_cards'):
            game.game_manager.save_player_cards(game.chat_id)

        result = {
            "success": True,
            "message": f"Факт изменен с '{old_fact}' на '{new_fact}'",
            "public_message": f"🔄 {player.get_display_name()} изменил свой факт!"
        }
""",
        usage_count=1
    ),

    "reveal_all_cards": SpecialCard(
        name="Полное раскрытие",
        description="Раскрой все свои карточки сразу",
        code="""
if not player.character:
    result = {"success": False, "message": "У вас нет персонажа"}
else:
    # Раскрываем все карточки
    cards_revealed = []
    for card_type in ['profession', 'biology', 'health', 'phobia', 'hobby', 'fact', 'baggage']:
        if not player.character.revealed_cards.get(card_type, False):
            player.character.revealed_cards[card_type] = True
            cards_revealed.append(card_type)

    if not cards_revealed:
        result = {"success": False, "message": "Все карточки уже раскрыты"}
    else:
        # Сохраняем изменения
        if hasattr(game, 'game_manager') and hasattr(game.game_manager, 'save_player_cards'):
            game.game_manager.save_player_cards(game.chat_id)

        card_names = {
            'profession': 'Профессия',
            'biology': 'Биология',
            'health': 'Здоровье',
            'phobia': 'Фобия', 
            'hobby': 'Хобби',
            'fact': 'Факт',
            'baggage': 'Багаж'
        }

        revealed_names = [card_names.get(ct, ct) for ct in cards_revealed]

        # Показываем все раскрытые карточки
        character_info = player.get_character_info(show_all=True)

        result = {
            "success": True,
            "message": f"Все карточки раскрыты: {', '.join(revealed_names)}",
            "public_message": f"💥 {player.get_display_name()} раскрыл все свои карточки!\n\n{character_info}"
        }
""",
        usage_count=1
    ),

    "target_selector": SpecialCard(
        name="Выбор цели",
        description="Выбери игрока для применения следующей специальной карточки",
        code="""
alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]

if not alive_players:
    result = {"success": False, "message": "Нет других игроков"}
else:
    # Сохраняем возможность выбора цели в следующем действии
    player.can_target_next = True

    available_names = [p.get_display_name() for p in alive_players]

    result = {
        "success": True,
        "message": f"Теперь вы можете выбрать цель для следующего действия. Доступные игроки: {', '.join(available_names)}",
        "public_message": f"🎯 {player.get_display_name()} подготовился к выбору цели!"
    }
""",
        usage_count=1
    )
}

def get_special_cards() -> Dict[str, SpecialCard]:
    """Возвращает словарь всех специальных карточек"""
    return SPECIAL_CARDS.copy()

def add_special_card(card_id: str, name: str, description: str, code: str, usage_count: int = 1) -> bool:
    """Добавляет новую специальную карточку"""
    try:
        SPECIAL_CARDS[card_id] = SpecialCard(name, description, code, usage_count)
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления специальной карточки {card_id}: {e}")
        return False

def remove_special_card(card_id: str) -> bool:
    """Удаляет специальную карточку"""
    try:
        if card_id in SPECIAL_CARDS:
            del SPECIAL_CARDS[card_id]
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка удаления специальной карточки {card_id}: {e}")
        return False

def save_special_cards():
    """Сохраняет изменения в файл (переписывает этот файл)"""
    try:
        import os
        import tempfile
        
        # Создаем содержимое файла
        file_content = '''# special_cards.py
# Файл для хранения специальных карточек с исполняемым кодом
# ВНИМАНИЕ: Этот файл может быть изменен ботом автоматически

import random
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class SpecialCard:
    """Класс специальной карточки"""
    
    def __init__(self, name: str, description: str, code: str, usage_count: int = 1):
        self.name = name
        self.description = description
        self.code = code
        self.usage_count = usage_count
        self.used = False
    
    def execute(self, game, player, bot, target_player=None, **kwargs) -> Dict[str, Any]:
        """Выполняет код специальной карточки"""
        if self.used and self.usage_count <= 0:
            return {"success": False, "message": "Карточка уже использована"}
        
        try:
            # Создаем безопасный контекст выполнения
            context = {
                'game': game,
                'player': player,
                'target_player': target_player,
                'bot': bot,
                'random': random,
                'logger': logger,
                'result': {"success": True, "message": "Карточка использована"}
            }
            
            # Выполняем код карточки
            exec(self.code, context)
            
            # Отмечаем использование
            if self.usage_count > 0:
                self.usage_count -= 1
                if self.usage_count <= 0:
                    self.used = True
            
            return context.get('result', {"success": True, "message": "Карточка выполнена"})
            
        except Exception as e:
            logger.error(f"Ошибка выполнения специальной карточки {self.name}: {e}")
            return {"success": False, "message": f"Ошибка выполнения: {e}"}

# Предустановленные специальные карточки
SPECIAL_CARDS = {
'''
        
        # Добавляем все карточки
        for card_id, card in SPECIAL_CARDS.items():
            file_content += f'    "{card_id}": SpecialCard(\n'
            file_content += f'        name="{card.name}",\n'
            file_content += f'        description="{card.description}",\n'
            file_content += f'        code="""{card.code}""",\n'
            file_content += f'        usage_count={card.usage_count}\n'
            file_content += f'    ),\n'
        
        file_content += '''}\n\ndef get_special_cards() -> Dict[str, SpecialCard]:
    """Возвращает словарь всех специальных карточек"""
    return SPECIAL_CARDS.copy()

def add_special_card(card_id: str, name: str, description: str, code: str, usage_count: int = 1) -> bool:
    """Добавляет новую специальную карточку"""
    try:
        SPECIAL_CARDS[card_id] = SpecialCard(name, description, code, usage_count)
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления специальной карточки {card_id}: {e}")
        return False

def remove_special_card(card_id: str) -> bool:
    """Удаляет специальную карточку"""
    try:
        if card_id in SPECIAL_CARDS:
            del SPECIAL_CARDS[card_id]
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка удаления специальной карточки {card_id}: {e}")
        return False

def save_special_cards():
    """Сохраняет изменения в файл (переписывает этот файл)"""
    # Эта функция будет переписана при автосохранении
    pass
'''
        
        # Записываем в текущий файл
        current_file = __file__
        
        # Создаем временный файл и атомарно заменяем
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tmp:
            tmp.write(file_content)
            tmp_name = tmp.name
        
        # Заменяем файл
        os.replace(tmp_name, current_file)
        
        logger.info("Специальные карточки сохранены в файл")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка сохранения специальных карточек: {e}")
        return False
