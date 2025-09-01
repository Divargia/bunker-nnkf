import random
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class PlayerCharacter:
    """Персонаж игрока"""
    profession: str
    gender: str
    age: int
    body_type: str
    disease: str
    phobia: str
    hobby: str
    fact: str
    baggage: str
    special_card: str = ""
    revealed_cards: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.revealed_cards is None:
            self.revealed_cards = {
                'profession': False,
                'biology': False,
                'health': False,
                'phobia': False,
                'hobby': False,
                'fact': False,
                'baggage': False,
                'special_card': False
            }

class Player:
    """Класс игрока"""
    
    def __init__(self, user_id: int, username: str, first_name: str):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.character: Optional[PlayerCharacter] = None
        self.is_alive = True
        self.votes_received = 0
        self.has_voted = False
        self.vote_target: Optional[int] = None
        self.is_admin = False
        
    def _weighted_choice(self, choices: List[Tuple[str, int]]) -> str:
        """Выбирает элемент с учетом весов"""
        if not choices:
            return ""
        
        # Если это обычный список строк, преобразуем в кортежи с равными весами
        if isinstance(choices[0], str):
            choices = [(choice, 1) for choice in choices]
        
        total_weight = sum(weight for _, weight in choices)
        r = random.randint(1, total_weight)
        
        for choice, weight in choices:
            r -= weight
            if r <= 0:
                return choice
        
        return choices[0][0]  # Fallback

    def generate_character(self, cards_data: Dict[str, List]) -> PlayerCharacter:
        """Генерирует случайного персонажа"""
        # Генерируем пол и возраст
        gender = self._weighted_choice(cards_data.get('biology', [('Мужчина', 1)]))
        age = random.randint(16, 100)

        # Генерируем телосложение и заболевание
        body_type = self._weighted_choice(cards_data.get('health_body', [('Обычный', 1)]))
        disease = self._weighted_choice(cards_data.get('health_disease', [('Полностью здоров', 1)]))

        # Генерируем специальную карточку (используем настройку из config)
        from config import GAME_SETTINGS
        special_card = ""
        special_card_id = ""

        if random.random() < GAME_SETTINGS['SPECIAL_CARD_CHANCE']:
            try:
                from special_cards import get_special_cards
                special_cards_dict = get_special_cards()
                if special_cards_dict:
                    special_card_id = random.choice(list(special_cards_dict.keys()))
                    special_card = special_cards_dict[special_card_id].description
            except ImportError:
                # Fallback если special_cards недоступен
                special_cards = cards_data.get('special_cards', [])
                if special_cards:
                    special_card = random.choice(special_cards)

        self.character = PlayerCharacter(
            profession=random.choice(cards_data.get('professions', ['Инженер'])),
            gender=gender,
            age=age,
            body_type=body_type,
            disease=disease,
            phobia=random.choice(cards_data.get('phobias', ['Боязнь высоты'])),
            hobby=random.choice(cards_data.get('hobbies', ['Чтение'])),
            fact=random.choice(cards_data.get('facts', ['Обычный человек'])),
            baggage=random.choice(cards_data.get('baggage', ['Рюкзак'])),
            special_card=special_card
        )

        # Добавляем поля для специальных карточек
        self.special_card_used = False
        if special_card_id:
            self.character.special_card_id = special_card_id

        return self.character
    
    def reveal_card(self, card_type: str) -> bool:
        """Раскрывает карточку персонажа"""
        if self.character and card_type in self.character.revealed_cards:
            self.character.revealed_cards[card_type] = True
            return True
        return False

    def get_character_info(self, show_all: bool = False) -> str:
        """Возвращает информацию о персонаже"""
        if not self.character:
            return "Персонаж не создан"

        info_parts = []

        def add_info(key: str, value: str, label: str):
            if show_all or self.character.revealed_cards.get(key, False):
                info_parts.append(f"{label}: {value}")
            else:
                info_parts.append(f"{label}: ❓")

        add_info('profession', self.character.profession, '💼 Профессия')
        add_info('biology', f"{self.character.gender} {self.character.age} лет", '👤 Биология')
        add_info('health', f"{self.character.body_type}, {self.character.disease}", '🫁 Здоровье')
        add_info('phobia', self.character.phobia, '🗣 Фобия')
        add_info('hobby', self.character.hobby, '🎮 Хобби')
        add_info('fact', self.character.fact, '🔎 Факт')
        add_info('baggage', self.character.baggage, '📦 Багаж')

        # УДАЛЕНО: специальные карточки больше не показываются в публичной информации
        # Показываем только в полной информации (в ЛС игрока)
        if show_all and self.character.special_card:
            info_parts.append(f"🃏 Специальная карточка: {self.character.special_card}")

        return '\n'.join(info_parts)
    
    def vote(self, target_user_id: int) -> bool:
        """Голосует против игрока"""
        if self.has_voted or not self.is_alive:
            return False
        
        self.vote_target = target_user_id
        self.has_voted = True
        return True
    
    def reset_vote(self):
        """Сбрасывает голос"""
        self.has_voted = False
        self.vote_target = None
        self.votes_received = 0

    def eliminate(self):
        """Исключает игрока"""
        # Проверяем иммунитет
        if hasattr(self, 'has_immunity') and self.has_immunity:
            self.has_immunity = False  # Снимаем иммунитет после использования
            return False  # Игрок не исключается

        self.is_alive = False
        return True
    
    def get_display_name(self) -> str:
        """Возвращает отображаемое имя"""
        return f"@{self.username}" if self.username else self.first_name

    def use_special_card(self, game, bot, target_player=None) -> Dict[str, any]:
        """Использует специальную карточку"""
        if not self.character or not self.character.special_card:
            return {"success": False, "message": "У вас нет специальной карточки"}

        if hasattr(self, 'special_card_used') and self.special_card_used:
            return {"success": False, "message": "Специальная карточка уже использована"}

        # Проверяем можно ли использовать в текущей фазе
        allowed_phases = ["card_reveal_1", "card_reveal_2", "card_reveal_3",
                          "card_reveal_4", "card_reveal_5", "card_reveal_6", "card_reveal_7"]

        if game.phase.value not in allowed_phases:
            return {"success": False, "message": "Специальные карточки можно использовать только в фазах раскрытия"}

        try:
            from special_cards import get_special_cards
            special_cards = get_special_cards()

            card_id = getattr(self.character, 'special_card_id', None)
            if not card_id or card_id not in special_cards:
                # Fallback - ищем по описанию
                for sid, card_obj in special_cards.items():
                    if card_obj.description == self.character.special_card:
                        card_id = sid
                        self.character.special_card_id = sid
                        break

            if not card_id or card_id not in special_cards:
                return {"success": False, "message": "Специальная карточка не найдена в системе"}

            card = special_cards[card_id]

            # ИСПРАВЛЕНО: передаем game_manager через игру для доступа к системе сохранения
            if hasattr(game, 'chat_id'):
                # Находим game_manager через глобальный доступ или передаем его
                import bot
                if hasattr(bot, '_bot_instance') and bot._bot_instance:
                    game.game_manager = bot._bot_instance.game_manager

            result = card.execute(game, self, bot, target_player)

            if result.get("success", False):
                self.special_card_used = True

                # ДОБАВЛЕНО: автосохранение после использования спецкарточки
                if hasattr(game, 'game_manager') and hasattr(game.game_manager, 'save_player_cards'):
                    game.game_manager.save_player_cards(game.chat_id)

            return result

        except ImportError:
            return {"success": False, "message": "Система специальных карточек недоступна"}
        except Exception as e:
            return {"success": False, "message": f"Ошибка использования карточки: {e}"}

    def serialize_to_dict(self) -> dict:
        """Преобразует игрока в словарь для сохранения"""
        data = {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'is_alive': self.is_alive,
            'votes_received': self.votes_received,
            'has_voted': self.has_voted,
            'vote_target': self.vote_target,
            'is_admin': self.is_admin,
            'special_card_used': getattr(self, 'special_card_used', False)
        }

        if self.character:
            data['character'] = {
                'profession': self.character.profession,
                'gender': self.character.gender,
                'age': self.character.age,
                'body_type': self.character.body_type,
                'disease': self.character.disease,
                'phobia': self.character.phobia,
                'hobby': self.character.hobby,
                'fact': self.character.fact,
                'baggage': self.character.baggage,
                'special_card': self.character.special_card,
                'special_card_id': getattr(self.character, 'special_card_id', ''),
                'revealed_cards': self.character.revealed_cards.copy()
            }

        return data

    def load_from_dict(self, data: dict):
        """Загружает данные игрока из словаря"""
        self.is_alive = data.get('is_alive', True)
        self.votes_received = data.get('votes_received', 0)
        self.has_voted = data.get('has_voted', False)
        self.vote_target = data.get('vote_target')
        self.is_admin = data.get('is_admin', False)
        self.special_card_used = data.get('special_card_used', False)

        if 'character' in data and self.character:
            char_data = data['character']
            self.character.profession = char_data.get('profession', '')
            self.character.gender = char_data.get('gender', '')
            self.character.age = char_data.get('age', 18)
            self.character.body_type = char_data.get('body_type', '')
            self.character.disease = char_data.get('disease', '')
            self.character.phobia = char_data.get('phobia', '')
            self.character.hobby = char_data.get('hobby', '')
            self.character.fact = char_data.get('fact', '')
            self.character.baggage = char_data.get('baggage', '')
            self.character.special_card = char_data.get('special_card', '')

            if 'special_card_id' in char_data:
                self.character.special_card_id = char_data['special_card_id']

            if 'revealed_cards' in char_data:
                self.character.revealed_cards.update(char_data['revealed_cards'])