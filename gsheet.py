import gspread
import json

class GSheet:
    def __init__(self):
        with open('config/gsheet.json', 'r') as f:
            self.sheet_url = json.load(f).get('SHEET_URL')
            self.gc = gspread.service_account(filename='config/credentials.json')
            self.sheet = self.gc.open_by_key(self.sheet_url)

    def make_new_sheet(self, name, link):
        # Check if sheet already exists. Delete if so.
        if name in [sheet.title for sheet in self.sheet.worksheets()]:
            self.sheet.del_worksheet(self.sheet.worksheet(name))
        # Add new sheet.
        ws = self.sheet.add_worksheet(title=name, rows=100, cols=26, index=0)
        ws.update_acell('A1', link)
        ws.format('A1:Z100', {'textFormat': {'fontFamily': 'Roboto Mono'}})
        ws.format('A1', {'textFormat': {'fontFamily': 'Roboto Mono', 'link': {'uri': link}}})
        return ws.url  # return link to sheet.

    def move_sheet_to_index(self, name, index):
        if name in [sheet.title for sheet in self.sheet.worksheets()]:
            ws = self.sheet.worksheet(name)
            reordered = [sheet for sheet in self.sheet.worksheets() if sheet.title != name]
            reordered.insert(index, ws)
            self.sheet.reorder_worksheets(reordered)

    def move_sheet_to_left(self, name):
        self.move_sheet_to_index(name, 0)
    
    def move_sheet_to_right(self, name):
        self.move_sheet_to_index(name, len(self.sheet.worksheets()) - 1)