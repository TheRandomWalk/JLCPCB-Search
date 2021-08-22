import argparse
import pandas
import math
import requests
import os
import sys
import io


# Settings

url = 'https://jlcpcb.com/componentSearch/uploadComponentInfo'
filename = 'data.parquet'


# Functions

def fixUnicode(df):
    df['First category'] = df['First category'].str.replace('\uff08', '(')
    df['First category'] = df['First category'].str.replace('\uff09', ')')
    df['First category'] = df['First category'].str.replace('\uff0c', ',')

    df['Second category'] = df['Second category'].str.replace('\uff08', '(')
    df['Second category'] = df['Second category'].str.replace('\uff09', ')')
    df['Second category'] = df['Second category'].str.replace('\uff0c', ',')

    df['Manufacturer'] = df['Manufacturer'].str.replace('\uff08', '(')
    df['Manufacturer'] = df['Manufacturer'].str.replace('\uff09', ')')

    df['PN'] = df['PN'].str.replace('\uff08', '(')
    df['PN'] = df['PN'].str.replace('\uff09', ')')
    df['PN'] = df['PN'].str.replace('\uff0c', ',')
    df['PN'] = df['PN'].str.replace('\uff0d', '-')
    df['PN'] = df['PN'].str.replace('\u3000', '')            # Ideographic space
    df['PN'] = df['PN'].str.replace('\u2103', '\u00b0C')     # Celsius
    df['PN'] = df['PN'].str.replace('\u03bc', '\u00b5')      # Small mu
    
    df['Package'] = df['Package'].str.replace('\u00d7', 'x')

    df['Description'] = df['Description'].str.replace('\uff08', '(')
    df['Description'] = df['Description'].str.replace('\uff09', ')')
    df['Description'] = df['Description'].str.replace('\uff0c', ',')
    df['Description'] = df['Description'].str.replace('\u2103', '\u00b0C')   # Celsius
    df['Description'] = df['Description'].str.replace('\u00AE', '(R)')
    df['Description'] = df['Description'].str.replace('\u2122', '(TM)')
    df['Description'] = df['Description'].str.replace('\u03A9', 'Ohms')
    df['Description'] = df['Description'].str.replace('\u201d', '\"')
    df['Description'] = df['Description'].str.replace('\uff0d', '-')
    df['Description'] = df['Description'].str.replace('\u2264', '<=')
    df['Description'] = df['Description'].str.replace('\uff05', '%')
    df['Description'] = df['Description'].str.replace('\uff1A', ': ')
    df['Description'] = df['Description'].str.replace('\u03bc', '\u00b5')    # small mu
    df['Description'] = df['Description'].str.replace('\u03c6', '')          # Small phi
    df['Description'] = df['Description'].str.replace('\u03a6', '')          # Capital phi
    
    def fixChinese(s): 
        if s is not None: 
            return s.encode('latin_1', errors = "ignore").decode('latin_1') 
        else: 
            return None

    df['Description'] = df['Description'].apply(fixChinese)
    df['Package'] = df['Package'].apply(fixChinese)

    return df


def download(args = None):
    print ('Downloading database... ')

    df = pandas.read_csv(io.StringIO(requests.get(url).content.decode('gbk')), index_col = False)
    df.columns = ['LCSC', 'First category', 'Second category', 'PN', 'Package', 'Pins', 'Manufacturer', 'Type', 'Description', 'Datasheet', 'Price', 'Stock']
    df.to_parquet(filename)

    print ('Saved {:,d} entries.'.format(df.shape[0]))


def makeCategories():
    if not os.path.isfile(filename):
        download()
    
    df = fixUnicode(pandas.read_parquet(filename))
    
    pairs = sorted(list(set(tuple(t) for t in (df[['First category', 'Second category']].values.tolist()))))

    categories = []

    primary = ''

    for (p, s) in pairs:
        if p != primary:
            categories.append([p])
            primary = p
    
        categories.append([p,s])

    return categories


def printCategories(args):
    categories = makeCategories()

    for i, category in enumerate(categories):
        if len(category) == 1:
            print('{:3d}: {:s}'.format(i, category[0]))
        else:
            print('{:3d}:   {:s}'.format(i, category[1]))


def filter(args):
    if not os.path.isfile(filename):
        download()

    df = fixUnicode(pandas.read_parquet(filename))

    if args.category is not None:
        categories = makeCategories()
        
        category = categories[int(args.category)]
        
        df = df.loc[df['First category'] == category[0]]

        if len(category) == 2:
            df = df.loc[df['Second category'] == category[1]]

    if args.lcsc is not None:
        df = df.loc[df['LCSC'] == args.lcsc]

    if args.pn is not None:
        df = df.loc[df['PN'].str.contains(args.pn, case = False, na = False, regex = False)]

    if args.manufacturer is not None:
        df = df.loc[df['Manufacturer'].str.contains(args.manufacturer, case = False, na = False, regex = False)]

    if args.package is not None:
        df = df.loc[df['Package'].str.contains(args.package, case = False, na = False, regex = False)]

    if args.pins is not None:
        df = df.loc[df['Pins'] == args.pins]

    if args.basic and not args.extended:
        df = df.loc[df['Type'] == 'Basic']

    if not args.basic and args.extended:
        df = df.loc[df['Type'] == 'Extended']

    if args.description is not None:
        for s in args.description:
            df = df.loc[df['Description'].str.contains(s, case = False, na = False, regex = False)]

    if args.price is not None:
        df = df.loc[df['Price'].str.extract('1-[^:]+:([^,]+)')[0].astype(float) < args.price]
        
    if args.stock is not None:
        df = df.loc[df['Stock'].astype(float) > args.stock]

    return df


