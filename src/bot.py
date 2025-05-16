import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
)
import pandas as pd

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    ADD_MED_NAME,
    ADD_MED_DOSAGE,
    ADD_MED_FORM,
    ADD_MED_FREQUENCY,
    ADD_MED_SCHEDULE,
    ADD_MED_DURATION,
    ADD_RELATIVE,
    SETTINGS,
) = range(8)

# Временное хранилище данных (в реальном проекте используйте базу данных)
user_data: Dict[int, Dict] = {}
medications: Dict[int, List[Dict]] = {}
relatives: Dict[int, List[str]] = {}

def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start - приветствие и основное меню."""
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        "Я бот 'Поддержка рядом', который поможет тебе следить за приемом лекарств.\n"
        "Выбери действие:",
        reply_markup=main_menu_keyboard(),
    )

def main_menu_keyboard():
    """Клавиатура главного меню."""
    keyboard = [
        [InlineKeyboardButton("Добавить лекарство", callback_data='add_med')],
        [InlineKeyboardButton("Мои лекарства", callback_data='my_meds')],
        [InlineKeyboardButton("Отчеты", callback_data='reports')],
        [InlineKeyboardButton("Настройки", callback_data='settings')],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_reports_keyboard():
    """Клавиатура для возврата в меню отчетов."""
    keyboard = [
        [InlineKeyboardButton("Назад к отчетам", callback_data='reports')],
        [InlineKeyboardButton("В главное меню", callback_data='back')],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_settings_keyboard():
    """Клавиатура для возврата в меню настроек."""
    keyboard = [
        [InlineKeyboardButton("Назад к настройкам", callback_data='settings')],
        [InlineKeyboardButton("В главное меню", callback_data='back')],
    ]
    return InlineKeyboardMarkup(keyboard)

def add_med_start(update: Update, context: CallbackContext) -> int:
    """Начало процесса добавления лекарства."""
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="Введите название лекарства:")
    return ADD_MED_NAME

def add_med_name(update: Update, context: CallbackContext) -> int:
    """Обработка названия лекарства."""
    context.user_data['med_name'] = update.message.text
    update.message.reply_text("Введите дозировку (например, 50 мг):")
    return ADD_MED_DOSAGE

def add_med_dosage(update: Update, context: CallbackContext) -> int:
    """Обработка дозировки лекарства."""
    context.user_data['med_dosage'] = update.message.text
    reply_keyboard = [['Таблетки', 'Капсулы'], ['Инъекции', 'Сироп'], ['Другое']]
    update.message.reply_text(
        "Выберите форму лекарства:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder='Форма лекарства'
        ),
    )
    return ADD_MED_FORM

def add_med_form(update: Update, context: CallbackContext) -> int:
    """Обработка формы лекарства."""
    context.user_data['med_form'] = update.message.text
    reply_keyboard = [['1 раз в день', '2 раза в день'], ['3 раза в день', 'По часам']]
    update.message.reply_text(
        "Выберите частоту приема:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder='Частота приема'
        ),
    )
    return ADD_MED_FREQUENCY

def add_med_frequency(update: Update, context: CallbackContext) -> int:
    """Обработка частоты приема."""
    frequency = update.message.text
    context.user_data['med_frequency'] = frequency
    
    if frequency == 'По часам':
        update.message.reply_text("Введите время приема через запятую (например, 8:00, 14:00, 20:00):")
        return ADD_MED_SCHEDULE
    else:
        # Для стандартных вариантов устанавливаем расписание автоматически
        if frequency == '1 раз в день':
            context.user_data['med_schedule'] = ['9:00']
        elif frequency == '2 раза в день':
            context.user_data['med_schedule'] = ['9:00', '21:00']
        elif frequency == '3 раза в день':
            context.user_data['med_schedule'] = ['9:00', '14:00', '21:00']
        
        return ask_med_duration(update, context)

def add_med_schedule(update: Update, context: CallbackContext) -> int:
    """Обработка пользовательского расписания."""
    times = [t.strip() for t in update.message.text.split(',')]
    context.user_data['med_schedule'] = times
    return ask_med_duration(update, context)

def ask_med_duration(update: Update, context: CallbackContext) -> int:
    """Запрос продолжительности курса."""
    reply_keyboard = [['До конца упаковки', 'Несколько дней'], ['Бессрочно']]
    update.message.reply_text(
        "Продолжительность курса:",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder='Продолжительность'
        ),
    )
    return ADD_MED_DURATION

def add_med_duration(update: Update, context: CallbackContext) -> int:
    """Обработка продолжительности курса."""
    duration = update.message.text
    context.user_data['med_duration'] = duration
    
    if duration == 'Несколько дней':
        update.message.reply_text("Введите количество дней:")
        return ADD_MED_DURATION  # Здесь нужно добавить обработку количества дней
    else:
        return save_medication(update, context)

def save_medication(update: Update, context: CallbackContext) -> int:
    """Сохранение лекарства и завершение процесса."""
    user_id = update.effective_user.id
    med_data = context.user_data
    
    # Создаем запись о лекарстве
    medication = {
        'name': med_data['med_name'],
        'dosage': med_data['med_dosage'],
        'form': med_data['med_form'],
        'frequency': med_data['med_frequency'],
        'schedule': med_data['med_schedule'],
        'duration': med_data['med_duration'],
        'created_at': datetime.now(),
        'last_taken': None,
        'history': [],
    }
    
    # Добавляем в хранилище
    if user_id not in medications:
        medications[user_id] = []
    medications[user_id].append(medication)
    
    # Очищаем временные данные
    context.user_data.clear()
    
    update.message.reply_text(
        "Лекарство успешно добавлено!",
        reply_markup=main_menu_keyboard(),
    )
    
    # Запускаем напоминания
    schedule_reminders(context, user_id, medication)
    
    return ConversationHandler.END

def schedule_reminders(context: CallbackContext, user_id: int, medication: Dict):
    """Планирование напоминаний для лекарства."""
    for time_str in medication['schedule']:
        # Парсим время
        hour, minute = map(int, time_str.split(':'))
        
        # Создаем задание для каждого дня
        context.job_queue.run_daily(
            send_reminder,
            time=datetime.time(hour=hour, minute=minute),
            days=(0, 1, 2, 3, 4, 5, 6),
            context={'user_id': user_id, 'med_name': medication['name']},
        )

def send_reminder(context: CallbackContext):
    """Отправка напоминания о приеме лекарства."""
    job = context.job
    user_id = job.context['user_id']
    med_name = job.context['med_name']
    
    # Проверяем, включены ли уведомления
    notifications_enabled = context.user_data.get('notifications_enabled', True)
    if not notifications_enabled:
        return  # Если уведомления выключены, не отправляем напоминание
    
    # Ищем лекарство
    user_meds = medications.get(user_id, [])
    medication = next((m for m in user_meds if m['name'] == med_name), None)
    
    if medication:
        # Создаем клавиатуру для подтверждения
        keyboard = [
            [InlineKeyboardButton("Я принял(а) лекарство", callback_data=f'taken_{med_name}')],
            [InlineKeyboardButton("Отложить напоминание (10 мин)", callback_data=f'snooze_{med_name}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение
        context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ Напоминание: примите {medication['name']} {medication['dosage']}",
            reply_markup=reply_markup,
        )
        
        # Запланировать проверку подтверждения
        context.job_queue.run_once(
            check_confirmation,
            when=30*60,  # 30 минут
            context={'user_id': user_id, 'med_name': med_name},
        )

def check_confirmation(context: CallbackContext):
    """Проверка, подтвержден ли прием."""
    job = context.job
    user_id = job.context['user_id']
    med_name = job.context['med_name']
    
    # Проверяем, было ли подтверждение
    user_meds = medications.get(user_id, [])
    medication = next((m for m in user_meds if m['name'] == med_name), None)
    
    if medication and not medication['last_taken']:
        # Если не подтверждено, отправляем уведомление родственникам
        notify_relatives(context, user_id, med_name)
        
        # Добавляем запись о пропуске
        medication['history'].append({
            'date': datetime.now(),
            'status': 'пропущен',
        })

def notify_relatives(context: CallbackContext, user_id: int, med_name: str):
    """Уведомление доверенных лиц о пропуске приема."""
    if user_id in relatives:
        for relative_username in relatives[user_id]:
            try:
                context.bot.send_message(
                    chat_id=relative_username,
                    text=f"⚠️ Пользователь не подтвердил прием {med_name} в назначенное время!",
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить {relative_username}: {e}")

def button_handler(update: Update, context: CallbackContext) -> None:
    """Обработчик нажатий на кнопки."""
    query = update.callback_query
    query.answer()
    
    if query.data.startswith('taken_'):
        # Подтверждение приема лекарства
        med_name = query.data[6:]
        confirm_intake(update, context, med_name)
    elif query.data.startswith('snooze_'):
        # Отложить напоминание
        med_name = query.data[7:]
        snooze_reminder(update, context, med_name)
    elif query.data == 'add_med':
        add_med_start(update, context)
    elif query.data == 'my_meds':
        show_my_meds(update, context)
    elif query.data == 'reports':
        show_reports_menu(update, context)
    elif query.data == 'settings':
        show_settings(update, context)
    elif query.data == 'week_report':
        # Отчет за неделю
        user_id = update.effective_user.id
        report_text = generate_report(user_id, 7)
        query.edit_message_text(
            text=report_text,
            reply_markup=back_to_reports_keyboard(),
        )
    elif query.data == 'month_report':
        # Отчет за месяц
        user_id = update.effective_user.id
        report_text = generate_report(user_id, 30)
        query.edit_message_text(
            text=report_text,
            reply_markup=back_to_reports_keyboard(),
        )
    elif query.data == 'export_data':
        # Экспорт данных
        user_id = update.effective_user.id
        filename = export_to_excel(user_id)
        if filename:
            try:
                with open(filename, 'rb') as file:
                    context.bot.send_document(
                        chat_id=user_id,
                        document=file,
                        filename=filename,
                        caption="Ваши данные по лекарствам.",
                    )
                query.edit_message_text(
                    text="Данные экспортированы!",
                    reply_markup=back_to_reports_keyboard(),
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке файла: {e}")
                query.edit_message_text(
                    text="Произошла ошибка при экспорте данных.",
                    reply_markup=back_to_reports_keyboard(),
                )
        else:
            query.edit_message_text(
                text="Нет данных для экспорта.",
                reply_markup=back_to_reports_keyboard(),
            )
    elif query.data == 'back':
        # Возврат в главное меню
        query.edit_message_text(
            text="Выбери действие:",
            reply_markup=main_menu_keyboard(),
        )
    elif query.data == 'list_relatives':
        # Показать список доверенных лиц
        list_relatives(update, context)
    elif query.data == 'notification_settings':
        # Настройка уведомлений
        notification_settings(update, context)
    elif query.data == 'toggle_notifications':
        # Переключение уведомлений
        toggle_notifications(update, context)

def confirm_intake(update: Update, context: CallbackContext, med_name: str):
    """Подтверждение приема лекарства."""
    user_id = update.effective_user.id
    user_meds = medications.get(user_id, [])
    medication = next((m for m in user_meds if m['name'] == med_name), None)
    
    if medication:
        medication['last_taken'] = datetime.now()
        medication['history'].append({
            'date': datetime.now(),
            'status': 'принято',
        })
        
        update.callback_query.edit_message_text(
            text=f"✅ Прием {med_name} подтвержден!",
        )

def snooze_reminder(update: Update, context: CallbackContext, med_name: str):
    """Откладывание напоминания."""
    user_id = update.effective_user.id
    user_meds = medications.get(user_id, [])
    medication = next((m for m in user_meds if m['name'] == med_name), None)
    
    if medication:
        # Переназначаем напоминание через 10 минут
        context.job_queue.run_once(
            send_reminder,
            when=10*60,
            context={'user_id': user_id, 'med_name': med_name},
        )
        
        update.callback_query.edit_message_text(
            text=f"⏸ Напоминание отложено на 10 минут.",
        )

def show_my_meds(update: Update, context: CallbackContext):
    """Показать список лекарств пользователя."""
    user_id = update.effective_user.id
    user_meds = medications.get(user_id, [])
    
    if not user_meds:
        update.callback_query.edit_message_text(
            text="У вас нет добавленных лекарств.",
            reply_markup=main_menu_keyboard(),
        )
        return
    
    text = "Ваши лекарства:\n\n"
    for med in user_meds:
        text += (
            f"💊 {med['name']} {med['dosage']} ({med['form']})\n"
            f"📅 График: {', '.join(med['schedule'])}\n"
            f"⏳ {med['duration']}\n"
            f"Последний прием: {med['last_taken'] if med['last_taken'] else 'еще не принималось'}\n\n"
        )
    
    update.callback_query.edit_message_text(
        text=text,
        reply_markup=main_menu_keyboard(),
    )

def show_reports_menu(update: Update, context: CallbackContext):
    """Меню отчетов."""
    keyboard = [
        [InlineKeyboardButton("Отчет за неделю", callback_data='week_report')],
        [InlineKeyboardButton("Отчет за месяц", callback_data='month_report')],
        [InlineKeyboardButton("Экспорт данных", callback_data='export_data')],
        [InlineKeyboardButton("Назад", callback_data='back')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.callback_query.edit_message_text(
        text="Выберите тип отчета:",
        reply_markup=reply_markup,
    )

def generate_report(user_id: int, days: int) -> str:
    """Генерация отчета за указанный период."""
    user_meds = medications.get(user_id, [])
    if not user_meds:
        return "Нет данных для отчета."
    
    report = f"Отчет за последние {days} дней:\n\n"
    
    for med in user_meds:
        # Фильтруем историю по периоду
        recent_history = [
            h for h in med['history']
            if h['date'] > datetime.now() - timedelta(days=days)
        ]
        
        taken = sum(1 for h in recent_history if h['status'] == 'принято')
        missed = sum(1 for h in recent_history if h['status'] == 'пропущен')
        total = taken + missed
        
        if total > 0:
            compliance = (taken / total) * 100
        else:
            compliance = 0
        
        report += (
            f"💊 {med['name']}:\n"
            f"✅ Принято: {taken} раз\n"
            f"❌ Пропущено: {missed} раз\n"
            f"📊 Соблюдение: {compliance:.1f}%\n\n"
        )
    
    return report

def export_to_excel(user_id: int) -> str:
    """Экспорт данных в Excel."""
    user_meds = medications.get(user_id, [])
    if not user_meds:
        return None
    
    # Создаем DataFrame для экспорта
    data = []
    for med in user_meds:
        for event in med['history']:
            data.append({
                'Лекарство': med['name'],
                'Дата': event['date'],
                'Статус': event['status'],
                'Дозировка': med['dosage'],
                'Форма': med['form'],
            })
    
    df = pd.DataFrame(data)
    filename = f"medicine_report_{user_id}_{datetime.now().date()}.xlsx"
    df.to_excel(filename, index=False)
    
    return filename

def show_settings(update: Update, context: CallbackContext):
    """Меню настроек."""
    keyboard = [
        [InlineKeyboardButton("Добавить доверенное лицо", callback_data='add_relative')],
        [InlineKeyboardButton("Мои доверенные лица", callback_data='list_relatives')],
        [InlineKeyboardButton("Настройка уведомлений", callback_data='notification_settings')],
        [InlineKeyboardButton("Назад", callback_data='back')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.callback_query.edit_message_text(
        text="Настройки:",
        reply_markup=reply_markup,
    )

def list_relatives(update: Update, context: CallbackContext):
    """Показать список доверенных лиц."""
    user_id = update.effective_user.id
    user_relatives = relatives.get(user_id, [])
    
    if not user_relatives:
        update.callback_query.edit_message_text(
            text="У вас нет добавленных доверенных лиц.",
            reply_markup=back_to_settings_keyboard(),
        )
        return
    
    text = "Ваши доверенные лица:\n\n"
    for relative in user_relatives:
        text += f"👤 {relative}\n"
    
    update.callback_query.edit_message_text(
        text=text,
        reply_markup=back_to_settings_keyboard(),
    )

def notification_settings(update: Update, context: CallbackContext):
    """Настройка уведомлений."""
    # Для простоты добавим переключатель включения/выключения уведомлений
    user_id = update.effective_user.id
    
    # Храним настройки уведомлений в user_data (можно расширить для других настроек)
    if 'notifications_enabled' not in context.user_data:
        context.user_data['notifications_enabled'] = True  # По умолчанию включены
    
    current_status = context.user_data['notifications_enabled']
    status_text = "включены" if current_status else "выключены"
    
    keyboard = [
        [
            InlineKeyboardButton(
                "Выключить уведомления" if current_status else "Включить уведомления",
                callback_data='toggle_notifications'
            )
        ],
        [InlineKeyboardButton("Назад к настройкам", callback_data='settings')],
        [InlineKeyboardButton("В главное меню", callback_data='back')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.callback_query.edit_message_text(
        text=f"Настройка уведомлений:\nТекущий статус: уведомления {status_text}",
        reply_markup=reply_markup,
    )

def toggle_notifications(update: Update, context: CallbackContext):
    """Переключение состояния уведомлений."""
    user_id = update.effective_user.id
    
    # Переключаем статус уведомлений
    context.user_data['notifications_enabled'] = not context.user_data.get('notifications_enabled', True)
    new_status = context.user_data['notifications_enabled']
    status_text = "включены" if new_status else "выключены"
    
    keyboard = [
        [
            InlineKeyboardButton(
                "Выключить уведомления" if new_status else "Включить уведомления",
                callback_data='toggle_notifications'
            )
        ],
        [InlineKeyboardButton("Назад к настройкам", callback_data='settings')],
        [InlineKeyboardButton("В главное меню", callback_data='back')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.callback_query.edit_message_text(
        text=f"Настройка уведомлений:\nТекущий статус: уведомления {status_text}",
        reply_markup=reply_markup,
    )

def add_relative_start(update: Update, context: CallbackContext) -> int:
    """Начало процесса добавления доверенного лица."""
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="Введите @username доверенного лица:")
    return ADD_RELATIVE

def add_relative(update: Update, context: CallbackContext) -> int:
    """Добавление доверенного лица."""
    username = update.message.text
    user_id = update.effective_user.id
    
    if not username.startswith('@'):
        update.message.reply_text("Пожалуйста, введите username, начиная с @")
        return ADD_RELATIVE
    
    if user_id not in relatives:
        relatives[user_id] = []
    
    if username not in relatives[user_id]:
        relatives[user_id].append(username)
        update.message.reply_text(
            f"{username} добавлен(а) в список доверенных лиц.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        update.message.reply_text(
            "Этот пользователь уже в списке доверенных лиц.",
            reply_markup=main_menu_keyboard(),
        )
    
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Отмена текущего действия."""
    update.message.reply_text(
        'Действие отменено.',
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext) -> None:
    """Обработчик ошибок."""
    logger.error(msg="Исключение при обработке обновления:", exc_info=context.error)
    
    try:
        update.message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте еще раз или обратитесь к разработчику."
        )
    except:
        pass

