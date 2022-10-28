#!/usr/bin/env python3
# pylint: disable=C0116,W0613
# This program is dedicated to the public domain under the CC0 license.
"""
Das ist ein Bot, der infos zum Speiseplan an der HBC gibt. => Git

TODO-Liste:

    ✓ Allergene und Zusatzstoffe parsen (regex pattern = r'\(.*?\)' -> Sachen in klammern)
    ✓ Allergene und Zusatzstoffe als settings pro chat fixieren (chat_data dict...)
    ✓ Vegan und vegetarisch...
    ✓ inline Keyboard? => für manche Funktionen (wie z.B. Allergene etc.) oder alles
    ✓ nächster Öffnungs-/Arbeitstag, statt "Morgen"?
    ☐ Anpassungen des großen Gesamtplans (Bild Lukas) ??
    ☐ beliebiger Termin => Dialog mit Termineingabe, "maximaler"/letztmöglicher Termin
    ☐ Submenü pdf => nächste Woche oder "großer Gesamtplan"
    ✓ Öffnungszeiten
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
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, Update)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, ConversationHandler, Filters,
                          MessageHandler, PicklePersistence, Updater)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

onoff = lambda x : 'AN' if x else 'AUS'

DAYS = ['MONTAG', 'DIENSTAG', 'MITTWOCH',
        'DONNERSTAG', 'FREITAG', 'SAMSTAG', 'SONNTAG']

SU_WEBSITE = "https://studierendenwerk-ulm.de/essen-trinken/speiseplaene/"

GO_HUNGRY_MSG = f"""Scheinbar gibt es nichts zu Essen! 😞"""

START_MSG = """Hi 👋👋\nWas hättest du gerne?\n\n"""

OPEN_TIMES = """
<u>Öffnungszeiten Mensa HBC:</u>
Mo - Do 7.30 bis 16.30 Uhr, Essensausgabe 11.30 bis 13.45 Uhr
Fr 7.30 bis 14.30 Uhr, Essensausgabe 11.30 bis 13.30 Uhr

<u>Cafeteria Aspach:</u>
11.45 bis 13.30 Uhr

<i>Stand: Oktober 2022</i>"""

SHORT_DISCLAIMER = "(<i>Alle Angaben ohne Gewähr.</i>)"

DISCLAIMER = """<i>Alle Angaben ohne Gewähr.\n\
Sind im Speiseplan nicht alle Zusatzstoffe angegeben, oder Klammern falsch gesetzt \
kann die Interpretation der Mahlzeiten u.U. nicht der Realität entsprechen.</i>
"""

FMODE_MENU_MSG ="""
    Einstellung des Filtermodus:
 - <u>Alle Additive zeigen</u>: Es werden alle Additive ausgeschrieben und nichts gefiltert
 - <u>Zutaten markieren</u>: Eingestellte Zutaten werden mit ❗ markiert
 - <u>Mahlzeiten filtern</u>: Mahlzeiten, die eine eingestellte Zutat enthalten werden rausgefiltert und nicht gezeigt
 - <u>Zutaten filtern</u>: Nur relevante (eingestellte) Zutaten werden gezeigt.
