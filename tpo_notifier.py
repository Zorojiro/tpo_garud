"""
TPO Company Notification Service
================================
Monitors VIIT TPO portal for new company listings and sends Telegram notifications.

Free Hosting Options:
1. Railway.app (recommended)
2. Render.com
3. PythonAnywhere
4. Replit
5. GitHub Actions (scheduled)

Author: Shubham Galande
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
        
# ============================================
# CONFIGURATION - Update these values
# ============================================

# TPO Portal Credentials
TPO_URL = os.getenv("TPO_URL", "https://tpo.vierp.in/")
TPO_USERNAME = os.getenv("TPO_USERNAME", "22210524@viit.ac.in")
TPO_PASSWORD = os.getenv("TPO_PASSWORD", "Satara@123")

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8266203414:AAGEzlTposHWxXKoVSa5AkSts3UhUOnlVgs")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7869927462")

# Check interval in seconds (default: 30 minutes)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "1800"))

# File to store known companies (for persistence)
DATA_FILE = os.getenv("DATA_FILE", "known_companies.json")

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('tpo_notifier.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# TELEGRAM FUNCTIONS
# ============================================

def send_telegram_message(message: str) -> bool:
    """Send a message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        if result.get("ok"):
            logger.info("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram error: {result}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_telegram_document(file_path: str, caption: str = "") -> bool:
    """Send a file to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            files = {'document': f}
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            response = requests.post(url, data=payload, files=files, timeout=60)
        return response.json().get("ok", False)
    except Exception as e:
        logger.error(f"Failed to send document: {e}")
        return False


# ============================================
# DATA PERSISTENCE
# ============================================

def load_known_companies() -> dict:
    """Load previously known companies from file"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading known companies: {e}")
    return {"companies": [], "last_check": None}


def save_known_companies(data: dict):
    """Save known companies to file"""
    try:
        data["last_check"] = datetime.now().isoformat()
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(data['companies'])} companies to {DATA_FILE}")
    except Exception as e:
        logger.error(f"Error saving known companies: {e}")


def get_company_hash(company: dict) -> str:
    """Generate a unique hash for a company"""
    key = f"{company.get('Company', '')}-{company.get('Registration Start', '')}"
    return hashlib.md5(key.encode()).hexdigest()


# ============================================
# SELENIUM SCRAPER
# ============================================

def create_driver():
    """Create a headless Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    # For cloud hosting (use system Chrome)
    chrome_options.binary_location = os.getenv("CHROME_BINARY", "")
    
    try:
        # Try with webdriver-manager first
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
    except:
        # Fallback for cloud hosting
        driver = webdriver.Chrome(options=chrome_options)
    
    return driver


def login_to_tpo(driver) -> bool:
    """Login to TPO portal"""
    try:
        driver.get(TPO_URL)
        time.sleep(3)
        
        wait = WebDriverWait(driver, 15)
        
        # Find and fill username
        username_selectors = [
            (By.NAME, "email"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[type='text']"),
        ]
        
        username_field = None
        for by, value in username_selectors:
            try:
                username_field = wait.until(EC.presence_of_element_located((by, value)))
                break
            except:
                continue
        
        if not username_field:
            logger.error("Could not find username field")
            return False
        
        username_field.clear()
        username_field.send_keys(TPO_USERNAME)
        
        # Find and fill password
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.clear()
        password_field.send_keys(TPO_PASSWORD)
        
        # Click login
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()
        
        time.sleep(5)
        
        if "dashboard" in driver.current_url.lower():
            logger.info("Login successful")
            return True
        else:
            logger.error(f"Login may have failed. Current URL: {driver.current_url}")
            return True  # Try to continue anyway
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return False


def extract_detail_value(driver, label: str) -> str:
    """Extract a value from the detail page by label"""
    try:
        elements = driver.find_elements(By.XPATH, f"//*[contains(text(),'{label}')]")
        for elem in elements:
            parent = elem.find_element(By.XPATH, "./..")
            siblings = parent.find_elements(By.XPATH, "./following-sibling::*")
            for sib in siblings:
                val = sib.text.strip()
                if val and val != ":" and val != label:
                    return val
            text = parent.text.replace(label, "").strip().strip(":").strip()
            if text and text != label:
                return text
    except:
        pass
    return ""


def scrape_companies(driver) -> list:
    """Scrape company data from the dashboard with detailed info"""
    companies = []
    
    try:
        driver.get("https://tpo.vierp.in/company-dashboard")
        time.sleep(3)
        
        # Scroll to load all
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        total_companies = len(rows)
        logger.info(f"Found {total_companies} rows in table")
        
        # Get basic info first
        basic_info = []
        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 10:
                    company = {
                        "Company": cells[0].text.strip(),
                        "Registration Start": cells[4].text.strip(),
                        "Registration End": cells[5].text.strip(),
                        "Max Package (LPA)": cells[6].text.strip(),
                        "Min Package (LPA)": cells[7].text.strip(),
                        "Placement Type": cells[8].text.strip(),
                        "Academic Year": cells[9].text.strip(),
                        "Max Stipend": "",
                        "Min Stipend": "",
                        "Job Locations": "",
                    }
                    if company["Company"]:
                        basic_info.append(company)
            except:
                continue
        
        # Now get detailed info for each company
        for idx, company in enumerate(basic_info):
            try:
                logger.info(f"Getting details for [{idx+1}/{len(basic_info)}] {company['Company']}")
                
                # Navigate back to dashboard
                driver.get("https://tpo.vierp.in/company-dashboard")
                time.sleep(2)
                
                # Find and click the info button for this company
                rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2 and cells[0].text.strip() == company["Company"]:
                        # Click info button in column 2
                        info_cell = cells[1]
                        try:
                            clickable = info_cell.find_element(By.CSS_SELECTOR, "svg, button, span, div")
                            driver.execute_script("arguments[0].click();", clickable)
                        except:
                            driver.execute_script("arguments[0].click();", info_cell)
                        time.sleep(2)
                        break
                
                # Extract detailed info
                max_stip = extract_detail_value(driver, "Max Stipend")
                min_stip = extract_detail_value(driver, "Min Stipend")
                location = extract_detail_value(driver, "Job Locations")
                
                if max_stip:
                    company["Max Stipend"] = max_stip
                if min_stip:
                    company["Min Stipend"] = min_stip
                if location:
                    company["Job Locations"] = location
                
                companies.append(company)
                
            except Exception as e:
                logger.error(f"Error getting details for {company['Company']}: {e}")
                companies.append(company)  # Add with basic info only
        
        logger.info(f"Scraped {len(companies)} companies with details")
        
    except Exception as e:
        logger.error(f"Error scraping companies: {e}")
    
    return companies


# ============================================
# NOTIFICATION LOGIC
# ============================================

def format_company_notification(company: dict, is_new: bool = True) -> str:
    """Format a company notification message"""
    status = "🆕 NEW COMPANY LISTED!" if is_new else "📋 Company Update"
    
    # Format stipend
    min_stip = company.get('Min Stipend', '') or '0'
    max_stip = company.get('Max Stipend', '') or '0'
    
    # Format location
    location = company.get('Job Locations', '') or 'Not specified'
    
    msg = f"""
{status}

