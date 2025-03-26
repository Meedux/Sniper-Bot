import time
import random
import re
import json
import os
import logging
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

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
        # Updated URL to the acc page
        self.target_url = "https://redaccs.com/#acc"
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
        
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        else:
            logger.warning("No configuration file provided or file not found. Using default values.")
        
        self.previous_listings = set()
        
        self.chrome_options = Options()
        if self.headless:
            self.chrome_options.add_argument("--headless=new")  # Using newer headless mode
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--disable-notifications")
        self.chrome_options.add_argument("--disable-popup-blocking")
        self.chrome_options.add_argument("--log-level=3")
        
        # Focus and performance optimizations
        self.chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        self.chrome_options.add_argument("--disable-background-timer-throttling")
        self.chrome_options.add_argument("--disable-renderer-backgrounding")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--no-sandbox")
        
        # More optimizations
        self.chrome_options.add_argument("--ignore-certificate-errors")
        self.chrome_options.add_argument("--disable-web-security")
        self.chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        
        # Prevent detection
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"
        ]
        self.chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        logger.info("Bot initialized with target URL: %s", self.target_url)
        logger.info("Karma threshold set to: %d", self.min_karma)
        if self.max_price:
            logger.info("Maximum price set to: $%.2f", self.max_price)
    
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
        logger.info("Starting browser session")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
        
        # Prevent bot detection
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.driver.execute_script("return navigator.userAgent").replace("Headless", "")})
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.wait = WebDriverWait(self.driver, 10)
        self.long_wait = WebDriverWait(self.driver, 30)
        self.actions = ActionChains(self.driver)
        
        # Maximize window for better visibility
        self.driver.maximize_window()
        return self.driver
    
    def close_browser(self):
        if hasattr(self, 'driver'):
            logger.info("Closing browser session")
            self.driver.quit()
    
    def save_debug_info(self, prefix="debug"):
        if self.debug_mode:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            try:
                screenshot_path = f"{prefix}_screenshot_{timestamp}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot to {screenshot_path}")
                
                html_path = f"{prefix}_page_{timestamp}.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                logger.info(f"Saved page source to {html_path}")
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
                time.sleep(0.5)
                
                element.click()
                return True
            except StaleElementReferenceException:
                if attempt < max_attempts - 1:
                    logger.warning(f"Stale element encountered on click attempt {attempt+1}, retrying...")
                    time.sleep(1)
                else:
                    logger.error("Failed to click element after multiple attempts due to stale reference")
                    return False
            except Exception as e:
                logger.error(f"Error clicking element: {str(e)}")
                if attempt < max_attempts - 1:
                    time.sleep(1)
                else:
                    return False
        return False
    
    def extract_karma(self, text):
        """Extract karma value from text"""
        karma_patterns = [
            r'(\d+[\d,]*)\s*karma',
            r'(\d+)\s*[kK](?:\s+karma|\s*karma)',
            r'karma\s*[:-]?\s*(\d+[\d,]*)',
            r'karma\s*[:-]?\s*(\d+)\s*[kK]'
        ]
        
        for pattern in karma_patterns:
            match = re.search(pattern, text.lower())
            if match:
                karma_str = match.group(1)
                karma_str = karma_str.replace(',', '')
                
                if 'k' in text.lower() and 'k' not in karma_str:
                    return int(float(karma_str) * 1000)
                return int(karma_str)
        
        return None
    
    def extract_price(self, price_text):
        price_match = re.search(r'(\d+\.\d+|\d+)', price_text.replace(',', ''))
        if price_match:
            return float(price_match.group(1))
        return None
    
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
                    time.sleep(random.uniform(0.03, 0.08))  # Faster typing
                    
                password_field.clear()
                for char in self.user_password:
                    password_field.send_keys(char)
                    time.sleep(random.uniform(0.03, 0.08))  # Faster typing
                
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[name='login']")
                self.click_with_retry(login_button)
                
                logger.info("Login credentials submitted, waiting for redirect...")
                
                time.sleep(5)
                
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
            
            # Look for Buy Now button
            buy_now_xpaths = [
                "//a[contains(text(), 'Buy Now')]",
                "//button[contains(text(), 'Buy Now')]",
                "//a[contains(@class, 'buy')]",
                "//button[contains(@class, 'buy')]"
            ]
            
            logger.info("Looking for Buy Now button...")
            for xpath in buy_now_xpaths:
                try:
                    buy_now_buttons = self.driver.find_elements(By.XPATH, xpath)
                    if buy_now_buttons:
                        logger.info(f"Found Buy Now button with XPath: {xpath}")
                        self.click_with_retry(buy_now_buttons[0], By.XPATH)
                        break
                except Exception:
                    continue
            
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
            time.sleep(0.3)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight*2/3);")
            time.sleep(0.3)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.3)
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
                    setTimeout(function(){}, 200);
                }
            """)
            
            return True
        except Exception as e:
            logger.error(f"Error while forcing page load: {str(e)}")
            return False
    
    def find_and_click_account_by_karma(self):
        """Find account listing with desired karma and click the buy button"""
        try:
            logger.info(f"Searching for accounts with karma >= {self.min_karma}...")
            
            # Force page elements to load
            self.force_page_load()
            
            # Find all table rows
            rows = self.driver.find_elements(By.TAG_NAME, "tr")
            if not rows:
                logger.warning("No rows found in table")
                return False
            
            logger.info(f"Found {len(rows)} rows in tables")
            
            valid_listings = []
            
            # Scan each row for karma
            for row_idx, row in enumerate(rows):
                try:
                    # Skip header rows
                    if row.find_elements(By.TAG_NAME, "th"):
                        continue
                    
                    # Scroll to ensure row is in view
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
                    time.sleep(0.2)
                    
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells:
                        continue
                    
                    row_text = row.text.strip()
                    
                    # Extract karma
                    karma = self.extract_karma(row_text)
                    if not karma or karma < self.min_karma:
                        continue
                    
                    # Extract price
                    price_match = re.search(r'\$\s*(\d+\.\d+|\d+)', row_text)
                    if price_match:
                        price_text = price_match.group(0)
                        price_value = float(price_match.group(1))
                        
                        # Skip if over max price
                        if self.max_price and price_value > self.max_price:
                            logger.info(f"Skipping listing with price {price_text} (exceeds maximum price)")
                            continue
                    
                    # Check if out of stock
                    out_of_stock = False
                    for out_indicator in ["out of stock", "sold out", "unavailable"]:
                        if out_indicator in row_text.lower():
                            out_of_stock = True
                            break
                    
                    if out_of_stock:
                        logger.info(f"Skipping out-of-stock row: {row_text[:50]}...")
                        continue
                    
                    # Find buy button in this row
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
                        buttons = row.find_elements(By.XPATH, xpath)
                        if buttons:
                            buy_button = buttons[0]
                            break
                    
                    if not buy_button:
                        # Try links as a fallback
                        links = row.find_elements(By.TAG_NAME, "a")
                        if links:
                            buy_button = links[0]
                    
                    if not buy_button:
                        logger.warning(f"No buy button found for row: {row_text[:50]}...")
                        continue
                    
                    # Store data about this account listing
                    valid_listings.append({
                        "karma": karma,
                        "row_text": row_text,
                        "buy_button": buy_button,
                        "price": price_text if price_match else "Unknown",
                        "price_value": price_value if price_match else 0
                    })
                    
                    logger.info(f"Found eligible account: Karma: {karma}, Price: {price_text if price_match else 'Unknown'}")
                    
                except StaleElementReferenceException:
                    logger.warning(f"Stale element encountered in row {row_idx}, skipping")
                    continue
                except Exception as e:
                    logger.error(f"Error processing row: {str(e)}")
            
            if not valid_listings:
                logger.warning("No accounts found matching karma criteria")
                return False
            
            # Sort by karma (highest first)
            valid_listings.sort(key=lambda x: x["karma"], reverse=True)
            
            selected_listing = valid_listings[0]
            logger.info(f"Selected account with {selected_listing['karma']} karma, price: {selected_listing['price']}")
            
            # Click the buy button for the selected listing
            buy_button = selected_listing["buy_button"]
            
            # Scroll and click
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", buy_button)
            time.sleep(0.5)
            
            logger.info("Clicking buy button...")
            if not self.retry_click(buy_button):
                logger.error("Failed to click buy button")
                return False
            
            # Wait 5 seconds as specified
            logger.info("Waiting 5 seconds for content to fully load...")
            time.sleep(5)
            
            return True
            
        except Exception as e:
            logger.error(f"Error finding account by karma: {str(e)}")
            self.save_debug_info("find_account_error")
            return False
    
    def apply_coupon_and_checkout(self):
        """Click showcoupon, apply coupon code, and fill out checkout information"""
        try:
            logger.info("Looking for coupon field...")
            
            # Click on showcoupon link
            try:
                showcoupon_link = self.wait.until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "showcoupon"))
                )
                logger.info("Found showcoupon link, clicking it...")
                self.click_with_retry(showcoupon_link)
                time.sleep(1)
            except TimeoutException:
                logger.warning("Showcoupon link not found, continuing without coupon")
            
            # Input coupon code if provided
            if self.coupon_code:
                try:
                    coupon_field = self.wait.until(
                        EC.presence_of_element_located((By.ID, "coupon_code"))
                    )
                    logger.info(f"Entering coupon code: {self.coupon_code}")
                    
                    coupon_field.clear()
                    for char in self.coupon_code:
                        coupon_field.send_keys(char)
                        time.sleep(random.uniform(0.03, 0.08))
                    
                    # Click apply coupon button
                    apply_button = self.driver.find_element(By.NAME, "apply_coupon")
                    self.click_with_retry(apply_button)
                    time.sleep(2)
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
                    for char in value:
                        field.send_keys(char)
                        time.sleep(random.uniform(0.03, 0.08))
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
        """Detect if captcha is present on the page"""
        captcha_indicators = [
            "g-recaptcha",
            "recaptcha",
            "h-captcha",
            "hcaptcha",
            "captcha"
        ]
        
        for indicator in captcha_indicators:
            try:
                captcha_elements = self.driver.find_elements(By.XPATH, 
                                                        f"//*[contains(@class, '{indicator}') or contains(@id, '{indicator}')]")
                if captcha_elements:
                    logger.warning(f"CAPTCHA detected on page ({indicator})")
                    return True
            except Exception:
                pass
        
        return False
    
    def handle_captcha(self):
        """Handle captcha by prompting user to solve it"""
        if self.detect_captcha():
            logger.warning("CAPTCHA detected - manual solving required")
            
            if not self.headless:
                logger.info("Please solve the CAPTCHA manually and press Enter in the console to continue...")
                input("Press Enter after solving the CAPTCHA...")
                return True
            else:
                logger.error("CAPTCHA detected in headless mode - cannot solve automatically")
                return False
        
        return True
    
    def complete_order(self):
        """Find and click the place_order button"""
        try:
            # Handle captcha if present
            if not self.handle_captcha():
                logger.error("Failed to handle captcha")
                return False
            
            logger.info("Looking for place_order button...")
            
            place_order_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "place_order"))
            )
            
            logger.info("Found place_order button, clicking it...")
            
            # Scroll to button
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", place_order_button)
            time.sleep(1)
            
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
        """Full purchase flow for a Reddit account"""
        try:
            # Step 1: Navigate to accounts page
            if not self.navigate_to_acc_page():
                logger.error("Failed to navigate to Reddit accounts page")
                return False
            
            # Step 2: Find and click account with desired karma
            if not self.find_and_click_account_by_karma():
                logger.error("Failed to find and select an account")
                return False
            
            # Step 3: Apply coupon and fill checkout info
            if not self.apply_coupon_and_checkout():
                logger.error("Failed to apply coupon and fill checkout form")
                return False
            
            # Step 4: Complete the order
            if not self.complete_order():
                logger.error("Failed to complete the order")
                return False
            
            logger.info("Successfully purchased Reddit account!")
            return True
            
        except Exception as e:
            logger.error(f"Error in purchase process: {str(e)}")
            self.save_debug_info("purchase_process_error")
            return False
    
    def monitor_and_purchase(self):
        try:
            self.start_browser()
        
            if self.user_email and self.user_password:
                if not self.login_if_needed():
                    logger.error("Failed to log in, aborting")
                    return
                else:
                    logger.info("Login successful")
            
            logger.info("Starting Reddit account purchase process")
            
            if self.purchase_reddit_account():
                logger.info("Successfully completed Reddit account purchase!")
            else:
                logger.error("Failed to purchase Reddit account")
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
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
            "target_url": "https://redaccs.com/#acc",
            "refresh_interval": 30,
            "min_karma": 1000,
            "max_price": 50.0,
            "headless": False,
            "test_mode": True,
            "debug_mode": True,
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
        print("Edit this file with your information, then run the script again.")
        exit(1)
    
    bot = RedditAccountSniperBot(config_file)
    bot.monitor_and_purchase()