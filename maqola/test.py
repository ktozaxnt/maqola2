from google import genai

# ВСТАВЬ СВОЙ НОВЫЙ КЛЮЧ
MY_API_KEY = "AIzaSyD4al5WScr6hrntlo_9EM-Qard4-W6ZNbM"

client = genai.Client(api_key=MY_API_KEY)

models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]

for model_name in models_to_try:
    print(f"Пробую модель {model_name}...")
    try:
        response = client.models.generate_content(
            model=model_name, 
            contents="Напиши 'ОК'"
        )
        print(f"УСПЕХ с {model_name}: {response.text}")
        break # Если сработало, выходим из цикла
    except Exception as e:
        print(f"Ошибка с {model_name}: {e}\n")