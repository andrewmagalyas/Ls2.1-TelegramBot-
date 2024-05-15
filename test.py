import telebot
from telebot import types
import json
import iso4217
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


class ConverterBot:
    def __init__(self):
        self.user_data = UserData()
        self.iso4217_mapping = {
            'USD': 'USD',
            'EUR': 'EUR',
            'UAH': 'UAH',
        }

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

    def menu_1(self, chat_id):
        markup = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
        for currency in self.iso4217_mapping.values():
            markup.add(types.KeyboardButton(currency))
        return markup

    def menu_2(self, chat_id):
        markup = types.ReplyKeyboardMarkup(row_width=2, one_time_keyboard=True)
        button_continue = types.KeyboardButton('CONTINUE')
        button_end = types.KeyboardButton('END')
        button_history = types.KeyboardButton('History')
        markup.add(button_continue, button_end, button_history)
        return markup

    def welcome(self, message):
        bot.send_message(message.chat.id,
                         'Привіт! Я бот конвертації валют. Використовуй команду /convert, щоб почати конвертацію.'
                         )

    def stop_bot(self, message):
        bot.send_message(message.chat.id, 'Бот призупинено.')
        bot.stop_polling()

    def start_conversion(self, message):
        markup = self.menu_1(message.chat.id)
        msg = bot.send_message(message.chat.id, 'Оберіть вихідну валюту:', reply_markup=markup)
        bot.register_next_step_handler(msg, self.source_currency)

    def source_currency(self, message):
        markup = types.ReplyKeyboardRemove(selective=False)
        self.user_data.set(message.chat.id, 'from_currency', message.text)
        msg = bot.send_message(message.chat.id, 'Введіть суму для конвертації:', reply_markup=markup)
        bot.register_next_step_handler(msg, self.amount_input)

    def amount_input(self, message):
        amount = message.text
        if not amount.isdigit():
            msg = bot.send_message(message.chat.id, 'Будь ласка, введіть число.')
            bot.register_next_step_handler(msg, self.amount_input)
            return
        self.user_data.set(message.chat.id, 'amount', int(amount))
        markup = self.menu_1(message.chat.id)
        msg = bot.send_message(message.chat.id, 'Оберіть цільову валюту:', reply_markup=markup)
        bot.register_next_step_handler(msg, self.result_conversation)

    def send_message_with_markup(self, chat_id, text, markup, next_step_handler):
        msg = bot.send_message(chat_id, text, reply_markup=markup)
        bot.register_next_step_handler(msg, next_step_handler)

    def result_conversation(self, message):
        from_currency = self.iso4217_mapping.get(self.user_data.get(message.chat.id, 'from_currency'))
        amount = self.user_data.get(message.chat.id, 'amount')
        target_currency = self.iso4217_mapping.get(message.text.upper())
        self.user_data.set(message.chat.id, 'to_currency', target_currency)

        rate_sell, rate_buy = self.get_exchange_rate(840 if target_currency == 'USD' else 978)  # USD: 840, EUR: 978
        if rate_sell is None or rate_buy is None:
            bot.send_message(message.chat.id, 'Вибачте, не можу знайти курс для даної валюти.')
            time.sleep(2)
            markup = self.menu_2(message.chat.id)
            self.send_message_with_markup(message.chat.id, 'Бажаєте продовжити далі чи зупинити бота?', markup,
                                          self.continue_or_stop
                                          )
            return

        if from_currency == target_currency:
            final_amount = amount
        else:
            if target_currency == 'UAH':
                final_amount = amount * rate_sell
            else:
                final_amount = amount / rate_buy

        self.save_conversion_history(message.chat.id, from_currency, target_currency, amount, final_amount)

        bot.send_message(message.chat.id, f'Результат конвертації: {final_amount:.2f} {target_currency}')
        time.sleep(2)

        markup = self.menu_2(message.chat.id)
        self.send_message_with_markup(message.chat.id, 'Бажаєте продовжити далі чи зупинити бота?', markup,
                                      self.continue_or_stop
                                      )

    def continue_or_stop(self, message):
        if message.text == 'CONTINUE':
            markup = self.menu_1(message.chat.id)
            msg = bot.send_message(message.chat.id, 'Оберіть вихідну валюту:', reply_markup=markup)
            bot.register_next_step_handler(msg, self.source_currency)
        elif message.text == 'END':
            bot.send_message(message.chat.id, 'Дякую. До побачення.')
            bot.stop_polling()
        elif message.text == 'History':
            history_data = self.get_conversion_history(message.chat.id)
            if history_data:
                history_text = 'Історія конвертацій:\n'
                for entry in history_data:
                    history_text += f"Вихідна валюта: {entry['from_currency']}, Цільова валюта: {entry['to_currency']}, Сума: {entry['amount']}, Результат: {entry['result']:.2f}\n"
                bot.send_message(message.chat.id, history_text)
                time.sleep(2.5)
                markup = self.menu_2(message.chat.id)
                msg = bot.send_message(message.chat.id, 'Бажаєте продовжити далі чи зупинити бота?',
                                       reply_markup=markup
                                       )
                bot.register_next_step_handler(msg, self.continue_or_stop)
            else:
                bot.send_message(message.chat.id, 'Історія конвертацій порожня.')


converter_bot = ConverterBot()


@bot.message_handler(commands=['start'])
def welcome(message):
    converter_bot.welcome(message)


@bot.message_handler(commands=['stop'])
def stop_bot(message):
    converter_bot.stop_bot(message)


@bot.message_handler(commands=['convert'])
def start_conversion(message):
    converter_bot.start_conversion(message)


bot.polling()
