# game_manager.py
import json
import os
import random
import threading
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
import time

from player import Player, PlayerCharacter
from timers import PhaseTimer, NotificationTimer
from config import GAME_SETTINGS, CARDS_DIR, DATA_DIR
from config import PLAYER_CARDS_DIR
from config import MESSAGE_DELAY, BOT_IMAGES
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    LOBBY = "lobby"
    ROLE_STUDY = "role_study"
    CARD_REVEAL_1 = "card_reveal_1"
    CARD_REVEAL_2 = "card_reveal_2"
    CARD_REVEAL_3 = "card_reveal_3"
    CARD_REVEAL_4 = "card_reveal_4"
    CARD_REVEAL_5 = "card_reveal_5"
    CARD_REVEAL_6 = "card_reveal_6"
    CARD_REVEAL_7 = "card_reveal_7"
    VOTING = "voting"
    RESULTS = "results"
    FINISHED = "finished"
    # Убираем DISCUSSION - его больше нет

class Game:
    """Класс игры"""

    def __init__(self, chat_id: int, admin_id: int):
        self.chat_id = chat_id
        self.admin_id = admin_id
        self.players: Dict[int, Player] = {}
        self.phase = GamePhase.LOBBY
        self.scenario = ""
        self.scenario_description = ""
        self.bunker_info = ""
        self.voting_results: Dict[int, int] = {}
        self.eliminated_players: List[int] = []
        self.winners: List[int] = []
        self.created_at = None
        self.current_card_phase = 1
        self.voting_rounds_left = 0
        # НЕ устанавливайте эти поля здесь!
        # self.current_player_index = 0
        # self.players_order = []
        self.lobby_message_id = None
        self.pin_message_id = None
        self.revote_candidates = []
        self.is_revoting = False
        self.lobby_message_id = None
        self.first_voting_completed = False
        self.players_order = []  # Порядок игроков для очереди
        self.current_player_index = 0  # Индекс текущего игрока
        self.current_turn_player_id = None  # ID игрока, чья сейчас очередь
        self.turn_started_at = None  # Время начала хода
        self.menu_sent_to_players = set()
        self.current_turn_message_id = None

    def add_player(self, user_id: int, username: str, first_name: str) -> bool:
        """Добавляет игрока в игру"""
        if len(self.players) >= GAME_SETTINGS['MAX_PLAYERS']:
            return False

        if user_id in self.players:
            return False

        player = Player(user_id, username, first_name)
        if user_id in ADMIN_IDS:  # Изменено с self.ADMIN_IDS на ADMIN_IDS
            player.is_admin = True

        self.players[user_id] = player
        return True

    def remove_player(self, user_id: int) -> bool:
        """Удаляет игрока из игры"""
        if user_id in self.players:
            del self.players[user_id]
            return True
        return False

    def get_alive_players(self) -> List[Player]:
        """Возвращает живых игроков"""
        return [p for p in self.players.values() if p.is_alive]

    def can_start(self) -> bool:
        """Проверяет возможность начала игры"""
        from config import GAME_SETTINGS
        return (self.phase == GamePhase.LOBBY and
                len(self.players) in GAME_SETTINGS['ALLOWED_PLAYERS'])

    def generate_scenario(self, scenarios: List[str]) -> Tuple[str, str]:
        """Генерирует сценарий катастрофы и описание бункера"""
        scenario = random.choice(scenarios) if scenarios else "Ядерная война"

        bunker_templates = [
            "Бункер рассчитан на {slots} человек. Запасов еды на 1 год. Есть генератор, медблок, библиотека.",
            "Убежище на {slots} мест. Автономность 2 года. Гидропоника, мастерская, спортзал.",
            "Подземное укрытие на {slots} человек. Запасы на 18 месяцев. Лаборатория, склад, комнаты отдыха."
        ]

        slots = len(self.get_alive_players()) - random.randint(1, 2)
        slots = max(1, slots)

        bunker_info = random.choice(bunker_templates).format(slots=slots)

        return scenario, bunker_info


