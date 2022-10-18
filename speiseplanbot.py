#!/usr/bin/env python3
# pylint: disable=C0116,W0613
# This program is dedicated to the public domain under the CC0 license.
"""
Das ist ein Bot, der infos zum Speiseplan an der HBC gibt. => Git

TODO-Liste:

    ✓ Allergene und Zusatzstoffe parsen (regex pattern = r'\(.*?\)' -> Sachen in klammern)
    ☐ Allergene und Zusatzstoffe als settings pro chat fixieren (chat_data dict...)
    ☐ Vegan und vegetarisch...
    ☐ inline Keyboard? => für manche Funktionen (wie z.B. Allergene etc.) oder alles
    ☐ nächster Öffnungs-/Arbeitstag, statt "Morgen"?
    ☐ Anpassungen des großen Gesamtplans (Bild Lukas) ??
    ☐ beliebiger Termin => Dialog mit Termineingabe, "maximaler"/letztmöglicher Termin
    ☐ Submenü pdf => nächste Woche oder "großer Gesamtplan"
    ☐ Öffnungszeiten
    ✓ "Alle Angaben ohne Gewähr"

"""
# from email import message
import logging
import re
# Data Manipulation
from datetime import datetime, timedelta
from itertools import chain

import pandas as pd
# python-telegram-bot
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (CallbackContext, CommandHandler, ConversationHandler,
                          Filters, MessageHandler, PicklePersistence, Updater)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

DAYS = ['MONTAG', 'DIENSTAG', 'MITTWOCH',
        'DONNERSTAG', 'FREITAG', 'SAMSTAG', 'SONNTAG']

SU_WEBSITE = "https://studierendenwerk-ulm.de/essen-trinken/speiseplaene/"

GO_HUNGRY_MSG = f"""Scheinbar gibt es nichts zu Essen! 😞"""

# Allergene.jpg
ZUSATZ_ALLERGENE = {
    "1": "Farbstoff",
    "2": "Konservierungsstoff",
    "3": "Antioxidationsmittel",
    "4": "Geschmacksverstärker",
    "5": "geschwefelt",
    "6": "geschwärzt",
    "7": "gewachst",
    "8": "Phosphat",
    "9": "Süßungsmittel",
    "10": "Phenylalanin",
    "11": "Alkohol",
    "18": "Gelatine",
    "13": "Krebstiere",
    "14": "Eier",
    "22": "Erdnüsse",
    "23": "Soja",
    "24": "Milch/Milchprodukte",
    "25": "Schalenfrüchte/alle Nussarten",
    "26": "Sellerie",
    "27": "Senf",
    "28": "Sesamsamen",
    "29": "Schwefeldioxid",
    "30": "Sulfite",
    "31": "Lupine",
    "32": "Weichtiere",
    "34": "Gluten",
    "35": "Fisch",
}
GELATINE_NUMBER = "18"
# GELATINE={ # 18
#     "S"  : "Schwein",
#     "R"  : "Rind",
# }
NUESSE_NUMBER = "25"
NUESSE = {  # 25
    "H": "Haselnuss",
    "W": "Walnuss",
    "P": "Pistazie",
    "Mn": "Mandel",
    "C": "Cashew",
    "Ma": "Macadamia",
    "Pk": "Pekanuss",
}
GLUTEN_NUMBER = "34"
GLUTEN = {  # 34
    "W": "Weizen",
    "G": "Gerste",
    "H": "Hafer",
    "R": "Roggen",
    "D": "Dinkel",
}
FLEISCH = {  # einzelner Buchstabe
    "R": "Rind",
    "S": "Schwein",
    "G": "Geflügel",
    "L": "Lamm",
    "W": "Wild",
}

TIERISCH = {  # nicht Fleisch, aber tierisch, also nicht vegan
    "13": "Krebstiere",
    "14": "Eier",
    "18": "Gelatine",
    "24": "Milch/Milchprodukte",
    "32": "Weichtiere",
    "35": "Fisch",
}

