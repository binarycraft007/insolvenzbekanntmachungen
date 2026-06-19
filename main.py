import json
import os
import smtplib
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

STATE_FILE = "seen_announcements.json"


def load_seen_announcements():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Warning: Could not parse {STATE_FILE}: {e}", file=sys.stderr)
    return set()


def save_seen_announcements(seen_set):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen_set)), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {STATE_FILE}: {e}", file=sys.stderr)


def send_email_notification(
    smtp_server, smtp_port, username, password, from_email, to_email, record
):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"🚨 Neuer Insolvenzeintrag: {record['debtor_name']} ({record['file_number']})"
    )
    msg["From"] = from_email
    msg["To"] = to_email

    # HTML Body
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: auto;">
        <h2 style="color: #d9534f; border-bottom: 2px solid #d9534f; padding-bottom: 5px; margin-top: 20px;">
          🚨 Neuer Insolvenzeintrag gefunden!
        </h2>
        <table style="border-collapse: collapse; width: 100%; margin: 15px 0;">
          <tr style="background-color: #f8f9fa;">
            <td style="padding: 10px; font-weight: bold; width: 180px; border-bottom: 1px solid #dee2e6;">Datum:</td>
            <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{record['date']}</td>
          </tr>
          <tr>
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #dee2e6;">Aktenzeichen:</td>
            <td style="padding: 10px; font-family: monospace; font-size: 1.1em; border-bottom: 1px solid #dee2e6;">{record['file_number']}</td>
          </tr>
          <tr style="background-color: #f8f9fa;">
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #dee2e6;">Gericht:</td>
            <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{record['court']}</td>
          </tr>
          <tr>
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #dee2e6;">Schuldner:</td>
            <td style="padding: 10px; font-weight: bold; color: #d9534f; border-bottom: 1px solid #dee2e6;">{record['debtor_name']}</td>
          </tr>
          <tr style="background-color: #f8f9fa;">
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #dee2e6;">Sitz/Wohnsitz:</td>
            <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{record['domicile']}</td>
          </tr>
          <tr>
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #dee2e6;">Register:</td>
            <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">{record['register']}</td>
          </tr>
        </table>
        
        <h3 style="color: #495057;">Bekanntmachungstext:</h3>
        <div style="background-color: #f8f9fa; border: 1px solid #ced4da; padding: 15px; font-family: 'Courier New', Courier, monospace; white-space: pre-wrap; border-left: 5px solid #d9534f; border-radius: 4px; font-size: 0.95em;">{record['announcement_text']}</div>
      </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    try:
        smtp_port = int(smtp_port)
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()

        server.login(username, password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        print(
            f"Successfully sent Email notification for {record['file_number']} to {to_email}."
        )
    except Exception as e:
        print(f"Error sending email notification: {e}", file=sys.stderr)


def scrape_insolvency_records(company_name):
    url = "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://neu.insolvenzbekanntmachungen.de",
        "Referer": url,
    }

    session = requests.Session()

    # 1. Initialize session and get ViewState
    try:
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error connecting to the portal: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.find("form", id="frm_suche")
    if not form:
        print("Error: Could not find search form on the landing page.", file=sys.stderr)
        return []

    view_state_el = form.find("input", {"name": "jakarta.faces.ViewState"})
    if not view_state_el:
        print("Error: Could not find ViewState in search form.", file=sys.stderr)
        return []
    view_state = view_state_el.get("value")

    action_url = form.get("action")
    post_url = urllib.parse.urljoin(url, action_url)

    # 2. Search POST request (Search range from 2018 to today)
    today_str = date.today().isoformat()
    search_data = {
        "frm_suche": "frm_suche",
        "frm_suche:lsom_bundesland:codelist:scl_bundesland:mysom": "",
        "frm_suche:lsi_insolvenzgerichte:codelist:scl_insolvenzgericht:mysom": "",
        "frm_suche:ldi_datumVon:datumHtml5": "2018-01-01",
        "frm_suche:ldi_datumBis:datumHtml5": today_str,
        "frm_suche:lsom_wildcard:lsom": "0",  # Starts with (*)
        "frm_suche:litx_firmaNachName:text": company_name,
        "frm_suche:litx_vorname:text": "",
        "frm_suche:litx_sitzWohnsitz:text": "",
        "frm_suche:sbc_ohneAbteilung": "",
        "frm_suche:iaz_aktenzeichen:itx_abteilung": "",
        "frm_suche:iaz_aktenzeichen:som_registerzeichen:mysom": "NO_CODE",
        "frm_suche:iaz_aktenzeichen:itx_lfdNr": "",
        "frm_suche:iaz_aktenzeichen:itx_jahr": "",
        "frm_suche:iaz_aktenzeichen:ih_aktenzeichen": "true",
        "frm_suche:lsom_gegenstand:codelist:mysom": "NO_CODE",
        "frm_suche:sbc_ohneDeutUnter": "",
        "frm_suche:ir_registereintrag:som_registergericht:mysom": "NO_CODE",
        "frm_suche:ir_registereintrag:som_registerart:mysom": "NO_CODE",
        "frm_suche:ir_registereintrag:itx_registernummer": "",
        "frm_suche:ir_registereintrag:ih_registereintrag": "true",
        "frm_suche:cbt_suchen": "Suchen",
        "jakarta.faces.ViewState": view_state,
    }

    try:
        search_res = session.post(
            post_url, data=search_data, headers=headers, timeout=15
        )
        search_res.raise_for_status()
    except Exception as e:
        print(f"Error performing search request: {e}", file=sys.stderr)
        return []

    # 3. Parse results list
    search_soup = BeautifulSoup(search_res.text, "html.parser")
    table = search_soup.find("table", id="tbl_ergebnis")
    if not table:
        return []

    rows = table.find_all("tr")[1:]
    results = []

    for idx, row in enumerate(rows):
        cols = row.find_all("td")
        if len(cols) < 7:
            continue

        record = {
            "date": cols[0].text.strip(),
            "file_number": cols[1].text.strip(),
            "court": cols[2].text.strip(),
            "debtor_name": cols[3].text.strip(),
            "domicile": cols[4].text.strip(),
            "register": cols[5].text.strip(),
            "announcement_text": "",
        }

        # Find detail form inside index 6
        detail_form = cols[6].find("form")
        if not detail_form:
            results.append(record)
            continue

        detail_action = detail_form.get("action")
        detail_post_url = urllib.parse.urljoin(url, detail_action)

        detail_view_state_el = detail_form.find(
            "input", {"name": "jakarta.faces.ViewState"}
        )
        detail_view_state = (
            detail_view_state_el.get("value") if detail_view_state_el else None
        )

        img_input = detail_form.find("input", type="image")
        if not img_input or not detail_view_state:
            results.append(record)
            continue

        img_name = img_input.get("name")

        # 4. Perform AJAX POST to retrieve publication text
        ajax_headers = headers.copy()
        ajax_headers["Faces-Request"] = "partial/ajax"
        ajax_headers["X-Requested-With"] = "XMLHttpRequest"

        ajax_data = {
            "jakarta.faces.partial.ajax": "true",
            "jakarta.faces.source": img_name,
            "jakarta.faces.partial.execute": img_name,
            "jakarta.faces.partial.render": "msgs frm_text:ihd_text",
            "jakarta.faces.behavior.event": "click",
            "jakarta.faces.partial.event": "click",
            img_name: img_name,
            f"{img_name}.x": "10",
            f"{img_name}.y": "10",
            detail_form.get("id"): detail_form.get("id"),
            "jakarta.faces.ViewState": detail_view_state,
        }

        try:
            ajax_res = session.post(
                detail_post_url, data=ajax_data, headers=ajax_headers, timeout=15
            )
            ajax_res.raise_for_status()

            xml_root = ET.fromstring(ajax_res.text)
            for update in xml_root.findall(".//update"):
                if update.get("id") == "frm_text:ihd_text" and update.text:
                    input_soup = BeautifulSoup(update.text, "html.parser")
                    input_el = input_soup.find("input")
                    if input_el:
                        record["announcement_text"] = input_el.get("value", "").strip()
        except Exception as e:
            print(
                f"Error fetching announcement text for row {idx}: {e}", file=sys.stderr
            )

        results.append(record)

    return results


def main():
    company = "XU Exponential University of Applied Sciences GmbH"
    print(f"Scraping results for '{company}' from neu.insolvenzbekanntmachungen.de...")

    results = scrape_insolvency_records(company)
    print(f"Found {len(results)} records on the portal.")

    seen_announcements = load_seen_announcements()
    new_records_found = False

    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    email_to = os.environ.get("EMAIL_TO")
    email_from = os.environ.get("EMAIL_FROM") or smtp_username

    for record in results:
        unique_key = f"{record['file_number']}_{record['date']}"

        if unique_key not in seen_announcements:
            print(f"New announcement found: {record['file_number']} ({record['date']})")
            new_records_found = True

            # Send notification if email configuration is provided
            if (
                smtp_server
                and smtp_port
                and smtp_username
                and smtp_password
                and email_to
            ):
                send_email_notification(
                    smtp_server,
                    smtp_port,
                    smtp_username,
                    smtp_password,
                    email_from,
                    email_to,
                    record,
                )
            else:
                print("Email (SMTP) credentials not configured. Skipping notification.")

            seen_announcements.add(unique_key)

    if new_records_found:
        save_seen_announcements(seen_announcements)
    else:
        print("No new announcements since last run.")


if __name__ == "__main__":
    main()