"""

MEATY_WORDS = {'fleisch', 'hähnchen', 'pute', 'schwein', 'rind', 'lamm', 'geflügel',
               'wienerle', 'schinken', 'jäger', 'speck', 'backhendl', 'hendl', 'cevapcici', 'kalb'}

FISHY_WORDS = {'lachs', 'fisch', 'scholle', 'aal', 'hering', 'forelle', 'thunfisch'}

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
    "14": "🥚 Eier",
    "22": "Erdnüsse",
    "23": "Soja",
    "24": "🥛 Milch/Milchprodukte",
    "25": "Schalenfrüchte/alle Nussarten",
    "26": "Sellerie",
    "27": "Senf",
    "28": "Sesamsamen",
    "29": "Schwefeldioxid",
    "30": "Sulfite",
    "31": "Lupine",
    "32": "🐙 Weichtiere",
    "34": "Gluten",
    "35": "🐟 Fisch",
}
GELATINE_NUMBER = "18"
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
    "R": "🐄 Rind",
    "S": "🐖 Schwein",
    "G": "🐓 Geflügel",
    "L": "🐑 Lamm",
    "W": "🦌🐗 Wild",
}
FISCH = {   # andere Tiere 
    "13": "Krebstiere",
    "32": "🐙 Weichtiere",
    "35": "🐟 Fisch",
}

TIERISCH = {  # nicht Fleisch, aber tierisch, also nicht vegan
    "14": "🥚 Eier",
    "18": "Gelatine",
    "24": "🥛 Milch/Milchprodukte",
}

NICHT_VEGAN = dict(FLEISCH, **TIERISCH)
NICHT_VEGETARISCH = dict({
    "13": "Krebstiere",
    "32": "🐙 Weichtiere",
    "35": "🐟 Fisch",
}, **FLEISCH, **FISCH)

HELP_MSG = f"""
/start um das Hauptmenü zu starten.
Da können auch verschiedene Einstellungen gemacht werden.

