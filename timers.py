# timers.py
import threading
import time
from typing import Dict, Callable, Optional
import logging

logger = logging.getLogger(__name__)

class GameTimer:
    """Таймер для игровых фаз"""
    
    def __init__(self):
        self.timers: Dict[str, threading.Timer] = {}
        self.active_timers: Dict[str, bool] = {}
    
    def start_timer(self, timer_id: str, duration: int, callback: Callable, *args, **kwargs):
        """Запускает таймер"""
        try:
            # Останавливаем существующий таймер если он есть
            self.stop_timer(timer_id)
            
            # Создаем новый таймер
            timer = threading.Timer(duration, self._timer_callback, 
                                  args=[timer_id, callback, args, kwargs])
            
            self.timers[timer_id] = timer
            self.active_timers[timer_id] = True
            timer.start()
            
            logger.info(f"Таймер {timer_id} запущен на {duration} секунд")
            
        except Exception as e:
            logger.error(f"Ошибка при запуске таймера {timer_id}: {e}")
    
    def stop_timer(self, timer_id: str) -> bool:
        """Останавливает таймер"""
        try:
            if timer_id in self.timers:
                self.timers[timer_id].cancel()
                del self.timers[timer_id]
                self.active_timers[timer_id] = False
                logger.info(f"Таймер {timer_id} остановлен")
                return True
        except Exception as e:
            logger.error(f"Ошибка при остановке таймера {timer_id}: {e}")
        return False
    
    def is_active(self, timer_id: str) -> bool:
        """Проверяет активность таймера"""
        return self.active_timers.get(timer_id, False)
    
    def _timer_callback(self, timer_id: str, callback: Callable, args: tuple, kwargs: dict):
        """Внутренний колбэк таймера"""
        try:
            self.active_timers[timer_id] = False
            if timer_id in self.timers:
                del self.timers[timer_id]
            
            # Вызываем колбэк
            callback(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Ошибка в колбэке таймера {timer_id}: {e}")
    
    def stop_all_timers(self):
        """Останавливает все таймеры"""
        timer_ids = list(self.timers.keys())
        for timer_id in timer_ids:
            self.stop_timer(timer_id)
    
    def get_remaining_time(self, timer_id: str) -> Optional[float]:
        """Возвращает оставшееся время таймера (приблизительно)"""
        # Это упрощенная реализация, для точного времени нужно хранить время старта
        return None

class PhaseTimer:
    """Специальный таймер для фаз игры"""
    
    def __init__(self, game_manager):
        self.game_manager = game_manager
        self.timer = GameTimer()
        self.phase_start_times: Dict[str, float] = {}
    
    def start_phase_timer(self, chat_id: int, phase: str, duration: int):
        """Запускает таймер фазы"""
        timer_id = f"phase_{chat_id}_{phase}"
        self.phase_start_times[timer_id] = time.time()
        
        self.timer.start_timer(
            timer_id, 
            duration,
            self._phase_timeout,
            chat_id, 
            phase
        )
    
    def stop_phase_timer(self, chat_id: int, phase: str = None):
        """Останавливает таймер фазы"""
        if phase:
            timer_id = f"phase_{chat_id}_{phase}"
            return self.timer.stop_timer(timer_id)
        else:
            # Останавливаем все таймеры для чата
            stopped = False
            for timer_id in list(self.timer.timers.keys()):
                if timer_id.startswith(f"phase_{chat_id}"):
                    self.timer.stop_timer(timer_id)
                    stopped = True
            return stopped
    
    def _phase_timeout(self, chat_id: int, phase: str):
        """Обработка истечения времени фазы"""
        try:
            logger.info(f"Истекло время фазы {phase} для чата {chat_id}")
            
            # Уведомляем game_manager о завершении фазы
            if hasattr(self.game_manager, 'on_phase_timeout'):
                self.game_manager.on_phase_timeout(chat_id, phase)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке таймаута фазы {phase}: {e}")
    
    def get_phase_remaining_time(self, chat_id: int, phase: str) -> Optional[int]:
        """Возвращает оставшееся время фазы в секундах"""
        timer_id = f"phase_{chat_id}_{phase}"
        
        if timer_id in self.phase_start_times and self.timer.is_active(timer_id):
            elapsed = time.time() - self.phase_start_times[timer_id]
            # Нужно знать изначальную длительность фазы
            # Это упрощенная версия
            return max(0, 300 - int(elapsed))  # По умолчанию 5 минут
        
        return None
    
    def is_phase_active(self, chat_id: int, phase: str) -> bool:
        """Проверяет активность таймера фазы"""
        timer_id = f"phase_{chat_id}_{phase}"
        return self.timer.is_active(timer_id)

class NotificationTimer:
    """Таймер для уведомлений"""
    
    def __init__(self, bot):
        self.bot = bot
        self.timer = GameTimer()
    
    def schedule_notification(self, chat_id: int, message: str, delay: int):
        """Планирует уведомление"""
        timer_id = f"notification_{chat_id}_{int(time.time())}"
        
        self.timer.start_timer(
            timer_id,
            delay,
            self._send_notification,
            chat_id,
            message
        )
    
    def _send_notification(self, chat_id: int, message: str):
        """Отправляет уведомление"""
        try:
            self.bot.send_message(chat_id, message)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления в чат {chat_id}: {e}")

    def schedule_phase_warnings(self, chat_id: int, phase: str, total_time: int):
        """Планирует предупреждения о завершении фазы"""
        warnings = [
            (total_time // 2, f"⏰ До конца фазы '{phase}' осталось {total_time // 2} секунд"),
            (total_time - 60, "⏰ До конца фазы осталась 1 минута!")
        ]

        for delay, message in warnings:
            if delay > 0 and delay < total_time:
                self.schedule_notification(chat_id, message, delay)
