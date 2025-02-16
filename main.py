import requests
import git
import speech_recognition as sr
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from bs4 import BeautifulSoup
import os
import json
import re
import sqlite3
import datetime
import subprocess
import pytesseract
from PIL import Image
from pytesseract import image_to_string
from sentence_transformers import SentenceTransformer, util

app = FastAPI()

# Ensure the data directory path is correctly set
DATA_DIR = os.path.abspath("data")

# Access the AI Proxy token from the environment variable
AIPROXY_TOKEN = os.environ.get("AIPROXY_TOKEN")
if not AIPROXY_TOKEN:
    raise EnvironmentError("AIPROXY_TOKEN environment variable not set")

# Use GPT-4o-Mini for any LLM-related tasks
LLM_MODEL = "GPT-4o-Mini"


import shlex

def run_shell_command(command):
    """Runs a shell command safely."""
    try:
        result = subprocess.run(shlex.split(command), check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Command failed: {e.stderr}")

import logging

logging.basicConfig(level=logging.DEBUG)

import pathlib

@app.post("/run")
def run_task(task: str):
    logging.debug(f"[{datetime.datetime.now()}] Received task: '{task}'")

    # 🔐 Security Check: Prevent Access Outside /data/
    forbidden_paths = ["../", "/..", "C:\\", "D:\\", "/etc/", "/home/", "/root/"]
    
    # Allow API URLs (http, https) but block invalid paths
    words = task.split()
    for word in words:
        if word.startswith("http://") or word.startswith("https://"):
            continue  # ✅ Allow API URLs
        if "/" in word or "\\" in word:  # Possible file path
            file_path = os.path.abspath(word)
            if not file_path.startswith(DATA_DIR) and "git@" not in task:
                raise HTTPException(status_code=403, detail="Access denied")

    # 🔐 Security Check: Prevent Deleting Any File
    if "delete" in task.lower() or "remove" in task.lower() or "rm " in task.lower():
        logging.warning(f"🚨 Security Alert: Attempt to delete data: {task}")
        raise HTTPException(status_code=403, detail="File deletion is not allowed.")

    try:
        # 🔹 Fetch Data from API
        if "fetch" in task.lower() and "api" in task.lower():
            logging.debug("✅ Matched: Fetch API Data")
            words = task.split()
            api_url = None
            output_file = None
            for i, word in enumerate(words):
                if word.startswith("http"):
                    api_url = word
                if word.endswith(".json") or word.endswith(".txt"):
                    output_file = os.path.abspath(os.path.join(DATA_DIR, os.path.basename(word)))

            if not api_url or not output_file:
                raise HTTPException(status_code=400, detail="Invalid task format. Specify an API URL and output file.")

            fetch_and_save_api_data(api_url, output_file)
            return {"message": f"Fetched data from {api_url} and saved to {output_file}"}

        # 🔹 Clone Git Repository
        if "clone" in task.lower() and "git" in task.lower():
            logging.debug("✅ Matched: Clone Git Repository")
            words = task.split()
            repo_url = "git@github.com:neelakandanr3/llm-automation-agent.git"
            commit_message = "Automated commit"

            for i, word in enumerate(words):
                if word.startswith("https://github.com/"):
                    repo_url = word
                if word.lower() == "commit" and i + 1 < len(words):
                    commit_message = " ".join(words[i+1:])

            if not repo_url:
                raise HTTPException(status_code=400, detail="Invalid task format. Specify a Git repository URL.")

            result = clone_and_commit_repo(repo_url, commit_message)
            return {"message": result}

        # 🔹 Image Processing: Rotate
        if "rotate image" in task.lower():
            logging.debug("✅ Matched: Rotate Image")
            match = re.search(r'Rotate image (.+?) by (\d+) degrees and save to (.+)', task, re.IGNORECASE)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid rotate image task format.")

            input_file, degrees, output_file = match.groups()
            input_path = os.path.join(DATA_DIR, input_file)
            output_path = os.path.join(DATA_DIR, output_file)

            rotate_image(input_path, output_path, int(degrees))
            return {"message": f"Rotated {input_file} by {degrees} degrees and saved to {output_file}"}

        # 🔹 Image Processing: Resize
        if "resize image" in task.lower():
            logging.debug("✅ Matched: Resize Image")
            match = re.search(r'Resize image (.+?) to (\d+)x(\d+) and save to (.+)', task, re.IGNORECASE)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid resize image task format.")

            input_file, width, height, output_file = match.groups()
            input_path = os.path.join(DATA_DIR, input_file)
            output_path = os.path.join(DATA_DIR, output_file)

            resize_image(input_path, output_path, int(width), int(height))
            return {"message": f"Resized {input_file} to {width}x{height} and saved to {output_file}"}

        # 🔹 Image Processing: Convert Format
        if "convert image" in task.lower():
            logging.debug("✅ Matched: Convert Image Format")
            match = re.search(r'Convert image (.+?) to (.+?) format and save to (.+)', task, re.IGNORECASE)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid convert image task format.")

            input_file, format, output_file = match.groups()
            input_path = os.path.join(DATA_DIR, input_file)
            output_path = os.path.join(DATA_DIR, output_file)

            convert_image_format(input_path, output_path, format)
            return {"message": f"Converted {input_file} to {format} format and saved to {output_file}"}
        if "scrape website" in task.lower():
            logging.info("✅ Matched: Web Scraping Task")
            match = re.search(r'Scrape website "(.+?)" and save to (.+?)$', task, re.IGNORECASE)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid web scraping task format.")

            url, output_file = match.groups()
            output_path = os.path.join(DATA_DIR, output_file)
            scrape_website(url, output_path)
            return {"message": f"Scraped data from {url} and saved to {output_file}"}

        # ✅ *Fetch Data from API*
        if "fetch" in task.lower() and "api" in task.lower():
            logging.debug("✅ Matched: Fetch API Data")
            words = task.split()
            api_url = next((word for word in words if word.startswith("http")), None)
            output_file = next((word for word in words if word.endswith((".json", ".txt"))), None)

            if not api_url or not output_file:
                raise HTTPException(status_code=400, detail="Invalid task format. Specify an API URL and output file.")

            output_path = os.path.join(DATA_DIR, os.path.basename(output_file))
            fetch_and_save_api_data(api_url, output_path)
            return {"message": f"Fetched data from {api_url} and saved to {output_file}"}

        # ✅ *Clone a Git Repository & Commit*
        if "clone" in task.lower() and "git" in task.lower():
            logging.debug("✅ Matched: Clone Git Repository")
            match = re.search(r'Clone Git repository (.+?) and commit (.+)', task, re.IGNORECASE)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid Git cloning task format.")

            repo_url, commit_message = match.groups()
            result = clone_and_commit_repo(repo_url, commit_message)
            return {"message": result}

        # ✅ *Format Markdown*
        if "format" in task.lower() and "prettier" in task.lower():
            logging.debug("✅ Matched: Format Markdown")
            file_path = os.path.abspath(os.path.join(DATA_DIR, "format.md"))
            command = f'npx prettier --write "{file_path}"'
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Prettier failed: {result.stderr}")
            return {"message": "File formatted"}

        # ✅ *Count Wednesdays*
        if "count" in task.lower() and "wednesday" in task.lower():
            logging.debug("✅ Matched: Count Wednesdays")
            count = count_weekdays(os.path.join(DATA_DIR, "dates.txt"), "Wednesday")
            output_file = os.path.join(DATA_DIR, "dates.txt")
            with open(output_file, "w") as f:
                f.write(str(count))
            return {"message": f"Found {count} Wednesdays"}

        # ✅ *Sort Contacts*
        if "sort" in task.lower() and "contacts" in task.lower():
            logging.debug("✅ Matched: Sort Contacts")
            sort_contacts(os.path.join(DATA_DIR, "contacts.json"), os.path.join(DATA_DIR, "contacts-sorted.json"))
            return {"message": "Contacts sorted"}

        # ✅ *Extract Recent Logs*
        if "extract" in task.lower() and "logs" in task.lower():
            logging.debug("✅ Matched: Extract Recent Logs")
            extract_recent_logs(os.path.join(DATA_DIR, "logs"), os.path.join(DATA_DIR, "logs-recent.txt"))
            return {"message": "Recent logs extracted"}

        # ✅ *Create Docs Index*
        if "create" in task.lower() and "index" in task.lower() and "markdown" in task.lower():
            logging.debug("✅ Matched: Create Docs Index")
            create_docs_index(os.path.join(DATA_DIR, "docs"), os.path.join(DATA_DIR, "docs", "index.json"))
            return {"message": "Docs index created"}

        # ✅ *Extract Email Sender*
        if "extract" in task.lower() and "email" in task.lower():
            logging.debug("✅ Matched: Extract Email Sender")
            extract_email_sender(os.path.join(DATA_DIR, "email.txt"), os.path.join(DATA_DIR, "email-sender.txt"))
            return {"message": "Email sender extracted"}

        # ✅ *Extract Credit Card Number (OCR)*
        if "extract" in task.lower() and "credit card" in task.lower():
            logging.debug("✅ Matched: Extract Credit Card Number")
            extract_credit_card(os.path.join(DATA_DIR, "credit_card.png"), os.path.join(DATA_DIR, "credit-card.txt"))
            return {"message": "Credit card number extracted"}

        # ✅ *Find Similar Comments*
        if "find" in task.lower() and "similar comments" in task.lower():
            logging.debug("✅ Matched: Find Similar Comments")
            find_similar_comments(os.path.join(DATA_DIR, "comments.txt"), os.path.join(DATA_DIR, "comments-similar.txt"))
            return {"message": "Similar comments found"}

        # ✅ *Calculate Ticket Sales*
        if "calculate" in task.lower() and "sales" in task.lower():
            logging.debug("✅ Matched: Calculate Ticket Sales")
            total_sales = calculate_ticket_sales(os.path.join(DATA_DIR, "ticket-sales.db"), "Gold")
            output_file = os.path.join(DATA_DIR, "ticket-sales-gold.txt")
            with open(output_file, "w") as f:
                f.write(str(total_sales))
            return {"message": f"Total Gold Ticket Sales: {total_sales}"}

        # ✅ *Run SQL Query*
        if "run sql query" in task.lower():
            logging.debug("✅ Matched: Run SQL Query")
            match = re.search(r'Run SQL query "(.*?)" on data/ticket-sales.db', task, re.IGNORECASE)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid SQL query format.")

            sql_query = match.group(1)
            if not sql_query.strip().lower().startswith(("select", "pragma")):
                raise HTTPException(status_code=403, detail="Only SELECT and PRAGMA queries are allowed.")

            result = run_sql_query(os.path.join(DATA_DIR, "ticket-sales.db"), sql_query)
            return {"message": "Query executed", "result": result}
        
        if "transcribe audio" in task.lower():
            logging.debug("✅ Matched: Transcribe Audio")
            logging.debug(f"Extracting audio transcription task from: {task}")  
            # Extract audio file and output file from task
            match = re.search(r'Transcribe audio from ([\w\-/\.]+) and save to ([\w\-/\.]+)', task, re.IGNORECASE)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid audio transcription task format.")

            audio_file, output_file = match.groups()
            audio_path = os.path.abspath(os.path.join(DATA_DIR, os.path.basename(audio_file)))
            output_path = os.path.abspath(os.path.join(DATA_DIR, os.path.basename(output_file)))

            # Ensure input file exists
            if not os.path.exists(audio_path):
                raise HTTPException(status_code=404, detail=f"Audio file not found: {audio_file}")

            # Transcribe the audio
            transcription = transcribe_audio(audio_path)

            # Save transcription
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcription)

            return {"message": f"Transcription saved to {output_file}"}

        logging.warning(f"⚠️ Task not recognized: '{task}'")
        return {"message": "Task not recognized"}

    except Exception as e:
        logging.error(f"❌ Error executing task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/read")
