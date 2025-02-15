import re
task = "Transcribe audio from data/audio.mp3 and save to data/transcription.txt"
match = re.search(r'Transcribe audio from ([\w\-/\.]+) and save to ([\w\-/\.]+)', task, re.IGNORECASE)
print(match.groups() if match else "No match found")