class GameManager:
    """Менеджер игр"""

    def __init__(self, bot):
        self.bot = bot
        self.games: Dict[int, Game] = {}  # chat_id -> Game
        self.phase_timer = PhaseTimer(self)
        self.notification_timer = NotificationTimer(bot)
        self.cards_data = self._load_cards_data()

    def _load_cards_data(self) -> Dict[str, List[str]]:
        """Загружает данные карточек"""
        default_cards = {
            'professions': [
                'Админ по вп', 'Слесарь', 'Разнорабочий', 'Адвокат', 'Судья',
                'Прокурор', 'Хирург', 'Ортопед', 'Стоматолог', 'Гинеколог',
                'Фермер', 'Физик ядерщик', 'Экономист', 'Инженер'
            ],
            'biology': [
                ('Мужчина', 70), ('Женщина', 70), ('Гермафродит', 5),
                ('Футанари', 3), ('Кантбой', 3), ('Разумная белая свинья', 1)
            ],
            'health_body': [
                ('Обычный', 40), ('Крупное телосложение', 20), ('Тощий', 20),
                ('Спортивное телосложение', 15), ('Карлик', 8), ('Уродливый', 8),
                ('Гигантизм', 5), ('Хвост кошки', 3), ('Хвост свиньи', 3),
                ('Пятачок', 3), ('Рога', 3), ('Три глаза', 1)
            ],
            'health_disease': [
                ('Полностью здоров', 30), ('Никогда не обследовался', 20),
                ('Непереносимость лактозы', 15), ('Плоскостопие', 10),
                ('Хроническая усталость', 8), ('Депрессия', 8),
                ('Хроническая бессонница', 8), ('Нет одного пальца', 5),
                ('Алопеция', 5), ('Аутизм', 3), ('Алкоголизм', 3),
                ('Три лишних пальца', 3), ('Немой', 2), ('Нет руки', 2),
                ('Нет ноги', 2), ('Шизофрения', 2), ('Раздвоение личности', 2),
                ('Парализован ниже пояса', 1), ('Лимфома', 1), ('Лейкемия', 1),
                ('Болезнь Альцгеймера', 1)
            ],
            'phobias': [
                'Андрофобия - боязнь мужчин', 'Арахнофобия - боязнь пауков'
            ],
            'hobbies': [
                'Квадробика', 'Хоббихорсинг', 'Пайка микросхем', 'Рукоделие',
                'Вязание', 'Стрельба из лука', 'Плаванье', 'Бокс', 'Вольная борьба'
            ],
            'facts': [
                'Утверждает что был укушен зомби', 'Телепат', 'Читает мысли',
                'Гений', 'Ушел после 6 класса', 'Не умеет читать',
                'Хрюкает как свинья когда смеётся', 'Моется раз в две недели',
                'Не смывает за собой в туалете', 'Женоненавистник',
                'Мужененавистник', 'Сексист', 'Сидел в тюрьме',
                'Серийный убийца', 'Извращенец', 'Раньше снимался в порно'
            ],
            'baggage': [
                'Белая разумная свинья', 'Мини электростанция', 'Фильтр для воды',
                'Аптечка первой помощи', 'Лекарства от вирусных заболеваний',
                'Противогазы', 'Пистолет без патронов', 'Бронежилет',
                'Пояс верности', 'Чемодан набитый дошираком', '20 килограмм риса'
            ],
            'special_cards': [
                'Поменяйся карточками фактов с любым неизгнанным игроком с открытой картой факта'
            ],
            'scenarios': [
                'Зомби-апокалипсис',
                'Нашествие разумных свиней',
                'Вирусная пандемия'
            ],
            'scenario_descriptions': {
                'Зомби-апокалипсис': 'В мире появился новый вирус который начал распространяться через телеграмм канал "no nuance confessions" все кто видели хоть пару строчек оттуда превращались в безмозглых зомби, время от времени говорящих что то про трансгендеров и инцест. Правительство пыталось заблокировать этот канал и запретить приложение "Telegram" но попытки были тщетны. Люди заражались и от укусов этих зомби что привело к ужасному Апокалипсису. Выберетесь из бункера и создайте вакцину, которая сможет спасти пострадавших.',
                'Нашествие разумных свиней': 'В ходе магического ритуала древнего колдуна Евгения открылся портал с разумными белыми свиньями-людоедами. Полчище голодных, уродливых животных заполонило мир и стало стремительно пожирать человечество. Свиньи проявили невероятные интеллектуальные способности для скота: благодаря гениальным стратегиям, учитывавшим уровень военной подготовки стран, они разбили войска, полностью уничтожили армию, спецслужбы и полицию, подорвали военные базы. В результате почти всё население было стёрто с лица Земли. Вам удалось спрятаться в бункере. Выберитесь из убежища, очистите Землю от этих адских созданий и заново постройте могущественную цивилизацию.',
                'Вирусная пандемия': 'Подписчики Telegram-канала "No Nuance Confessions" решили начать ставить опасные эксперименты над собой, чтобы воплотить свои мнения в реальность и стать максимально уникальными. Однако по своей неосторожности они создали новый вирус: каждый из них начал превращаться в олицетворение своих «мнений», закреплённых в тейках. Например, Сейзук, который писал о том, что пердеть в общественных местах — это норма, сам стал постоянно вонять из-за непрекращающегося пердежа на публике. Другой участник, поддерживающий трансгендерность в своих тейках, сам превратился в транса: вместо пениса у него выросла вагина, а на груди появились женские признаки. Ваша задача — остановить распространение вируса и создать лекарство для его нейтрализации.'
            },
            'events': [
                {'type': 'помеха', 'name': 'Короткое замыкание',
                 'description': 'Провода на секунду вспыхнули в дальнем углу бункера рядом с автоматической системой очистки воздуха. Уже чувствуется запах гари. Нужно срочно что-то предпринять, иначе все задохнутся.'},
                {'type': 'помеха', 'name': 'Чумная крыса',
                 'description': 'На складе с зерном вы обнаружили серую крысу. Она очень дружелюбная и любит ласку, легко поддаётся дрессировке. Через три дня после контакта с ней у вас началась лихорадка и озноб.'},
                {'type': 'припасы', 'name': 'Блины',
                 'description': 'Вкусные свежие блины были оставлены на кухне неизвестной персоной. Рядом с тарелкой записка: "С любовью, Диана". Если съесть блины, это поможет растянуть имеющиеся запасы на год и немного порадовать себя.'},
                {'type': 'припасы', 'name': 'Боеприпасы',
                 'description': 'Пистолет и патроны лежат в коробке из-под обуви. В случае крайней необходимости это поможет вам обезопасить себя.'},
                {'type': 'комната', 'name': 'Криокапсулы',
                 'description': 'Вы нашли три криокапсулы в секретной комнате. Можно прилечь и поспать в них на год, чтобы скоротать время.'},
                {'type': 'комната', 'name': 'Игровая комната',
                 'description': 'Просторная комната с дюжиной стеллажей, заполненных настольными, компьютерными и азартными играми. Вам точно не будет скучно.'}
            ]
        }

        # Пытаемся загрузить из файлов
        cards_data = {}
        for category, default_list in default_cards.items():
            file_path = os.path.join(CARDS_DIR, f'{category}.json')

            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        cards_data[category] = json.load(f)
                else:
                    cards_data[category] = default_list
                    # Сохраняем дефолтные данные
                    self._save_cards_category(category, default_list)
            except Exception as e:
                logger.error(f"Ошибка загрузки {category}: {e}")
                cards_data[category] = default_list

        return cards_data

    def _save_cards_category(self, category: str, cards: List[str]):
        """Сохраняет категорию карточек"""
        try:
            file_path = os.path.join(CARDS_DIR, f'{category}.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(cards, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения {category}: {e}")

    def create_game(self, chat_id: int, admin_id: int) -> bool:
        """Создает новую игру"""
        if chat_id in self.games:
            return False

        self.games[chat_id] = Game(chat_id, admin_id)

        # ДОБАВЛЕНО: пытаемся загрузить существующие карточки
        self.load_player_cards(chat_id)

        logger.info(f"Создана игра в чате {chat_id}")
        return True

    def join_game(self, chat_id: int, user_id: int, username: str, first_name: str) -> bool:
        """Присоединяет игрока к игре"""
        if chat_id not in self.games:
            return False

        game = self.games[chat_id]
        if game.phase != GamePhase.LOBBY:
            return False

        return game.add_player(user_id, username, first_name)

    def leave_game(self, chat_id: int, user_id: int) -> bool:
        """Игрок покидает игру"""
        if chat_id not in self.games:
            return False

        game = self.games[chat_id]
        return game.remove_player(user_id)

    def start_game(self, chat_id: int, user_id: int) -> bool:
        """Начинает игру"""
        if chat_id not in self.games:
            return False

        game = self.games[chat_id]

        # Проверяем права админа
        if user_id != game.admin_id:
            return False

        # Проверяем возможность начала
        if not game.can_start():
            return False

        # Генерируем персонажей
        for player in game.players.values():
            player.generate_character(self.cards_data)

        # Генерируем сценарий
        game.scenario, game.bunker_info = game.generate_scenario(
            self.cards_data.get('scenarios', [])
        )

        # Сохраняем описание сценария
        game.scenario_description = self.cards_data.get('scenario_descriptions', {}).get(game.scenario,
                                                                                         "Описание недоступно")

        # Отправляем краткое название сценария
        try:
            self.bot.send_message(
                chat_id,
                f"🌍 **Сценарий катастрофы:** {game.scenario}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки названия сценария: {e}")

        # Отправляем полное описание сценария отдельно
        try:
            self.bot.send_message(
                chat_id,
                f"📖 **Полное описание сценария:**\n\n{game.scenario_description}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки описания сценария: {e}")

        try:
            pin_message = self.bot.send_message(
                chat_id,
                "📌 **Игра началась!** Следите за обновлениями в этом сообщении.",
                parse_mode='Markdown'
            )
            try:
                self.bot.pin_chat_message(chat_id, pin_message.message_id)
                game.pin_message_id = pin_message.message_id
            except Exception as pin_error:
                logger.warning(f"Не удалось закрепить сообщение: {pin_error}")
                # Продолжаем без закрепления
        except Exception as e:
            logger.error(f"Ошибка создания сообщения игры: {e}")

        # Отправляем персонажей игрокам в ЛС
        self._send_characters_to_players(chat_id)

        # Переходим к первому раунду раскрытия карт (только профессии)
        self._start_card_reveal_phase(chat_id, 1)
        return True

    def _start_role_study_phase(self, chat_id: int):
        """Начинает фазу изучения ролей"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        game.phase = GamePhase.ROLE_STUDY

        duration = GAME_SETTINGS['ROLE_STUDY_TIME']

        # Отправляем сообщения игрокам
        self._send_phase_message(chat_id, "🎭 Фаза изучения ролей началась!", duration)

        # Сначала отправляем все карточки
        self._send_characters_to_players(chat_id)

        # Добавляем задержку перед запуском таймеров, чтобы все карточки успели дойти
        def start_timers():
            self.phase_timer.start_phase_timer(chat_id, "role_study", duration)
            self.notification_timer.schedule_phase_warnings(chat_id, "изучения ролей", duration)

        threading.Timer(5, start_timers).start()



    def _start_voting_phase(self, chat_id: int):
        """Начинает фазу голосования"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        game.phase = GamePhase.VOTING

        # Сбрасываем голоса
        for player in game.players.values():
            player.reset_vote()

        # Показываем открытые карты перед голосованием
        self._show_revealed_cards_summary(chat_id)

        vote_text = "🗳️ **Фаза голосования началась!**\n\n"
        vote_text += "Голосуйте против тех, кто НЕ должен попасть в бункер."

        from keyboards import get_voting_inline_keyboard
        keyboard = get_voting_inline_keyboard(chat_id)

        try:
            self.bot.send_message(
                chat_id,
                vote_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения о голосовании: {e}")

        duration = GAME_SETTINGS['VOTING_TIME']
        self.phase_timer.start_phase_timer(chat_id, "voting", duration)

    def _start_results_phase(self, chat_id: int):
        """Начинает фазу результатов"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        game.phase = GamePhase.RESULTS

        # Отмечаем что первое голосование завершено
        if not hasattr(game, 'first_voting_completed'):
            game.first_voting_completed = True

        # Подсчитываем голоса
        self._count_votes(chat_id)

        # Определяем исключенных
        self._eliminate_players(chat_id)

        # Отправляем результаты
        self._send_voting_results(chat_id)

        duration = GAME_SETTINGS['RESULTS_TIME']

        # Проверяем окончание игры
        if self._check_game_end(chat_id):
            self._finish_game(chat_id)
        else:
            # ДОБАВЛЕНО: повторно отправляем меню после голосования
            self._resend_menus_after_voting(chat_id)

            self.phase_timer.start_phase_timer(chat_id, "results", duration)

    def _count_votes(self, chat_id: int):
        """Подсчитывает голоса"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        votes_count: Dict[int, int] = {}

        # Инициализируем счетчики
        for player in game.get_alive_players():
            votes_count[player.user_id] = 0

        # Подсчитываем голоса
        for player in game.get_alive_players():
            if player.vote_target and player.vote_target in votes_count:
                # Проверяем двойной голос
                vote_power = 2 if hasattr(player, 'double_vote_active') and player.double_vote_active else 1
                votes_count[player.vote_target] += vote_power

        # Сохраняем результаты
        game.voting_results = votes_count

        # Обновляем счетчики игроков
        for user_id, count in votes_count.items():
            if user_id in game.players:
                game.players[user_id].votes_received = count

    def _eliminate_players(self, chat_id: int):
        """Исключает игроков с наибольшим количеством голосов"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        if not game.voting_results:
            return

        # Находим максимальное количество голосов
        max_votes = max(game.voting_results.values())

        if max_votes == 0:
            return

        # Находим игроков с максимальным количеством голосов
        candidates_for_elimination = []
        for user_id, votes in game.voting_results.items():
            if votes == max_votes:
                candidates_for_elimination.append(user_id)

        # НОВОЕ: проверяем на ничью
        if len(candidates_for_elimination) > 1:
            # Ничья - никого не исключаем
            try:
                candidates_names = []
                for user_id in candidates_for_elimination:
                    if user_id in game.players:
                        candidates_names.append(game.players[user_id].get_display_name())

                self._send_message_with_delay_and_image(
                    chat_id,
                    f"🤝 **НИЧЬЯ!** Игроки {', '.join(candidates_names)} получили равное количество голосов ({max_votes}) и остаются в игре.",
                    'results',
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления о ничьей: {e}")
            return

        # Исключаем единственного игрока с максимальным количеством голосов
        user_id = candidates_for_elimination[0]
        if user_id in game.players:
            player = game.players[user_id]

            # Проверяем иммунитет и спец. защиту
            if hasattr(player, 'has_immunity') and player.has_immunity:
                player.has_immunity = False
                try:
                    self._send_message_with_delay_and_image(
                        chat_id,
                        f"🛡️ {player.get_display_name()} защищен иммунитетом!",
                        'results'
                    )
                except:
                    pass
            elif hasattr(player, 'pig_immunity') and player.pig_immunity:
                try:
                    self._send_message_with_delay_and_image(
                        chat_id,
                        f"🐷 {player.get_display_name()} защищен свиным иммунитетом!",
                        'results'
                    )
                except:
                    pass
            else:
                # Проверяем месть при изгнании
                if hasattr(player, 'revenge_active') and player.revenge_active:
                    # Логика мести
                    pass

                if player.eliminate():
                    game.eliminated_players.append(user_id)

    def use_special_card(self, chat_id: int, user_id: int, target_id: int = None) -> dict:  # new
        """Использование специальной карточки"""
        if chat_id not in self.games:
            return {"success": False, "message": "Игра не найдена"}

        game = self.games[chat_id]
        if user_id not in game.players:
            return {"success": False, "message": "Игрок не найден"}

        player = game.players[user_id]
        target_player = game.players.get(target_id) if target_id else None

        return player.use_special_card(game, self.bot, target_player)


    def _check_game_end(self, chat_id: int) -> bool:
        """Проверяет окончание игры"""
        if chat_id not in self.games:
            return True

        game = self.games[chat_id]
        alive_players = game.get_alive_players()

        # Извлекаем количество мест из описания бункера
        bunker_slots = self._extract_bunker_slots(game.bunker_info)

        # Игра заканчивается, если осталось игроков <= количества мест
        return len(alive_players) <= bunker_slots


    def _extract_bunker_slots(self, bunker_info: str) -> int:
        """Извлекает количество мест в бункере"""
        import re
        match = re.search(r'(\d+)\s+(?:человек|мест)', bunker_info)
        return int(match.group(1)) if match else 1


    def _finish_game(self, chat_id: int):
        """Завершает игру"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        game.phase = GamePhase.FINISHED

        # Определяем победителей
        game.winners = [p.user_id for p in game.get_alive_players()]

        # Отправляем финальное сообщение
        self._send_final_results(chat_id)

        # Останавливаем таймеры
        self.phase_timer.stop_phase_timer(chat_id)

        # Удаляем игру через некоторое время
        threading.Timer(300, self._cleanup_game, args=[chat_id]).start()  # 5 минут

    def _cleanup_game(self, chat_id: int):
        """Очищает завершенную игру"""
        if chat_id in self.games:
            # ДОБАВЛЕНО: удаляем файл карточек
            self.delete_player_cards(chat_id)

            del self.games[chat_id]
            logger.info(f"Игра в чате {chat_id} удалена")

    def _send_phase_message(self, chat_id: int, message: str, duration: int):
        """Отправляет сообщение о фазе"""
        try:
            time_text = f"⏱️ Время: {duration // 60}:{duration % 60:02d}"
            full_message = f"{message}\n\n{time_text}"

            # Убираем проблемную клавиатуру пока что
            # from keyboards import get_cards_menu_inline_keyboard
            # keyboard = get_cards_menu_inline_keyboard(chat_id)

            self.bot.send_message(
                chat_id,
                full_message,
                # reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения о фазе: {e}")

    def _send_message_with_delay_and_image(self, chat_id: int, text: str, image_key: str = None, **kwargs):
        """Отправляет сообщение с возможным изображением"""

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

    def _send_characters_to_players(self, chat_id: int):
        """Отправляет персонажей игрокам"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        for player in game.players.values():
            try:
                character_text = f"🎭 **Ваш персонаж:**\n\n"
                character_text += player.get_character_info(show_all=True)
                character_text += f"\n\n💡 Используйте кнопки для раскрытия карточек в общем чате."

                self.bot.send_message(player.user_id, character_text)
            except Exception as e:
                # Если не можем отправить в ЛС, отправляем в общий чат
                logger.warning(f"Не удалось отправить персонажа в ЛС {player.user_id}: {e}")
                try:
                    mention = f"@{player.username}" if player.username else player.first_name
                    character_text = f"🎭 **Персонаж для {mention}:**\n\n"
                    character_text += player.get_character_info(show_all=True)
                    self.bot.send_message(chat_id, character_text)
                except Exception as e2:
                    logger.error(f"Ошибка отправки персонажа в чат: {e2}")

    def _send_voting_results(self, chat_id: int):
        """Отправляет результаты голосования с логикой переголосования"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        # Сортируем по количеству голосов (только тех, за кого голосовали)
        voted_results = {uid: votes for uid, votes in game.voting_results.items() if votes > 0}

        if not voted_results:
            try:
                self.bot.send_message(chat_id, "📊 Никто не получил голосов. Переходим к следующей фазе.")
            except:
                pass
            return

        sorted_results = sorted(voted_results.items(), key=lambda x: x[1], reverse=True)

        results_text = "📊 **Результаты голосования:**\n\n"

        for user_id, votes in sorted_results:
            if user_id in game.players:
                player = game.players[user_id]
                results_text += f"{player.get_display_name()}: {votes} голос(ов)\n"

        # Проверяем на равенство голосов
        max_votes = max(voted_results.values())
        tied_players = [uid for uid, votes in voted_results.items() if votes == max_votes]

        if len(tied_players) > 1:
            # Переголосование
            results_text += f"\n🔄 **ПЕРЕГОЛОСОВАНИЕ!**\nРавное количество голосов. Голосование только между:"
            for uid in tied_players:
                if uid in game.players:
                    results_text += f"\n• {game.players[uid].get_display_name()}"

            # Устанавливаем флаг переголосования
            game.revote_candidates = tied_players
            game.is_revoting = True

        try:
            self._send_message_with_delay_and_image(
                chat_id,
                results_text,
                'results',  # изображение для результатов
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки результатов голосования: {e}")

    def _send_final_results(self, chat_id: int):
        """Отправляет финальные результаты"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        final_text = "🎉 **ИГРА ЗАВЕРШЕНА!**\n\n"
        final_text += f"🌍 Сценарий: {game.scenario}\n"
        final_text += f"🏠 {game.bunker_info}\n\n"

        final_text += "🏆 **Попали в бункер:**\n"
        for user_id in game.winners:
            if user_id in game.players:
                player = game.players[user_id]
                final_text += f"✅ {player.get_display_name()}\n"

        if game.eliminated_players:
            final_text += "\n💀 **Исключены:**\n"
            for user_id in game.eliminated_players:
                if user_id in game.players:
                    player = game.players[user_id]
                    final_text += f"❌ {player.get_display_name()}\n"

        final_text += "\n🎮 Спасибо за игру!"

        try:
            self._send_message_with_delay_and_image(
                chat_id,
                final_text,
                'game_end'  # изображение окончания игры
            )
        except Exception as e:
            logger.error(f"Ошибка отправки финальных результатов: {e}")

    def on_phase_timeout(self, chat_id: int, phase: str):
        """Обработчик истечения времени фазы"""
        try:
            logger.info(f"Таймаут фазы {phase} в чате {chat_id}")

            if phase == "role_study":
                threading.Timer(5, self._start_discussion_phase, args=[chat_id]).start()
            elif phase == "discussion":
                threading.Timer(5, self._start_voting_phase, args=[chat_id]).start()
            elif phase == "voting":
                threading.Timer(5, self._start_results_phase, args=[chat_id]).start()
            elif phase == "results":
                threading.Timer(5, self._start_discussion_phase, args=[chat_id]).start()

        except Exception as e:
            logger.error(f"Ошибка в обработчике таймаута: {e}")

    def vote_player(self, chat_id: int, voter_id: int, target_id: int) -> bool:
        """Игрок голосует против другого игрока"""
        if chat_id not in self.games:
            return False

        game = self.games[chat_id]

        if game.phase != GamePhase.VOTING:
            return False

        if voter_id not in game.players or target_id not in game.players:
            return False

        voter = game.players[voter_id]
        target = game.players[target_id]

        if not voter.is_alive or not target.is_alive:
            return False

        return voter.vote(target_id)

        success = voter.vote(target_id)

        if success:
            # ДОБАВЛЕНО: автосохранение после голосования
            self.save_player_cards(chat_id)

        return success

    def reveal_card(self, chat_id: int, user_id: int, card_type: str) -> bool:
        """Игрок раскрывает карточку"""
        if chat_id not in self.games:
            return False

        game = self.games[chat_id]
        if user_id not in game.players:
            return False

        # Проверяем очередь
        if game.current_turn_player_id and game.current_turn_player_id != user_id:
            return False

        # Проверяем фазу
        expected_phase = f"card_reveal_{game.current_card_phase}"
        if game.phase.value != expected_phase:
            return False

        # Проверка типа карты только для первой фазы
        if game.current_card_phase == 1 and card_type != "profession":
            return False

        success = game.players[user_id].reveal_card(card_type)

        if success:
            # ИЗМЕНЕНО: отмечаем что игрок завершил ход в этой фазе
            player = game.players[user_id]
            setattr(player, f'turn_completed_phase_{game.current_card_phase}', True)

            # Сохраняем изменения
            self.save_player_cards(chat_id)

            # Останавливаем таймер хода
            timer_id = f"turn_{chat_id}_{user_id}"
            self.phase_timer.timer.stop_timer(timer_id)

            # Проверяем завершение фазы
            if self._check_phase_completion(chat_id, game.current_card_phase):
                self._handle_card_phase_end(chat_id, game.current_card_phase)
            else:
                # Переходим к следующему игроку
                game.current_player_index += 1
                self._start_next_turn(chat_id, game.current_card_phase)

        return success

    def get_game_info(self, chat_id: int) -> Optional[str]:
        """Возвращает информацию об игре"""
        if chat_id not in self.games:
            return None

        game = self.games[chat_id]

        info = f"🎮 **Информация об игре**\n\n"
        info += f"📍 Фаза: {game.phase.value}\n"
        info += f"👥 Игроков: {len(game.players)}\n"
        info += f"💚 Живых: {len(game.get_alive_players())}\n"

        if game.scenario:
            info += f"🌍 Сценарий: {game.scenario}\n"

        if game.bunker_info:
            info += f"🏠 Бункер: {game.bunker_info}\n"

        return info


    def get_players_list(self, chat_id: int) -> Optional[str]:
        """Возвращает список игроков"""
        if chat_id not in self.games:
            return None

        game = self.games[chat_id]

        if not game.players:
            return "Нет игроков"

        players_text = "👥 **Игроки:**\n\n"

        for i, player in enumerate(game.players.values(), 1):
            status = "👑" if player.is_admin else "👤"
            alive_status = "💚" if player.is_alive else "💀"
            players_text += f"{i}. {status} {alive_status} {player.get_display_name()}\n"

        return players_text


    # Методы для управления карточками админом
    def add_card(self, category: str, card_text: str) -> bool:
        """Добавляет карточку в категорию"""
        try:
            if category not in self.cards_data:
                self.cards_data[category] = []

            if card_text not in self.cards_data[category]:
                self.cards_data[category].append(card_text)
                self._save_cards_category(category, self.cards_data[category])
                return True

        except Exception as e:
            logger.error(f"Ошибка добавления карточки: {e}")

        return False

    def remove_card(self, category: str, card_text: str) -> bool:
        """Удаляет карточку из категории"""
        try:
            if category in self.cards_data and card_text in self.cards_data[category]:
                self.cards_data[category].remove(card_text)
                self._save_cards_category(category, self.cards_data[category])
                return True
        except Exception as e:
            logger.error(f"Ошибка удаления карточки: {e}")

        return False


    def get_cards_list(self, category: str) -> Optional[List[str]]:
        """Возвращает список карточек категории"""
        return self.cards_data.get(category, None)


    def _get_voting_phases(self) -> List[str]:
        """Возвращает фазы с голосованием"""
        return ["card_reveal_2", "card_reveal_3", "card_reveal_6", "card_reveal_7"]


    def _should_have_voting(self, phase: str, player_count: int) -> bool:
        """Определяет нужно ли голосование в данной фазе"""
        voting_phases = {
            "card_reveal_2": True,
            "card_reveal_3": True,
            "card_reveal_5": player_count >= 6,
            "card_reveal_6": player_count >= 8,
            "card_reveal_7": player_count >= 10,
        }
        return voting_phases.get(phase, False)


    def _calculate_voting_rounds(self, player_count: int, phase: str) -> int:
        """Рассчитывает количество раундов голосования"""
        if phase == "card_reveal_7":
            if player_count >= 16:
                return 3
            elif player_count >= 12:
                return 2
            elif player_count >= 10:
                return 1
        return 1

    def _start_card_reveal_phase(self, chat_id: int, card_number: int):
        """Начинает фазу раскрытия карточек с поочерёдностью"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        phase_name = f"card_reveal_{card_number}"
        game.phase = GamePhase(phase_name)
        game.current_card_phase = card_number

        # Показываем событие перед каждым раскрытием карт
        self._show_random_event(chat_id)

        # ИЗМЕНЕНО: универсальное сообщение после первой фазы
        if card_number == 1:
            message = f"🎴 **Фаза раскрытия: 💼 Профессия**\n\n"
            message += "Игроки будут раскрывать профессии по очереди."
        else:
            message = f"🎴 **Фаза раскрытия карточек #{card_number}**\n\n"
            message += "Игроки раскрывают карточки по своему выбору."

        # Инициализируем систему очерёдности
        alive_players = game.get_alive_players()
        if not game.players_order or game.current_card_phase == 1:
            game.players_order = alive_players.copy()
            random.shuffle(game.players_order)
            game.current_player_index = 0

        # Добавляем кнопку для перехода в бота
        from keyboards import get_cards_menu_inline_keyboard
        keyboard = get_cards_menu_inline_keyboard(chat_id)

        try:
            self._send_message_with_delay_and_image(
                chat_id,
                message,
                'card_reveal',  # ключ изображения
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения фазы: {e}")

        self._update_pin_message(chat_id, message)

        # Запускаем первый ход
        self._start_next_turn(chat_id, card_number)

    def _start_next_turn(self, chat_id: int, card_number: int):
        """Начинает ход следующего игрока"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        alive_players = game.get_alive_players()

        # Логика поиска следующего игрока (без изменений)
        current_card_types = {
            1: "profession", 2: "biology", 3: "health",
            4: "phobia", 5: "hobby", 6: "fact", 7: "baggage"
        }

        card_type = current_card_types.get(card_number, "profession")

        available_players = []
        for player in alive_players:
            if (not player.character.revealed_cards.get(card_type, False) and
                    not getattr(player, f'abstained_card_{card_type}', False)):
                available_players.append(player)

        if not available_players:
            self._handle_card_phase_end(chat_id, card_number)
            return

        # Находим следующего игрока
        next_player = None
        for i in range(game.current_player_index, len(game.players_order)):
            if game.players_order[i] in available_players:
                next_player = game.players_order[i]
                game.current_player_index = i
                break

        if not next_player:
            for i in range(0, game.current_player_index):
                if game.players_order[i] in available_players:
                    next_player = game.players_order[i]
                    game.current_player_index = i
                    break

        if not next_player:
            next_player = available_players[0]
            game.current_player_index = game.players_order.index(
                next_player) if next_player in game.players_order else 0

        game.current_turn_player_id = next_player.user_id
        game.turn_started_at = time.time()

        # ИЗМЕНЕНО: только кнопка в чате
        if card_number == 1:
            turn_message = f"🎯 **Очередь:** {next_player.get_display_name()}\nРаскройте профессию"
        else:
            turn_message = f"🎯 **Очередь:** {next_player.get_display_name()}"

        from keyboards import get_cards_menu_inline_keyboard
        keyboard = get_cards_menu_inline_keyboard(chat_id)

        try:
            self._send_message_with_delay_and_image(
                chat_id,
                turn_message,
                None,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения хода: {e}")

        # ИЗМЕНЕНО: отправляем уведомление в ЛС только о том, что очередь
        user_id = next_player.user_id
        try:
            if card_number == 1:
                notify_text = f"⏰ **Ваша очередь!** Раскройте профессию за {GAME_SETTINGS['TURN_TIMEOUT']} секунд"
            else:
                notify_text = f"⏰ **Ваша очередь!** Раскройте карту за {GAME_SETTINGS['TURN_TIMEOUT']} секунд"

            # Сохраняем ID уведомления для удаления
            turn_msg = self.bot.send_message(user_id, notify_text, parse_mode='Markdown')
            game.current_turn_message_id = turn_msg.message_id

        except Exception as e:
            logger.error(f"Ошибка уведомления об очереди: {e}")

        # Запускаем таймер на ход
        timer_id = f"turn_{chat_id}_{user_id}"
        self.phase_timer.timer.start_timer(
            timer_id,
            GAME_SETTINGS['TURN_TIMEOUT'],
            self._handle_turn_timeout,
            chat_id,
            card_number
        )

    def _resend_menus_after_voting(self, chat_id: int):
        """Повторно отправляет меню игрокам после голосования"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        for player in game.get_alive_players():
            try:
                from keyboards import get_cards_menu_inline_keyboard
                keyboard = get_cards_menu_inline_keyboard(chat_id)

                self.bot.send_message(
                    player.user_id,
                    "🎮 **Меню обновлено после голосования**\n\nИспользуйте кнопки для управления карточками:",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка повторной отправки меню игроку {player.user_id}: {e}")

    def _check_phase_completion(self, chat_id: int, card_number: int) -> bool:
        """Проверяет завершена ли фаза раскрытия карточек"""
        if chat_id not in self.games:
            return True

        game = self.games[chat_id]
        alive_players = game.get_alive_players()

        # Подсчитываем сколько игроков сделали ход в этой фазе
        players_completed = 0

        for player in alive_players:
            # Проверяем сделал ли игрок ход в этой фазе
            has_turn_completed = getattr(player, f'turn_completed_phase_{card_number}', False)

            if has_turn_completed:
                players_completed += 1

        # Фаза завершена когда все сделали ход
        return players_completed >= len(alive_players)

    def _handle_card_phase_end(self, chat_id: int, card_number: int):
        """Обрабатывает окончание фазы раскрытия карточки"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        alive_count = len(game.get_alive_players())
        phase_name = f"card_reveal_{card_number}"

        # Проверяем нужно ли голосование
        if self._should_have_voting(phase_name, alive_count):
            self._start_voting_phase(chat_id)
        else:
            # Переходим к следующей карточке или завершаем игру
            if card_number < 7 and not self._check_game_end(chat_id):
                self._start_card_reveal_phase(chat_id, card_number + 1)
            else:
                self._finish_game(chat_id)

    def _handle_results_end(self, chat_id: int):
        """Обрабатывает окончание фазы результатов"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        # Проверяем есть ли переголосование
        if hasattr(game, 'is_revoting') and game.is_revoting:
            # Логика переголосования
            pass
        else:
            # Переходим к следующей фазе или завершаем игру
            if self._check_game_end(chat_id):
                self._finish_game(chat_id)
            else:
                next_card = game.current_card_phase + 1
                if next_card <= 7:
                    self._start_card_reveal_phase(chat_id, next_card)
                else:
                    self._finish_game(chat_id)

    def _handle_turn_timeout(self, chat_id: int, card_number: int):
        """Обрабатывает истечение времени хода с автоматическим раскрытием"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        if game.current_turn_player_id:
            current_player = game.players.get(game.current_turn_player_id)
            if current_player:
                # ДОБАВЛЕНО: удаляем уведомление об очереди
                if hasattr(game, 'current_turn_message_id') and game.current_turn_message_id:
                    try:
                        self.bot.delete_message(game.current_turn_player_id, game.current_turn_message_id)
                        game.current_turn_message_id = None
                    except Exception as e:
                        logger.debug(f"Не удалось удалить сообщение очереди при таймауте: {e}")
                # Автоматически раскрываем карточку
                card_to_reveal = None

                if card_number == 1:
                    # Первая фаза - только профессия
                    if not current_player.character.revealed_cards.get('profession', False):
                        card_to_reveal = 'profession'
                else:
                    # Остальные фазы - случайная нераскрытая карточка
                    available_cards = []
                    card_types = ['profession', 'biology', 'health', 'phobia', 'hobby', 'fact', 'baggage']

                    for card_type in card_types:
                        if not current_player.character.revealed_cards.get(card_type, False):
                            available_cards.append(card_type)

                    if available_cards:
                        import random
                        card_to_reveal = random.choice(available_cards)

                # Раскрываем карточку
                if card_to_reveal and self.reveal_card(chat_id, game.current_turn_player_id, card_to_reveal):
                    # Получаем информацию о карточке для отправки в чат
                    character = current_player.character

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

                    card_name = card_names.get(card_to_reveal, card_to_reveal)
                    card_value = card_values.get(card_to_reveal, "Неизвестно")

                    try:
                        self._send_message_with_delay_and_image(
                            chat_id,
                            f"⏱️ Время истекло! Автоматически раскрыта карточка {current_player.get_display_name()}:\n**{card_name}**: {card_value}",
                            'card_reveal',
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки автораскрытия: {e}")
                else:
                    # Если нет карточек для раскрытия, просто отмечаем завершение хода
                    setattr(current_player, f'turn_completed_phase_{card_number}', True)
                    self.save_player_cards(chat_id)

                    try:
                        self.bot.send_message(
                            chat_id,
                            f"⏱️ Время истекло! {current_player.get_display_name()} пропустил ход."
                        )
                    except Exception as e:
                        logger.error(f"Ошибка уведомления о таймауте: {e}")

        # Проверяем завершение фазы
        if self._check_phase_completion(chat_id, card_number):
            self._handle_card_phase_end(chat_id, card_number)
        else:
            # Переходим к следующему игроку
            game.current_player_index += 1
            self._start_next_turn(chat_id, card_number)

    def _show_random_event(self, chat_id: int):
        """Показывает случайное событие"""
        events = self.cards_data.get('events', [])
        if events:
            event = random.choice(events)
            event_text = f"⚡ **СОБЫТИЕ: {event['name']}** ({event['type']})\n\n{event['description']}"

            try:
                self._send_message_with_delay_and_image(
                    chat_id,
                    event_text,
                    'event',  # изображение для события
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка отправки события: {e}")

    def _update_pin_message(self, chat_id: int, new_text: str):
        """Обновляет закрепленное сообщение"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]
        if hasattr(game, 'pin_message_id') and game.pin_message_id:
            try:
                self.bot.edit_message_text(
                    new_text,
                    chat_id,
                    game.pin_message_id,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.debug(f"Не удалось обновить закрепленное сообщение: {e}")

    def _show_revealed_cards_summary(self, chat_id: int):
        """Показывает сводку открытых карт перед голосованием"""
        if chat_id not in self.games:
            return

        game = self.games[chat_id]

        summary_text = "📋 **ОТКРЫТЫЕ КАРТЫ:**\n\n"

        for player in game.get_alive_players():
            if not player.character:
                continue

            player_info = f"**{player.get_display_name()}**\n"
            has_revealed_cards = False

            if player.character.revealed_cards.get('profession', False):
                player_info += f"💼 Профессия: {player.character.profession}\n"
                has_revealed_cards = True

            if player.character.revealed_cards.get('biology', False):
                player_info += f"👤 Биология: {player.character.gender} {player.character.age} лет\n"
                has_revealed_cards = True

            # ... остальные карты аналогично

            if has_revealed_cards:
                summary_text += player_info + "\n"

        try:
            self.bot.send_message(chat_id, summary_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка отправки сводки карт: {e}")

    def save_player_cards(self, chat_id: int):
        """Сохраняет карточки всех игроков в игре"""
        if chat_id not in self.games:
            return False

        try:
            game = self.games[chat_id]
            game_data = {
                'chat_id': chat_id,
                'phase': game.phase.value,
                'current_card_phase': getattr(game, 'current_card_phase', 1),
                'players': {}
            }

            for user_id, player in game.players.items():
                player_data = {
                    'user_id': user_id,
                    'username': player.username,
                    'first_name': player.first_name,
                    'is_alive': player.is_alive,
                    'is_admin': player.is_admin,
                    'votes_received': player.votes_received,
                    'has_voted': player.has_voted,
                    'vote_target': player.vote_target,
                    'special_card_used': getattr(player, 'special_card_used', False)
                }

                if player.character:
                    player_data['character'] = {
                        'profession': player.character.profession,
                        'gender': player.character.gender,
                        'age': player.character.age,
                        'body_type': player.character.body_type,
                        'disease': player.character.disease,
                        'phobia': player.character.phobia,
                        'hobby': player.character.hobby,
                        'fact': player.character.fact,
                        'baggage': player.character.baggage,
                        'special_card': player.character.special_card,
                        'special_card_id': getattr(player.character, 'special_card_id', ''),
                        'revealed_cards': player.character.revealed_cards.copy()
                    }

                    # Сохраняем информацию о воздержании
                    for card_type in ['profession', 'biology', 'health', 'phobia', 'hobby', 'fact', 'baggage']:
                        abstain_attr = f'abstained_card_{card_type}'
                        if hasattr(player, abstain_attr):
                            player_data[abstain_attr] = getattr(player, abstain_attr)

                game_data['players'][str(user_id)] = player_data

            # Сохраняем в файл
            filename = os.path.join(PLAYER_CARDS_DIR, f'game_{chat_id}.json')
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(game_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Карточки игроков для чата {chat_id} сохранены")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения карточек игроков: {e}")
            return False

    def load_player_cards(self, chat_id: int):
        """Загружает карточки игроков из файла"""
        try:
            filename = os.path.join(PLAYER_CARDS_DIR, f'game_{chat_id}.json')

            if not os.path.exists(filename):
                return False

            with open(filename, 'r', encoding='utf-8') as f:
                game_data = json.load(f)

            if chat_id not in self.games:
                return False

            game = self.games[chat_id]

            # Восстанавливаем данные игроков
            for user_id_str, player_data in game_data.get('players', {}).items():
                user_id = int(user_id_str)

                if user_id in game.players:
                    player = game.players[user_id]

                    # Восстанавливаем основные данные
                    player.is_alive = player_data.get('is_alive', True)
                    player.votes_received = player_data.get('votes_received', 0)
                    player.has_voted = player_data.get('has_voted', False)
                    player.vote_target = player_data.get('vote_target')
                    player.special_card_used = player_data.get('special_card_used', False)

                    # Восстанавливаем персонажа
                    if 'character' in player_data and player.character:
                        char_data = player_data['character']

                        player.character.profession = char_data.get('profession', '')
                        player.character.gender = char_data.get('gender', '')
                        player.character.age = char_data.get('age', 18)
                        player.character.body_type = char_data.get('body_type', '')
                        player.character.disease = char_data.get('disease', '')
                        player.character.phobia = char_data.get('phobia', '')
                        player.character.hobby = char_data.get('hobby', '')
                        player.character.fact = char_data.get('fact', '')
                        player.character.baggage = char_data.get('baggage', '')
                        player.character.special_card = char_data.get('special_card', '')

                        if 'special_card_id' in char_data:
                            player.character.special_card_id = char_data['special_card_id']

                        if 'revealed_cards' in char_data:
                            player.character.revealed_cards.update(char_data['revealed_cards'])

                    # Восстанавливаем информацию о воздержании
                    for card_type in ['profession', 'biology', 'health', 'phobia', 'hobby', 'fact', 'baggage']:
                        abstain_attr = f'abstained_card_{card_type}'
                        if abstain_attr in player_data:
                            setattr(player, abstain_attr, player_data[abstain_attr])

            logger.info(f"Карточки игроков для чата {chat_id} загружены")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки карточек игроков: {e}")
            return False

    def delete_player_cards(self, chat_id: int):
        """Удаляет файл с карточками игроков"""
        try:
            filename = os.path.join(PLAYER_CARDS_DIR, f'game_{chat_id}.json')
            if os.path.exists(filename):
                os.remove(filename)
                logger.info(f"Файл карточек для чата {chat_id} удален")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления файла карточек: {e}")
            return False

    def get_player_by_name(self, chat_id: int, name: str):
        """Находит игрока по имени (для использования в спецкарточках)"""
        if chat_id not in self.games:
            return None

        game = self.games[chat_id]
        name_lower = name.lower()

        for player in game.players.values():
            if (player.username and player.username.lower() == name_lower) or \
                    (player.first_name and player.first_name.lower() == name_lower):
                return player

        return None