def read_file(path: str):
    """Reads a file inside the /app/data/ directory."""
    full_path = os.path.abspath(os.path.join(DATA_DIR, path))

    # Ensure the file is inside /app/data/
    if not full_path.startswith(DATA_DIR):
        raise HTTPException(status_code=403, detail="Access denied: Outside allowed directory")

    # Check if file exists
    if not os.path.isfile(full_path):
        logging.error(f"❌ File not found: {full_path} (Requested: {path})")
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        # Serve binary files
        if full_path.endswith((".png", ".jpg", ".jpeg", ".mp3", ".wav")):
            return FileResponse(full_path)

        # Read and return text-based files
        with open(full_path, "r", encoding="utf-8") as file:
            return {"filename": path, "content": file.read()}

    except Exception as e:
        logging.error(f"❌ Error reading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

# -------------------- Helper Functions --------------------

def count_weekdays(file_path, weekday):
    """Counts occurrences of a specific weekday in a file."""
    formats = ["%Y-%m-%d", "%d-%b-%Y", "%b %d, %Y", "%Y/%m/%d %H:%M:%S"]

    with open(file_path, "r") as f:
        lines = f.readlines()

    count = 0
    for date in lines:
        date = date.strip()
        for fmt in formats:
            try:
                parsed_date = datetime.datetime.strptime(date, fmt)
                if parsed_date.strftime("%A") == weekday:
                    count += 1
                break
            except ValueError:
                continue
    return count

def sort_contacts(input_file, output_file):
    """Sorts contacts in JSON by last_name and first_name."""
    with open(input_file, "r") as f:
        contacts = json.load(f)
    sorted_contacts = sorted(contacts, key=lambda x: (x["last_name"], x["first_name"]))
    with open(output_file, "w") as f:
        json.dump(sorted_contacts, f, indent=4)

def extract_recent_logs(log_dir, output_file):
    """Extracts the first line of the 10 most recent .log files."""
    logs = [(f, os.path.getmtime(os.path.join(log_dir, f))) for f in os.listdir(log_dir) if f.endswith(".log")]
    recent_logs = sorted(logs, key=lambda x: x[1], reverse=True)[:10]
    with open(output_file, "w") as f:
        for log, _ in recent_logs:
            with open(os.path.join(log_dir, log), "r") as lf:
                f.write(lf.readline())

def create_docs_index(docs_dir, output_file):
    """Creates an index of Markdown files mapping filenames to their H1 titles, even in subdirectories."""
    index = {}

    if not os.path.exists(docs_dir):
        raise HTTPException(status_code=404, detail="Docs directory not found.")

    # Walk through all subdirectories
    for root, _, files in os.walk(docs_dir):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)

                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("# "):  # Look for the first H1 header
                            relative_path = os.path.relpath(file_path, docs_dir)  # Store relative path
                            index[relative_path] = line[2:].strip()
                            break

    if not index:
        raise HTTPException(status_code=404, detail="No valid Markdown files with headers found.")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=4)

    logging.debug(f"✅ Created docs index: {output_file}")

