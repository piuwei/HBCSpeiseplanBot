#!/usr/bin/env python3
import urllib.request
from datetime import date

from bs4 import BeautifulSoup

from parse_food_pdf import get_calendarweek, parse_date_from_pdf


def get_menulinks(menuurl = 'https://studierendenwerk-ulm.de/essen-trinken/speiseplaene/',
                  link_identifier = '/BC'):
    with urllib.request.urlopen(menuurl) as r:
        html_doc = r.read().decode("UTF-8")
    
    soup = BeautifulSoup(html_doc, 'html.parser')
    foodlinks = []
    
    # if this breaks...try sth like this and fish for the links in the <div>:
    # soup.find(id="akkordeon-speiseplan-biberach")
    for link in soup.find_all('a'):
        if link_identifier in link.get('href'):
            foodlinks.append(link.get('href').replace(" ", "%20"))
            
    return foodlinks
                    
def save_speiseplan(pdf_dl, fname) -> None:
    with open(f"./dld/{fname}", 'wb') as f:
        f.write(pdf_dl)
        
    # store a copy with calendar week parsed from inside the pdf (in case filename is "wrong")
    # this is the one we use
    pdate = parse_date_from_pdf(f"./dld/{fname}")
    cw = get_calendarweek(pdate)
    yyyy = date.today().year
    
    with open(f"./Speiseplan_CW{cw}_{yyyy}.pdf", 'wb') as f:
        f.write(pdf_dl)
        
    print(f"saved --> ./dld/{fname}, ./Speiseplan_CW{cw}_{yyyy}.pdf")
    
def main():
    
    menuurl = 'https://studierendenwerk-ulm.de/essen-trinken/speiseplaene/'
    foodlinks = get_menulinks(menuurl)
    
    for foodlink in foodlinks:
        fname = foodlink.split("/")[-1].replace("%20", "_")
        with urllib.request.urlopen(foodlink) as speiseplan:
            pdf_dl = speiseplan.read()
        save_speiseplan(pdf_dl, fname)
        
if __name__ == "__main__":
    main()
