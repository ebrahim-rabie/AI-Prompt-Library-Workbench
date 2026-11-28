# AI Prompt Library & Workbench

Course: CSAI 203 - Introduction to Software Engineering (Fall 2026)  
Institution: Zewail City of Science, Technology and Innovation

## Team Members

- Mohamed Tamer - 202402014 (Representative: s-mohmed.refaay@zewailcity.edu.eg)
- Hassan Saad - 202402360
- Mazen Mohamed - 202400910
- Ebrahim Mohamed - 202401474

## Project Description

AI Prompt Library & Workbench is a community platform for creating, sharing, and testing reusable AI prompt templates. Registered users can define template variables, manage drafts, publish versioned prompts, fork existing templates, and organize collections. The platform includes an interactive workbench to test templates with custom variable inputs, as well as rating, review, and moderation features.

## Repository Structure

- `docs/` - Contains submitted documents and deliverables.
- `src/` - Application source code, organized following the MVC pattern.
- `tests/` - Test cases, unit tests, and validation scripts.
- `deployment/` - Deployment instructions, configuration files, and environment setup scripts.
- `migrations/` - Database migration scripts and schema files.

## Documents

- [Software Requirements Specification (SRS)](docs/CSAI203_SRS_202402014.pdf)
- [System Design Document](docs/CSAI203_Design_202402014.pdf)

## Setup and Running Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/ebrahim-rabie/AI-Prompt-Library-Workbench.git
   cd AI-Prompt-Library-Workbench
   ```

Requirements: Python 3.11 or newer. All commands run from the repository root.

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

3. Environment configuration:
   Copy [`deployment/.env.example`](deployment/.env.example) to `.env` in the project root and fill in
   `SECRET_KEY` and `ADMIN_PASSWORD`. Leave `DATABASE_URL` empty to use SQLite (`instance/dev.db`).

4. Create the database (runs the scripts in `migrations/`):
   ```bash
   flask --app src/wsgi.py db upgrade
   ```

5. Load the first administrator and the initial tags:
   ```bash
   python deployment/seed.py
   ```

6. Run the application, then open http://127.0.0.1:5000:
   ```bash
   flask --app src/wsgi.py run
   ```

7. Run the tests:
   ```bash
   python -m pytest
   ```

When a model changes, create a new migration with
`flask --app src/wsgi.py db migrate -m "describe the change"` and review the generated file before
committing it. Production settings are described in [deployment/README.md](deployment/README.md).

## Code Layout (MVC)

| Layer | Folder | Contents |
|---|---|---|
| Model | `src/app/models/` | SQLAlchemy entities for all 10 tables, enumerations, validation rules |
| Model | `src/app/services/` | Business rules called by the controllers (`AuthService`, `CollectionService`, ...) - names follow Design Figure 3 |
| Controller | `src/app/controllers/` | Flask Blueprints, one per feature, and the error pages |
| Controller | `src/app/middleware/auth.py` | `AuthMiddleware`: `enforce_session_timeout`, `create_session`, `require_login` (401), `require_admin` (403), `check_ownership` (403), `not_owner` |
| View | `src/app/templates/`, `src/app/static/` | Jinja2 templates (all extend `base.html`) and CSS |

New features add a Blueprint in `src/app/controllers/`, register it in `_register_blueprints()` in
`src/app/__init__.py`, and add tests under `tests/unit/` and `tests/integration/`.
