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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

# Import TwoCaptcha for automated CAPTCHA solving
try:
    from twocaptcha import TwoCaptcha
    CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    CAPTCHA_SOLVER_AVAILABLE = False
    logging.warning("TwoCaptcha module not found. To enable automated CAPTCHA solving, install it with: pip install 2captcha-python")

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
        
        # CAPTCHA solving configuration
        self.captcha_api_key = ""
        self.captcha_solver = None
        
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        else:
            logger.warning("No configuration file provided or file not found. Using default values.")
        
        # Initialize CAPTCHA solver if API key is provided
        if self.captcha_api_key and CAPTCHA_SOLVER_AVAILABLE:
            try:
                self.captcha_solver = TwoCaptcha(self.captcha_api_key)
                logger.info("CAPTCHA solver initialized with API key")
            except Exception as e:
                logger.error(f"Failed to initialize CAPTCHA solver: {str(e)}")
        
        self.chrome_options = Options()
        if self.headless:
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
        self.chrome_options.add_argument("--blink-settings=imagesEnabled=false")  # Speed up by disabling images
        
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
        logger.info("Search keyword set to: %s", self.search_keyword)
        if self.max_price:
            logger.info("Maximum price set to: $%.2f", self.max_price)
        
        if self.captcha_api_key:
            if not CAPTCHA_SOLVER_AVAILABLE:
                logger.error("CAPTCHA API key provided but 2captcha-python package is not installed")
                logger.error("Please install it with: pip install 2captcha-python")
            else:
                try:
                    self.captcha_solver = TwoCaptcha(self.captcha_api_key)
                    logger.info("2Captcha solver initialized with API key")
                except Exception as e:
                    logger.error(f"Failed to initialize 2Captcha solver: {str(e)}")
        else:
            logger.warning("No CAPTCHA API key provided - automated CAPTCHA solving will not be available")
            logger.warning("Please add a 2Captcha API key to your config file")
    
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

            # Load CAPTCHA solver configuration
            self.captcha_api_key = config.get('captcha_api_key', "")
            
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
        self.short_wait = WebDriverWait(self.driver, 5)
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
        """Find account listing with 50x keyword and click the buy button"""
        try:
            logger.info(f"Searching for accounts with keyword: {self.search_keyword}...")
            
            # Force page elements to load
            self.force_page_load()
            
            # Find all table cells
            cells = self.driver.find_elements(By.TAG_NAME, "td")
            if not cells:
                logger.warning("No table cells found")
                return False
            
            logger.info(f"Found {len(cells)} table cells to search")
            
            matching_row = None
            
            # Search each TD for the keyword
            for cell in cells:
                try:
                    cell_text = cell.text.strip()
                    
                    # Check if cell contains the keyword
                    if self.search_keyword.lower() in cell_text.lower():
                        logger.info(f"Found matching cell with text: {cell_text}")
                        
                        # Get the parent row
                        matching_row = cell.find_element(By.XPATH, "./..")
                        break
                
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    logger.error(f"Error processing cell: {str(e)}")
            
            if not matching_row:
                logger.warning(f"No cells found containing keyword: {self.search_keyword}")
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
            
            # Wait 5 seconds as specified
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
        """Detect if captcha is present on the page"""
        captcha_indicators = [
            "g-recaptcha",
            "recaptcha",
            "h-captcha",
            "hcaptcha",
            "captcha"
        ]
        
        captcha_data = {}
        page_source = self.driver.page_source.lower()
        
        # Fast check in page source first
        for indicator in captcha_indicators:
            if indicator in page_source:
                logger.warning(f"CAPTCHA indicator found in page source: {indicator}")
                
                # Verify with DOM elements
                try:
                    captcha_elements = self.driver.find_elements(By.XPATH, 
                                                            f"//*[contains(@class, '{indicator}') or contains(@id, '{indicator}')]")
                    if captcha_elements:
                        logger.warning(f"CAPTCHA element confirmed on page ({indicator})")
                        
                        # Gather information about the CAPTCHA
                        if "g-recaptcha" in indicator or "recaptcha" in indicator:
                            captcha_data['type'] = 'recaptcha'
                            
                            # Look for site key
                            site_key_match = re.search(r'data-sitekey=["\']([^"\']+)["\']', page_source)
                            if site_key_match:
                                captcha_data['site_key'] = site_key_match.group(1)
                                
                        elif "hcaptcha" in indicator or "h-captcha" in indicator:
                            captcha_data['type'] = 'hcaptcha'
                            
                            # Look for site key
                            site_key_match = re.search(r'data-sitekey=["\']([^"\']+)["\']', page_source)
                            if site_key_match:
                                captcha_data['site_key'] = site_key_match.group(1)
                        
                        return True, captcha_data
                except Exception as e:
                    logger.error(f"Error analyzing CAPTCHA element: {str(e)}")
        
        return False, captcha_data
    
    def solve_recaptcha(self, site_key):
        """Solve reCAPTCHA using 2Captcha service with better error handling"""
        if not self.captcha_solver:
            logger.error("CAPTCHA solver not initialized")
            return None
            
        try:
            logger.info("Sending reCAPTCHA to 2Captcha for solving...")
            logger.info(f"Using site key: {site_key}")
            
            # Get the page URL
            page_url = self.driver.current_url
            
            # Add additional parameters to improve solving accuracy
            result = self.captcha_solver.recaptcha(
                sitekey=site_key,
                url=page_url,
                invisible=1,  # Try with invisible recaptcha option
                enterprise=0  # Set to 1 if it's an enterprise reCAPTCHA
            )
            
            if result.get('code') == 'OK':
                logger.info("2Captcha successfully solved the reCAPTCHA!")
                return result.get('token')
            else:
                logger.error(f"2Captcha failed to solve reCAPTCHA: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error communicating with 2Captcha service: {str(e)}")
            return None
    
    def solve_hcaptcha(self, site_key):
        """Solve hCaptcha using 2Captcha service with better error handling"""
        if not self.captcha_solver:
            logger.error("CAPTCHA solver not initialized")
            return None
            
        try:
            logger.info("Sending hCaptcha to 2Captcha for solving...")
            logger.info(f"Using site key: {site_key}")
            
            # Get the page URL
            page_url = self.driver.current_url
            
            result = self.captcha_solver.hcaptcha(
                sitekey=site_key,
                url=page_url
            )
            
            if result.get('code') == 'OK':
                logger.info("2Captcha successfully solved the hCaptcha!")
                return result.get('token')
            else:
                logger.error(f"2Captcha failed to solve hCaptcha: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error communicating with 2Captcha service: {str(e)}")
            return None
    
    def submit_captcha_solution(self, token, captcha_type):
        """Submit the CAPTCHA solution to the page"""
        if not token:
            return False
            
        try:
            if captcha_type == 'recaptcha':
                # Submit the solution for reCAPTCHA
                self.driver.execute_script(
                    "document.getElementById('g-recaptcha-response').innerHTML = arguments[0];", token)
                
                # Trigger the callback
                self.driver.execute_script(
                    "___grecaptcha_cfg.clients[0].callback(arguments[0]);", token)
                
            elif captcha_type == 'hcaptcha':
                # Submit the solution for hCaptcha
                self.driver.execute_script(
                    "document.querySelector('textarea[name=\"h-captcha-response\"]').innerHTML = arguments[0];", token)
                
                # Submit the form or trigger callback
                self.driver.execute_script(
                    "document.querySelector('form').submit();")
                
            # Wait for the CAPTCHA to process
            time.sleep(2)
            
            # Verify if CAPTCHA is no longer present
            is_captcha, _ = self.detect_captcha()
            if not is_captcha:
                logger.info("CAPTCHA successfully solved and submitted!")
                return True
            else:
                logger.warning("CAPTCHA solution was submitted but CAPTCHA still appears to be present")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting CAPTCHA solution: {str(e)}")
            return False
    
    def handle_captcha(self):
        """Handle captcha using 2Captcha service exclusively"""
        is_captcha, captcha_data = self.detect_captcha()
        
        if not is_captcha:
            return True
            
        logger.warning("CAPTCHA detected - using 2Captcha to solve automatically")
        
        # Check if we have the required components for automated solving
        if not CAPTCHA_SOLVER_AVAILABLE:
            logger.error("CAPTCHA detected but 2Captcha package is not installed")
            logger.error("Please run: pip install 2captcha-python")
            return False
            
        if not self.captcha_api_key:
            logger.error("CAPTCHA detected but no API key is configured")
            logger.error("Please add your 2Captcha API key to the config file")
            return False
        
        if not self.captcha_solver:
            logger.error("CAPTCHA solver not initialized despite API key being present")
            logger.error("This is likely an internal error - please check the logs")
            return False
        
        if 'type' not in captcha_data or 'site_key' not in captcha_data:
            logger.error("CAPTCHA detected but could not determine type or site key")
            logger.error("The CAPTCHA may be of an unsupported type")
            return False
        
        # Proceed with automated solving
        captcha_type = captcha_data['type']
        site_key = captcha_data['site_key']
        
        # Attempt to solve with retries
        max_solve_attempts = 3
        for attempt in range(1, max_solve_attempts + 1):
            logger.info(f"CAPTCHA solving attempt {attempt}/{max_solve_attempts}")
            
            token = None
            if captcha_type == 'recaptcha':
                token = self.solve_recaptcha(site_key)
            elif captcha_type == 'hcaptcha':
                token = self.solve_hcaptcha(site_key)
            else:
                logger.error(f"Unsupported CAPTCHA type: {captcha_type}")
                return False
                
            if not token:
                logger.error(f"Failed to get solution token from 2Captcha service (attempt {attempt})")
                if attempt < max_solve_attempts:
                    logger.info("Waiting 5 seconds before retrying...")
                    time.sleep(5)
                    continue
                else:
                    logger.error("Maximum solving attempts reached. Could not solve CAPTCHA automatically.")
                    return False
            
            # We have a token, attempt to submit it
            if self.submit_captcha_solution(token, captcha_type):
                logger.info("CAPTCHA solved successfully by 2Captcha!")
                return True
            else:
                logger.error(f"Failed to submit CAPTCHA solution (attempt {attempt})")
                if attempt < max_solve_attempts:
                    logger.info("Waiting 5 seconds before retrying...")
                    time.sleep(5)
                else:
                    logger.error("Maximum submission attempts reached. Could not apply CAPTCHA solution.")
                    return False
        
        # We should never reach here due to the returns above, but just in case
        return False
    
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
        """Full purchase flow for a Reddit account with explicit CAPTCHA handling"""
        try:
            # Verify 2Captcha is properly set up before starting
            if not self.captcha_api_key or not CAPTCHA_SOLVER_AVAILABLE:
                logger.error("Cannot proceed with purchase - 2Captcha is not properly configured")
                logger.error("Please install 2captcha-python and provide a valid API key")
                return False
            
            # Step 1: Navigate to accounts page
            if not self.navigate_to_acc_page():
                logger.error("Failed to navigate to Reddit accounts page")
                return False
            
            # Step 2: Find and click account with 50x keyword
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
            "target_url": "https://redaccs.com/shop/",
            "refresh_interval": 30,
            "min_karma": 1000,
            "max_price": 50.0,
            "headless": False,
            "test_mode": True,
            "debug_mode": True,
            "search_keyword": "50x",
            "coupon_code": "YOUR_COUPON_HERE",
            "captcha_api_key": "YOUR_2CAPTCHA_API_KEY",
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
        print("\nTo enable automated CAPTCHA solving:")
        print("1. Install the 2captcha module: pip install 2captcha-python")
        print("2. Get an API key from https://2captcha.com/")
        print("3. Add your API key to the config file")
        exit(1)

    
    
    bot = RedditAccountSniperBot(config_file)
    bot.run()