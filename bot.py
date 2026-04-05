import json
import random
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# --- загрузка вопросов ---
with open("quiz_updated.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

# --- старт ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_index = random.randint(0, len(questions) - 1)
    await send_question(update, context, q_index)


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # перемешиваем вопросы по диапазонам
    part1 = random.sample(questions[:287], 20)
    part2 = random.sample(questions[287:540], 20)

    test_questions = part1 + part2
    random.shuffle(test_questions)

    context.user_data["test_mode"] = True
    context.user_data["test_questions"] = test_questions
    context.user_data["test_index"] = 0
    context.user_data["correct"] = 0
    context.user_data["wrong"] = 0

    await update.message.reply_text("📝 Test byl spuštěn. Hodně štěstí!")
    await send_test_question(update, context)


async def send_test_question(update_or_query, context):
    index = context.user_data["test_index"]
    questions_list = context.user_data["test_questions"]

    if index >= len(questions_list):
        await finish_test(update_or_query, context)
        return

    question = questions_list[index]
    context.user_data["current_q"] = question
    context.user_data["selected"] = []

    message = update_or_query.message if hasattr(update_or_query, "message") else update_or_query

    text = f"❓ Otázka {index + 1}/40:\n{question['question']['text']}\n\n"
    for opt in question["options"]:
        text += f"{opt['key']}) {opt.get('text','')}\n"

    keyboard = [[InlineKeyboardButton(f"{opt['key']})", callback_data=f"opt_{opt['key']}")]
                for opt in question["options"]]
    keyboard.append([InlineKeyboardButton("✅ Zkontrolovat", callback_data="check")])

    markup = InlineKeyboardMarkup(keyboard)

    if question["question"].get("image") and os.path.exists(question["question"]["image"]):
        with open(question["question"]["image"], "rb") as img:
            await message.reply_photo(photo=img, caption=text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)
    for opt in question["options"]:
        if opt.get("image") and os.path.exists(opt["image"]):
            caption = f"{opt['key']}) {opt.get('text','')}"
            with open(opt["image"], "rb") as img:
                await message.reply_photo(photo=img, caption=caption)
# --- переход к вопросу ---
async def go_to_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Napis číslo otázky: /q 5")
        return
    try:
        num = int(context.args[0]) - 1
    except:
        await update.message.reply_text("Chyba v čísle")
        return
    if num < 0 or num >= len(questions):
        await update.message.reply_text("Číslo otázky mimo rozsah")
        return
    await send_question(update, context, num)

# --- отправка вопроса с текстом и картинками вариантов ---

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def send_question(update_or_query, context, q_index):
    question = questions[q_index]
    context.user_data["current_q"] = q_index
    context.user_data["selected"] = []

    # --- объект сообщения, откуда пришёл запрос ---
    message = update_or_query.message if hasattr(update_or_query, "message") else update_or_query

    # --- формируем текст вопроса с вариантами ---
    text = f"❓ Otázka {q_index + 1}:\n{question['question']['text']}\n\n"
    for opt in question["options"]:
        text += f"{opt['key']}) {opt.get('text','')}\n"

    # --- клавиатура ---
    keyboard = [[InlineKeyboardButton(f"{opt['key']})", callback_data=f"opt_{opt['key']}")]
                for opt in question["options"]]
    keyboard.append([InlineKeyboardButton("✅ Zkontrolovat", callback_data="check")])
    markup = InlineKeyboardMarkup(keyboard)

    # --- отправляем сообщение с картинкой вопроса (если есть) ---
    if question["question"].get("image") and os.path.exists(question["question"]["image"]):
        with open(question["question"]["image"], "rb") as img:
            main_msg = await message.reply_photo(
                photo=img,
                caption=text,
                reply_markup=markup
            )
    else:
        main_msg = await message.reply_text(
            text=text,
            reply_markup=markup
        )

    # --- (опционально) отправляем картинки вариантов отдельно ---
    for opt in question["options"]:
        if opt.get("image") and os.path.exists(opt["image"]):
            caption = f"{opt['key']}) {opt.get('text','')}"
            with open(opt["image"], "rb") as img:
                await message.reply_photo(photo=img, caption=caption)
async def update_buttons(query, context):
    selected = context.user_data.get("selected", [])

    # --- получаем вопрос ---
    if context.user_data.get("test_mode"):
        question = context.user_data["current_q"]
    else:
        q_index = context.user_data["current_q"]
        question = questions[q_index]

    # --- формируем текст ---
    text = f"❓ {question['question']['text']}\n\n"
    for opt in question["options"]:
        mark = "✅" if opt["key"] in selected else "▫️"
        text += f"{mark} {opt['key']}) {opt.get('text','')}\n"

    # --- кнопки ---
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅ ' if opt['key'] in selected else ''}{opt['key']})",
            callback_data=f"opt_{opt['key']}"
        )]
        for opt in question["options"]
    ]

    keyboard.append([InlineKeyboardButton("✅ Zkontrolovat", callback_data="check")])
    markup = InlineKeyboardMarkup(keyboard)

    # --- обновляем сообщение ---
    if query.message.photo:
        await query.edit_message_caption(caption=text, reply_markup=markup)
    else:
        await query.edit_message_text(text=text, reply_markup=markup)
