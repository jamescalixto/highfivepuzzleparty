from gsheet import GSheet
import json
import logging
import sys

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from discord_webhook import DiscordWebhook

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Data storage.
TASK_FILE = 'data/tasks.json'

# Config files.
DISCORD_CONFIG_FILE = 'config/discord.json'

# GSheet handler.
gsheet = GSheet()

# Logging.
logging.getLogger("werkzeug").setLevel(logging.ERROR)  # Only log errors from Flask.
logging.basicConfig(
    level=logging.INFO,
    filename='data/server.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
)
log = logging.getLogger(__name__)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/board')
def board():
    tasks = load_tasks()
    return render_template('board.html', tasks=tasks)

@socketio.on('connect')
def handle_connect():
    tasks = load_tasks()  # Load the current tasks from storage.
    emit('update_tasks', tasks)  # Send tasks to the newly connected client.

def load_tasks():
    try:
        with open(TASK_FILE, 'r') as file:
            tasks = json.load(file)
            log.debug(f"Reloaded {len(tasks)} task(s) from file.")
            return tasks
    except (FileNotFoundError, json.JSONDecodeError):
        log.error(f"Failed to load tasks from file.")
        return []

def save_tasks(tasks):
    with open(TASK_FILE, 'w') as file:
        json.dump(tasks, file, indent=2)
        log.debug(f"Saved {len(tasks)} task(s) to file.")


@socketio.on('add_task')
def handle_add_task(data):
    try:
        new_task = data.get("task", {})
        if (new_task.get("sheetLink") == ""):
            new_task["sheetLink"] = gsheet.make_new_sheet(new_task.get("name"), new_task.get("puzzleLink"))
        tasks = load_tasks()
        tasks.append(new_task)
        save_tasks(tasks)
        emit('update_tasks', tasks, broadcast=True)
        log.info(f"Added new task {new_task.get('name')}: {new_task}")
    except Exception as e:
        log.error(f"Error adding task: {e}")

@socketio.on('update_task')
def handle_update_task(data):
    try:
        updated_task = data.get("task", {})
        tasks = load_tasks()
        for i, task in enumerate(tasks):
            if task.get("uuid", -1) == updated_task.get("uuid"):  # Compare uuid:
                # Check for state change, to avoid firing events for changes to Done tasks.
                changed_state = task.get("state") != updated_task.get("state")
                
                # General task update.
                tasks[i] = updated_task
                save_tasks(tasks)
                emit('update_tasks', tasks, broadcast=True)
                log.info(f"Updated task {updated_task.get('name')}: {updated_task}")

                # Special events for moving tasks to Done.
                if changed_state and updated_task.get("state") == "Done":
                    fire_discord_message(data)
                    gsheet.move_sheet_to_right(updated_task.get("name"))
                    log.info(f"(Moved task {updated_task.get('name')} to Done)")
                # Special events for moving tasks out of Done.
                elif changed_state and task.get("state") == "Done":
                    gsheet.move_sheet_to_left(updated_task.get("name"))
                    log.info(f"(Moved task {updated_task.get('name')} out of Done)")
                return
    except Exception as e:
        log.error(f"Error updating task: {e}")

@socketio.on('delete_task')
def handle_delete_task(data):
    try:
        deleted_task = data.get("task", {});
        tasks = load_tasks()
        # TODO: fix this.
        # if deleted_task in tasks:
        #     tasks.remove(deleted_task)
        if deleted_task.get("uuid", -1) in [task.get("uuid") for task in tasks]:
            deleted_task = [t for t in tasks if t.get("uuid") == deleted_task.get("uuid")][0]
            tasks.remove(deleted_task)
            save_tasks(tasks)
            emit('update_tasks', tasks, broadcast=True)
            log.info(f"Deleted task {deleted_task.get('name')}: {deleted_task}")
    except Exception as e:
        log.error(f"Error deleting task: {e}")

def fire_discord_message(data):
    task_name = data.get("task", {}).get("name", "")
    message = f'🎉 we\'ve solved "{task_name}" — good job all! 🎉'
    try:
        with open(DISCORD_CONFIG_FILE, 'r') as f:
            webhook_url = json.load(f).get('WEBHOOK_URL')
        webhook = DiscordWebhook(url=webhook_url, content=message, tts=True)
        return webhook.execute()
    except Exception as e:
        log.error(f"Failed to fire Discord message '{message}': {e}")