def extract_email_sender(email_file, output_file):
    """Extracts the sender’s email address from an email file."""
    with open(email_file, "r") as f:
        content = f.read()
    match = re.search(r"From: .*<([^>]+)>", content)
    if match:
        with open(output_file, "w") as f:
            f.write(match.group(1))
    else:
        raise HTTPException(status_code=404, detail="No email sender found in file.")

def extract_credit_card(image_path, output_file):
    """Extracts credit card number from an image using OCR with improved accuracy."""
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Credit card image not found.")

    image = Image.open(image_path)

    # Convert image to grayscale to improve OCR
    image = image.convert("L")

    # Use PSM 6 (Assumes a single block of text) and whitelist numbers
    custom_config = "--psm 6 -c tessedit_char_whitelist=0123456789"

    text = pytesseract.image_to_string(image, config=custom_config)

    logging.debug(f"OCR extracted text: {text}")

    # Extract only numbers that look like credit card numbers (13-19 digits)
    card_numbers = re.findall(r"\b\d{13,19}\b", text)

    if card_numbers:
        with open(output_file, "w") as f:
            f.write(card_numbers[0])  # Save the first detected card number
        return
    else:
        raise HTTPException(status_code=404, detail="No valid credit card number found.")

def find_similar_comments(input_file, output_file):
    """Finds the most similar pair of comments using embeddings."""
    model = SentenceTransformer("all-MiniLM-L6-v2")

    with open(input_file, "r") as f:
        comments = f.readlines()

    if len(comments) < 2:
        raise HTTPException(status_code=400, detail="Not enough comments to compare.")

    embeddings = model.encode(comments, convert_to_tensor=True)
    similarity_matrix = util.pytorch_cos_sim(embeddings, embeddings)

    max_sim = 0
    pair = ("", "")
    for i in range(len(comments)):
        for j in range(i+1, len(comments)):
            if similarity_matrix[i][j] > max_sim:
                max_sim = similarity_matrix[i][j]
                pair = (comments[i], comments[j])

    with open(output_file, "w") as f:
        f.write(pair[0].strip() + "\n" + pair[1].strip())