# --- проверка ---
async def check_answer(query, context):
    selected = set(context.user_data["selected"])

    # --- режим теста ---
    if context.user_data.get("test_mode"):
        question = context.user_data["current_q"]
        correct = set(question["answer"])

        if selected == correct:
            context.user_data["correct"] += 1
            result = "✅ Správně!"
        else:
            context.user_data["wrong"] += 1
            result = f"❌ Špatně\nSprávná odpověď: {', '.join(correct)}"

        keyboard = [[InlineKeyboardButton("➡️ Další", callback_data="next")]]

        if query.message.photo:
            text = (query.message.caption or "") + "\n\n" + result
            await query.edit_message_caption(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            text = (query.message.text or "") + "\n\n" + result
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

        return

    # --- обычный режим ---
    q_index = context.user_data["current_q"]
    question = questions[q_index]

    correct = set(question["answer"])

    if selected == correct:
        result = "✅ Správně!"
    else:
        result = f"❌ Špatně\nSprávná odpověď: {', '.join(correct)}"

    keyboard = [[InlineKeyboardButton("➡️ Další", callback_data="next")]]

    if query.message.photo:
        text = (query.message.caption or "") + "\n\n" + result
        await query.edit_message_caption(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        text = (query.message.text or "") + "\n\n" + result
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # --- обработка кнопок ---
async def handle_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    selected = context.user_data.get("selected", [])

    if data.startswith("opt_"):
        key = data.split("_")[1]
        if key in selected:
            selected.remove(key)
        else:
            selected.append(key)
        context.user_data["selected"] = selected
        await update_buttons(query, context)

    elif data == "check":
        await check_answer(query, context)

    elif data == "next":
      if context.user_data.get("test_mode"):
        context.user_data["test_index"] += 1
        await send_test_question(query, context)
      else:
        q_index = random.randint(0, len(questions) - 1)
        await send_question(query, context, q_index)

         
async def finish_test(update_or_query, context):
    correct = context.user_data["correct"]
    wrong = context.user_data["wrong"]
    total = correct + wrong

    percent = int((correct / total) * 100) if total > 0 else 0

    result = "✅ PROŠEL" if percent >= 80 else "❌ NEPROŠEL"

    text = (
        f"📊 Výsledek testu:\n\n"
        f"✔️ Správně: {correct}\n"
        f"❌ Špatně: {wrong}\n"
        f"📈 Úspěšnost: {percent}%\n\n"
        f"{result}"
    )

    message = update_or_query.message if hasattr(update_or_query, "message") else update_or_query
    await message.reply_text(text)

    context.user_data["test_mode"] = False

async def end_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("test_mode"):
        await update.message.reply_text("⛔ Test byl ukončen.")
        await finish_test(update, context)
    else:
        await update.message.reply_text("Žádný test neběží.")



# --- запуск ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("q", go_to_question))
    app.add_handler(CallbackQueryHandler(handle_click))
    app.add_handler(CommandHandler("test", start_test))
    app.add_handler(CommandHandler("endtest", end_test))
    print("Bot spuštěn...")
    app.run_polling()

if __name__ == "__main__":
    main()