NICHT_VEGAN = dict(FLEISCH, **TIERISCH)
NICTH_VEGETARISCH = dict({
    "13": "Krebstiere",
    "32": "Weichtiere",
    "35": "Fisch",
}, **FLEISCH)

# Vielleicht habe ich mich aber auch geirrt?
# Mit /speiseplan_pdf kann ich dir zum Nachschauen eine pdf-Datei schicken.

# Alternativ kannst du auch auf der Website des Studierendenwerk Ulm nachschauen:
# {SU_WEBSITE}
# """

HELP_MSG = f"""Schau im Menü was ich alles kann. 😎
/start um das Hauptmenü zu starten.

Alternativ kannst du auch auf der Website des Studierendenwerk Ulm nachschauen:
{SU_WEBSITE}

Alle Angaben ohne Gewähr. :)
"""

COMMANDS = [
    ("start", "Auswahlmenü starten"),
    ("heute", "Heute"),
    ("morgen", "Morgen"),
    ("allergene", "Allergene schicken"),
    ("speiseplan_pdf", "aktuelle KW als .pdf"),
    ("help", "Hilfe"),
    # ("cancel", "Abbrechen"),
]

MAIN_MENU, ADDS_MENU  = range(2)

# kb_main = [
#     ["👏 HEUTE", "📅 Termin"],
#     ["🌇 Nächster Öffnungstag"],
#     ["🚫 ALLERGENE", "📄 PDF"]]
# main_markup = ReplyKeyboardMarkup(kb_main, resize_keyboard=True)


# kb_adds = [
#     ["👏 HEUTE", "📅 Termin"],
#     ["🌇 Nächster Öffnungstag"],
#     ["🚫 ALLERGENE", "📄 PDF"]]





def format_meals(meal_data: pd.Series) -> str:
    """Takes Data of meals in a Series (1 day) and returns it in a pretty format"""

    formatted_meals = ""
    if any(meal_data == "GESCHLOSSEN"):
        return "GESCHLOSSEN"
    elif any(meal_data == "WOCHENENDE"):
        return "WOCHENENDE, GESCHLOSSEN"

    for m_idx in meal_data.index:
        meal = meal_data.loc[m_idx]
        if m_idx:
            if meal:
                addlist = get_adds(meal)
                additives = ''
                for i in addlist:
                    add = translate_add(i)
                    if add not in additives:
                        additives += add + ", "

                formatted_meals += f"<b>{m_idx}</b>\n{meal}\n<i>Allergene/Zusatzstoffe: {additives}</i>\n\n"

    return formatted_meals


def check_day(lookday: datetime) -> str:
    """Checks for the given day and constructs a response message.

    Example:
    df = pd.read_csv('./meals.csv')
    today = datetime.today()
    message = check_day(today, df)
    """

    r_meals = pd.Series(dtype='object')
    r_weekday = DAYS[lookday.weekday()]
    r_dateformat = "%d.%m.%Y"
    r_date = lookday.strftime(r_dateformat)
    weekend = lookday.weekday() > 4
    cw = lookday.isocalendar()[1]

    try:
        meal_data = pd.read_csv(f'./Meals_CW{cw}.csv',
                                index_col=0,
                                keep_default_na=False)
    except FileNotFoundError:
        message = f"<b>{r_weekday}, {r_date}</b>\n\nKann die Datei nicht finden."
        return message

    df_days = meal_data.columns.values
    for i, d in enumerate(df_days):
        if weekend:
            r_meals = pd.Series("WOCHENENDE")
        elif meal_data.empty:
            r_meals = pd.Series(GO_HUNGRY_MSG)
        elif lookday.weekday() == i:
            r_meals = meal_data[d]

    message = f"<b>{r_weekday}, {r_date}</b>\n\n{format_meals(r_meals)}"
    return message


