# BIOMARK - Setup Guide

## What to Install

### 1. Python 3.10+
- Download: https://www.python.org/downloads/
- ⚠️ Check **"Add Python to PATH"** during installation

### 2. Git
- Download: https://git-scm.com/downloads

### 3. Python Dependencies
Run in the `backend` folder:
```bash
pip install -r requirements.txt
```

> **Note:** PostgreSQL is NOT needed locally — the app uses SQLite by default.

---

## Quick Start

```bash
# 1. Clone the project
git clone <your-repo-url>

# 2. Go to backend folder
cd "BIOMARK FINAL/backend"

# 3. (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the server
uvicorn main:app --reload
```

Then open the HTML files in `main_site/` or `face_site/` in a browser.