def calculate_ticket_sales(db_file, ticket_type):
    """Calculates total sales for a given ticket type."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(units * price) FROM tickets WHERE type=?", (ticket_type,))
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total
    
def clone_and_commit_repo(repo_url, commit_message):
    """Clones a Git repository into /data/ and makes a commit."""
    repo_name = os.path.basename(repo_url).replace(".git", "")  # Extract repo name
    repo_path = os.path.join(DATA_DIR, repo_name)

    try:
        # If repo already exists, pull latest changes
        if os.path.exists(repo_path):
            logging.debug(f"🔄 Repository {repo_name} already exists. Pulling latest changes...")
            repo = git.Repo(repo_path)
            repo.remotes.origin.pull()
        else:
            logging.debug(f"🛠️ Cloning repository {repo_url} into {repo_path}...")
            repo = git.Repo.clone_from(repo_url, repo_path)

        # Create a dummy file to commit
        dummy_file = os.path.join(repo_path, "dummy.txt")
        with open(dummy_file, "w") as f:
            f.write("This is a test commit.\n")

        # Commit changes
        repo.git.add(dummy_file)
        repo.index.commit(commit_message)
        repo.remotes.origin.push()  # Push the commit

        logging.debug(f"✅ Commit successful in {repo_name}")
        return f"Commit made in {repo_name} with message: {commit_message}"

    except Exception as e:
        logging.error(f"❌ Git operation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {str(e)}")
    
def run_sql_query(db_file, query):
    """Executes an SQL query on the SQLite database and returns results."""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute(query)

        # If it's a SELECT query, fetch results
        if query.strip().lower().startswith("select"):
            rows = cursor.fetchall()
        else:
            conn.commit()  # Important: Commit changes for INSERT/UPDATE/DELETE
            rows = "Query executed successfully."

        conn.close()
        return rows if rows else "No results found."
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL error: {str(e)}")
    
def scrape_website(url, output_file):
    """Scrapes text content from a webpage and saves it to a file."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise error for bad responses

        soup = BeautifulSoup(response.text, "html.parser")
        text_content = soup.get_text(separator="\n", strip=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text_content)

        logging.info(f"✅ Scraped content saved to {output_file}")

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Web scraping failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Web scraping failed: {str(e)}")
    
