import os
import sqlite3
import telebot
from telebot import types

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN) # type: ignore 

class CreateMenu:
    def __init__(self): # class construct. defines db file
        self.__db_path = os.getcwd()
        self.db_name = os.path.join(self.__db_path, 'database.db')
    
    def __connect(self): # db connection function
        connect = sqlite3.connect(self.db_name)
        return connect
    
    def __select_button(self, type_menu: str) -> dict: # accept "menu type" as an argument. Returns dictionary where key = button text, value = button callbackdata
        with self.__connect() as connect:
            cursor = connect.cursor()
            sql = """SELECT btn_name, btn_callback FROM create_menu WHERE type_menu = (?) ORDER BY order_num"""
            select_db = cursor.execute(sql, (type_menu,))
            result = dict()
            for btn_name, btn_callback in select_db.fetchall():
                result[btn_name] = btn_callback
            return result

    def create_menu(self, type_menu: str) -> types.InlineKeyboardMarkup: # TG bot menu creation
        markup = types.InlineKeyboardMarkup()
        btn_list = self.__select_button(type_menu)
        for element in btn_list.items():
            btn = types.InlineKeyboardButton(text= element[0], callback_data= element[1])
            markup.add(btn)
        return markup
