#!/usr/bin/env python3
"""
Selenium script to reactivate a cancelled PayPal member in MembershipWorks.

Flow:
  1. Login to MembershipWorks admin
  2. Navigate to Members → "Accounts on free membership" group
  3. Search for the username
  4. Open their profile → Membership Billing tab
  5. Switch from "Cancel Subscription" state to "DataMB Pro"
  6. Save

NOTE: Selectors are based on the existing create_stripe_member_account.py pattern.
      You will likely need to inspect and adjust some XPaths after a first test run.
"""

import os
import sys
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reactivation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MemberReactivator:
    def __init__(self):
        self.driver = None
        self.wait = None

        self.subscriber_username = os.getenv('SUBSCRIBER_USERNAME')
        self.platform_username = os.getenv('PLATFORM_USERNAME')
        self.platform_password = os.getenv('PLATFORM_PASSWORD')

        if not all([self.subscriber_username, self.platform_username, self.platform_password]):
            logger.error("Missing required environment variables")
            raise ValueError("Missing required environment variables")

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1200,800')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.wait = WebDriverWait(self.driver, 60)
        logger.info("Chrome driver set up successfully")

    def login(self):
        logger.info("Logging in to MembershipWorks admin")
        self.driver.get("https://membershipworks.com/admin/")

        email_field = self.wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='eml']"))
        )
        password_field = self.driver.find_element(By.NAME, "pwd")
        email_field.send_keys(self.platform_username)
        password_field.send_keys(self.platform_password)

        login_button = self.driver.find_element(By.CSS_SELECTOR, ".SFfrm button")
        login_button.click()

        self.driver.maximize_window()
        logger.info("Logged in successfully")

    def navigate_to_free_members_group(self):
        """Navigate to the 'Accounts on free membership' group in Members section."""
        logger.info("Navigating to Members section")

        members_link = self.wait.until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Members')]"))
        )
        self._wait_for_overlays()
        self.driver.execute_script("arguments[0].scrollIntoView(true);", members_link)
        time.sleep(1)
        self.driver.execute_script("arguments[0].click();", members_link)

        self.wait.until(EC.presence_of_element_located((By.ID, "SFdekmnu")))
        self._wait_for_overlays()

        logger.info("Clicking 'Accounts on free membership'")
        free_group = self.wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//td[@id='SFdbdnum_nf']/ancestor::tr[contains(@class,'SFclk')]"
            " | //tr[contains(@class, 'SFclk')][.//td[normalize-space()='Accounts on free membership']]"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", free_group)
        self.driver.execute_script("arguments[0].click();", free_group)

        self._wait_for_overlays()
        logger.info("Navigated to free membership group")

    def find_and_open_member(self):
        """Search for the username in the current member list and open their profile."""
        logger.info(f"Searching for username: {self.subscriber_username}")

        try:
            search_input = self.wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//input[@id='SFdektag' or @aria-label='Search keywords' or @placeholder='Search by name or keyword']"
            )))
            search_input.clear()
            search_input.send_keys(self.subscriber_username)
            search_btn = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[contains(@class,'SFfndtag')]//button[normalize-space(text())='Search']"
            )))
            self.driver.execute_script("arguments[0].click();", search_btn)
            time.sleep(2)  # Wait for live search results
        except TimeoutException:
            logger.warning("Could not find search input — trying to scroll and find member manually")

        member_link = self.wait.until(EC.element_to_be_clickable((
            By.XPATH,
            f"//div[contains(@class,'SFcrdnam') and normalize-space()='{self.subscriber_username}']"
            f" | //*[contains(text(), '{self.subscriber_username}')]"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", member_link)
        self.driver.execute_script("arguments[0].click();", member_link)

        # Wait for the profile page to load
        self.wait.until(EC.presence_of_element_located((
            By.XPATH, "//a[normalize-space(text())='Profile' and @role='tab']"
        )))
        logger.info(f"Opened profile for: {self.subscriber_username}")

    def reactivate_membership(self):
        """Go to Membership Billing tab and switch from cancelled state to DataMB Pro."""
        logger.info("Opening Membership Billing tab")

        billing_tab = self.wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//a[normalize-space(text())='Membership Billing' and @role='tab']"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", billing_tab)
        self.driver.execute_script("arguments[0].click();", billing_tab)

        self._wait_for_overlays()

        logger.info("Looking for Update / Reactivate button")
        try:
            update_btn = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[normalize-space(text())='Update'] | //a[normalize-space(text())='Update']"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", update_btn)
            self.driver.execute_script("arguments[0].click();", update_btn)
            self._wait_for_overlays()
        except TimeoutException:
            logger.warning("No 'Update' button found — membership level dropdown may be directly editable")

        logger.info("Selecting 'DataMB Pro' membership level")
        membership_select = self.wait.until(
            EC.presence_of_element_located((By.NAME, "lvl"))
        )
        select = Select(membership_select)
        select.select_by_visible_text("DataMB Pro")

        # Do not send welcome email during reactivation.
        try:
            welcome_checkbox = self.wait.until(EC.presence_of_element_located((By.NAME, "_en")))
            if welcome_checkbox.is_selected():
                self.driver.execute_script("arguments[0].click();", welcome_checkbox)
        except TimeoutException:
            logger.info("Welcome email checkbox not found — continuing")

        # Save
        save_btn = self.wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//div[@id='SFusrpaybtx']//button[normalize-space(text())='Save']"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", save_btn)
        self.driver.execute_script("arguments[0].click();", save_btn)

        self._wait_for_overlays()
        logger.info(f"Membership reactivated to DataMB Pro for: {self.subscriber_username}")

    def take_screenshot(self, name):
        try:
            os.makedirs("screenshots", exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"screenshots/{name}_{ts}.png"
            self.driver.save_screenshot(path)
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")

    def _wait_for_overlays(self):
        try:
            self.wait.until(EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, ".loading, .overlay, .spinner")
            ))
        except Exception:
            pass

    def cleanup(self):
        if self.driver:
            self.driver.quit()
            logger.info("Driver closed")

    def run(self):
        try:
            logger.info("=== Starting Member Reactivation ===")
            logger.info(f"Username: {self.subscriber_username}")

            self.setup_driver()
            self.login()
            self.navigate_to_free_members_group()
            self.find_and_open_member()
            self.reactivate_membership()

            time.sleep(3)
            self.take_screenshot("reactivation_success")
            logger.info("=== Reactivation Completed Successfully ===")
            return True

        except Exception as e:
            logger.error(f"Reactivation failed: {e}")
            self.take_screenshot("reactivation_error")
            return False
        finally:
            self.cleanup()


def main():
    creator = MemberReactivator()
    success = creator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
