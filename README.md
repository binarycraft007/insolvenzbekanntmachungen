# German Insolvency Announcements Scraper

A lightweight, dependency-free Python tool to scrape the official German insolvency portal ([neu.insolvenzbekanntmachungen.de](https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf)) for notices relating to **XU Exponential University of Applied Sciences GmbH** (or any other specified entity). 

The scraper is designed to run locally or as a scheduled GitHub Action, checking for new listings and notifying you via HTML email.

## Key Features
* **No Heavy Dependencies**: Unlike standard browser-automation setups, this scraper runs directly on `requests` and `BeautifulSoup`. No Playwright, Puppeteer, or Chromium/WebDriver installations required.
* **JSF Reverse Engineering**: Handles complex JavaServer Faces (JSF) states, resolving the `jakarta.faces.ViewState` and dynamically simulating Mojarra AJAX postbacks (`Faces-Request: partial/ajax`) to fetch full publication texts.
* **State Management**: Persists already seen entries inside a local [seen_announcements.json](seen_announcements.json) file to prevent sending duplicate notifications.
* **SMTP Email Alerts**: Automatically emails styled HTML messages containing a metadata summary and the full announcement text when a new notice is discovered.
* **GitHub Actions Integration**: Built-in support to run on a daily schedule and automatically commit/push state updates back to the repository.

---

## Code Overview

- **[main.py](main.py)**: The core script that executes the session handshake, search POST, AJAX detail fetch, and sends the SMTP notification.
- **[.github/workflows/scrape_and_notify.yml](.github/workflows/scrape_and_notify.yml)**: The GitHub Actions schedule that triggers the Python script daily and commits the updated state back to the repo.
- **[seen_announcements.json](seen_announcements.json)**: A JSON database containing the keys of already notified filings to ensure deduplication.

---

## Local Setup & Run

This project is managed using [uv](https://github.com/astral-sh/uv).

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Run the script locally:
   ```bash
   uv run main.py
   ```

To test the email notification functionality locally, pass the SMTP credentials as environment variables:
```bash
export SMTP_SERVER="smtp.yourprovider.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your-auth-username"
export SMTP_PASSWORD="your-app-password"
export EMAIL_TO="recipient@example.com"
export EMAIL_FROM="sender@example.com"

uv run main.py
```

---

## GitHub Actions Configuration

To set up automatic daily checks and email notifications via GitHub Actions:

1. Push this repository to GitHub.
2. Ensure GitHub Actions are enabled in **Settings** -> **Actions** -> **General** -> **Actions permissions** (select "Allow all actions and workflows").
3. Go to **Settings** -> **Actions** -> **General** -> **Workflow permissions** and select **Read and write permissions** (this allows the action bot to commit `seen_announcements.json` back to your repo).
4. Add the following **Repository Secrets** under **Settings** -> **Secrets and variables** -> **Actions**:

| Secret Name | Description | Example |
| :--- | :--- | :--- |
| `SMTP_SERVER` | SMTP Server Hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP Port | `587` (STARTTLS) or `465` (SSL) |
| `SMTP_USERNAME` | SMTP Authentication Username | `elliot.huang` or `user@gmail.com` |
| `SMTP_PASSWORD` | SMTP Password or App Password | `abcd efgh ijkl mnop` |
| `EMAIL_TO` | Target Email for alerts | `recipient@example.com` |
| `EMAIL_FROM` | Sender Email (must be valid) | `sender@example.com` |

5. Head over to the **Actions** tab on GitHub, select **Scrape and Notify**, and click **Run workflow** to run the scraper manually for the first time.
