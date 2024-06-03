import telebot
from telebot import types
import json
import time
import requests
from config import API_KEY, URL

bot = telebot.TeleBot(API_KEY)
url = URL


class UserData:
    def __init__(self):
        self.data = {}

    def set(self, chat_id, key, value):
        if chat_id not in self.data:
            self.data[chat_id] = {}
        self.data[chat_id][key] = value

    def get(self, chat_id, key):
        if chat_id in self.data and key in self.data[chat_id]:
            return self.data[chat_id][key]
        return None

    def remove(self, chat_id):
        if chat_id in self.data:
            del self.data[chat_id]


class MenuBot:
    def __init__(self):
        self.user_data = UserData()
        self.iso4217_mapping = {
            'USD': 'USD',
            'EUR': 'EUR',
            'UAH': 'UAH',
        }

    def menu_1(self, chat_id):
        markup = types.InlineKeyboardMarkup(row_width=2)
        button_other_currency = types.InlineKeyboardButton('ІНШІ ВАЛЮТИ', callback_data='other currency')
        for currency in self.iso4217_mapping.values():
            markup.add(types.InlineKeyboardButton(currency, callback_data=currency))
        markup.add(button_other_currency)
        return markup

    def menu_2(self, chat_id):
        markup = types.InlineKeyboardMarkup(row_width=2)
        button_continue = types.InlineKeyboardButton('CONTINUE', callback_data='continue')
        button_end = types.InlineKeyboardButton('END', callback_data='end')
        button_history = types.InlineKeyboardButton('History', callback_data='history')
        markup.add(button_continue, button_end, button_history)
        return markup


class ConverterBot:
    def __init__(self, menu_bot):
        self.user_data = UserData()
        self.menu_bot = menu_bot
        self.iso4217_mapping = self.menu_bot.iso4217_mapping

    def save_conversion_history(self, chat_id, from_currency, to_currency, amount, result):
        history_file = f'history_{chat_id}.json'
        try:
            with open(history_file, 'r') as file:
                history_data = json.load(file)
        except FileNotFoundError:
            history_data = []

        history_data.append({
            'from_currency': from_currency,
            'to_currency': to_currency,
            'amount': amount,
            'result': result,
            'timestamp': int(time.time())
        })

        history_data = history_data[-10:]

        with open(history_file, 'w') as file:
            json.dump(history_data, file)

    def get_conversion_history(self, chat_id):
        history_file = f"history_{chat_id}.json"
        try:
            with open(history_file, 'r') as file:
                history_data = json.load(file)
        except FileNotFoundError:
            return None

        return history_data

    def get_exchange_rate(self, currency_code):
        response = requests.get(url)
        if not response:
            print("No data received from API")
            return None, None
        data = response.json()
        print(data)
        for item in data:
            if isinstance(item, dict) and item.get('currencyCodeA') == currency_code and item.get('currencyCodeB') == 980:
                if 'rateSell' in item:
                    rate_sell = item['rateSell']
                    rate_buy = item.get('rateBuy')
                    return rate_sell, rate_buy
                elif 'rateCross' in item:
                    rate_cross = item['rateCross']
                    return rate_cross, rate_cross
        return None, None

    def welcome(self, message):
        bot.send_message(message.chat.id,
                         'Привіт! Я бот конвертації валют. Використовуй команду /convert, щоб почати конвертацію.'
                         )

    def stop_bot(self, message):
        bot.send_message(message.chat.id, 'Бот призупинено.')
        bot.stop_polling()

    def start_conversion(self, input):
        if isinstance(input, types.CallbackQuery):
            chat_id = input.from_user.id
        elif isinstance(input, types.Message):
            chat_id = input.chat.id
        else:
            return
        self.user_data.remove(chat_id)
        markup = self.menu_bot.menu_1(chat_id)
        msg = bot.send_message(chat_id, 'Оберіть вихідну валюту:', reply_markup=markup)


    def source_currency(self, input):
        if isinstance(input, types.CallbackQuery):
            selected_currency = input.data
            chat_id = input.from_user.id
        elif isinstance(input, types.Message):
            selected_currency = input.text
            chat_id = input.chat.id
        else:
            return

        self.user_data.set(chat_id, 'from_currency', selected_currency)
        msg = bot.send_message(chat_id, 'Введіть суму для конвертації:')
        bot.register_next_step_handler(msg, self.amount_input)

    def amount_input(self, input):
        if isinstance(input, types.CallbackQuery):
            chat_id = input.from_user.id
            amount = input.data
        elif isinstance(input, types.Message):
            chat_id = input.chat.id
            amount = input.text
        else:
            return

        if not amount.isdigit():
            msg = bot.send_message(chat_id, 'Будь ласка, введіть число.')
            bot.register_next_step_handler(msg, self.amount_input)
            return msg

        self.user_data.set(chat_id, 'amount', int(amount))
        markup = self.menu_bot.menu_1(chat_id)
        msg = bot.send_message(chat_id, 'Оберіть цільову валюту:', reply_markup=markup)


    def result_conversation(self, input):
        if isinstance(input, types.Message):
            chat_id = input.chat.id
            from_currency = self.user_data.get(chat_id, 'from_currency')
            amount = self.user_data.get(chat_id, 'amount')
            target_currency = input.text
            self.user_data.set(chat_id, 'to_currency', target_currency)
        elif isinstance(input, types.CallbackQuery):
            chat_id = input.message.chat.id
            from_currency = self.user_data.get(chat_id, 'from_currency')
            amount = self.user_data.get(chat_id, 'amount')
            target_currency = input.data
            self.user_data.set(chat_id, 'to_currency', target_currency)
        else:
            return

        rate_sell, rate_buy = self.get_exchange_rate(840 if target_currency == 'USD' else 978)  # USD: 840, EUR: 978
        if rate_buy is None:
            bot.send_message(chat_id, 'Вибачте, не можу знайти курс для даної валюти.')
            time.sleep(2)
            markup = self.menu_bot.menu_2(chat_id)
            msg = bot.send_message(chat_id, 'Бажаєте продовжити далі чи зупинити бота?', reply_markup=markup)

            return

        if from_currency == target_currency:
            final_amount = amount
        else:
            if target_currency == 'UAH':
                final_amount = amount * rate_sell
            else:
                final_amount = amount / rate_buy

        self.save_conversion_history(chat_id, from_currency, target_currency, amount, final_amount)

        bot.send_message(chat_id, f'Результат конвертації: {final_amount:.2f} {target_currency}')
        time.sleep(2)

        markup = self.menu_bot.menu_2(chat_id)
        msg = bot.send_message(chat_id, 'Бажаєте продовжити далі чи зупинити бота?', reply_markup=markup)


    def send_message_with_markup(self, chat_id, text, markup, next_step_handler):
        msg = bot.send_message(chat_id, text, reply_markup=markup)
        bot.register_next_step_handler(msg, next_step_handler)

    def continue_or_stop(self, input):
        if isinstance(input, types.CallbackQuery):
            chat_id = input.from_user.id
            data = input.data
        elif isinstance(input, types.Message):
            chat_id = input.chat.id
            data = input.text.lower()
        else:
            return
        self.user_data.remove(chat_id)
        if data == 'continue':
            markup = self.menu_bot.menu_1(chat_id)
            msg = bot.send_message(chat_id, 'Оберіть вихідну валюту:', reply_markup=markup)
        elif data == 'end':
            bot.send_message(chat_id, 'Дякую. До побачення.')
        elif data == 'history':
            history_data = self.get_conversion_history(chat_id)
            if history_data:
                history_text = 'Історія конвертацій:\n'
                for entry in history_data:
                    history_text += f"Вихідна валюта: {entry['from_currency']}, Цільова валюта: {entry['to_currency']}, Сума: {entry['amount']}, Результат: {entry['result']:.2f}\n"
                bot.send_message(chat_id, history_text)
                time.sleep(2.5)
            else:
                bot.send_message(chat_id, 'Історія конвертацій порожня.')
            markup = self.menu_bot.menu_2(chat_id)
            msg = bot.send_message(chat_id, 'Бажаєте продовжити далі чи зупинити бота?', reply_markup=markup)