def rotate_image(input_path, output_path, degrees):
    """Rotates an image by a given number of degrees."""
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Image file not found.")

    try:
        output_path = os.path.abspath(os.path.join(DATA_DIR, os.path.basename(output_path)))  # Fix path issue
        image = Image.open(input_path)
        rotated_image = image.rotate(-degrees, expand=True)  # Negative for counter-clockwise rotation
        rotated_image.save(output_path)
        logging.debug(f"✅ Rotated image saved to {output_path}")
    except Exception as e:
        logging.error(f"❌ Image rotation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image rotation failed: {str(e)}")

def resize_image(input_path, output_path, width, height):
    """Resizes an image to specified width and height."""
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Image file not found.")

    try:
        output_path = os.path.abspath(os.path.join(DATA_DIR, os.path.basename(output_path)))  # Fix path issue
        image = Image.open(input_path)
        resized_image = image.resize((width, height))
        resized_image.save(output_path)
        logging.debug(f"✅ Resized image saved to {output_path}")
    except Exception as e:
        logging.error(f"❌ Image resizing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image resizing failed: {str(e)}")

def convert_image_format(input_path, output_path, format):
    """Converts an image to a specified format (e.g., PNG to JPEG)."""
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="Image file not found.")

    try:
        output_path = os.path.abspath(os.path.join(DATA_DIR, os.path.basename(output_path)))  # Fix path issue
        image = Image.open(input_path)
        image.save(output_path, format=format.upper())  # Ensure correct format
        logging.debug(f"✅ Converted image saved to {output_path}")
    except Exception as e:
        logging.error(f"❌ Image conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image conversion failed: {str(e)}")
    
def transcribe_audio(audio_path):
    """Transcribes speech from an MP3 audio file using SpeechRecognition."""
    
    # Convert MP3 to WAV (temporarily)
    temp_wav = audio_path.replace(".mp3", "_temp.wav")

    try:
        subprocess.run(["ffmpeg", "-i", audio_path, "-acodec", "pcm_s16le", "-ar", "16000", temp_wav], check=True)
        
        # Load the WAV file for transcription
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_wav) as source:
            audio_data = recognizer.record(source)

        # Transcribe using Google Web Speech API
        text = recognizer.recognize_google(audio_data)
        os.remove(temp_wav)  # Delete temp file after transcription

        logging.debug(f"✅ Transcription: {text}")
        return text

    except sr.UnknownValueError:
        raise HTTPException(status_code=400, detail="Could not understand audio")
    except sr.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error with speech recognition service: {str(e)}")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error converting MP3 to WAV: {str(e)}")
    
# function using the AI Proxy token
def fetch_and_save_api_data(api_url, output_file):
    """Fetches data from an API and saves it to a file."""
    headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}"}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raise error for HTTP failures

        # Save response content
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(response.text)

        logging.debug(f"✅ API data saved to {output_file}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ API fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"API fetch failed: {str(e)}")