def printSimple(args):
    df = filter(args)

    if df.shape[0] > 0:
        df['Price'] = df['Price'].str.extract('1-[^:]+:([^,]+)')[0].astype(float)
        df['Stock'] = df['Stock'].apply('{:,}'.format)
    
        df = df.sort_values(by = ['Type', 'Second category', 'Manufacturer', 'Description'])
        df = df[['LCSC', 'PN', 'Manufacturer', 'Description', 'Type', 'Stock', 'Price']]

        pandas.options.display.width = None
        pandas.options.display.max_columns = None
        pandas.options.display.float_format = '${:,.3f}'.format

        print(df.to_string(index = False))


def printFull(args):
    df = filter(args)

    df['Price'] = df['Price'].str.extract('1-[^:]+:([^,]+)')[0].astype(float)

    df = df.sort_values(by = ['Type', 'Second category', 'Manufacturer', 'Description'])

    for i in range(df.shape[0]):
        entry = df.iloc[i]

        print('LCSC:         {:s}'.format(str(entry['LCSC'])))
        print('PN:           {:s}'.format(str(entry['PN'])))
        print('Category:     {:s}'.format(str(entry['Second category'])))
        print('Manufacturer: {:s}'.format(str(entry['Manufacturer'])))
        print('Description:  {:s}'.format(str(entry['Description'])))
        print('Package:      {:s}'.format(str(entry['Package'])))
        print('Pins:         {:d}'.format(entry['Pins']))
        print('Datasheet:    {:s}'.format(str(entry['Datasheet'])))
        print('Type:         {:s}'.format(str(entry['Type'])))
        print('Stock:        {:,d}'.format(entry['Stock']))
        
        if math.isnan(entry['Price']):
            print('Price:        NaN')
        else:
            print('Price:        ${:,.3f}'.format(entry['Price']))

        if i != df.shape[0] - 1:
            print()


# Code

formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position = 90, width = 90)

parser = argparse.ArgumentParser(formatter_class = formatter)

subparsers = parser.add_subparsers()

parserDownload   = subparsers.add_parser('download',   help = 'downloads the component database from JLCPCB')
parserCategories = subparsers.add_parser('categories', help = 'list available categories')
parserHorizontal = subparsers.add_parser('simple',     help = 'print the most important fields of the components', formatter_class = formatter)
parserVertical   = subparsers.add_parser('full',       help = 'print all the fields of the components', formatter_class = formatter)

parserDownload.set_defaults(func = download)
parserCategories.set_defaults(func = printCategories)
parserHorizontal.set_defaults(func = printSimple)
parserVertical.set_defaults(func = printFull)

parserHorizontal.add_argument('-lcsc',         help = 'filter by LCSC code')
parserHorizontal.add_argument('-pn',           help = 'filter by manufacturer part number')
parserHorizontal.add_argument('-category',     help = 'filter by component category', type = int)
parserHorizontal.add_argument('-manufacturer', help = 'filter by manufacturer name substring')
parserHorizontal.add_argument('-description',  help = 'filter by description substring', nargs = '*')
parserHorizontal.add_argument('-package',      help = 'filter by package substring')
parserHorizontal.add_argument('-pins',         help = 'filter by number of pins', type = int)
parserHorizontal.add_argument('-basic',        help = 'filter basic components', action = 'store_true')
parserHorizontal.add_argument('-extended',     help = 'filter extended components', action = 'store_true')
parserHorizontal.add_argument('-price',        help = 'filter by maximum unitary price', type = float)
parserHorizontal.add_argument('-stock',        help = 'filter by minimum stock', type = int)

parserVertical.add_argument('-lcsc',         help = 'filter by LCSC code')
parserVertical.add_argument('-pn',           help = 'filter by manufacturer part number')
parserVertical.add_argument('-category',     help = 'filter by component category', type = int)
parserVertical.add_argument('-manufacturer', help = 'filter by manufacturer name substring')
parserVertical.add_argument('-description',  help = 'filter by description substring', nargs = '*')
parserVertical.add_argument('-package',      help = 'filter by package substring')
parserVertical.add_argument('-pins',         help = 'filter by number of pins', type = int)
parserVertical.add_argument('-basic',        help = 'filter basic components', action = 'store_true')
parserVertical.add_argument('-extended',     help = 'filter extended components', action = 'store_true')
parserVertical.add_argument('-price',        help = 'filter by maximum unitary price', type = float)
parserVertical.add_argument('-stock',        help = 'filter by minimum stock', type = int)

if len(sys.argv) > 1:
    args = parser.parse_args()
    args.func(args)
else:
    parser.print_help()