Alle Angaben ohne Gewähr. :)
"""

MAIN_MENU, ADDS_MENU, FILTER_MENU, FMODE_MENU  = range(4)

# Inline-Keyboards
kb_main = [
    [InlineKeyboardButton("👏 Heute", callback_data='today'),
     InlineKeyboardButton("🌇 Nächstes Mal", callback_data='nextday')],
    [InlineKeyboardButton("⚙ Einstellungen", callback_data='adds')]
    ]
main_markup = InlineKeyboardMarkup(kb_main)

kb_adds = [
    [InlineKeyboardButton("Zutaten einstellen", callback_data='filter'),   #> kb_filter
     InlineKeyboardButton("Filter-Modus", callback_data='fmode')],           #> kb_fmode
    [InlineKeyboardButton("Einfacher Modus", callback_data='simple')],
    [InlineKeyboardButton("Zurück", callback_data='back')]
    ]
adds_markup = InlineKeyboardMarkup(kb_adds)

FILTER_DICT = {
        'vegetarian' : 'vegetarisch',
        'vegan' : 'vegan',
        'nopig' : 'Schwein',
        'default' : 'Nichts filtern',
        }
kb_filter = [
    [InlineKeyboardButton("Vegetarisch", callback_data='vegetarian'),
     InlineKeyboardButton("Vegan", callback_data='vegan')],
    [InlineKeyboardButton("Schwein", callback_data='nopig'),
     InlineKeyboardButton("Nichts filtern", callback_data='default')],
    [InlineKeyboardButton("Zurück", callback_data='back')],
    #  todo: InlineKeyboardButton("Individuell", callback_data='special'), #> großes Submenu(s) oder texteingabe
    ]
filter_markup = InlineKeyboardMarkup(kb_filter)

DEFAULT_FMODE = {
            'default' : 1, # showall
            'filter_adds' : 0,
            'filter_meals' : 0,
            'mark' : 0,
            'simple' : 0, # makes other settings irrelevant
            }

kb_fmode = [
    [InlineKeyboardButton("Alle Additive zeigen", callback_data='default'),      # Alles wird gezeigt/geparst, nix gefiltert
     InlineKeyboardButton("Zutaten markieren", callback_data='mark')],     # Eingestellte Zutaten werden mit❗und <b> </b>markiert
    [InlineKeyboardButton("Mahlzeiten filtern", callback_data='filter_meals'),     # Mahlzeiten mit markierten Zutaten werden nicht gezeigt
     InlineKeyboardButton("Zutaten filtern", callback_data='filter_adds')],       # Nur eingestellte Zutaten zeigen
    [InlineKeyboardButton("Zurück", callback_data='back')],
     ]
fmode_markup = InlineKeyboardMarkup(kb_fmode)

# todo: Mehr Optionen (submenu):
    #  InlineKeyboardButton("📅 Termin", callback_data='date')],
    #  InlineKeyboardButton("📄 PDF", callback_data='nextday')]]
def parse_meal_info(meal):
        
    co2 = re.findall(r'(?s)(CO2.*?g)', meal)
    prices = re.findall(r'(?s)(\d,\d{2} €)', meal)
    meal_text = re.search(r'(?s)(.*?)((?=CO2)|(?=\d,\d{2} )|$)', meal) # everything before CO2 or prices
    res_dict = {'meal': meal_text.group(0), 'co2_text': co2, 'prices_text': prices}
    
    return res_dict

def format_meals(meal_data: pd.Series, filter='default', fmode='default') -> str:
    """Takes Data of meals in a Series (1 day) and returns it in a pretty format,
    TODO: Zutaten Filtern nach geg. Einstellungen in chat_data
     
    """

    if any(meal_data == "GESCHLOSSEN"):
        return "GESCHLOSSEN"
    elif any(meal_data == "WOCHENENDE"):
        return "WOCHENENDE, GESCHLOSSEN"
        
    if filter=='default':
        filter_values = []
    elif filter=='vegetarian':
        filter_values = set().union(*[NICHT_VEGETARISCH.values(), MEATY_WORDS, FISHY_WORDS])
    elif filter=='vegan':
        filter_values = set().union(*[NICHT_VEGAN.values(), TIERISCH.values(), MEATY_WORDS, FISHY_WORDS])
    elif filter=='nopig':
        filter_values = ['schwein']
        
    # todo regex filter ('special'), any user defined keywords... sth. like:
    # if filter=='special:
        # filter_values.union(tbd: user_defined_words)
        
    formatted_meals = []
    for m_idx in meal_data.index:
        meal_text = meal_data.loc[m_idx]
        if m_idx:
            meal_info_dict = parse_meal_info(meal_text)
            
            meal = meal_info_dict['meal']
            if meal and meal != 'siehe Monitor': # exclude uninformative "siehe Monitor"
                co2 = meal_info_dict['co2_text']
                if co2 : co2 = co2[0]
                prices = meal_info_dict['prices_text']
                if prices :
                    prices = f"S: {prices[0]} | M: {prices[1]} | G: {prices[2]}"
                
                # print(meal, co2, prices)
                addlist = get_adds(meal) # raw numbers and letters
                additives = ''
                for i in addlist:
                    add = translate_add(i) # translated string value
                    if add not in additives:
                        additives += add + ", "
                        
                
                # print(meal, meal.lower())
                # define vegan / vegetarian and meaty/fishy
                contains_meat = any([f for f in dict(FLEISCH).values() if f in additives]) or \
                                any([mw for mw in MEATY_WORDS if mw.lower() in meal.lower()])
                contains_fish = any([f for f in dict(FISCH).values() if f in additives]) or \
                                any([fw for fw in FISHY_WORDS if fw.lower() in meal.lower()])
                vegetarian = not contains_meat and not contains_fish
                
                contains_animal_product = any([nv for nv in TIERISCH.values() if nv in additives])
                vegan = not contains_animal_product and vegetarian
                
                # check for level of veganity/veganness/animality
                veganness = 'veganität unklar, '
                prefix_len = len(veganness)
                sep = ', '
                
                # x = lambda x, msg, sep: msg + x + sep
                if contains_meat:
                    veganness += "enthält Fleisch" + sep
                    
                if contains_fish:
                    veganness += "enthält Fisch/Meeresfrüchte" + sep
                    
                if vegan:
                    veganness += "vegan" + sep
                elif vegetarian:
                    veganness += "vegetarisch" + sep
                
                veganness = veganness[prefix_len:-len(sep)]
                
                if fmode['simple']:
                    formatted_meals.append(
                    f"<u>{m_idx}</u> → <i>{veganness}</i>\n🍽 <b>{meal}</b>\n{prices}\n\n\n"
                    )
                    continue
                    
                # show only relevant adds if filtermode set
                if fmode['filter_adds'] and not fmode['default']:
                    additives = ''
                    for i in addlist:
                        add = translate_add(i)
                        if filter_values:
                            for f in filter_values:
                                if f in add and add not in additives:
                                    additives += add + ", "
                        else:
                            additives += add + ", "
                                
                # mark adds if filtermode set
                if fmode['mark']:
                    for f in filter_values:
                        danger_pos_adds = additives.find(f)
                        if danger_pos_adds != -1 :
                            additives = additives[:danger_pos_adds] + "❗" + additives[danger_pos_adds:]

                        danger_pos_meal = meal.lower().find(f.lower())
                        if danger_pos_meal != -1 :
                            meal = meal[:danger_pos_meal] + "❗" + meal[danger_pos_meal:]
                            
                additives = additives[:-2]
                newline_str = "\n" # no backslash in f-string
                
                formatted_meals.append(
                    f"""<u>{m_idx}</u> → <i>{veganness}</i>\n🍽 <b>{meal}</b>\n{prices}\n{"<i>"+additives+"</i>"+newline_str if additives else ''}\n\n"""
                    )
                
    if fmode['default']: # show all meals, dont filter
        return formatted_meals
                                    
    if fmode['filter_meals']:
        formatted_meals_new = []
        for formatted_meal in formatted_meals:
            if not [f for f in filter_values if f.lower() in formatted_meal.lower()]:
                formatted_meals_new.append(formatted_meal)
        formatted_meals = formatted_meals_new
    return formatted_meals
    
def check_day(lookday: datetime, filter='default', fmode='default') -> str:
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

    message = f"<b>{r_weekday}, {r_date}</b>\n\n" + "".join(format_meals(r_meals,
                                                                         filter=filter,
                                                                         fmode=fmode))
    return message

def get_next_day(context):
    """take df and get next row from today or lookday"""

    today = datetime.today()
    settings = get_settings(context)
    
    message = 'GESCHLOSSEN'
    day_counter = 0 
    while ('GESCHLOSSEN' in message):
        day_counter += 1 # mindestens morgen?
        next_day = today + timedelta(days=day_counter)
        message = check_day(next_day,
                            filter = settings['filter_setting'],
                            fmode = settings['fmode_setting'])
        
    return message


def start(update: Update, context: CallbackContext) -> int:
    
    # make default settings
    chat_keys = context.chat_data.keys()
    if 'filter_setting' not in chat_keys: 
        context.chat_data['filter_setting'] = 'default'
        
    if 'fmode_setting' not in chat_keys: 
        context.chat_data['fmode_setting'] = DEFAULT_FMODE

    update.message.reply_text(START_MSG + SHORT_DISCLAIMER,
                              reply_markup=main_markup,
                              parse_mode='HTML')

    return MAIN_MENU

def get_settings(context: CallbackContext):
    settings = {}
    if 'filter_setting' in context.chat_data.keys():
        filter_setting = context.chat_data['filter_setting']
    else:
        filter_setting = 'default'

    if 'fmode_setting' in context.chat_data.keys():
        fmode_setting = context.chat_data['fmode_setting']
    else:
        fmode_setting = DEFAULT_FMODE
        
    settings['filter_setting'] = filter_setting
    settings['fmode_setting'] = fmode_setting
    return settings

def respond_via_cmd_or_conv(message, markup, conv_state, update, context):
    if update.callback_query: # Inline Conversation / Menu
        query = update.callback_query
        query.answer()
        query.edit_message_text(message, reply_markup=markup, parse_mode='HTML')
        return conv_state
    else: # call from command
        context.bot.send_message(chat_id=update.message.chat_id,
                                    text=message,
                                    parse_mode='HTML')
        return None
            
def today(update: Update, context: CallbackContext):
    """Send today's meals."""

    # fetch data
    today = datetime.today()
    settings = get_settings(context)
    
    # pack message
    message = check_day(today,
                        filter = settings['filter_setting'],
                        fmode = settings['fmode_setting'])
    
    return respond_via_cmd_or_conv(message, main_markup, MAIN_MENU, update, context)

