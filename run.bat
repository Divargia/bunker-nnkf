@echo off
chcp 65001 > nul
echo 🎮 Bunker RP Bot - Запуск
echo ========================

:: Проверяем Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не найден! Установите Python 3.7+
    pause
    exit /b 1
)

:: Проверяем зависимости
echo 📦 Проверка зависимостей...
python -c "import telebot" > nul 2>&1
if %errorlevel% neq 0 (
    echo 📥 Установка зависимостей...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ❌ Ошибка установки зависимостей!
        pause
        exit /b 1
    )
)

:: Проверяем конфигурацию
echo 🔍 Проверка конфигурации...
python main.py --check
if %errorlevel% neq 0 (
    echo ⚠️ Проблемы с конфигурацией. Проверьте config.py
    echo.
    echo 💡 Не забудьте указать:
    echo    - BOT_TOKEN (токен от @BotFather)
    echo    - ADMIN_ID (ваш Telegram ID)
    echo.
    pause
)

:: Запускаем бота
echo.
echo 🚀 Запуск бота...
python main.py
pause
