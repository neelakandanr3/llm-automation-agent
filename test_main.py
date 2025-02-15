import requests

BASE_URL = "http://localhost:8000"

def test_format_markdown():
    """Test formatting a Markdown file with Prettier."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Format data/format.md with prettier 3.4.2"})
    assert response.status_code == 200, f"Prettier formatting failed. Response: {response.text}"

def test_count_wednesdays():
    """Test counting Wednesdays in a dates file."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Count the number of Wednesdays in data/dates.txt"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/dates.txt"})
    assert result.status_code == 200

    assert result.json()["content"].replace(".", "", 1).isdigit()

def test_sort_contacts():
    """Test sorting contacts JSON."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Sort contacts in data/contacts.json"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/contacts-sorted.json"})
    assert result.status_code == 200

def test_extract_recent_logs():
    """Test extracting recent log file contents."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Extract recent logs from data/logs/"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/logs-recent.txt"})
    assert result.status_code == 200

def test_calculate_ticket_sales():
    """Test calculating sales for Gold ticket type."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Calculate total sales for Gold tickets"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/ticket-sales-gold.txt"})
    assert result.status_code == 200

    # Validate the content is a number
    content = result.json()["content"].strip()
    try:
        total_sales = float(content)
        assert total_sales >= 0  # Ensure it's a non-negative value
    except ValueError:
        assert False, f"Invalid number format: {content}"

def test_create_docs_index():
    """Test creating a Markdown index."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Create an index for Markdown files in data/docs/"})
    assert response.status_code == 200

    # Check both possible locations for index.json
    result = requests.get(f"{BASE_URL}/read", params={"path": "data/docs/index.json"})
    if result.status_code != 200:
        result = requests.get(f"{BASE_URL}/read", params={"path": "data/index.json"})

    assert result.status_code == 200, "Docs index file not found"

def test_extract_email_sender():
    """Test extracting sender email."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Extract sender email from data/email.txt"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/email-sender.txt"})
    assert result.status_code == 200
    assert "@" in result.json()["content"]

def test_extract_credit_card():
    """Test extracting a credit card number from an image."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Extract credit card number from data/credit_card.png"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/credit-card.txt"})
    assert result.status_code == 200
    assert result.json()["content"].replace(" ", "").isdigit()

def test_find_similar_comments():
    """Test finding the most similar comments."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Find the most similar comments in data/comments.txt"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/comments-similar.txt"})
    assert result.status_code == 200

def test_invalid_task():
    """Test handling of an unrecognized task."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Unknown task"})
    assert response.status_code == 200
    assert response.json()["message"] == "Task not recognized"

def test_security_prevent_external_access():
    """Test that accessing files outside /data/ is blocked."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Read /etc/passwd"})
    assert response.status_code == 403
    assert response.json()["detail"] in ["Access outside /data/ is not allowed.", "Access denied"]

def test_security_prevent_file_deletion():
    """Test that file deletion is blocked."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Delete data/dates.txt"})
    assert response.status_code == 403
    assert response.json()["detail"] == "File deletion is not allowed."

def test_fetch_api_data():
    """Test fetching data from an API and saving it to a file."""
    test_api_url = "https://jsonplaceholder.typicode.com/todos/1"
    test_output_file = "data/api-data.json"

    response = requests.post(f"{BASE_URL}/run", params={"task": f"Fetch data from API {test_api_url} and save to {test_output_file}"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": test_output_file})
    assert result.status_code == 200
    assert "userId" in result.json()["content"]  # Validate expected JSON content

def test_clone_git_repo():
    """Test cloning a Git repository and making a commit."""
    test_repo_url = "git@github.com:neelakandanr3/llm-automation-agent.git"
    test_commit_message = "Automated commit test"

    response = requests.post(f"{BASE_URL}/run", params={"task": f"Clone Git repository {test_repo_url} and commit {test_commit_message}"})
    assert response.status_code == 200
    assert "Commit made" in response.json()["message"]

def test_rotate_image():
    """Test rotating an image."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Rotate image credit_card.png by 90 degrees and save to data/rotated.png"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/rotated.png"})
    assert result.status_code == 200

def test_resize_image():
    """Test resizing an image."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Resize image credit_card.png to 100x100 and save to data/resized.png"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/resized.png"})
    assert result.status_code == 200

def test_convert_image():
    """Test converting an image format."""
    response = requests.post(f"{BASE_URL}/run", params={"task": "Convert image credit_card.png to jpeg format and save to data/converted.jpeg"})
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/converted.jpeg"})
    assert result.status_code == 200

def test_transcribe_audio():
    """Test transcribing an audio file."""
    response = requests.post(
        f"{BASE_URL}/run",
        params={"task": "Transcribe audio from data/audio.mp3 and save to data/transcription.txt"},
    )
    assert response.status_code == 200

    result = requests.get(f"{BASE_URL}/read", params={"path": "data/transcription.txt"})
    assert result.status_code == 200
    assert len(result.json()["content"].strip()) > 0  # Ensure transcription is not empty