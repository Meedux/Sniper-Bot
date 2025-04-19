import time
import random
import re
import json
import os
import logging
import sys
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

# Path to the Buster CAPTCHA solver extension
BUSTER_EXTENSION_PATH = "buster.crx"

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"reddit_sniper_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class RedditAccountSniperBot:
    def __init__(self, config_file=None):
        # URL to the shop page
        self.target_url = "https://redaccs.com/shop/"
        self.refresh_interval = 30
        self.min_karma = 1000
        self.max_price = None
        self.headless = False
        self.debug_mode = False
        self.user_email = ""
        self.user_password = ""
        self.first_name = "John"
        self.last_name = "Doe"
        self.coupon_code = ""
        self.search_keyword = "50x"  # Added search keyword for 50x accounts
        
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        else:
            logger.warning("No configuration file provided or file not found. Using default values.")
        
        self.chrome_options = Options()
        if self.headless:
            logger.warning("Headless mode may affect CAPTCHA solving")
            self.chrome_options.add_argument("--headless=new")  # Using newer headless mode
            
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--disable-notifications")
        self.chrome_options.add_argument("--disable-popup-blocking")
        self.chrome_options.add_argument("--log-level=3")
        
        # Performance optimizations
        self.chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        self.chrome_options.add_argument("--disable-background-timer-throttling")
        self.chrome_options.add_argument("--disable-renderer-backgrounding")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--ignore-certificate-errors")
        
        # We need images enabled for CAPTCHA solving
        self.chrome_options.add_argument("--blink-settings=imagesEnabled=true")
        
        # Prevent detection
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ]
        self.chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        logger.info("Bot initialized with target URL: %s", self.target_url)
        logger.info("Search keyword set to: %s", self.search_keyword)
        if self.max_price:
            logger.info("Maximum price set to: $%.2f", self.max_price)
        
        self.test_mode = getattr(self, 'test_mode', False)
        
        # Try to import the GoogleRecaptchaBypass library to check if it's installed
        try:
            import RecaptchaSolver
            logger.info("GoogleRecaptchaBypass library detected")
        except ImportError:
            logger.warning("GoogleRecaptchaBypass library not found. Please install it with: pip install GoogleRecaptchaBypass")
    
    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            self.target_url = config.get('target_url', self.target_url)
            self.refresh_interval = config.get('refresh_interval', self.refresh_interval)
            self.min_karma = config.get('min_karma', self.min_karma)
            self.max_price = config.get('max_price', self.max_price)
            self.headless = config.get('headless', self.headless)
            self.debug_mode = config.get('debug_mode', False)
            self.coupon_code = config.get('coupon_code', "")
            self.search_keyword = config.get('search_keyword', self.search_keyword)
            
            self.test_mode = config.get('test_mode', False)
            if self.test_mode:
                logger.info("TEST MODE ENABLED - No actual purchases will be made")
            
            if self.debug_mode:
                logger.info("DEBUG MODE ENABLED - Will save screenshots and HTML on errors")
            
            if 'credentials' in config:
                self.user_email = config['credentials'].get('email', '')
                self.user_password = config['credentials'].get('password', '')
            
            if 'checkout_info' in config:
                self.first_name = config['checkout_info'].get('first_name', 'John')
                self.last_name = config['checkout_info'].get('last_name', 'Doe')
            
            logger.info("Configuration loaded from %s", config_file)
        except Exception as e:
            logger.error("Error loading configuration file: %s", str(e))
    
    def start_browser(self):
        logger.info("Starting browser session...")
        
        try:
            # Prioritize using the local chromedriver.exe that exists in the same directory
            if os.path.exists("chromedriver.exe"):
                logger.info("Found local chromedriver.exe, using it directly")
                try:
                    service = Service(executable_path=os.path.abspath("chromedriver.exe"))
                    self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
                    logger.info("Chrome started successfully using local chromedriver.exe")
                except Exception as e:
                    logger.error(f"Error using local chromedriver.exe: {str(e)}")
                    # If specific architecture error, provide clear guidance
                    if "not a valid Win32 application" in str(e):
                        logger.error("The chromedriver.exe is not compatible with your system architecture.")
                        logger.error("Please download the correct version for your system (32-bit or 64-bit).")
                        logger.error("Visit: https://googlechromelabs.github.io/chrome-for-testing/")
                    raise
            else:
                # Fallback to webdriver-manager if local chromedriver.exe not found
                logger.info("No local chromedriver.exe found, using webdriver-manager")
                
                # Try to find Chrome version to download matching driver
                import subprocess
                import re
                
                # Try to determine Chrome version
                chrome_version = None
                try:
                    # For Windows
                    process = subprocess.Popen(
                        r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version',
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
                    )
                    output, error = process.communicate()
                    if output:
                        match = re.search(r'version\s+REG_SZ\s+([\d\.]+)', output.decode('utf-8'))
                        if match:
                            chrome_version = match.group(1)
                            logger.info(f"Detected Chrome version: {chrome_version}")
                except Exception as e:
                    logger.warning(f"Could not determine Chrome version: {str(e)}")
                
                # Create a service
                if chrome_version:
                    # Extract major version
                    major_version = chrome_version.split('.')[0]
                    try:
                        service = Service(ChromeDriverManager(version=major_version).install())
                        logger.info(f"Using ChromeDriver version matching Chrome {major_version}")
                    except Exception as e:
                        logger.warning(f"Failed to find ChromeDriver for version {major_version}, falling back to latest: {str(e)}")
                        service = Service(ChromeDriverManager().install())
                else:
                    service = Service(ChromeDriverManager().install())
                    
                # Start the browser with the service
                self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
                logger.info("Chrome started successfully using webdriver-manager")
            
            # Prevent bot detection
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', 
                                     {"userAgent": self.driver.execute_script("return navigator.userAgent").replace("Headless", "")})
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Setup wait times
            self.wait = WebDriverWait(self.driver, 10)
            self.long_wait = WebDriverWait(self.driver, 30)
            self.short_wait = WebDriverWait(self.driver, 5)
            self.actions = ActionChains(self.driver)
            
            # Maximize window for better visibility
            self.driver.maximize_window()
            logger.info("Browser session started successfully")
            return self.driver
            
        except Exception as e:
            detailed_error = str(e)
            logger.error(f"Error starting browser session: {detailed_error}")
            
            # Provide specific guidance based on common errors
            if "not a valid Win32 application" in detailed_error:
                logger.error("This error typically means you're using a chromedriver.exe that's incompatible with your system.")
                logger.error("Your Chrome browser and system might be 64-bit while chromedriver.exe is 32-bit (or vice versa).")
                logger.error("Please download the correct chromedriver.exe version for your system from:")
                logger.error("https://googlechromelabs.github.io/chrome-for-testing/")
            elif "Chrome failed to start" in detailed_error:
                logger.error("Chrome browser failed to start. Make sure Chrome is installed and not running in crash-recovery mode.")
            elif "session not created" in detailed_error:
                logger.error("Session not created. This typically means the chromedriver.exe version doesn't match your Chrome browser version.")
                logger.error("Download the matching version from: https://googlechromelabs.github.io/chrome-for-testing/")
            
            if hasattr(self, 'driver'):
                try:
                    self.driver.quit()
                except:
                    pass
            raise
    
    def close_browser(self):
        if hasattr(self, 'driver'):
            logger.info("Closing browser session")
            self.driver.quit()
    
    def save_debug_info(self, prefix="debug"):
        if self.debug_mode:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            try:
                if hasattr(self, 'driver'):
                    screenshot_path = f"{prefix}_screenshot_{timestamp}.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"Saved screenshot to {screenshot_path}")
                    
                    html_path = f"{prefix}_page_{timestamp}.html"
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    logger.info(f"Saved page source to {html_path}")
                else:
                    logger.warning("Can't save debug info: driver not initialized or already closed")
            except Exception as e:
                logger.error(f"Failed to save debug info: {str(e)}")
    
    def retry_click(self, element, max_attempts=3):
        """Retry clicking an element if StaleElementReferenceException occurs"""
        for attempt in range(max_attempts):
            try:
                element.click()
                return True
            except StaleElementReferenceException:
                if attempt < max_attempts - 1:
                    logger.warning(f"Stale element encountered on click attempt {attempt+1}, retrying...")
                    time.sleep(0.5)
                else:
                    logger.error("Failed to click element after multiple attempts due to stale reference")
                    return False
            except Exception as e:
                logger.error(f"Error clicking element: {str(e)}")
                return False
        return False
    
    def click_with_retry(self, element_locator, locator_type=By.CSS_SELECTOR, max_attempts=3):
        """Find and click an element with retry logic to handle stale elements"""
        for attempt in range(max_attempts):
            try:
                if isinstance(element_locator, str):
                    # If element_locator is a string, it's a selector
                    element = self.wait.until(EC.element_to_be_clickable((locator_type, element_locator)))
                else:
                    # If element_locator is already a WebElement
                    element = element_locator
                    
                # Scroll to the element to make sure it's visible
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.3)  # Reduced wait time
                
                element.click()
                return True
            except StaleElementReferenceException:
                if attempt < max_attempts - 1:
                    logger.warning(f"Stale element encountered on click attempt {attempt+1}, retrying...")
                    time.sleep(0.5)
                else:
                    logger.error("Failed to click element after multiple attempts due to stale reference")
                    return False
            except Exception as e:
                logger.error(f"Error clicking element: {str(e)}")
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
                else:
                    return False
        return False
    
    def login_if_needed(self):
        try:
            logger.info("Checking login status...")
            
            logged_in_indicators = ["my-account", "logout", "account"]
            
            for indicator in logged_in_indicators:
                try:
                    if self.driver.find_element(By.XPATH, f"//*[contains(@class, '{indicator}') or contains(text(), '{indicator}')]"):
                        logger.info("Already logged in")
                        return True
                except NoSuchElementException:
                    pass
            
            logger.info("Not logged in, navigating to login page...")
            
            self.driver.get("https://redaccs.com/my-account/")
            
            try:
                username_field = self.wait.until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                logger.info("Login form found, entering credentials...")
                
                password_field = self.driver.find_element(By.ID, "password")
                
                username_field.clear()
                for char in self.user_email:
                    username_field.send_keys(char)
                    time.sleep(random.uniform(0.01, 0.05))  # Ultra-fast typing
                    
                password_field.clear()
                for char in self.user_password:
                    password_field.send_keys(char)
                    time.sleep(random.uniform(0.01, 0.05))  # Ultra-fast typing
                
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[name='login']")
                self.click_with_retry(login_button)
                
                logger.info("Login credentials submitted, waiting for redirect...")
                
                time.sleep(3)  # Reduced wait time
                
                # Check for successful login
                for indicator in logged_in_indicators:
                    try:
                        if self.driver.find_element(By.XPATH, f"//*[contains(@class, '{indicator}') or contains(text(), '{indicator}')]"):
                            logger.info("Login successful!")
                            return True
                    except NoSuchElementException:
                        pass
                
                logger.error("Login failed! Check your credentials.")
                self.save_debug_info("login_failed")
                return False
                
            except Exception as e:
                logger.error(f"Error in login process: {str(e)}")
                self.save_debug_info("login_error")
                return False
            
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return False
    
    def navigate_to_acc_page(self):
        """Navigate to the Reddit accounts page"""
        try:
            logger.info("Navigating to Reddit accounts page...")
            self.driver.get(self.target_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 20).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            
            # Wait for content to load (10 seconds as specified)
            logger.info("Waiting 10 seconds for content to load...")
            time.sleep(10)
            
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to Reddit accounts page: {str(e)}")
            self.save_debug_info("navigation_error")
            return False
    
    def force_page_load(self):
        """Forces the page to load by simulating user interactions"""
        try:
            logger.info("Forcing page content to load...")
            
            # Focus window
            self.driver.execute_script("window.focus();")
            
            # Scroll actions to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(0.2)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight*2/3);")
            time.sleep(0.2)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            
            # Find tables and scroll to them
            self.driver.execute_script("""
                // Simulate user interaction
                var evt = new MouseEvent('mousemove', {
                    'view': window,
                    'bubbles': true,
                    'cancelable': true
                });
                document.dispatchEvent(evt);
                
                // Focus on tables
                var tables = document.getElementsByTagName('table');
                for (var i = 0; i < tables.length; i++) {
                    tables[i].scrollIntoView({behavior: 'smooth', block: 'center'});
                }
            """)
            
            return True
        except Exception as e:
            logger.error(f"Error while forcing page load: {str(e)}")
            return False
    
    def find_and_click_account_by_keyword(self):
        """Find account listing with keyword and click the buy button"""
        try:
            logger.info(f"Searching for accounts with keyword: {self.search_keyword}...")
            
            # Force page elements to load
            self.force_page_load()
            
            # Wait 5 seconds before searching table rows to ensure content is fully loaded
            logger.info("Waiting 5 seconds for table content to stabilize...")
            time.sleep(5)
            
            # Find all table rows
            rows = self.driver.find_elements(By.TAG_NAME, "tr")
            if not rows:
                logger.warning("No table rows found")
                return False
            
            logger.info(f"Found {len(rows)} table rows to search")
            
            matching_row = None
            
            # Search each TR for the keyword
            for row in rows:
                try:
                    row_text = row.text.strip()
                    
                    # Check if row contains the keyword
                    if self.search_keyword.lower() in row_text.lower():
                        logger.info(f"Found matching row with text: {row_text}")
                        matching_row = row
                        break
                
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    logger.error(f"Error processing row: {str(e)}")
            
            if not matching_row:
                logger.warning(f"No rows found containing keyword: {self.search_keyword}")
                return False
            
            # Find buy button in the matching row
            buy_button = None
            buy_button_xpaths = [
                ".//button[@type='submit']",
                ".//input[@type='submit']",
                ".//button[contains(@class, 'buy')]",
                ".//a[contains(@class, 'buy')]",
                ".//button[contains(text(), 'Buy')]",
                ".//a[contains(text(), 'Buy')]",
                ".//button",
                ".//a[contains(@href, 'add-to-cart')]"
            ]
            
            for xpath in buy_button_xpaths:
                buttons = matching_row.find_elements(By.XPATH, xpath)
                if buttons:
                    buy_button = buttons[0]
                    break
            
            if not buy_button:
                # Try links as a fallback
                links = matching_row.find_elements(By.TAG_NAME, "a")
                if links:
                    buy_button = links[0]
            
            if not buy_button:
                logger.warning(f"No buy button found in the matching row")
                return False
            
            # Scroll and click the buy button
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", buy_button)
            time.sleep(0.5)
            
            logger.info("Clicking buy button...")
            if not self.retry_click(buy_button):
                logger.error("Failed to click buy button")
                return False
            
            # Wait 5 seconds as specified for content to load
            logger.info("Waiting 5 seconds for content to fully load...")
            time.sleep(5)
            
            return True
            
        except Exception as e:
            logger.error(f"Error finding account by keyword: {str(e)}")
            self.save_debug_info("find_account_error")
            return False
    
    def apply_coupon_and_checkout(self):
        """Click showcoupon, apply coupon code, and fill out checkout information"""
        try:
            logger.info("Looking for coupon field...")
            
            # Click on showcoupon link
            try:
                showcoupon_link = self.short_wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "showcoupon"))
                )
                logger.info("Found showcoupon link, clicking it...")
                self.click_with_retry(showcoupon_link)
                time.sleep(0.5)
            except TimeoutException:
                logger.warning("Showcoupon link not found, continuing without coupon")
            
            # Input coupon code if provided
            if self.coupon_code:
                try:
                    coupon_field = self.short_wait.until(
                        EC.presence_of_element_located((By.ID, "coupon_code"))
                    )
                    logger.info(f"Entering coupon code: {self.coupon_code}")
                    
                    coupon_field.clear()
                    coupon_field.send_keys(self.coupon_code)
                    
                    # Click apply coupon button
                    apply_button = self.driver.find_element(By.NAME, "apply_coupon")
                    self.click_with_retry(apply_button)
                    time.sleep(1)
                except TimeoutException:
                    logger.warning("Coupon field not found")
                except Exception as e:
                    logger.error(f"Error applying coupon: {str(e)}")
            
            # Fill checkout information
            logger.info("Filling checkout information...")
            
            checkout_fields = {
                "billing_first_name": self.first_name,
                "billing_last_name": self.last_name,
                "billing_email": self.user_email
            }
            
            for field_id, value in checkout_fields.items():
                try:
                    field = self.wait.until(
                        EC.presence_of_element_located((By.ID, field_id))
                    )
                    
                    field.clear()
                    field.send_keys(value)
                except TimeoutException:
                    logger.warning(f"Field not found: {field_id}")
                except Exception as e:
                    logger.error(f"Error filling field {field_id}: {str(e)}")
            
            # Check terms checkbox if present
            try:
                terms_checkbox = self.driver.find_element(By.ID, "terms")
                if not terms_checkbox.is_selected():
                    terms_checkbox.click()
                    logger.info("Checked terms and conditions")
            except NoSuchElementException:
                pass
            
            logger.info("Checkout form filled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error in checkout process: {str(e)}")
            self.save_debug_info("checkout_error")
            return False
    
    def detect_captcha(self):
        """Detect if captcha is present on the page and return its type (recaptcha/hcaptcha)"""
        try:
            # Look for reCAPTCHA iframe
            recaptcha_iframe = self.driver.find_elements(By.CSS_SELECTOR, 'iframe[src*="google.com/recaptcha"]')
            if recaptcha_iframe:
                logger.info("reCAPTCHA detected on the page")
                return True, "recaptcha", recaptcha_iframe[0]
            
            # Look for hCaptcha iframe
            hcaptcha_iframe = self.driver.find_elements(By.CSS_SELECTOR, 'iframe[src*="hcaptcha.com"]')
            if hcaptcha_iframe:
                logger.info("hCaptcha detected on the page")
                return True, "hcaptcha", hcaptcha_iframe[0]
            
            # No CAPTCHA found
            return False, None, None
            
        except Exception as e:
            logger.error(f"Error detecting CAPTCHA: {str(e)}")
            return False, None, None
    
    def solve_captcha(self):
        try:
            self.driver.switch_to.default_content()
            logger.info("Starting CAPTCHA solution process with NextCaptcha...")
            
            if self.debug_mode:
                self.driver.save_screenshot("captcha_initial.png")
            
            # Check if reCAPTCHA is present
            recaptcha_present = False
            recaptcha_key = None
            
            try:
                # First try to find the site key in any div with g-recaptcha class
                g_recaptcha_divs = self.driver.find_elements(By.CLASS_NAME, "g-recaptcha")
                if g_recaptcha_divs:
                    recaptcha_present = True
                    for div in g_recaptcha_divs:
                        key = div.get_attribute("data-sitekey")
                        if key:
                            recaptcha_key = key
                            logger.info(f"Found reCAPTCHA key: {recaptcha_key}")
                            break
                
                # Check in iframes if no key found yet
                if not recaptcha_key:
                    iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        src = iframe.get_attribute("src") or ""
                        if "google.com/recaptcha" in src:
                            recaptcha_present = True
                            # Try to extract the site key from the iframe src
                            key_match = re.search(r"k=([^&]+)", src)
                            if key_match:
                                recaptcha_key = key_match.group(1)
                                logger.info(f"Found reCAPTCHA key in iframe: {recaptcha_key}")
                                break
            except Exception as e:
                logger.error(f"Error detecting reCAPTCHA: {str(e)}")
            
            if not recaptcha_present:
                logger.info("No reCAPTCHA detected on the page")
                return True
            
            if not recaptcha_key:
                logger.error("reCAPTCHA detected but could not find the site key")
                return False
            
            logger.info("reCAPTCHA detected, attempting to solve with NextCaptcha...")
            
            try:
                # Import required libraries for NextCaptcha
                import requests
                import time
                
                # NextCaptcha API credentials
                api_key = "next_887d0a4fd8fd346ae9cff5b6dbc0106428"
                
                # Current URL where the CAPTCHA is located
                page_url = self.driver.current_url
                
                # Create a session for API requests
                session = requests.Session()
                
                # Step 1: Create a task to solve the reCAPTCHA
                logger.info("Creating reCAPTCHA solving task...")
                create_task_payload = {
                    "clientKey": api_key,
                    "task": {
                        "type": "RecaptchaV2TaskProxyless",
                        "websiteURL": page_url,
                        "websiteKey": recaptcha_key,
                        "isInvisible": False  # Set to True if it's invisible reCAPTCHA
                    }
                }
                
                create_task_url = "https://api.nextcaptcha.com/createTask"
                
                try:
                    response = session.post(create_task_url, json=create_task_payload)
                    response_data = response.json()
                    
                    if response.status_code != 200 or not response_data.get("taskId"):
                        logger.error(f"Failed to create task: {response_data.get('errorDescription', 'Unknown error')}")
                        return False
                    
                    task_id = response_data["taskId"]
                    logger.info(f"Task created successfully, ID: {task_id}")
                    
                    # Step 2: Get the solution
                    get_solution_url = "https://api.nextcaptcha.com/getTaskResult"
                    get_solution_payload = {
                        "clientKey": api_key,
                        "taskId": task_id
                    }
                    
                    # Poll for solution with exponential backoff
                    max_attempts = 15
                    for attempt in range(1, max_attempts + 1):
                        logger.info(f"Waiting for solution (attempt {attempt}/{max_attempts})...")
                        time.sleep(5)  # Wait 5 seconds between checks
                        
                        solution_response = session.post(get_solution_url, json=get_solution_payload)
                        solution_data = solution_response.json()
                        
                        if solution_data.get("status") == "ready":
                            token = solution_data.get("solution", {}).get("gRecaptchaResponse")
                            if token:
                                logger.info("Successfully obtained reCAPTCHA token from NextCaptcha")
                                
                                # First, find the checkbox iframe and try to click it directly
                                self.mark_recaptcha_checkbox_checked()
                                
                                # Also apply the token to ensure it works if visual clicking doesn't work
                                logger.info("Applying reCAPTCHA token to the page...")
                                self.driver.execute_script(f"""
                                    try {{
                                        document.querySelector('[name="g-recaptcha-response"]').innerHTML = "{token}";
                                    }} catch(e) {{}}
                                    
                                    var textareas = document.getElementsByTagName('textarea');
                                    for (var i = 0; i < textareas.length; i++) {{
                                        if (textareas[i].name == 'g-recaptcha-response') {{
                                            textareas[i].innerHTML = "{token}";
                                        }}
                                    }}
                                    
                                    if (typeof ___grecaptcha_cfg !== 'undefined') {{
                                        for (var key in ___grecaptcha_cfg.clients) {{
                                            if (___grecaptcha_cfg.clients[key].hasOwnProperty('callback')) {{
                                                try {{
                                                    ___grecaptcha_cfg.clients[key]['callback']("{token}");
                                                    break;
                                                }} catch(e) {{}}
                                            }}
                                        }}
                                    }}
                                    
                                    // Attempt to trigger completed state display
                                    try {{
                                        // This marks the recaptcha as visually solved
                                        var checkboxes = document.querySelectorAll(".recaptcha-checkbox");
                                        for (var i = 0; i < checkboxes.length; i++) {{
                                            checkboxes[i].classList.add("recaptcha-checkbox-checked");
                                            checkboxes[i].setAttribute("aria-checked", "true");
                                        }}
                                    }} catch(e) {{}}
                                """)
                                
                                logger.info("reCAPTCHA token applied to the page")
                                
                                # Try again to mark the checkbox as checked after token application
                                time.sleep(1)
                                self.mark_recaptcha_checkbox_checked()
                                
                                # Take a screenshot to verify if it worked
                                if self.debug_mode:
                                    self.driver.save_screenshot("captcha_after_solution.png")
                                    logger.info("Saved screenshot after CAPTCHA solution")
                                
                                time.sleep(2)
                                return True
                            else:
                                logger.error("Solution ready but no token received")
                                return False
                        elif solution_data.get("status") == "processing":
                            continue
                        else:
                            logger.error(f"Error in solution: {solution_data.get('errorDescription', 'Unknown error')}")
                            return False
                    
                    logger.error("Maximum attempts reached waiting for CAPTCHA solution")
                    return False
                    
                except requests.RequestException as e:
                    logger.error(f"API request error: {str(e)}")
                    return False
                    
            except ImportError as e:
                logger.error(f"Required library not installed: {str(e)}")
                logger.error("Please install it with: pip install requests")
                return False
                    
            except Exception as e:
                logger.error(f"Error using NextCaptcha: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error in CAPTCHA solving: {str(e)}")
            if self.debug_mode:
                self.save_debug_info("captcha_error")
            return False
            
    def mark_recaptcha_checkbox_checked(self):
        """Enhanced method to ensure reCAPTCHA checkbox appears checked"""
        logger.info("Attempting to mark reCAPTCHA checkbox as checked...")
        
        try:
            # Switch back to default content before starting
            self.driver.switch_to.default_content()
            
            # First find all recaptcha iframes
            recaptcha_iframes = self.driver.find_elements(By.CSS_SELECTOR, 'iframe[src*="google.com/recaptcha"]')
            checkbox_iframe = None
            
            if not recaptcha_iframes:
                logger.warning("No reCAPTCHA iframes found")
                return False
                
            logger.info(f"Found {len(recaptcha_iframes)} reCAPTCHA iframes")
            
            # Try to find the checkbox iframe
            for iframe in recaptcha_iframes:
                title = iframe.get_attribute("title") or ""
                src = iframe.get_attribute("src") or ""
                
                # The checkbox iframe typically has "recaptcha" in title and doesn't contain "challenge"
                if (("recaptcha" in title.lower() and "challenge" not in title.lower()) or 
                    ("anchor" in src and "challenge" not in src)):
                    checkbox_iframe = iframe
                    logger.info(f"Found potential checkbox iframe with title: {title}")
                    break
            
            if not checkbox_iframe:
                # If we couldn't identify by title, just try the first iframe
                logger.warning("Could not identify the checkbox iframe by title, trying first iframe")
                checkbox_iframe = recaptcha_iframes[0]
            
            # Switch to the iframe
            logger.info("Switching to checkbox iframe")
            self.driver.switch_to.frame(checkbox_iframe)
            
            # Try multiple ways to find and click the checkbox
            checkbox_selectors = [
                "div.recaptcha-checkbox-border",
                "div.recaptcha-checkbox-checkmark",
                "div.recaptcha-checkbox",
                "span.recaptcha-checkbox"
            ]
            
            clicked = False
            for selector in checkbox_selectors:
                try:
                    checkbox_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if checkbox_elements:
                        logger.info(f"Found checkbox element with selector: {selector}")
                        
                        # First check if already checked
                        is_checked = len(self.driver.find_elements(By.CSS_SELECTOR, "div.recaptcha-checkbox-checked")) > 0
                        
                        if is_checked:
                            logger.info("Checkbox is already checked")
                            clicked = True
                            break
                        
                        # Try clicking the element
                        logger.info(f"Attempting to click checkbox with selector: {selector}")
                        checkbox_elements[0].click()
                        time.sleep(1)
                        
                        # Verify if checkbox is now checked
                        is_checked = len(self.driver.find_elements(By.CSS_SELECTOR, "div.recaptcha-checkbox-checked")) > 0
                        if is_checked:
                            logger.info("Successfully clicked checkbox - checkmark is visible")
                            clicked = True
                            break
                        else:
                            logger.warning("Clicked checkbox but checkmark is not visible")
                            
                        # Also try using JavaScript to mark it as checked
                        self.driver.execute_script("""
                            try {
                                var checkboxes = document.querySelectorAll(".recaptcha-checkbox");
                                for (var i = 0; i < checkboxes.length; i++) {
                                    checkboxes[i].classList.add("recaptcha-checkbox-checked");
                                    checkboxes[i].setAttribute("aria-checked", "true");
                                }
                            } catch(e) {}
                        """)
                        
                        # Check again
                        is_checked = len(self.driver.find_elements(By.CSS_SELECTOR, "div.recaptcha-checkbox-checked")) > 0
                        if is_checked:
                            logger.info("Successfully marked checkbox as checked via JavaScript")
                            clicked = True
                            break
                except Exception as e:
                    logger.warning(f"Error trying checkbox selector '{selector}': {str(e)}")
            
            # Switch back to default content
            self.driver.switch_to.default_content()
            
            if clicked:
                return True
            else:
                logger.warning("Could not visibly mark checkbox as checked using any method")
                return False
                
        except Exception as e:
            logger.error(f"Error in mark_recaptcha_checkbox_checked: {str(e)}")
            # Make sure we're back at the default content
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False
    
    def complete_order(self):
        """Find and click the place_order button, handling CAPTCHA if present"""
        try:
            logger.info("Checking for CAPTCHA before completing order...")
            
            # Check for CAPTCHA and solve it
            has_captcha, captcha_type, _ = self.detect_captcha()
            if has_captcha:
                logger.info(f"{captcha_type} detected on checkout page, attempting to solve...")
                if not self.solve_captcha():
                    logger.error(f"Failed to solve {captcha_type}")
                    self.save_debug_info("captcha_failure")
                    return False
                logger.info("CAPTCHA solved successfully")
            
            logger.info("Looking for place_order button...")
            
            # Find and click the place_order button
            place_order_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "place_order"))
            )
            
            logger.info("Found place_order button, clicking it...")
            
            # Scroll to button
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", place_order_button)
            time.sleep(0.5)
            
            if self.test_mode:
                logger.info("TEST MODE: Would have clicked place_order button here")
                return True
            
            # Click the button
            if not self.click_with_retry(place_order_button):
                logger.error("Failed to click place_order button")
                return False
            
            # Wait for order confirmation
            try:
                self.wait.until(EC.url_contains("order-received"))
                logger.info("Order confirmed successfully!")
                return True
            except TimeoutException:
                error_messages = self.driver.find_elements(By.CSS_SELECTOR, ".woocommerce-error li")
                if error_messages:
                    for error in error_messages:
                        logger.error(f"Order error: {error.text}")
                else:
                    logger.error("Order confirmation not received, but no specific errors found")
                self.save_debug_info("order_error")
                return False
            
        except Exception as e:
            logger.error(f"Error completing order: {str(e)}")
            self.save_debug_info("complete_order_error")
            return False
    
    def purchase_reddit_account(self):
        """Full purchase flow for a Reddit account with Buster CAPTCHA handling"""
        try:
            # Start the process
            logger.info("Starting Reddit account purchase process...")
            
            # Step 1: Navigate to accounts page
            if not self.navigate_to_acc_page():
                logger.error("Failed to navigate to Reddit accounts page")
                return False
            
            # Step 2: Find and click account with matching keyword
            if not self.find_and_click_account_by_keyword():
                logger.error("Failed to find and select an account")
                return False
            
            # Step 3: Apply coupon and fill checkout info
            if not self.apply_coupon_and_checkout():
                logger.error("Failed to apply coupon and fill checkout form")
                return False
            
            # Step 4: Complete the order (includes CAPTCHA handling)
            if not self.complete_order():
                logger.error("Failed to complete the order")
                return False
            
            logger.info("Successfully purchased Reddit account!")
            return True
            
        except Exception as e:
            logger.error(f"Error in purchase process: {str(e)}")
            self.save_debug_info("purchase_process_error")
            return False
    
    def run(self):
        try:
            try:
                self.start_browser()
            except Exception as e:
                logger.error(f"Failed to start browser: {str(e)}")
                logger.error("Please make sure Chrome is installed and up to date")
                return
        
            # Login only if credentials were provided
            if self.user_email and self.user_password:
                if not self.login_if_needed():
                    logger.error("Failed to log in, aborting")
                    return
                logger.info("Login successful")
            
            # Set up monitoring loop
            max_attempts = 5
            attempt_count = 0
            refresh_delay = self.refresh_interval  # Use the configured refresh interval
            
            logger.info(f"Starting monitoring loop with {max_attempts} attempts, refreshing every {refresh_delay} seconds")
            
            while attempt_count < max_attempts:
                attempt_count += 1
                logger.info(f"Monitoring attempt {attempt_count} of {max_attempts}")
                
                # Navigate to target URL for the first attempt or when explicitly needed
                if attempt_count == 1:
                    logger.info(f"Navigating to target URL: {self.target_url}")
                    self.driver.get(self.target_url)
                    time.sleep(3)
                
                # Start the purchase process
                logger.info("Starting Reddit account purchase process")
                
                purchase_successful = False
                
                try:
                    # Force page load first to ensure content is visible
                    self.force_page_load()
                    
                    # Check if any tables are present
                    table_rows = self.driver.find_elements(By.TAG_NAME, "tr")
                    
                    # If no table rows found, try clicking the reset button
                    if not table_rows:
                        logger.warning("No table rows found, trying to click reset button")
                        try:
                            reset_buttons = self.driver.find_elements(By.CLASS_NAME, "reset")
                            if reset_buttons:
                                logger.info("Found reset button, clicking it")
                                reset_buttons[0].click()
                                time.sleep(5)  # Give time for the page to reset
                                self.force_page_load()  # Force page load again after reset
                            else:
                                logger.warning("No reset button found, refreshing page")
                                self.driver.refresh()
                                time.sleep(5)
                        except Exception as e:
                            logger.error(f"Error clicking reset button: {str(e)}")
                            # Navigate directly to target URL as fallback
                            self.driver.get(self.target_url)
                            time.sleep(5)
                    
                    # Step 1: Find and click account with matching keyword
                    if self.find_and_click_account_by_keyword():
                        logger.info("Found matching account, proceeding with purchase...")
                        
                        # Step 2: Apply coupon and fill checkout info
                        if self.apply_coupon_and_checkout():
                            logger.info("Checkout form completed, proceeding to complete order")
                            
                            # Step 3: Complete the order (includes CAPTCHA handling)
                            if self.complete_order():
                                logger.info("Successfully purchased Reddit account!")
                                purchase_successful = True
                                break  # Exit the loop if successful
                            else:
                                logger.error("Failed to complete the order")
                        else:
                            logger.error("Failed to apply coupon and fill checkout form")
                    else:
                        logger.warning(f"No matching accounts found in attempt {attempt_count}/{max_attempts}")
                        
                        # Try clicking the reset button if account not found
                        logger.info("Clicking reset button to refresh available accounts")
                        try:
                            reset_buttons = self.driver.find_elements(By.CLASS_NAME, "reset")
                            if reset_buttons:
                                reset_buttons[0].click()
                                time.sleep(5)  # Give time for the page to refresh
                            else:
                                # Fallback to direct page refresh
                                logger.warning("Reset button not found, refreshing page directly")
                                self.driver.refresh()
                                time.sleep(5)
                        except Exception as e:
                            logger.error(f"Error clicking reset button: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"Error during purchase process in attempt {attempt_count}: {str(e)}")
                    self.save_debug_info(f"error_attempt_{attempt_count}")
                    
                    # Try to recover by refreshing the page
                    try:
                        logger.info("Attempting to recover by refreshing the page")
                        self.driver.get(self.target_url)
                        time.sleep(5)
                    except:
                        pass
                
                # Continue to next attempt if not successful
                if not purchase_successful and attempt_count < max_attempts:
                    logger.info(f"Waiting {refresh_delay} seconds before next attempt...")
                    time.sleep(refresh_delay)
                elif not purchase_successful:
                    logger.warning("Maximum monitoring attempts reached without successful purchase")
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in main process: {str(e)}")
            self.save_debug_info("unexpected_error")
        finally:
            self.close_browser()

if __name__ == "__main__":
    print("="*80)
    print("Reddit Account Sniper Bot")
    print("="*80)
    
    config_file = "reddit_sniper_config.json"
    
    if not os.path.exists(config_file):
        print(f"Config file '{config_file}' not found.")
        print("Creating example config file. Please edit it with your details and run the script again.")
        
        example_config = {
            "target_url": "https://redaccs.com/shop/",
            "refresh_interval": 30,
            "min_karma": 1000,
            "max_price": 50.0,
            "headless": False,
            "test_mode": True,
            "debug_mode": True,
            "search_keyword": "50x",
            "coupon_code": "YOUR_COUPON_HERE",
            "credentials": {
                "email": "your_email@example.com",
                "password": "your_password"
            },
            "checkout_info": {
                "first_name": "John",
                "last_name": "Doe"
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(example_config, f, indent=4)
            
        print(f"Example config file created at '{config_file}'")
        exit(1)
    
    # Create and run the bot
    bot = RedditAccountSniperBot(config_file)
    bot.run()