def get_next_day(df, lookday=None):
    """take df and get next row from today or lookday"""

    if not lookday:
        lookday = datetime.today()
    if lookday.date() in df.index.date:
        return df.loc[str(lookday)]
    else:
        diff_df = df.index-lookday
        return df.loc[diff_df >= timedelta(days=0)].iloc[0]


def start(update: Update, context: CallbackContext) -> int:

    keyboard = [["👏 HEUTE", "📅 Termin"], [
        "🌇 Nächster Öffnungstag"], ["🚫 ALLERGENE", "📄 PDF"]]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text(
        'Siehe Auswahlmenü unten', reply_markup=reply_markup)

    return MAIN_MENU


def heute(update: Update, context: CallbackContext) -> int:
    """Send today's meals."""

    # fetch data
    today = datetime.today()

    # pack message
    message = check_day(today)
    context.bot.send_message(
        chat_id=update.effective_chat.id, text=message, parse_mode='HTML')

    return MAIN_MENU


def morgen(update: Update, context: CallbackContext) -> int:
    """Send tomorrow's meals."""

    # fetch data
    today = datetime.today()
    tomorrow = today + timedelta(days=1)

    # pack & send message
    message = check_day(tomorrow)
    context.bot.send_message(
        chat_id=update.effective_chat.id, text=message, parse_mode='HTML')

    return MAIN_MENU


def adds_menu(update: Update, context: CallbackContext) -> int:
    return ADDS_MENU


def allergene(update: Update, context: CallbackContext) -> int:
    """Send allergene pic or send msg, that its pinned already

       #todo: => umbenennen/zusatzfunktion "DIÄT" o.ä. \
        -   Submenu => 1. Vegetarisch, 2. Vegan, 3. kein Schwein\
            4. individuelle Eingabe => Liste anzeigen, Zahleninput/Buchstabeninput verarbeiten
            -> chat_data['add_filter']

        -   Menu für allergene Modus: chat_data['modus']
                ALL: Zeige alle Additive (eingestellte Additive wirkungslos, aber nicht gelöscht),
                MAR_A: markiere eingestellte Additive mit ‼ (Double Exclamation Mark Emoji) oder ❗ ,
                    und fett <b> </b>, und zeige alle
                FIL_M: filtere die komplette Mahlzeit, die eines der eingestellten additive enthält 
                FIL_A: zeige nur eingestellte additive, alle Mahl        
    """

    allerg_pic_fn = "./allergene_09-2022.jpg"

    this_chat = context.bot.get_chat(chat_id=update.effective_chat.id)

    already_pinned_msg = """
    Sieht so aus, als wären die Allergene schon ⬆ angepinnt 📌.
    """
    # can only get one pinned message, so better ever only pin one
    # if this_chat.pinned_message:
    #     if this_chat.pinned_message.document:
    #         pin_fname = this_chat.pinned_message.document.file_name
    #         if "allergene" in pin_fname:
    #             context.bot.send_message(chat_id=update.effective_chat.id,
    #                                      text=already_pinned_msg,
    #                                      parse_mode='HTML')
    # else:
    with open(allerg_pic_fn, 'rb') as f:
        chat_id = update.effective_chat.id
        allergene_msg = context.bot.send_document(chat_id, f)
        context.bot.pin_chat_message(chat_id=chat_id,
                                     message_id=allergene_msg.message_id)
    return MAIN_MENU


def get_adds(meal_string: str, chained=True) -> list:
    """Returns the additives from a string as a list of strings.\\
    Deletes all whitespace.
    More exactly: Returns all strings inside of round Brackets as \\
    comma-separated strings in a single (chained) list
    """

    pattern = r'(?s)\((.*?)\)'  # everything inside Brackets
    prog = re.compile(pattern)
    result = prog.findall(meal_string)
    result = [re.sub(r"\s+", "", r) for r in result]  # delete whitespace
    if chained:
        return list(chain.from_iterable([a.split(',') for a in result]))
    else:
        return result

