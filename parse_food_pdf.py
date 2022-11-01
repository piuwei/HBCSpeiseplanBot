#!/usr/bin/env python3
from datetime import date, datetime

import camelot
import pandas as pd

from speiseplanbot import DAYS


def get_calendarweek(datestring = "07.10.2022") -> int:
    pdate = datetime.strptime(datestring, "%d.%m.%Y")
    cw = pdate.isocalendar()[1]
    return cw

def parse_date_from_pdf(fn = "Latest_Speiseplan.pdf", which_date=1) -> str:
    dates = camelot.read_pdf(fn,
                            flavor='stream',
                            table_areas = ['10,540,150,520'],
                            # position of title and dates, may need to adjust in future versions, '0,0,0,0' in bottom left corner
                            )
    
    datumsangaben = dates[0].df.iloc[0].loc[0].split('–')
    datestring = datumsangaben[which_date].strip()
    
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
    # todo: scan for vegan / vegetarian pictures, possible? => mini pics in new layout
    
    # settings changed for new table layout on 22-10-21
    tables_lattice = camelot.read_pdf(fn,
                                  flavor='lattice',
                                  suppress_stdout = True,
                                  table_areas = ['1,520,842,60'],
                                  # strip_text = '',
                                      
                                  # all
                                  # table_areas
                                  # line_scale = 50,
                                  # split_text = False,
                                  
                                  # stream
                                  # columns
                                  # row_tol = 21,      #2
                                  # column_tol = 0,   #0
                                  
                                  
                                  # lattice
                                  joint_tol = 10,
                                  threshold_blocksize = 7,
                                  shift_text = ['b'],
                                  process_background = True,
                                  line_tol = 10,
                                  line_scale = 20,
                                  # copy_text
                                  
                                  #pdfminer LAParams
                                    layout_kwargs={
                                    #   'line_overlap':0.99,
                                    #   'line_margin':0.7,
                                    #   'word_margin' : 0.15,
                                      # 'boxes_flow': 1,
                                      },
                                    
                                  )
    
    df = tables_lattice[0].df

    # Cleanup
    #   - delete random invisble crap (gone in newer version (since 22-10-24)), and unnessecary newlines
    # df = df.apply(lambda x: x.str.replace(r"\n?|Mensa HS Prittwitzstraße|hinterhuhinterlegthinterlegt", "", regex=True))

    #   - make it nice one-liners
    df = df.apply(lambda x: x.str.replace(r"\n", " ", regex=True))

    #   - indexing, and col naming
    df.columns = ['KATEGORIE'] + DAYS[:5]
    df = df.set_index('KATEGORIE', verify_integrity=True)
    df.index = df.index.str.strip()
    
    return df

def main():
    
    # todo: autodelete old csv files (e.g. older than 4 weeks)

    today       = date.today()
    current_cw  = today.isocalendar()[1]
    next_cw     = today.isocalendar()[1] + 1
    yyyy        = today.year

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
        
        df.to_csv(f'./Meals_CW{cw}.csv'),
    except FileNotFoundError:
        print(f'CW{next_cw}, not there (yet?)')
        pass # else
    
    except:
        raise
    
if __name__ == "__main__":
    main()
