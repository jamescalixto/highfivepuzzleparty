import asyncio
import json
import logging
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import socketio

from gsheet import GSheet
from discord_webhook import DiscordWebhook

# Ensure required directories exist
os.makedirs('data', exist_ok=True)

# Configure server logging
logging.basicConfig(
    level=logging.INFO,
    filename='data/server.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
)
log = logging.getLogger(__name__)

# Data files and configs
TASK_FILE = 'data/tasks.json'
DISCORD_CONFIG_FILE = 'config/discord.json'

# Initialize GSheet handler with fallback if config is missing
try:
    gsheet = GSheet()
except Exception as e:
    log.warning(f"Google Sheets client could not be initialized (check config/): {e}")
    gsheet = None

# Initialize FastAPI application
app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Socket.IO ASGI server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

def load_tasks():
    """Load tasks list from the local JSON storage file."""
    try:
        with open(TASK_FILE, 'r') as file:
            tasks = json.load(file)
            log.debug(f"Reloaded {len(tasks)} task(s) from file.")
            return tasks
    except (FileNotFoundError, json.JSONDecodeError):
        log.error("Failed to load tasks from file.")
        return []

def save_tasks(tasks):
    """Save tasks list to the local JSON storage file."""
    try:
        with open(TASK_FILE, 'w') as file:
            json.dump(tasks, file, indent=2)
            log.debug(f"Saved {len(tasks)} task(s) to file.")
    except Exception as e:
        log.error(f"Failed to save tasks: {e}")

def fire_discord_message(data):
    """Send a victory notification to the configured Discord channel webhook."""
    task_name = data.get("task", {}).get("name", "")
    message = f'🎉 we\'ve solved "{task_name}" — good job all! 🎉'
    try:
        if not os.path.exists(DISCORD_CONFIG_FILE):
            log.warning("Discord config file not found; skipping Discord announcement.")
            return None
        with open(DISCORD_CONFIG_FILE, 'r') as f:
            webhook_url = json.load(f).get('WEBHOOK_URL')
        if not webhook_url:
            log.warning("Discord webhook URL not configured; skipping Discord announcement.")
            return None
        webhook = DiscordWebhook(url=webhook_url, content=message, tts=True)
        return webhook.execute()
    except Exception as e:
        log.error(f"Failed to fire Discord message '{message}': {e}")

# HTTP Routing
@app.get("/")
def index():
    """Serves the main static information index page."""
    return FileResponse("templates/index.html")

@app.get("/board")
def board():
    """Serves the puzzle board tracker page."""
    return FileResponse("templates/board.html")

# Socket.IO WebSocket Event Handlers
@sio.on('connect')
async def handle_connect(sid, environ):
    """Sends current tasks list to the newly connected Socket.IO client."""
    tasks = load_tasks()
    await sio.emit('update_tasks', tasks, to=sid)

@sio.on('add_task')
async def handle_add_task(sid, data):
    """Creates a new puzzle sheet tab and adds the task to tracking."""
    try:
        new_task = data.get("task", {})
        # Create a new Google sheet if one doesn't exist
        if new_task.get("sheetLink") == "":
            if gsheet is not None:
                # Run blocking API calls in executor thread pool to keep event loop free
                sheet_link = await asyncio.to_thread(
                    gsheet.make_new_sheet, 
                    new_task.get("name"), 
                    new_task.get("puzzleLink")
                )
                new_task["sheetLink"] = sheet_link
            else:
                log.warning("Google Sheets client is not configured; sheetLink remains empty.")
        
        tasks = load_tasks()
        tasks.append(new_task)
        save_tasks(tasks)
        
        # Broadcast updated tasks list to all clients
        await sio.emit('update_tasks', tasks)
        log.info(f"Added new task {new_task.get('name')}: {new_task}")
    except Exception as e:
        log.error(f"Error adding task: {e}")

@sio.on('update_task')
async def handle_update_task(sid, data):
    """Updates properties of a task and shifts the Google Sheet tab left/right on state transition."""
    try:
        updated_task = data.get("task", {})
        tasks = load_tasks()
        for i, task in enumerate(tasks):
            if task.get("uuid", -1) == updated_task.get("uuid"):
                # Check for state changes to trigger sheet reordering and Discord notifications
                changed_state = task.get("state") != updated_task.get("state")
                
                tasks[i] = updated_task
                save_tasks(tasks)
                
                await sio.emit('update_tasks', tasks)
                log.info(f"Updated task {updated_task.get('name')}: {updated_task}")

                if changed_state and updated_task.get("state") == "Done":
                    await asyncio.to_thread(fire_discord_message, data)
                    if gsheet is not None:
                        await asyncio.to_thread(gsheet.move_sheet_to_right, updated_task.get("name"))
                    log.info(f"(Moved task {updated_task.get('name')} to Done)")
                
                elif changed_state and task.get("state") == "Done":
                    if gsheet is not None:
                        await asyncio.to_thread(gsheet.move_sheet_to_left, updated_task.get("name"))
                    log.info(f"(Moved task {updated_task.get('name')} out of Done)")
                return
    except Exception as e:
        log.error(f"Error updating task: {e}")

@sio.on('delete_task')
async def handle_delete_task(sid, data):
    """Removes a task from tracking and broadcasts the update."""
    try:
        deleted_task = data.get("task", {})
        tasks = load_tasks()
        matching_tasks = [t for t in tasks if t.get("uuid") == deleted_task.get("uuid")]
        if matching_tasks:
            task_to_remove = matching_tasks[0]
            tasks.remove(task_to_remove)
            save_tasks(tasks)
            await sio.emit('update_tasks', tasks)
            log.info(f"Deleted task {task_to_remove.get('name')}: {task_to_remove}")
    except Exception as e:
        log.error(f"Error deleting task: {e}")

# Start the uvicorn server directly when script is executed
if __name__ == "__main__":
    uvicorn.run("server:socket_app", host="0.0.0.0", port=8000, reload=True)