# Allergen ausschreiben


def translate_add(additive: str) -> str:
    """Takes string of 1 additive/allergen in numberform + optional letter
    and returns it written out as word(s) in "dictionary style"
    e.g.
    '14'    -> '14: Eier'
    '34W'   -> '34: Gluten W: Weizen'
    '99XY'  -> '99XY': N/A
    """

    pattern = r'(\d*)([a-zA-Z]*)'  # group numbers and letters
    prog = re.compile(pattern)
    res = prog.findall(additive)[0]  # only first result

    number = res[0]
    letter = res[1]
    words = ''
    try:
        if number:
            words += f'{number}: {ZUSATZ_ALLERGENE[number]} '

        if letter:
            if not number:  # => Fleisch?, einzelner Buchstabe
                words += f"{letter}: {FLEISCH[letter]}"
            elif number == GELATINE_NUMBER:
                words += f"{letter}: {FLEISCH[letter]}"
            elif number == GLUTEN_NUMBER:
                words += f"{letter}: {GLUTEN[letter]}"
            elif number == NUESSE_NUMBER:
                words += f"{letter}: {NUESSE[letter]}"
            else:
                words += f"{letter}: N/A"

    except KeyError:
        # print("ERROR: Unbekannter Zusatzstoff oder Allergen. Möglicherweise muss die Liste aktualisiert werden. Oder ein Eintragungsfehler im Speiseplan besteht.")
        words = f"'{number}{letter}': N/A"

    return words


def pdf(update: Update, context: CallbackContext) -> int:
    """Send current pdf-file"""

    today = datetime.today()
    cw = today.isocalendar()[1]
    pdf_fn = f"./Speiseplan_CW{cw}_2022.pdf"
    with open(pdf_fn, 'rb') as f:
        chat_id = update.effective_chat.id
        context.bot.send_document(chat_id, f)
    return MAIN_MENU


def cancel(update: Update, context: CallbackContext) -> int:
    """Returns to menu start"""
    # maybe add something here later
    return MAIN_MENU


def end(update: Update, context: CallbackContext) -> int:
    """Returns to menu start"""
    # maybe add something here later
    return MAIN_MENU


def help_command(update: Update, context: CallbackContext) -> None:
    """Displays info on how to use the bot."""
    update.message.reply_text(HELP_MSG)


def main() -> None:
    """Run the bot."""

    # read config and store each line in config_dict
    config_filename = "devbot.conf"
    # config_filename = "speiseplanbot.conf"
    with open(config_filename) as f:
        config_dict = {
            'token': None,
            'dev_id': None,
        }
        for line in f.readlines():
            k, v = line.strip().split()
            if k.lower() in config_dict.keys():
                config_dict[k.lower()] = v

    global DEV_ID
    DEV_ID = config_dict['dev_id']
    persistence = PicklePersistence(filename="speiseplanbot_pickle")

    updater = Updater(config_dict['token'], persistence=persistence)
    dispatcher = updater.dispatcher

    # Add conversation handler with predefined states:
    conv_handler = ConversationHandler(
        # per_message = True,
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(Filters.regex(r"HEUTE"), heute),
                   MessageHandler(Filters.regex(r"MORGEN"), morgen),
                   MessageHandler(Filters.regex(r"ALLERGENE"), allergene),
                   MessageHandler(Filters.regex(r"PDF"), pdf)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(CommandHandler('heute', heute))
    dispatcher.add_handler(CommandHandler('morgen', morgen))
    dispatcher.add_handler(CommandHandler('allergene', allergene))
    dispatcher.add_handler(CommandHandler('speiseplan_pdf', pdf))
    dispatcher.add_handler(CommandHandler('cancel', cancel))

    dispatcher.bot.set_my_commands(COMMANDS)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
