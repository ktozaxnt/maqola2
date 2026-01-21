import os

print("=== ИСПРАВЛЕНИЕ КОНФИГУРАЦИИ (FINAL FIX) ===")

# 1. Твои данные
base_user = "DanikBotUZ"
bot_name = "manager"

print(f"Пользователь: {base_user}")
print(f"Название бота: {bot_name}")
print("\nВставь тот самый длинный код (пароль бота):")
password = input("Код: ").strip()

# 2. Пишем user-config.py (ТУТ ДОЛЖНО БЫТЬ ЧИСТОЕ ИМЯ)
config_text = f"""# -*- coding: utf-8 -*-
mylang = 'uz'
family = 'wikipedia'
# В конфиге пишем БАЗОВОЕ имя (без @manager)
usernames['wikipedia']['uz'] = '{base_user}'
password_file = 'user-password.py'
"""

with open('user-config.py', 'w', encoding='utf-8') as f:
    f.write(config_text)

# 3. Пишем user-password.py (А ВОТ ТУТ СПЕЦИАЛЬНЫЙ ФОРМАТ)
# Формат: (Пользователь, 'BotPassword', ИмяБота, СамКод)
pass_text = f"('{base_user}', 'BotPassword', '{bot_name}', '{password}')"

with open('user-password.py', 'w', encoding='utf-8') as f:
    f.write(pass_text)

# 4. Удаляем глючные сессии
import glob
for f in glob.glob("*.lwp") + glob.glob("pywikibot-*.lwp"):
    try: os.remove(f)
    except: pass

print("\n✅ ФАЙЛЫ ИСПРАВЛЕНЫ!")
print("Теперь запускай bot.py")