def main() -> None:
    """Запуск бота."""
    # Создаем Updater и передаем ему токен бота
    updater = Updater("8156244486:AAF2VLO95xxJQbp6hsm7dBw-YdD2B-XoYO4")
    
    # Получаем диспетчер для регистрации обработчиков
    dispatcher = updater.dispatcher
    
    # Обработчик команды /start
    dispatcher.add_handler(CommandHandler("start", start))
    
    # Обработчик добавления лекарства (ConversationHandler)
    add_med_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_med_start, pattern='^add_med$')],
        states={
            ADD_MED_NAME: [MessageHandler(Filters.text & ~Filters.command, add_med_name)],
            ADD_MED_DOSAGE: [MessageHandler(Filters.text & ~Filters.command, add_med_dosage)],
            ADD_MED_FORM: [MessageHandler(Filters.text & ~Filters.command, add_med_form)],
            ADD_MED_FREQUENCY: [MessageHandler(Filters.text & ~Filters.command, add_med_frequency)],
            ADD_MED_SCHEDULE: [MessageHandler(Filters.text & ~Filters.command, add_med_schedule)],
            ADD_MED_DURATION: [MessageHandler(Filters.text & ~Filters.command, add_med_duration)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dispatcher.add_handler(add_med_conv)
    
    # Обработчик добавления доверенного лица
    add_relative_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_relative_start, pattern='^add_relative$')],
        states={
            ADD_RELATIVE: [MessageHandler(Filters.text & ~Filters.command, add_relative)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dispatcher.add_handler(add_relative_conv)
    
    # Обработчик кнопок
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик ошибок
    dispatcher.add_error_handler(error_handler)
    
    # Запускаем бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()