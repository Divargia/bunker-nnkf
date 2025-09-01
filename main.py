#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
▒▒▒▒██  ██
    ██        ГИТХАБ: https://github.com/Divargia
██████▒▒██    АВТОР: divargia
██  ██  ██    ТЕЛЕГРАМ: @divargia
██████  ██

Спасибо за сотрудничество, я куплю себе майнкрафт!
                     --@divargia 

у меня день до дедлайна, ниего не работает, спец карточки сломались, всё пошло по пизде, бэкенд зло, пайтон зло, invalid syntax нахуй блять
"""

import sys
import os
import logging
import time
from pathlib import Path

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BOT_TOKEN, ADMIN_IDS, DATA_DIR
from bot import BunkerBot

logger = logging.getLogger(__name__)


def check_environment():
    """Проверка окружения и конфигурации"""
    errors = []

    # Проверяем токен бота
    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        errors.append("❌ Не установлен токен бота. Укажите BOT_TOKEN в config.py или переменной окружения.")

    # Проверяем ID администратора
    if ADMIN_IDS == 123456789:
        errors.append("⚠️ Не установлен ID администратора. Укажите ADMIN_ID в config.py или переменной окружения.")

    # Проверяем права на запись
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        test_file = os.path.join(DATA_DIR, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except Exception as e:
        errors.append(f"❌ Нет прав на запись в директорию {DATA_DIR}: {e}")

    return errors


def main():
    """Основная функция"""
    try:
        print("🚀 Запуск Bunker RP Bot...")
        print("=" * 50)

        # Проверяем окружение
        errors = check_environment()
        if errors:
            print("⚠️ Обнаружены проблемы с конфигурацией:")
            for error in errors:
                print(f"  {error}")

            if any("❌" in error for error in errors):
                print("\n💥 Критические ошибки! Бот не может быть запущен.")
                return 1
            else:
                print("\n⚠️ Предупреждения обнаружены, но бот может работать.")
                time.sleep(3)

        # Создаем и запускаем бота
        bot = BunkerBot()
        print("✅ Бот успешно инициализирован")
        print(f"👑 ID администратора: {ADMIN_IDS}")
        print(f"📁 Директория данных: {DATA_DIR}")
        print("-" * 50)

        # Пробная отправка сообщения (если нужно)
        # bot.bot.send_message(ADMIN_IDS, "Бот успешно запущен!")

        # Запускаем бота
        bot.start_polling()

    except KeyboardInterrupt:
        print("\n⏹️ Получен сигнал остановки...")
        if 'bot' in locals():
            bot.stop()
        print("✅ Бот остановлен")
        return 0

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"\n💥 Критическая ошибка: {e}")
        return 1


def install_requirements():
    """Установка зависимостей"""
    try:
        import telebot
        print("✅ pyTelegramBotAPI установлен")
    except ImportError:
        print("❌ pyTelegramBotAPI не установлен")
        print("💡 Установите командой: pip install pyTelegramBotAPI")
        return False

    return True


def show_help():
    """Показ справaки"""
    help_text = """
🎮 Bunker RP Telegram Bot

📋 Использование:
  python main.py          - Запуск бота
  python main.py --help   - Эта справка
  python main.py --check  - Проверка конфигурации

⚙️ Настройка:
1. Получите токен бота у @BotFather
2. Укажите токен в config.py (BOT_TOKEN) или переменной окружения
3. Укажите ваш ID в config.py (ADMIN_ID)
4. Запустите бота: python main.py

📁 Структура файлов:
  main.py         - Точка входа
  config.py       - Конфигурация
  bot.py          - Основной класс бота
  game_manager.py - Игровая логика
  player.py       - Класс игрока
  handlers.py     - Обработчики команд
  keyboards.py    - Клавиатуры
  timers.py       - Система таймеров
  data/           - Данные бота
  data/cards/     - Карточки игры

🎯 Команды бота:
  /start - Главное меню
  /game  - Быстрое создание/присоединение к игре
  /help  - Справка
  /admin - Панель администратора (только для админа)
  /stop  - Остановить игру (админ игры)

🌐 Поддержка:
  - Создавайте игры в группах
  - Поддержка 3-8 игроков
  - Автоматические таймеры фаз
  - Система голосования
  - Настраиваемые карточки
"""
    print(help_text)


if __name__ == "__main__":
    # Обработка аргументов командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h', 'help']:
            show_help()
            sys.exit(0)
        elif sys.argv[1] in ['--check', '-c', 'check']:
            print("🔍 Проверка конфигурации...")
            errors = check_environment()

            if not errors:
                print("✅ Конфигурация корректна!")

                if install_requirements():
                    print("✅ Все зависимости установлены!")
                    print("🚀 Готов к запуску!")

            else:
                for error in errors:
                    print(f"  {error}")

            sys.exit(0)
        elif sys.argv[1] in ['--install', '-i', 'install']:
            print("📦 Проверка зависимостей...")
            install_requirements()
            sys.exit(0)

    # Проверяем зависимости перед запуском
    if not install_requirements():
        sys.exit(1)

    # Запускаем бота
    exit_code = main()
    sys.exit(exit_code)
