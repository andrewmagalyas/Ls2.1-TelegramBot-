"""
Тести на виконання команд /start та /convert, та отримання данних за url
Домашнє завдання WebHW4
Андрій Магаляс
"""

import unittest
from unittest.mock import patch, MagicMock
import requests
from main import bot, menu_bot, converter_bot, welcome, start_conversion, URL

class TestTelegramBot(unittest.TestCase):
    @patch('telebot.TeleBot.send_message')
    @patch('telebot.TeleBot.clear_step_handler_by_chat_id')
    def test_start_command(self, mock_clear_step_handler, mock_send_message):
        message = MagicMock()
        message.chat.id = 12345
        message.text = '/start'

        welcome(message)

        mock_send_message.assert_called_once_with(message.chat.id, 'Привіт! Я бот конвертації валют. Використовуй команду /convert, щоб почати конвертацію.')
        mock_clear_step_handler.assert_called_once_with(message.chat.id)

    @patch('telebot.TeleBot.send_message')
    @patch('telebot.TeleBot.clear_step_handler_by_chat_id')
    def test_convert_command(self, mock_clear_step_handler, mock_send_message):
        message = MagicMock()
        message.chat.id = 12345
        message.text = '/convert'

        start_conversion(message)

        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0]
        self.assertEqual(call_args[0], message.chat.id)
        self.assertEqual(call_args[1], 'Оберіть вихідну валюту:')
        self.assertTrue('reply_markup' in mock_send_message.call_args[1])
        mock_clear_step_handler.assert_called_once_with(message.chat.id)

class TestExchangeRate(unittest.TestCase):
    @patch('requests.get')
    def test_get_exchange_rate(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "currencyCodeA": 840,
                "currencyCodeB": 980,
                "rateSell": 27.0,
                "rateBuy": 26.5
            }
        ]
        mock_get.return_value = mock_response

        rate_sell, rate_buy = converter_bot.get_exchange_rate(840)

        mock_get.assert_called_once_with(URL)
        self.assertEqual(rate_sell, 27.0)
        self.assertEqual(rate_buy, 26.5)


if __name__ == '__main__':
    unittest.main()