def next_day(update: Update, context: CallbackContext):
    """Send next opening day's meals."""
        
    message = get_next_day(context)
        
    return respond_via_cmd_or_conv(message, main_markup, MAIN_MENU, update, context)


def adds_menu(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    message ="""
 - <u>Zutaten einstellen</u>: Hier können die Zutaten eingestellt werden, die markiert oder gefiltert werden sollen
 - <u>Filter-Modus</u>: Hier kann eingstellt werden, ob gefiltert und/oder markiert werden soll.
 - <u>Einfacher Modus</u>: Speiseplan ohne ausgeschriebene Zutaten zeigen.
"""
    # query.edit_message_reply_markup(reply_markup=adds_markup)
    
    query.edit_message_text(message, reply_markup=adds_markup, parse_mode='HTML')
    return ADDS_MENU

def filter_menu(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    # message = "FILTER"
    query.edit_message_reply_markup(reply_markup=filter_markup)
    
    # query.edit_message_text(message, reply_markup=filter_markup, parse_mode='HTML')
    return FILTER_MENU

def fmode_menu(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    message = FMODE_MENU_MSG
    query.edit_message_text(message,
                            reply_markup=fmode_markup,
                            parse_mode='HTML')
    return FMODE_MENU

def pretty_settings(settings):
    
    print(settings['filter_setting'], settings['fmode_setting'])
    message = ''
    simple_mode = settings['fmode_setting']['simple']
    if simple_mode:
        message += f"<b>EINFACHER MODUS AN </b>\n(Filter-Einstellungen wirkungslos)\n\n<s>"
        
    if settings['filter_setting']:
        fsetting = settings['filter_setting']
        message += f"Filter: {FILTER_DICT[fsetting]}\n"
        # todo: add user-defined filter keywords
        
    if settings['fmode_setting'] and settings['fmode_setting']['default']:
        fmode = settings['fmode_setting']
        message += f"""Filtermodus gewählt:
- <b>Alle Additive zeigen: {onoff(fmode['default'])}</b>
- Zutaten markieren: {onoff(fmode['mark'])}{"</s>" if simple_mode else ""}<s>
- Mahlzeiten filtern: {onoff(fmode['filter_meals'])}
- Zutaten filtern: {onoff(fmode['filter_adds'])}</s>"""

    elif settings['fmode_setting']:
        fmode = settings['fmode_setting']
        message += f"""Filtermodus gewählt:
- Alle Additive zeigen: {onoff(fmode['default'])}
- Zutaten markieren: {onoff(fmode['mark'])}
- Mahlzeiten filtern: {onoff(fmode['filter_meals'])}
- Zutaten filtern: {onoff(fmode['filter_adds'])}{"</s>" if simple_mode else ""}"""

    return message

def make_preview(context):
    next_day = get_next_day(context)
    preview = f"VORSCHAU DER EINSTELLUNGEN:\n\n{next_day}"
    message = f"{preview}\n\n{pretty_settings(context.chat_data)}"
    return message

def set_simple_mode(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    qd = query.data
    
    context.chat_data['fmode_setting'][qd] ^= 1
    
    message = make_preview(context)
    query.edit_message_text(message, reply_markup=adds_markup, parse_mode='HTML')
    
    return ADDS_MENU
    
def set_filter(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    
    context.chat_data['filter_setting'] = query.data
    
    message = make_preview(context)
    query.edit_message_text(message,
                            reply_markup=filter_markup,
                            parse_mode='HTML')
    return FILTER_MENU
    
def set_fmode(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    qd = query.data
    
    context.chat_data['fmode_setting'][qd] ^= 1 # toggle setting
    
    message = make_preview(context)    
    query.edit_message_text(message, reply_markup=fmode_markup, parse_mode='HTML')
    return FMODE_MENU

def allergene_jpeg(update: Update, context: CallbackContext) -> int:
    """Send allergene pic"""
    
    allerg_pic_fn = "./allergene_09-2022.jpg"
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
            words += f"{number}={ZUSATZ_ALLERGENE[number]}"

        if letter:
            if not number:  # => Fleisch?, einzelner Buchstabe
                words += f"{letter}={FLEISCH[letter]}"
            elif number == GELATINE_NUMBER:
                words = f"{number}{letter}={FLEISCH[letter]}~{ZUSATZ_ALLERGENE[number]}"
            elif number == GLUTEN_NUMBER:
                words = f"{number}{letter}={GLUTEN[letter]}~{ZUSATZ_ALLERGENE[number]}"
            elif number == NUESSE_NUMBER:
                words = f"{number}{letter}={NUESSE[letter]}"
            else:
                words += f"{letter}=N/A"

    except KeyError:
        # print("ERROR: Unbekannter Zusatzstoff oder Allergen. Möglicherweise muss die Liste aktualisiert werden. Oder ein Eintragungsfehler im Speiseplan besteht.")
        words = f"'{number}{letter}'=N/A"

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

def back_to_main(update: Update, context: CallbackContext) -> int:
    """Returns to menu start"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(START_MSG + SHORT_DISCLAIMER,
                            reply_markup=main_markup, parse_mode='HTML')
    
    return MAIN_MENU

def back_to_adds(update: Update, context: CallbackContext) -> int:
    """Returns to menu start"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_reply_markup(reply_markup=adds_markup)
    
    return ADDS_MENU

def back_to_filter(update: Update, context: CallbackContext) -> int:
    """Returns to menu start"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_reply_markup(reply_markup=filter_markup, parse_mode='HTML')
    
    return FILTER_MENU

def end(update: Update, context: CallbackContext) -> int:
    """Returns to menu start"""
    # maybe add something here later
    return MAIN_MENU


def help_command(update: Update, context: CallbackContext) -> None:
    """Displays info on how to use the bot."""
    update.message.reply_text(HELP_MSG)
    
def open_times(update: Update, context: CallbackContext) -> None:
    """Displays opening times."""
    update.message.reply_text(OPEN_TIMES,
                              reply_markup=main_markup,
                              parse_mode='HTML')
    

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
            MAIN_MENU: [
                CallbackQueryHandler(today, pattern = r"^today$"),
                CallbackQueryHandler(next_day, pattern = r"^nextday$"),
                CallbackQueryHandler(adds_menu, pattern = r"^adds$"),
                #    MessageHandler(Filters.regex(r"PDF"), pdf)
                ],
            ADDS_MENU: [
                CallbackQueryHandler(filter_menu, pattern = r"^filter$"),
                CallbackQueryHandler(fmode_menu, pattern = r"^fmode$"),
                CallbackQueryHandler(set_simple_mode, pattern = r"^simple$"),
                CallbackQueryHandler(back_to_main, pattern = r"^back$"),
                ],
            FILTER_MENU: [
                CallbackQueryHandler(set_filter, pattern = r"^default|vegetarian|vegan|nopig|special$"),
                CallbackQueryHandler(back_to_adds, pattern = r"^back$"),
                ],
            FMODE_MENU: [
                CallbackQueryHandler(set_fmode, pattern = r"^default|mark|filter_meals|filter_adds$"),
                CallbackQueryHandler(back_to_adds, pattern = r"^back$"),
                ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(CommandHandler('today', today))
    dispatcher.add_handler(CommandHandler('next', next_day))
    dispatcher.add_handler(CommandHandler('allergene', allergene_jpeg))
    dispatcher.add_handler(CommandHandler('speiseplan_pdf', pdf))
    dispatcher.add_handler(CommandHandler('open', open_times))
    
    
    # dispatcher.add_handler(CommandHandler('cancel', cancel))


    COMMANDS = [
        ("start", "Auswahlmenü starten"),
        ("today", "Heute"),
        ("next", "Nächster Öffnungstag"),
        ("open", "Zeige Öffnungszeiten Mensa HBC"),
        ("allergene", "Allergene als .jpg schicken"),
        ("speiseplan_pdf", "aktuelle KW als .pdf"),
        ("help", "Hilfe"),
        # ("cancel", "Abbrechen"),
    ]
    
    dispatcher.bot.set_my_commands(COMMANDS)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
