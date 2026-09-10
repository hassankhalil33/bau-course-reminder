import os
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ==================== CONFIGURATION ====================
BUSINESS_CORE_CRNS = ["10502", "10522", "10585"]  # Business Administration Core
UNIVERSITY_ELECTIVE_CRNS = ["10337", "10336"]  # University Elective Courses

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Your exact bot token string
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")     # Your exact numeric chat ID string
# =======================================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload)
        print(f"Telegram response: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

def parse_visible_rows(page, target_crns, found_courses):
    """Scrapes visible table data rows and groups schedules by CRN"""
    rows = page.locator("tr").all()
    for row in rows:
        cells = [c.strip() for c in row.locator("td").all_text_contents() if c.strip()]
        
        if any("ASPx.Add" in item for item in cells):
            continue
            
        matched_crn = next((crn for crn in target_crns if crn in cells), None)
        if matched_crn:
            crn_idx = cells.index(matched_crn)
            try:
                course_title = cells[crn_idx + 2]
                section = cells[crn_idx + 3]
                day = cells[crn_idx + 6]
                class_time = cells[crn_idx + 7]
                capacity_status = cells[crn_idx + 11]
                
                if matched_crn not in found_courses:
                    found_courses[matched_crn] = {
                        "title": course_title,
                        "section": section,
                        "status": capacity_status,
                        "schedules": []
                    }
                
                sched_entry = f"🗓️ {day} ({class_time})"
                if sched_entry not in found_courses[matched_crn]["schedules"]:
                    found_courses[matched_crn]["schedules"].append(sched_entry)
            except IndexError:
                continue

def check_portal():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        found_courses = {}
        
        # 1. Open the portal once
        print("Opening BAU course offering portal...")
        page.goto("https://mis.bau.edu.lb/web/v15/courseoffering.aspx", timeout=60000)
        
        print("Expanding Campus: Beirut...")
        beirut_header = page.locator("text='CAMPUS: Beirut'").first
        if beirut_header.is_visible():
            beirut_header.click()
            page.wait_for_timeout(10000) # Strict 10-second requirement
            
        # ----------------------------------------------------
        # PATH 1: UNIVERSITY ELECTIVES
        # ----------------------------------------------------
        print("Expanding Faculty: University Elective Courses...")
        elective_faculty = page.locator("text='FACULTY: University Elective Courses'").first
        if elective_faculty.is_visible():
            elective_faculty.click()
            page.wait_for_timeout(10000)
            
        print("Expanding Attribute: University Elective Courses...")
        elective_attr = page.locator("text='ATTRIBUTE: University Elective Courses'").first
        if elective_attr.is_visible():
            elective_attr.click()
            page.wait_for_timeout(10000)
            
        print("Scraping Elective rows...")
        parse_visible_rows(page, UNIVERSITY_ELECTIVE_CRNS, found_courses)
        
        # ----------------------------------------------------
        # PATH 2: BUSINESS ADMINISTRATION (Continuous Session)
        # ----------------------------------------------------
        print("\nMoving directly to Faculty: Business Administration...")
        faculty_header = page.locator("text='FACULTY: Business Administration'").first
        if faculty_header.is_visible():
            faculty_header.click()
            page.wait_for_timeout(10000)
            
        print("Expanding Attribute: General Business Core Courses...")
        attr_header = page.locator("text='ATTRIBUTE: General Business Core Courses'").first
        if attr_header.is_visible():
            attr_header.click()
            page.wait_for_timeout(10000)
            
        print("Scraping Business Core rows...")
        parse_visible_rows(page, BUSINESS_CORE_CRNS, found_courses)
        
        # ----------------------------------------------------
        # NOTIFICATION PROCESSOR
        # ----------------------------------------------------
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        print(f"\nProcessing alerts at {timestamp}...")
        
        for crn, data in found_courses.items():
            print(f"CRN {crn} Status: {data['status']}")
            
            if data["status"].lower() != "closed":
                schedule_lines = "\n".join(data["schedules"])
                
                alert_msg = (
                    f"🚨 *BAU COURSE SEAT OPEN!*\n\n"
                    f"📚 *Course:* {data['title']}\n"
                    f"🔢 *Section:* {data['section']}\n"
                    f"🔑 *CRN:* {crn}\n"
                    f"🟢 *Seats available:* {data['status']}\n\n"
                    f"*Class Schedule:*\n{schedule_lines}\n\n"
                    f"⏱️ _Checked on: {timestamp}_"
                )
                send_telegram(alert_msg)
                
        browser.close()

if __name__ == "__main__":
    check_portal()