🏢 <b>{company.get('Company', 'N/A')}</b>

💰 <b>Package:</b> ₹{company.get('Min Package (LPA)', 'N/A')} - ₹{company.get('Max Package (LPA)', 'N/A')} LPA
💵 <b>Stipend:</b> ₹{min_stip} - ₹{max_stip}
📋 <b>Type:</b> {company.get('Placement Type', 'N/A')}
📍 <b>Location:</b> {location}
📅 <b>Registration:</b>
   • Start: {company.get('Registration Start', 'N/A')}
   • End: {company.get('Registration End', 'N/A')}

🔗 <b>Apply:</b> https://tpo.vierp.in/company-dashboard
"""
    return msg


def check_for_new_companies():
    """Main function to check for new companies"""
    logger.info("=" * 50)
    logger.info("Starting company check...")
    
    # Load known companies
    data = load_known_companies()
    known_hashes = {get_company_hash(c) for c in data["companies"]}
    
    driver = None
    try:
        # Create browser and login
        driver = create_driver()
        
        if not login_to_tpo(driver):
            logger.error("Login failed, skipping this check")
            return
        
        # Scrape current companies
        current_companies = scrape_companies(driver)
        
        if not current_companies:
            logger.warning("No companies found, skipping update")
            return
        
        # Find new companies
        new_companies = []
        for company in current_companies:
            company_hash = get_company_hash(company)
            if company_hash not in known_hashes:
                new_companies.append(company)
                known_hashes.add(company_hash)
        
        # Send notifications for new companies
        if new_companies:
            logger.info(f"Found {len(new_companies)} new companies!")
            
            # Send header
            header = f"""
🎓 <b>TPO ALERT - {len(new_companies)} New Company(s)!</b>
📅 {datetime.now().strftime('%d-%b-%Y %H:%M')}
{"="*35}
"""
            send_telegram_message(header)
            time.sleep(0.5)
            
            # Send each new company
            for company in new_companies:
                msg = format_company_notification(company, is_new=True)
                send_telegram_message(msg)
                time.sleep(0.5)
                logger.info(f"Notified about: {company['Company']}")
        else:
            logger.info("No new companies found")
        
        # Update known companies
        data["companies"] = current_companies
        save_known_companies(data)
        
    except Exception as e:
        logger.error(f"Error during check: {e}")
        send_telegram_message(f"⚠️ TPO Notifier Error: {str(e)[:200]}")
    
    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed")


# ============================================
# MAIN SERVICE LOOP
# ============================================

def run_service():
    """Run the notification service continuously"""
    logger.info("=" * 50)
    logger.info("TPO Company Notification Service Started")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds ({CHECK_INTERVAL/60:.1f} minutes)")
    logger.info("=" * 50)
    
    # Send startup notification
    send_telegram_message(f"""
🚀 <b>TPO Notifier Started!</b>

📊 Monitoring: {TPO_URL}
⏰ Check Interval: {CHECK_INTERVAL/60:.0f} minutes
📱 Notifications will be sent here

<i>Service started at {datetime.now().strftime('%d-%b-%Y %H:%M')}</i>
""")
    
    # Initial check
    check_for_new_companies()
    
    # Continuous monitoring loop
    while True:
        try:
            logger.info(f"Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
            check_for_new_companies()
        except KeyboardInterrupt:
            logger.info("Service stopped by user")
            send_telegram_message("🛑 TPO Notifier Service Stopped")
            break
        except Exception as e:
            logger.error(f"Service error: {e}")
            time.sleep(60)  # Wait a minute before retrying


def run_once():
    """Run a single check (for testing or cron jobs)"""
    logger.info("Running single check...")
    check_for_new_companies()
    logger.info("Check complete")


# ============================================
# ENTRY POINT
# ============================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Single run mode (for cron/scheduled tasks)
        run_once()
    else:
        # Continuous service mode
        run_service()