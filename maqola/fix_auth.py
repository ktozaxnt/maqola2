import os

print("=== ФИНАЛЬНЫЙ РЕМОНТ АВТОРИЗАЦИИ ===")

# 1. Введи тот самый код
print("Вставь длинный пароль (32 символа) для 'DanikBotUZ@manager':")
password = input("Код: ").strip()

# 2. Правильно записываем user-config.py
config_text = """# -*- coding: utf-8 -*-
mylang = 'uz'
family = 'wikipedia'
usernames['wikipedia']['uz'] = 'DanikBotUZ'
password_file = 'user-password.py'
"""

with open('user-config.py', 'w', encoding='utf-8') as f:
    f.write(config_text)

# 3. Правильно записываем user-password.py (С ИМПОРТОМ!)
# Это решит ошибку с аргументами
pass_text = f"""from pywikibot.login import BotPassword
('DanikBotUZ', BotPassword('manager', '{password}'))
"""

with open('user-password.py', 'w', encoding='utf-8') as f:
    f.write(pass_text)

# 4. Чистим кэш
import glob
for f in glob.glob("*.lwp") + glob.glob("pywikibot-*.lwp"):
    try: os.remove(f)
    except: pass

print("\n✅ ГОТОВО! Теперь запускай bot.py")