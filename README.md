# CounselorApp

CounselorApp is a Flask web app that helps users explore career options through a guided chat. It asks about their work responsibilities, interests, and preferences, then uses the OpenAI API to suggest roles they could explore.

## Features

- Start by entering your name or uploading a PDF résumé. The app uses PyMuPDF to extract text from uploaded résumés.
- Get role suggestions based on your answers, ask for more detail about a role, or request a new set of suggestions.
- Generate a short questionnaire to compare two or three roles.
- Export the conversation as a plain-text transcript.

## Run locally

Clone the repository and create a fresh Python virtual environment. These commands are for Windows PowerShell.

```powershell
git clone https://github.com/alexslep04/CounselorApp.git
cd CounselorApp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install Flask openai PyMuPDF
```

In [CounselorApp.py](CounselorApp.py), change the OpenAI client initialization to `client = OpenAI()` so it can read your key from the environment. Set the key for your current terminal session and start the app.

```powershell
$env:OPENAI_API_KEY = "your-api-key"
python CounselorApp.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and start a chat. The app requests `gpt-4` for its AI features.

## Project files

| File | Purpose |
| --- | --- |
| [CounselorApp.py](CounselorApp.py) | Flask routes, session state, résumé parsing, and OpenAI requests |
| [index.html](index.html) | Browser chat interface, résumé upload, and transcript download |

Sessions are stored in memory and reset when the server restarts. Exporting a transcript writes a text file to disk. The app sends résumé text and relevant chat answers to OpenAI, so use sample data when trying the prototype.
