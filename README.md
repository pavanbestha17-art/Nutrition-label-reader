# Nutrition Insight
A polished Flask-based Nutrition Label Reader mini-project.

## Run locally
1. Install Python 3.10+.
2. Open terminal in this folder.
3. `python -m venv .venv`
4. Activate it (Windows: `.venv\\Scripts\\activate`; macOS/Linux: `source .venv/bin/activate`).
5. `pip install -r requirements.txt`
6. `python app.py`
7. Open http://127.0.0.1:5000

## Features
Dashboard charts, category visualization, averages, product CRUD, search/filter, comparison and CSV export. JSON storage, server-side numeric validation, CSRF token checks, structured logging, responsive styling.

## Tests
From this folder run: `python -m unittest discover -s tests`

## Notes
Set a strong `SECRET_KEY` environment variable before deployment. For public deployment, use a production WSGI server, HTTPS, a persistent data volume and consider database-backed storage. Charts use Chart.js loaded from a CDN.
