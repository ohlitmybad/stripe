#!/usr/bin/env python3
"""
Selenium script to delete a member account in MembershipWorks.

Flow:
  1. Login to MembershipWorks admin
  2. Open Members (all members)
  3. Search for the username
  4. Open their profile
  5. Click Delete tab/action
  6. Click "Delete account & all associated data"

NOTE: Selectors are loosely based on create_stripe_member_account.py.
      Inspect and adjust XPaths after a first test run.
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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deletion.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

MW_ADMIN = "https://membershipworks.com/admin/"
MW_ALL = "https://membershipworks.com/admin/#all"


class MemberDeleter:
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
        self.wait_long = WebDriverWait(self.driver, 90)
        logger.info("Chrome driver set up successfully")

    def _ensure_all_accounts_scope(self):
        """
        Global search must use All Accounts, not a folder. Hash navigation to
        #all is more reliable than clicking #SFhdrall (often times out in CI/headless).
        """
        logger.info("Switching to All Accounts (global search)")
        self.driver.get(MW_ALL)
        time.sleep(2)
        try:
            self.wait_long.until(EC.presence_of_element_located((By.ID, "SFdektag")))
            logger.info("All Accounts: search field ready")
            return
        except TimeoutException:
            logger.warning("SFdektag not found after #all; trying Members then #all")

        try:
            members_link = WebDriverWait(self.driver, 45).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Members')]"))
            )
            self.driver.execute_script("arguments[0].click();", members_link)
            time.sleep(2)
            self.driver.get(MW_ALL)
            time.sleep(2)
            self.wait_long.until(EC.presence_of_element_located((By.ID, "SFdektag")))
            logger.info("All Accounts after Members + #all")
            return
        except TimeoutException:
            logger.warning("Members + #all did not expose search; trying nav link")

        try:
            all_accounts_link = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#SFhdrall a, li#SFhdrall a"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", all_accounts_link)
            self.driver.execute_script("arguments[0].click();", all_accounts_link)
            time.sleep(2)
            self.wait_long.until(EC.presence_of_element_located((By.ID, "SFdektag")))
            logger.info("All Accounts via header link click")
        except TimeoutException:
            logger.warning("Could not switch to All Accounts; continuing with current scope")

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
        self.wait.until(EC.presence_of_element_located((By.ID, "SFhdr")))
        logger.info("Logged in successfully")

    def navigate_to_members(self):
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
        self._ensure_all_accounts_scope()

    def find_and_open_member(self):
        """Search for the username across all members and open their profile."""
        logger.info(f"Searching for username: {self.subscriber_username}")

        # --- ADJUST THIS: search input on the members list ---
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
            time.sleep(2)
        except TimeoutException:
            logger.warning("Could not find search input — will attempt direct match")

        # Click matching member row
        member_link = self.wait.until(EC.element_to_be_clickable((
            By.XPATH,
            f"//div[contains(@class,'SFcrdnam') and normalize-space()='{self.subscriber_username}']"
            f" | //*[contains(text(), '{self.subscriber_username}')]"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", member_link)
        self.driver.execute_script("arguments[0].click();", member_link)

        # Confirm profile loaded
        self.wait.until(EC.presence_of_element_located((
            By.XPATH, "//a[normalize-space(text())='Profile' and @role='tab']"
        )))
        logger.info(f"Opened profile for: {self.subscriber_username}")

    def opened_member_matches_target(self):
        """Ensure opened profile name exactly matches the requested member name."""
        try:
            # Some profile loads render the name asynchronously; wait for non-empty text.
            self.wait.until(
                lambda d: len(
                    d.execute_script(
                        "const el=document.querySelector('#SFusrnam');"
                        "return el ? (el.textContent || '').trim() : '';"
                    )
                ) > 0
            )
            opened_name = self.driver.execute_script(
                "const direct=document.querySelector('#SFusrnam');"
                "if (direct && (direct.textContent || '').trim()) return direct.textContent.trim();"
                "const alt=document.querySelector('h1#SFusrnam, h1[id*=SFusrnam], h1');"
                "return alt ? (alt.textContent || '').trim() : '';"
            )
            expected_name = self.subscriber_username.strip()
            is_match = opened_name == expected_name
            if not is_match:
                logger.warning(
                    f"Opened member name mismatch. Expected '{expected_name}', got '{opened_name}'. Skipping deletion."
                )
            return is_match
        except Exception as e:
            logger.warning(f"Could not verify opened member name: {e}. Skipping deletion.")
            return False

    def close_profile(self):
        """Close member profile and return to members list."""
        try:
            close_btn = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//nav[@id='SFusradmmnu']//a[normalize-space(text())='Close']"
            )))
            self.driver.execute_script("arguments[0].click();", close_btn)
            self._wait_for_overlays()
        except Exception:
            self.driver.back()
            self._wait_for_overlays()

    def delete_account(self):
        """Delete account via top action menu."""
        logger.info("Clicking Delete action in top member menu")
        try:
            delete_action = self.wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//nav[@id='SFusradmmnu']//a[@role='button' and normalize-space(text())='Delete']"
            )))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", delete_action)
            self.driver.execute_script("arguments[0].click();", delete_action)
            self._wait_for_overlays()
        except TimeoutException:
            logger.error("Could not find Delete action")
            raise

        delete_all_btn = self.wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//div[contains(@class,'SFmnu')]//button[normalize-space(text())='Delete account & all associated data']"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", delete_all_btn)
        self.driver.execute_script("arguments[0].click();", delete_all_btn)
        self._wait_for_overlays()
        logger.info(f"Account deleted for: {self.subscriber_username}")

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
            logger.info("=== Starting Member Account Deletion ===")
            logger.info(f"Username: {self.subscriber_username}")

            self.setup_driver()
            self.login()
            self.navigate_to_members()
            self.find_and_open_member()
            if not self.opened_member_matches_target():
                self.close_profile()
                logger.info("Exited without deletion due to name mismatch")
                return True
            self.delete_account()

            time.sleep(3)
            self.take_screenshot("deletion_success")
            logger.info("=== Account Deletion Completed Successfully ===")
            return True

        except Exception as e:
            logger.error(f"Deletion failed: {e}")
            self.take_screenshot("deletion_error")
            return False
        finally:
            self.cleanup()


def main():
    deleter = MemberDeleter()
    success = deleter.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
