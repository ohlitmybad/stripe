#!/usr/bin/env python3
"""
Selenium script to create accounts for new Stripe subscribers in MembershipWorks
"""

import os
import sys
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('account_creation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class StripeAccountCreator:
    def __init__(self):
        self.driver = None
        self.wait = None
        
        # Get environment variables
        self.subscriber_name = os.getenv('SUBSCRIBER_NAME')
        self.subscriber_email = os.getenv('SUBSCRIBER_EMAIL')
        self.timestamp = os.getenv('TIMESTAMP')
        self.source = os.getenv('SOURCE')
        
        # Platform credentials - using environment variables for security
        self.platform_username = os.getenv('PLATFORM_USERNAME')
        self.platform_password = os.getenv('PLATFORM_PASSWORD')
        
        # Validate required environment variables
        if not all([self.subscriber_name, self.subscriber_email, 
                   self.platform_username, self.platform_password]):
            logger.error("Missing required environment variables")
            raise ValueError("Missing required environment variables")
    
    def setup_driver(self):
        """Set up Chrome driver with options for GitHub Actions"""
        try:
            chrome_options = Options()
            # For GitHub Actions, we need headless mode
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1200,800")
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Install and set up ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 60)
            logger.info("Chrome driver set up successfully")
            
        except Exception as e:
            logger.error(f"Failed to set up Chrome driver: {str(e)}")
            raise
    
    def login_to_platform(self):
        """Login to MembershipWorks admin panel"""
        try:
            logger.info("Navigating to MembershipWorks admin panel")
            self.driver.get("https://membershipworks.com/admin/")
            
            # Wait for login form and fill credentials
            email_field = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@name='eml']"))
            )
            password_field = self.driver.find_element(By.NAME, "pwd")
            
            email_field.send_keys(self.platform_username)
            password_field.send_keys(self.platform_password)
            
            # Submit login form
            login_button = self.driver.find_element(By.CSS_SELECTOR, ".SFfrm button")
            login_button.click()
            
            # Maximize window after login
            self.driver.maximize_window()
            
            logger.info("Successfully logged into MembershipWorks")
            
        except TimeoutException:
            logger.error("Timeout during login process")
            self.take_screenshot("login_timeout")
            raise
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            self.take_screenshot("login_error")
            raise
    
    def create_user_account(self):
        """Create a new user account with the subscriber data using MembershipWorks workflow"""
        try:
            logger.info(f"Creating account for: {self.subscriber_name} ({self.subscriber_email})")
            
            # Navigate to Members section
            members_link = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Members')]"))
            )
            
            # Wait for overlays to disappear
            try:
                self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".loading, .overlay, .spinner")))
            except:
                pass
            
            # Click Members link
            self.driver.execute_script("arguments[0].scrollIntoView(true);", members_link)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", members_link)
            
            # Wait for the main content area to load
            self.wait.until(EC.presence_of_element_located((By.ID, "SFdekmnu")))
            
            # Wait for overlays to disappear again
            try:
                self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".loading, .overlay, .spinner")))
            except:
                pass
            
            # Click the "Add" button in the nav bar
            add_button = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//nav[@id='SFdekmnu']/a[@role='button' and normalize-space(text())='Add']"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", add_button)
            self.driver.execute_script("arguments[0].click();", add_button)
            
            # Fill out the Add Member form with subscriber data
            name_field = self.wait.until(EC.presence_of_element_located((By.NAME, "nam")))
            email_field = self.wait.until(EC.presence_of_element_located((By.NAME, "eml")))
            
            name_field.send_keys(self.subscriber_name)
            email_field.send_keys(self.subscriber_email)
            
            # Click the 'Add Account' button
            add_account_btn = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[@id='SFdekadddlg']//button[normalize-space(text())='Add Account']"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", add_account_btn)
            self.driver.execute_script("arguments[0].click();", add_account_btn)
            
            logger.info("Account creation form submitted successfully")
            
        except TimeoutException:
            logger.error("Timeout during account creation")
            self.take_screenshot("creation_timeout")
            raise
        except Exception as e:
            logger.error(f"Account creation failed: {str(e)}")
            self.take_screenshot("creation_error")
            raise
    
    def setup_membership_billing(self):
        """Set up membership billing for the new account"""
        try:
            logger.info("Setting up membership billing")
            
            # Wait for the profile page to load
            self.wait.until(EC.presence_of_element_located((By.XPATH, "//a[normalize-space(text())='Profile' and @role='tab']")))
            
            # Click the 'Membership Billing' tab
            billing_tab = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//a[normalize-space(text())='Membership Billing' and @role='tab']"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", billing_tab)
            self.driver.execute_script("arguments[0].click();", billing_tab)
            
            # Select 'DataMB Pro' from the membership level dropdown
            membership_select = self.wait.until(EC.presence_of_element_located((By.NAME, "lvl")))
            select = Select(membership_select)
            select.select_by_visible_text("DataMB Pro")
            
            # Check 'Send new member welcome email'
            welcome_checkbox = self.wait.until(EC.presence_of_element_located((By.NAME, "_en")))
            if not welcome_checkbox.is_selected():
                self.driver.execute_script("arguments[0].click();", welcome_checkbox)
            
            # Click the 'Save' button in the Membership Billing section
            save_btn = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[@id='SFusrpaybtx']//button[normalize-space(text())='Save']"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", save_btn)
            self.driver.execute_script("arguments[0].click();", save_btn)
            
            logger.info("Membership billing setup completed")
            
        except Exception as e:
            logger.error(f"Membership billing setup failed: {str(e)}")
            self.take_screenshot("billing_error")
            raise
    
    def add_stripe_label(self):
        """Add the 'Stripe payments' label to the account"""
        try:
            logger.info("Adding Stripe payments label")
            
            # Click the 'Add Label' button
            add_label_btn = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[span[text()='Add Label']]"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", add_label_btn)
            self.driver.execute_script("arguments[0].click();", add_label_btn)
            
            # Click the 'Stripe payments' label in the label dialog
            stripe_label_btn = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[@id='SFusrlbldlg']//button[normalize-space(text())='Stripe payments']"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", stripe_label_btn)
            self.driver.execute_script("arguments[0].click();", stripe_label_btn)
            
            logger.info("Stripe payments label added successfully")
            
        except Exception as e:
            logger.error(f"Adding Stripe label failed: {str(e)}")
            self.take_screenshot("label_error")
            raise
    
    def take_screenshot(self, name):
        """Take a screenshot for debugging"""
        try:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshots/{name}_{timestamp}.png"
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
        except Exception as e:
            logger.error(f"Failed to take screenshot: {str(e)}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            logger.info("Driver closed")
    
    def run(self):
        """Main execution method"""
        try:
            logger.info("Starting MembershipWorks account creation process")
            logger.info(f"Subscriber: {self.subscriber_name}")
            logger.info(f"Email: {self.subscriber_email}")
            logger.info(f"Source: {self.source}")
            logger.info(f"Timestamp: {self.timestamp}")
            
            self.setup_driver()
            self.login_to_platform()
            self.create_user_account()
            self.setup_membership_billing()
            self.add_stripe_label()
            
            # Wait a moment before closing
            time.sleep(5)
            
            logger.info("Account creation completed successfully")
            self.take_screenshot("final_success")
            return True
            
        except Exception as e:
            logger.error(f"Account creation failed: {str(e)}")
            self.take_screenshot("final_error")
            return False
        finally:
            self.cleanup()

def main():
    """Main function"""
    creator = StripeAccountCreator()
    success = creator.run()
    
    if success:
        logger.info("Script completed successfully")
        sys.exit(0)
    else:
        logger.error("Script failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
