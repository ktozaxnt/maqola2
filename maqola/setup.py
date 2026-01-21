import os

print("=== ФИНАЛЬНАЯ НАСТРОЙКА БОТА ===")

# 1. Данные
# Вводим чистое имя, без собак
base_user = "DanikBotUZ" 
bot_suffix = "manager"      # Имя пароля, который мы создали в Шаге 1

# Собираем правильный логин для Википедии: "DanikBotUZ@manager"
full_login = f"{base_user}@{bot_suffix}"

print(f"Пользователь: {base_user}")
print(f"Имя пароля: {bot_suffix}")
print(f"Полный логин: {full_login}")

print("\nВставь НОВЫЙ код, который ты только что получил в Википедии:")
password = input("Код: ").strip()

# 2. Создаем user-config.py
config_text = f"""# -*- coding: utf-8 -*-
mylang = 'uz'
family = 'wikipedia'
# Для конфига используем полное имя с @manager, чтобы наверняка
usernames['wikipedia']['uz'] = '{full_login}'
password_file = 'user-password.py'
"""

with open('user-config.py', 'w', encoding='utf-8') as f:
    f.write(config_text)

# 3. Создаем user-password.py
# Здесь тоже используем полное имя
pass_text = f"('{full_login}', '{password}')"

with open('user-password.py', 'w', encoding='utf-8') as f:
    f.write(pass_text)

print("\n✅ НАСТРОЙКА ЗАВЕРШЕНА!")
print("Теперь бот будет заходить как 'DanikBotUZ@manager'.")
print("Запускай bot.py!")