menu_bot = MenuBot()
converter_bot = ConverterBot(menu_bot)

def start_command_handler(func):
    def wrapper(callback_query):
        if callback_query == '/start':
            converter_bot.welcome(callback_query)
        else:
            func(callback_query)
    return wrapper

@start_command_handler
@bot.message_handler(commands=['start'])
def welcome(message):
    converter_bot.welcome(message)
    bot.clear_step_handler_by_chat_id(message.chat.id)

converter_bot.source_currency = start_command_handler(converter_bot.source_currency)
converter_bot.amount_input = start_command_handler(converter_bot.amount_input)
converter_bot.result_conversation = start_command_handler(converter_bot.result_conversation)
converter_bot.continue_or_stop = start_command_handler(converter_bot.continue_or_stop)


@bot.message_handler(commands=['convert'])
def start_conversion(message):
    converter_bot.start_conversion(message)

@bot.message_handler(func=lambda message: True)
def handle_source_currency_message(message):
    converter_bot.source_currency(message)

@bot.callback_query_handler(func=lambda call: call.data in ['continue', 'end', 'history'])
def handle_callback_queries(call):
    converter_bot.continue_or_stop(call)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    data = call.data

    if data in converter_bot.iso4217_mapping.values():
        from_currency = converter_bot.user_data.get(chat_id, 'from_currency')
        target_currency = converter_bot.user_data.get(chat_id, 'to_currency')

        if not from_currency:
            print(f"Setting source currency: {data} for chat_id: {chat_id}")
            converter_bot.source_currency(call)
        else:
            print(f"Setting target currency: {data} for chat_id: {chat_id}")
            converter_bot.user_data.set(chat_id, 'to_currency', data)
            converter_bot.result_conversation(call)
    else:
        print(f"Calling continue_or_stop with data: {data} for chat_id: {chat_id}")
        converter_bot.continue_or_stop(call)



bot.polling()