# config.py
import os

# Токен бота (получить у @BotFather)
BOT_TOKEN = os.getenv('BOT_TOKEN', '8317600716:AAED6tDCQ2O9WGmJrwG8mWc0BIS_km21le0')

# ID администраторов бота (можно несколько через запятую)
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '6156642056').split(',') if x.strip()]

# ID группы для кнопки возврата (оставьте пустым, чтобы отключить)
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID', '-1002924425942')) if os.getenv('GROUP_CHAT_ID', '0') != '0' else None

# Разрешенный чат для игры (если указан, бот работает только в нем)
ALLOWED_CHAT_ID = int(os.getenv('ALLOWED_CHAT_ID', '0')) if os.getenv('ALLOWED_CHAT_ID', '0') != '0' else None

# Задержка между сообщениями в группе (в секундах)
MESSAGE_DELAY = float(os.getenv('MESSAGE_DELAY', '5.0'))

# URL изображений для сообщений (оставьте пустыми чтобы отключить)
BOT_IMAGES = {
    'lobby': '/home/divargia/Рабочий стол/bnnkf-0.9.3/pics/Untitled120_20250829224044.png',  # Изображение для лобби
    'game_start': '/home/divargia/Рабочий стол/bnnkf-0.9.3/pics/IMG_20250830_230607_663.jpg',  # Изображение при начале игры
    'card_reveal': '/home/divargia/Рабочий стол/bnnkf-0.9.3/pics/voroniny_41789360_orig_-398726767.jpeg',  # Изображение при раскрытии карт
    'voting': '/home/divargia/Рабочий стол/bnnkf-0.9.3/pics/Screenshot_20250825_184901_TikTok.png',  # Изображение для голосования
    'results': '/home/divargia/Рабочий стол/bnnkf-0.9.3/pics/static-assets-upload1252707106506292399.jpg',  # Изображение результатов
    'game_end': '/home/divargia/Рабочий стол/bnnkf-0.9.3/pics/-2147483648_-213497.jpg',  # Изображение окончания игры
    'event': '/home/divargia/Рабочий стол/bnnkf-0.9.3/pics/-2147483648_-213499.jpg',  # Изображение для событий
}

# Настройки игры
GAME_SETTINGS = {
    'ALLOWED_PLAYERS': [2, 6, 8, 10, 12, 14, 16],
    'MIN_PLAYERS': 2,
    'MAX_PLAYERS': 16,
    'LOBBY_TIMEOUT': 300,
    'ROLE_STUDY_TIME': 60,
    'DISCUSSION_TIME': 60,
    'VOTING_TIME': 60,
    'RESULTS_TIME': 60,
    'CARD_REVEAL_TIME': 60,
    'TURN_TIMEOUT': 60,  # НОВОЕ: время на ход для раскрытия карты
    'SPECIAL_CARD_CHANCE': 0.2,
    'CARDS_TO_REVEAL': [1, 2, 3, 4, 5, 6, 7],
}

# Пути к файлам
DATA_DIR = 'data'
CARDS_DIR = os.path.join(DATA_DIR, 'cards')
PLAYER_CARDS_DIR = os.path.join(DATA_DIR, 'player_cards')  # НОВОЕ

# Создаем необходимые директории
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CARDS_DIR, exist_ok=True)
os.makedirs(PLAYER_CARDS_DIR, exist_ok=True)  # НОВОЕ

# Логирование
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'bunker_bot.log'
}