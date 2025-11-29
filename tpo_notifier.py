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

# WhatsApp Configuration (CallMeBot API)
# To get API key: 1) Save +34 644 33 66 63 in contacts
#                 2) Send "I allow callmebot to send me messages" via WhatsApp
#                 3) You'll receive your API key
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")  # Your phone with country code, e.g., +919876543210
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")  # API key from CallMeBot

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
# WHATSAPP FUNCTIONS (CallMeBot API)
# ============================================

def html_to_whatsapp(html_text: str) -> str:
    """Convert HTML formatting to WhatsApp formatting"""
    import re
    # Convert HTML bold to WhatsApp bold
    text = re.sub(r'<b>(.*?)</b>', r'*\1*', html_text)
    text = re.sub(r'<strong>(.*?)</strong>', r'*\1*', text)
    # Convert HTML italic to WhatsApp italic
    text = re.sub(r'<i>(.*?)</i>', r'_\1_', text)
    text = re.sub(r'<em>(.*?)</em>', r'_\1_', text)
    # Remove other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def send_whatsapp_message(message: str) -> bool:
    """Send a message via WhatsApp using CallMeBot API"""
    if not WHATSAPP_ENABLED:
        return False
    
    if not WHATSAPP_PHONE or not WHATSAPP_API_KEY:
        logger.warning("WhatsApp not configured: Missing phone or API key")
        return False
    
    try:
        # Convert HTML to WhatsApp formatting
        whatsapp_text = html_to_whatsapp(message)
        
        # URL encode the message
        from urllib.parse import quote
        encoded_message = quote(whatsapp_text)
        
        # Clean phone number (remove spaces, keep + and digits)
        phone = ''.join(c for c in WHATSAPP_PHONE if c.isdigit() or c == '+')
        
        # CallMeBot API endpoint
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_message}&apikey={WHATSAPP_API_KEY}"
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            logger.info("WhatsApp message sent successfully")
            return True
        else:
            logger.error(f"WhatsApp error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False


def send_notification(message: str) -> bool:
    """Send notification to both Telegram and WhatsApp"""
    telegram_sent = send_telegram_message(message)
    whatsapp_sent = send_whatsapp_message(message)
    
    return telegram_sent or whatsapp_sent


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
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Only set binary location if explicitly provided
    chrome_binary = os.getenv("CHROME_BINARY", "")
    if chrome_binary:
        chrome_options.binary_location = chrome_binary
    
    try:
        # Try with webdriver-manager first
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        logger.info("Created Chrome driver with webdriver-manager")
    except Exception as e:
        logger.warning(f"webdriver-manager failed: {e}, trying default")
        # Fallback for cloud hosting
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Created Chrome driver with default")
    
    return driver


def login_to_tpo(driver) -> bool:
    """Login to TPO portal"""
    try:
        logger.info(f"Navigating to {TPO_URL}")
        driver.get(TPO_URL)
        
        # Wait for Vue.js SPA to fully load
        logger.info("Waiting for page to fully load...")
        time.sleep(10)  # Initial wait for SPA
        
        # Wait for any input field to appear (Vue.js renders dynamically)
        wait = WebDriverWait(driver, 60)
        
        try:
            # Wait for any input element to be present
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
            logger.info("Found input elements on page")
        except:
            logger.warning("Timeout waiting for input elements")
        
        # Additional wait for Vue.js rendering
        time.sleep(5)
        
        logger.info(f"Current URL: {driver.current_url}")
        logger.info(f"Page title: {driver.title}")
        
        # Get all inputs on the page
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        logger.info(f"Found {len(all_inputs)} input elements")
        
        for idx, inp in enumerate(all_inputs):
            try:
                inp_type = inp.get_attribute("type")
                inp_name = inp.get_attribute("name")
                inp_placeholder = inp.get_attribute("placeholder")
                logger.info(f"Input {idx}: type={inp_type}, name={inp_name}, placeholder={inp_placeholder}")
            except:
                pass
        
        # Try multiple selectors for username field
        username_selectors = [
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.NAME, "email"),
            (By.NAME, "username"),
            (By.ID, "email"),
            (By.ID, "username"),
            (By.CSS_SELECTOR, "input[placeholder*='email' i]"),
            (By.CSS_SELECTOR, "input[placeholder*='Email' i]"),
            (By.CSS_SELECTOR, "input[placeholder*='user' i]"),
            (By.XPATH, "//input[@type='email']"),
            (By.XPATH, "//input[@type='text']"),
            (By.XPATH, "//input[contains(@placeholder, 'mail')]"),
            (By.XPATH, "//input[contains(@class, 'email')]"),
            (By.XPATH, "//input[contains(@class, 'user')]"),
        ]
        
        username_field = None
        for by, value in username_selectors:
            try:
                elements = driver.find_elements(by, value)
                if elements:
                    for elem in elements:
                        if elem.is_displayed():
                            username_field = elem
                            logger.info(f"Found username field with: {by} = {value}")
                            break
                    if username_field:
                        break
            except Exception as e:
                continue
        
        # If still not found, try the first visible input
        if not username_field and all_inputs:
            for inp in all_inputs:
                try:
                    if inp.is_displayed() and inp.get_attribute("type") != "hidden":
                        username_field = inp
                        logger.info("Using first visible input as username field")
                        break
                except:
                    continue
        
        if not username_field:
            # Log more page source for debugging
            logger.error("Could not find username field")
            page_source = driver.page_source
            logger.info(f"Full page length: {len(page_source)}")
            # Look for Vue app div
            if "id=\"app\"" in page_source or "id='app'" in page_source:
                logger.info("Vue.js app div found - SPA detected")
            # Save screenshot for debugging
            try:
                driver.save_screenshot("/tmp/login_page.png")
                logger.info("Screenshot saved to /tmp/login_page.png")
            except:
                pass
            return False
        
        # Clear and fill username
        try:
            username_field.clear()
        except:
            pass
        username_field.send_keys(TPO_USERNAME)
        logger.info(f"Entered username: {TPO_USERNAME}")
        time.sleep(1)
        
        # Find and fill password
        password_selectors = [
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.NAME, "password"),
            (By.ID, "password"),
            (By.XPATH, "//input[@type='password']"),
        ]
        
        password_field = None
        for by, value in password_selectors:
            try:
                elements = driver.find_elements(by, value)
                if elements:
                    for elem in elements:
                        if elem.is_displayed():
                            password_field = elem
                            logger.info(f"Found password field with: {by} = {value}")
                            break
                    if password_field:
                        break
            except:
                continue
        
        if not password_field:
            logger.error("Could not find password field")
            return False
        
        password_field.clear()
        password_field.send_keys(TPO_PASSWORD)
        logger.info("Entered password")
        time.sleep(1)
        
        # Find and click login button
        login_selectors = [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[@type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Login')]"),
            (By.XPATH, "//button[contains(text(), 'login')]"),
            (By.XPATH, "//button[contains(text(), 'Sign')]"),
            (By.XPATH, "//button[contains(text(), 'SIGN')]"),
            (By.XPATH, "//input[@type='submit']"),
            (By.CSS_SELECTOR, "button.v-btn"),
            (By.CSS_SELECTOR, "button.login"),
            (By.CSS_SELECTOR, "button"),
            (By.XPATH, "//span[contains(text(), 'Login')]/ancestor::button"),
            (By.XPATH, "//span[contains(text(), 'SIGN')]/ancestor::button"),
        ]
        
        login_btn = None
        for by, value in login_selectors:
            try:
                elements = driver.find_elements(by, value)
                if elements:
                    for elem in elements:
                        if elem.is_displayed():
                            login_btn = elem
                            logger.info(f"Found login button with: {by} = {value}")
                            break
                    if login_btn:
                        break
            except:
                continue
        
        if login_btn:
            driver.execute_script("arguments[0].click();", login_btn)
            logger.info("Clicked login button")
        else:
            # Try pressing Enter instead
            from selenium.webdriver.common.keys import Keys
            password_field.send_keys(Keys.RETURN)
            logger.info("Pressed Enter to submit")
        
        time.sleep(10)  # Wait for login to complete
        
        logger.info(f"After login URL: {driver.current_url}")
        
        if "dashboard" in driver.current_url.lower() or "company" in driver.current_url.lower():
            logger.info("Login successful!")
            return True
        else:
            logger.warning(f"Login might have failed. Current URL: {driver.current_url}")
            # Try to continue anyway - maybe we're logged in
            return True
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
            send_notification(header)
            time.sleep(1)  # CallMeBot rate limit
            
            # Send each new company
            for company in new_companies:
                msg = format_company_notification(company, is_new=True)
                send_notification(msg)
                time.sleep(1)  # CallMeBot rate limit
                logger.info(f"Notified about: {company['Company']}")
        else:
            logger.info("No new companies found")
        
        # Update known companies
        data["companies"] = current_companies
        save_known_companies(data)
        
    except Exception as e:
        logger.error(f"Error during check: {e}")
        send_notification(f"⚠️ TPO Notifier Error: {str(e)[:200]}")
    
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
    logger.info(f"WhatsApp enabled: {WHATSAPP_ENABLED}")
    logger.info("=" * 50)
    
    # Send startup notification
    send_notification(f"""
🚀 <b>TPO Notifier Started!</b>

📊 Monitoring: {TPO_URL}
⏰ Check Interval: {CHECK_INTERVAL/60:.0f} minutes
📱 Telegram: ✅ Enabled
📱 WhatsApp: {'✅ Enabled' if WHATSAPP_ENABLED else '❌ Disabled'}

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
            send_notification("🛑 TPO Notifier Service Stopped")
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