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
import shlex
import logging
import pathlib
from PIL import Image
from pytesseract import image_to_string
from sentence_transformers import SentenceTransformer, util

app = FastAPI()

# Ensure AI Proxy token is set
if "AIPROXY_TOKEN" not in os.environ:
    raise RuntimeError("AIPROXY_TOKEN is not set. Please export it before running.")

AIPROXY_TOKEN = os.environ["AIPROXY_TOKEN"]
AIPROXY_API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/embeddings"

DATA_DIR = os.path.abspath("data")

def call_ai_proxy(task_description):
    """Send task description to AI Proxy and return structured task details."""
    headers = {
        "Authorization": f"Bearer {AIPROXY_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Parse the given task into structured JSON format."},
            {"role": "user", "content": task_description}
        ],
        "temperature": 0.2
    }

    response = requests.post(AIPROXY_API_URL, headers=headers, json=payload)
    
    if response.status_code == 401:
        raise RuntimeError("Invalid AI Proxy token. Check and update AIPROXY_TOKEN.")

    if response.status_code != 200:
        raise RuntimeError(f"AI Proxy request failed: {response.text}")

    return json.loads(response.json().get("choices", [{}])[0].get("message", {}).get("content", "{}"))

@app.post("/run")
def run_task(task: str):
    logging.debug(f"[{datetime.datetime.now()}] Received task: '{task}'")

    # 🔍 *Step 1: Parse Task Using AI Proxy*
    try:
        structured_task = call_ai_proxy(task)
    except Exception as e:
        logging.error(f"AI Proxy Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI Proxy Error: {str(e)}")

    if not structured_task:
        raise HTTPException(status_code=400, detail="AI Proxy failed to parse task.")

    # Extract parsed task details
    action = structured_task.get("action", "").lower()
    input_file = structured_task.get("input_file", "")
    output_file = structured_task.get("output_file", "")
    additional_params = structured_task.get("params", {})

    # Normalize paths
    input_path = os.path.join(DATA_DIR, input_file) if input_file else None
    output_path = os.path.join(DATA_DIR, output_file) if output_file else None

    # 🔐 *Step 2: Security Checks*
    if input_path and not input_path.startswith(DATA_DIR):
        raise HTTPException(status_code=403, detail="Access denied to input file.")

    if output_path and not output_path.startswith(DATA_DIR):
        raise HTTPException(status_code=403, detail="Access denied to output file.")

    # Block deletion tasks
    if action in ["delete", "remove"]:
        logging.warning(f"🚨 Security Alert: Attempt to delete {input_path}")
        raise HTTPException(status_code=403, detail="File deletion is not allowed.")

    # 🛠 *Step 3: Execute Task*
    try:
        if action == "fetch_api":
            return fetch_and_save_api_data(additional_params["api_url"], output_path)
        elif action == "clone_git":
            return clone_and_commit_repo(additional_params["repo_url"], additional_params["commit_message"])
        elif action == "rotate_image":
            return rotate_image(input_path, output_path, additional_params["degrees"])
        elif action == "resize_image":
            return resize_image(input_path, output_path, additional_params["width"], additional_params["height"])
        elif action == "convert_image":
            return convert_image_format(input_path, output_path, additional_params["format"])
        elif action == "scrape_website":
            return scrape_website(additional_params["url"], output_path)
        elif action == "count_weekdays":
            return count_weekdays(input_path, additional_params["weekday"], output_path)
        elif action == "sort_contacts":
            return sort_contacts(input_path, output_path)
        elif action == "extract_logs":
            return extract_recent_logs(input_path, output_path)
        elif action == "create_docs_index":
            return create_docs_index(input_path, output_path)
        elif action == "extract_email":
            return extract_email_sender(input_path, output_path)
        elif action == "extract_credit_card":
            return extract_credit_card(input_path, output_path)
        elif action == "find_similar_comments":
            return find_similar_comments(input_path, output_path)
        elif action == "calculate_sales":
            return calculate_ticket_sales(input_path, additional_params["ticket_type"], output_path)
        elif action == "run_sql_query":
            return run_sql_query(input_path, additional_params["query"])
        elif action == "transcribe_audio":
            return transcribe_audio(input_path, output_path)
        else:
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
