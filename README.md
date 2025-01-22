# HighFive Puzzle Party
Full website for puzzle hunt information and puzzle board tracking. Designed to replace the previous Trello + Zapier workflow.

# Features
- Static information page for displaying assorted team FAQs.
- Puzzle board to keep track of what puzzles have been worked on.
- Automatically creates a tab in a Google Sheet for created puzzles, and moves them left/right to keep the sheet organized.
- Automatically announces in Discord when a puzzle is moved to Done.

# Setup

## General 
- Install requirements with `pip install -r requirements.txt`.
- Ensure all information and all links in `index.html` are correct.
- Delete existing `data/tasks.json`.

## Google Sheets and `credentials.json`
- Set up a new Google Cloud project and enable the Google Sheets API.
- Create a new Service Account and create a new key for it.
- Add `config/credentials.json` from the Google Cloud -> APIs and Services -> Credentials -> Service Accounts -> account.
- Make a new Google Sheet and share it with the service account email.
- Add the Google Sheet ID (from the URL) into `config/gsheet.json` as `SHEET_URL`.


## Discord
- Add a new webhook to the Discord channel.
- Add the webhook URL to `config/discord.json` as `WEBHOOK_URL`.

# Running and hosting
- Buy a domain name and set it up on Cloudflare.
- (optional) add filters to prevent undesired traffic from hitting the website.
- Set up a new Ubuntu VM in [UTM](https://mac.getutm.app/) on the host computer.
- Set up [Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/) and [hupper](https://stackoverflow.com/questions/36817604/how-to-change-and-reload-python-code-in-waitress-without-restarting-the-server) and set up a localhost web server that automatically restarts when local files are changed.
- Set up a [Cloudflare tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) to allow external traffic to connect to the localhost web server.
- Setup Tailscale SSH on the computer and test `ssh` and `scp` for remote administration.