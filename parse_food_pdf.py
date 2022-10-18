#!/usr/bin/env python3
from datetime import date, datetime

import camelot
import pandas as pd


def get_calendarweek(datestring = "07.10.2022") -> int:
    pdate = datetime.strptime(datestring, "%d.%m.%Y")
    cw = pdate.isocalendar()[1]
    return cw

def parse_date_from_pdf(fn = "Latest_Speiseplan.pdf", which_date=1) -> str:
    dates = camelot.read_pdf(fn,
                            flavor='stream',
                            table_areas = ['10,590,280,520'],
                            # position of title and dates, may need to adjust in future versions, '0,0,0,0' in bottom left corner
                            )
    
    datumsangaben = dates[0].df.iloc[1].loc[0].split(' ')
    datestring = datumsangaben[which_date]
    
    if which_date==0:
        today = date.today()
        datestring = datestring.replace('-', str(today.year))
    
    return datestring

def parse_speiseplan_to_df(fn = "Latest_Speiseplan.pdf") -> pd.DataFrame:
    """Parse pdf file for Speiseplan Data.\\
    Maybe needs to be adjusted if Speiseplan changes (Table). \\
    Assumes a meal in every category for every day, probably returns wrong data otherwise.
    
    Also does some basic cleanup of data specific to HBC-Speiseplan file.
    """
    # todo: scan for vegan / vegetarian pictures
    
    # good settings as of 22-09-29, possibly needs adjustments on changes in table layout
    tables_lattice = camelot.read_pdf(fn,
                          flavor='lattice',
                          process_background = True,
                          suppress_stdout=True, #quiet
                          line_tol = 2.5,
                          threshold_blocksize = 15,
                          shift_text = ['b'],
                          split_text = False,
                          layout_kwargs={'detect_vertical': False, 'word_margin' : 0.15},
                          ) 
    
    df = tables_lattice[0].df

    # Cleanup
    #   - delete random invisble crap and unnessecary newlines
    df = df.apply(lambda x: x.str.replace(r"\n?|Mensa HS Prittwitzstraße|hinterhuhinterlegthinterlegt", "", regex=True))

    #   - make it nice one-liners
    df = df.apply(lambda x: x.str.replace(r"\n", " ", regex=True))
    
    #   - indexing, and col naming
    df[0].iloc[0] = "KATEGORIE"
    df = df.rename(columns=df.iloc[0])\
           .drop(0, axis=0)\
           .set_index("KATEGORIE", verify_integrity=True)
           
    df.index = df.index.str.strip()
    
    return df

def main():
    
    # todo: autodelete old csv files (e.g. older than 4 weeks)

    today = date.today()
    current_cw = today.isocalendar()[1]
    next_cw = today.isocalendar()[1] + 1
    yyyy = today.year

    try: #current week, should be there 
        file = f"./Speiseplan_CW{current_cw}_{yyyy}.pdf"
        df = parse_speiseplan_to_df(file)
        
        # reads calendar week from dates in the file
        pdate = parse_date_from_pdf(file)
        cw = get_calendarweek(pdate)
        
        df.to_csv(f'./Meals_CW{cw}.csv')
    except:
        pass

    try: #next week, might be there
        file = f"./Speiseplan_CW{next_cw}_{yyyy}.pdf"
        df = parse_speiseplan_to_df(file)
        
        # reads calendar week from dates in the file
        pdate = parse_date_from_pdf(file)
        cw = get_calendarweek(pdate)
        
        df.to_csv(f'./Meals_CW{cw}.csv')
    except:
        pass
    
if __name__ == "__main__":
    main()
