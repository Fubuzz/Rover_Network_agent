#!/usr/bin/env python3
"""
LinkedIn Profile Scraper and Summarizer

A production-ready tool that scrapes LinkedIn profiles and generates
executive summaries using Claude API.
"""

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import undetected_chromedriver as uc
from anthropic import Anthropic
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from improved_extraction import (
    extract_experience_improved,
    extract_education_improved,
    extract_skills_improved,
    extract_certifications_improved
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class ProfileData:
    """Structured storage for LinkedIn profile data."""
    name: str = ""
    headline: str = ""
    about: str = ""
    location: str = ""
    experience: List[Dict[str, str]] = field(default_factory=list)
    education: List[Dict[str, str]] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    certifications: List[Dict[str, str]] = field(default_factory=list)


class LinkedInScraper:
    """
    Automated LinkedIn profile scraper with Claude API integration.

    Features:
    - Undetected Chrome browser automation
    - Manual login with 2FA support
    - Comprehensive profile data extraction
    - AI-powered executive summary generation
    """

    LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"

    def __init__(
        self,
        api_key: str,
        headless: bool = False,
        page_timeout: int = 30,
        element_timeout: int = 10,
        linkedin_email: Optional[str] = None,
        linkedin_password: Optional[str] = None,
        user_data_dir: Optional[str] = None,
    ):
        """
        Initialize the LinkedIn scraper.

        Args:
            api_key: Anthropic API key for Claude
            headless: Run browser in headless mode
            page_timeout: Page load timeout in seconds
            element_timeout: Element wait timeout in seconds
            linkedin_email: LinkedIn email for automated login (optional)
            linkedin_password: LinkedIn password for automated login (optional)
            user_data_dir: Chrome user data directory for session persistence (optional)
        """
        self.api_key = api_key
        self.headless = headless
        self.page_timeout = page_timeout
        self.element_timeout = element_timeout
        self.driver: Optional[uc.Chrome] = None
        self.anthropic_client = Anthropic(api_key=api_key)
        self.linkedin_email = linkedin_email
        self.linkedin_password = linkedin_password
        self.user_data_dir = user_data_dir or str(Path.home() / ".linkedin_scraper_chrome")

    def setup_driver(self) -> None:
        """Initialize undetected Chrome driver with appropriate options."""
        logger.info("Setting up Chrome driver...")

        options = uc.ChromeOptions()

        if self.headless:
            options.add_argument("--headless=new")
            logger.info("Running in headless mode")

        # Anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")

        # User agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Add user data directory for session persistence
        if self.user_data_dir:
            user_data_path = Path(self.user_data_dir)
            user_data_path.mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={user_data_path.absolute()}")
            logger.info(f"Using Chrome user data directory: {user_data_path.absolute()}")

        try:
            self.driver = uc.Chrome(options=options, version_main=None)
            self.driver.set_page_load_timeout(self.page_timeout)
            logger.info("Chrome driver initialized successfully")
        except WebDriverException as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise

    def is_logged_in(self) -> bool:
        """
        Check if user is already logged in to LinkedIn.

        Returns:
            True if logged in, False otherwise
        """
        if not self.driver:
            return False

        try:
            # Try navigating to LinkedIn feed or home page
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(3)

            # Check if we're on login page or feed
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()

            # If we're redirected to login, we're not logged in
            if "login" in current_url or "challenge" in current_url:
                return False

            # Check for feed indicators
            if "feed" in current_url or "mynetwork" in current_url:
                return True

            # Check for logged-in page elements
            logged_in_indicators = [
                "nav__button-secondary",
                "global-nav",
                "feed-container",
                "search-global-typeahead"
            ]

            for indicator in logged_in_indicators:
                try:
                    self.driver.find_element(By.CLASS_NAME, indicator)
                    logger.info("Already logged in to LinkedIn")
                    return True
                except NoSuchElementException:
                    continue

            return False
        except Exception as e:
            logger.debug(f"Error checking login status: {e}")
            return False

    def automated_login(self) -> bool:
        """
        Automatically log in to LinkedIn using credentials.
        Checks if already logged in first.

        Returns:
            True if login successful, False otherwise
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized. Call setup_driver() first.")

        # Check if already logged in
        if self.is_logged_in():
            logger.info("Session already active, skipping login")
            return True

        if not self.linkedin_email or not self.linkedin_password:
            logger.warning("No credentials provided, falling back to manual login")
            return self.manual_login()

        logger.info("Navigating to LinkedIn login page...")
        self.driver.get(self.LINKEDIN_LOGIN_URL)
        time.sleep(3)

        # Check again if we got redirected (already logged in)
        if self.is_logged_in():
            logger.info("Already logged in (redirected from login page)")
            return True

        try:
            # Find and fill email field
            logger.info("Entering email...")
            email_selectors = [
                "input#username",
                "input[name='session_key']",
                "input[type='text']",
                "#username"
            ]
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue

            if not email_field:
                logger.error("Could not find email field - may already be logged in")
                # Check one more time
                if self.is_logged_in():
                    return True
                return self.manual_login()

            email_field.clear()
            email_field.send_keys(self.linkedin_email)
            time.sleep(1)

            # Find and fill password field
            logger.info("Entering password...")
            password_selectors = [
                "input#password",
                "input[name='session_password']",
                "input[type='password']",
                "#password"
            ]
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if not password_field:
                logger.error("Could not find password field")
                return self.manual_login()

            password_field.clear()
            password_field.send_keys(self.linkedin_password)
            time.sleep(1)

            # Find and click login button
            logger.info("Clicking login button...")
            login_selectors = [
                "button[type='submit']",
                "button.btn-primary",
                "input[type='submit']",
                "button[data-litms-control-urn='login-submit']"
            ]
            login_button = None
            for selector in login_selectors:
                try:
                    login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue

            if not login_button:
                logger.error("Could not find login button")
                return self.manual_login()

            login_button.click()
            time.sleep(3)

            # Check for 2FA or verification challenge
            current_url = self.driver.current_url
            if "challenge" in current_url or "checkpoint" in current_url:
                logger.info("2FA/Verification required. Waiting for completion in browser...")
                print("\n" + "="*70)
                print("2FA/VERIFICATION REQUIRED")
                print("="*70)
                print("Please complete the verification in the browser window.")
                print("Waiting for verification to complete...")
                print("="*70)
                
                # Wait for verification to complete (max 2 minutes)
                max_wait = 120
                start_time = time.time()
                while time.time() - start_time < max_wait:
                    time.sleep(2)
                    current_url = self.driver.current_url
                    if "challenge" not in current_url and "checkpoint" not in current_url:
                        if self.is_logged_in():
                            logger.info("Verification completed successfully")
                            break
                else:
                    logger.warning("Verification timeout - proceeding anyway")

            # Verify login by checking for feed or profile elements
            try:
                WebDriverWait(self.driver, 15).until(
                    lambda d: "feed" in d.current_url or 
                             "mynetwork" in d.current_url or 
                             "in/" in d.current_url or
                             "linkedin.com/feed" in d.current_url
                )
                logger.info("Login verified successfully")
                return True
            except TimeoutException:
                logger.warning("Could not verify login automatically. Please verify manually.")
                return self.manual_login()

        except Exception as e:
            logger.error(f"Error during automated login: {e}")
            logger.info("Falling back to manual login...")
            return self.manual_login()

    def manual_login(self) -> bool:
        """
        Navigate to LinkedIn login and wait for manual user authentication.

        Returns:
            True if login successful, False otherwise
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized. Call setup_driver() first.")

        logger.info("Navigating to LinkedIn login page...")
        self.driver.get(self.LINKEDIN_LOGIN_URL)
        time.sleep(2)

        print("\n" + "="*70)
        print("MANUAL LOGIN REQUIRED")
        print("="*70)
        print("Please complete the following steps in the browser window:")
        print("1. Enter your LinkedIn email and password")
        print("2. Complete any 2FA/verification if prompted")
        print("3. Wait until you see your LinkedIn feed")
        print("="*70)
        print("\nWaiting for login to complete...")

        # Wait for login to complete by checking URL changes
        max_wait_time = 120  # 2 minutes max wait
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            current_url = self.driver.current_url
            # Check if we're logged in
            if ("feed" in current_url or 
                "mynetwork" in current_url or 
                "in/" in current_url and "login" not in current_url):
                logger.info("Login verified successfully")
                return True
            
            # Check if still on login page
            if "login" not in current_url and "challenge" not in current_url:
                # Might be logged in, verify
                if self.is_logged_in():
                    logger.info("Login verified successfully")
                    return True
            
            time.sleep(2)
        
        # Final check
        if self.is_logged_in():
            logger.info("Login verified successfully")
            return True
        
        logger.warning("Login timeout - proceeding anyway. Please verify you're logged in.")
        return True

    def navigate_to_profile(self, profile_url: str) -> bool:
        """
        Navigate to target LinkedIn profile and wait for it to fully load.

        Args:
            profile_url: Full LinkedIn profile URL

        Returns:
            True if navigation successful
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized")

        logger.info(f"Navigating to profile: {profile_url}")

        try:
            self.driver.get(profile_url)
            
            # Wait for page to start loading
            time.sleep(2)

            # Wait for profile main section to load
            try:
                WebDriverWait(self.driver, self.element_timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "main"))
                )
            except TimeoutException:
                # Try alternative wait conditions
                try:
                    WebDriverWait(self.driver, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except TimeoutException:
                    pass

            # Wait for profile content to be visible - try multiple selectors
            profile_loaded = False
            content_selectors = [
                "section[id*='experience']",
                "section[data-section='experience']",
                "h1",
                ".pv-text-details__left-panel",
                "div.profile-photo-edit__preview",
            ]
            
            for selector in content_selectors:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    profile_loaded = True
                    break
                except TimeoutException:
                    continue
            
            if not profile_loaded:
                logger.warning("Some profile elements may not have loaded, continuing anyway...")

            # Additional wait for dynamic content
            time.sleep(2)

            logger.info("Profile page loaded successfully")
            return True

        except TimeoutException:
            logger.error("Timeout waiting for profile page to load")
            return False
        except WebDriverException as e:
            logger.error(f"Error navigating to profile: {e}")
            return False

    def scrape_detailed_experience(self, base_profile_url: str) -> Optional[BeautifulSoup]:
        """
        Navigate to the detailed experience page to get ALL experience entries.

        Args:
            base_profile_url: Base LinkedIn profile URL

        Returns:
            BeautifulSoup object of the detailed experience page, or None if failed
        """
        if not self.driver:
            return None

        # Construct detailed experience URL
        experience_url = base_profile_url.rstrip('/') + '/details/experience/'
        logger.info(f"Navigating to detailed experience page: {experience_url}")

        try:
            self.driver.get(experience_url)
            time.sleep(3)

            # Wait for experience content to load
            WebDriverWait(self.driver, self.element_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )

            # Scroll to load all content
            logger.info("Scrolling to load all experience entries...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            for _ in range(5):  # Scroll a few times to load everything
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            logger.info("Successfully loaded detailed experience page")
            return BeautifulSoup(self.driver.page_source, 'lxml')

        except Exception as e:
            logger.warning(f"Could not load detailed experience page: {e}")
            return None

    def scrape_detailed_skills(self, base_profile_url: str) -> Optional[BeautifulSoup]:
        """
        Navigate to the detailed skills page to get ALL skills.

        Args:
            base_profile_url: Base LinkedIn profile URL

        Returns:
            BeautifulSoup object of the detailed skills page, or None if failed
        """
        if not self.driver:
            return None

        # Construct detailed skills URL
        skills_url = base_profile_url.rstrip('/') + '/details/skills/'
        logger.info(f"Navigating to detailed skills page: {skills_url}")

        try:
            self.driver.get(skills_url)
            time.sleep(3)

            # Wait for skills content to load
            WebDriverWait(self.driver, self.element_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )

            # Scroll to load all content
            logger.info("Scrolling to load all skills...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            for _ in range(3):  # Scroll a few times
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            logger.info("Successfully loaded detailed skills page")
            return BeautifulSoup(self.driver.page_source, 'lxml')

        except Exception as e:
            logger.warning(f"Could not load detailed skills page: {e}")
            return None

    def scroll_to_load_content(self) -> None:
        """Scroll through the entire profile to load all lazy-loaded sections and expand all content."""
        if not self.driver:
            return

        logger.info("Scrolling through profile to load all content...")

        # First, try to click all "Show more" buttons to expand sections
        try:
            show_more_selectors = [
                "button[aria-label*='Show more']",
                "button[aria-label*='show more']",
                "button:contains('Show more')",
                "span.show-more-less-text__text--more",
                "button.inline-show-more-text__button",
            ]
            
            for selector in show_more_selectors:
                try:
                    # Use JavaScript to find and click all "Show more" buttons
                    self.driver.execute_script("""
                        var buttons = document.querySelectorAll('button[aria-label*="Show more"], button[aria-label*="show more"], button.inline-show-more-text__button, span.show-more-less-text__text--more');
                        buttons.forEach(function(btn) {
                            if (btn.offsetParent !== null) { // Check if visible
                                btn.click();
                            }
                        });
                    """)
                    time.sleep(1)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Could not click all 'Show more' buttons: {e}")

        # Get initial height
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        scroll_attempts = 0
        max_attempts = 15  # Increased attempts

        while scroll_attempts < max_attempts:
            # Scroll down gradually
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Try clicking "Show more" buttons again as we scroll
            try:
                self.driver.execute_script("""
                    var buttons = document.querySelectorAll('button[aria-label*="Show more"], button[aria-label*="show more"], button.inline-show-more-text__button');
                    buttons.forEach(function(btn) {
                        if (btn.offsetParent !== null) {
                            btn.click();
                        }
                    });
                """)
            except Exception:
                pass

            # Calculate new height
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                # Try scrolling in smaller increments to trigger lazy loads
                for i in range(3):
                    self.driver.execute_script(f"window.scrollBy(0, {500 * (i + 1)});")
                    time.sleep(1)
                    # Check for new content
                    current_height = self.driver.execute_script("return document.body.scrollHeight")
                    if current_height > new_height:
                        new_height = current_height
                        break
                
                if new_height == last_height:
                    break

            last_height = new_height
            scroll_attempts += 1

        # Scroll back to top slowly to ensure everything is loaded
        self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
        time.sleep(2)

        logger.info("Finished loading all content")

    def extract_text_safe(self, element, selector: str, attribute: str = "text") -> str:
        """
        Safely extract text from an element.

        Args:
            element: BeautifulSoup element to search within
            selector: CSS selector
            attribute: 'text' for text content, or attribute name

        Returns:
            Extracted text or empty string
        """
        try:
            found = element.select_one(selector)
            if not found:
                return ""

            if attribute == "text":
                return found.get_text(strip=True)
            else:
                return found.get(attribute, "")
        except Exception:
            return ""

    def extract_with_selenium(self, selectors: List[str], timeout: int = 5) -> str:
        """
        Try to extract text using Selenium with multiple selector fallbacks.

        Args:
            selectors: List of CSS selectors to try
            timeout: Timeout for each selector attempt

        Returns:
            Extracted text or empty string
        """
        if not self.driver:
            return ""

        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                text = element.text.strip()
                if text:
                    return text
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception:
                continue
        return ""

    def extract_profile_data(self) -> ProfileData:
        """
        Extract all relevant data from the loaded LinkedIn profile.

        Returns:
            ProfileData object with extracted information
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized")

        logger.info("Extracting profile data...")

        profile = ProfileData()
        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        # Save HTML for debugging (only when DEBUG_SCRAPER env is set)
        if os.getenv("DEBUG_SCRAPER"):
            debug_html_path = Path("debug_profile.html")
            with open(debug_html_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            logger.info(f"Saved HTML for debugging to {debug_html_path}")

        # Extract name with multiple fallback selectors
        try:
            name_selectors = [
                "h1.text-heading-xlarge",
                "h1[class*='text-heading-xlarge']",
                "h1.top-card-layout__title",
                "h1.pv-text-details__left-panel h1",
                "h1.break-words",
                "h1[data-anonymize='person-name']",
                "h1"
            ]
            for selector in name_selectors:
                profile.name = self.extract_text_safe(soup, selector)
                if profile.name:
                    logger.info(f"Found name using selector '{selector}': {profile.name}")
                    break
            
            # Fallback to Selenium if BeautifulSoup failed
            if not profile.name:
                logger.info("Trying Selenium fallback for name extraction...")
                profile.name = self.extract_with_selenium(name_selectors)
                if profile.name:
                    logger.info(f"Found name using Selenium: {profile.name}")
            
            # Final fallback: try to extract from page title or URL
            if not profile.name:
                try:
                    page_title = self.driver.title
                    # LinkedIn titles are usually "Name | LinkedIn"
                    if "|" in page_title:
                        profile.name = page_title.split("|")[0].strip()
                        logger.info(f"Extracted name from page title: {profile.name}")
                    else:
                        # Try to extract from URL
                        current_url = self.driver.current_url
                        if "/in/" in current_url:
                            # URL format: linkedin.com/in/name-slug/
                            url_part = current_url.split("/in/")[1].split("/")[0]
                            # Convert slug to readable name (basic attempt)
                            profile.name = url_part.replace("-", " ").title()
                            logger.info(f"Extracted name from URL slug: {profile.name}")
                except Exception as e:
                    logger.warning(f"Could not extract name from fallback methods: {e}")
            
            if not profile.name:
                logger.warning("Could not extract name with any method")
        except Exception as e:
            logger.warning(f"Could not extract name: {e}")

        # Extract headline with multiple fallback selectors
        try:
            headline_selectors = [
                "div.text-body-medium",
                "div[class*='text-body-medium']",
                "div.top-card-layout__headline",
                "div.pv-text-details__left-panel div.text-body-medium",
                "div.break-words.text-body-medium",
                "div.text-body-medium.break-words"
            ]
            for selector in headline_selectors:
                profile.headline = self.extract_text_safe(soup, selector)
                if profile.headline:
                    logger.info(f"Found headline using selector '{selector}': {profile.headline[:50]}...")
                    break
            if not profile.headline:
                logger.warning("Could not extract headline with any selector")
        except Exception as e:
            logger.warning(f"Could not extract headline: {e}")

        # Extract location with multiple fallback selectors
        try:
            location_selectors = [
                "span.text-body-small.inline",
                "span[class*='text-body-small'][class*='inline']",
                "div.top-card-layout__first-subline span",
                "span.text-body-small",
                "div.pv-text-details__left-panel span.text-body-small"
            ]
            for selector in location_selectors:
                profile.location = self.extract_text_safe(soup, selector)
                if profile.location:
                    logger.info(f"Found location using selector '{selector}': {profile.location}")
                    break
            if not profile.location:
                logger.warning("Could not extract location with any selector")
        except Exception as e:
            logger.warning(f"Could not extract location: {e}")

        # Extract About section
        try:
            about_section = soup.find("section", {"data-section": "summary"}) or \
                          soup.find("section", class_=re.compile(".*summary.*", re.I))

            if about_section:
                # Look for the about text in various possible locations
                about_text = self.extract_text_safe(about_section, "div.display-flex.ph5.pv3") or \
                           self.extract_text_safe(about_section, "div.inline-show-more-text") or \
                           self.extract_text_safe(about_section, "span[aria-hidden='true']")

                if about_text:
                    profile.about = about_text
                    logger.info(f"Found about section: {len(about_text)} characters")
        except Exception as e:
            logger.warning(f"Could not extract about section: {e}")

        # Extract Experience using improved method
        try:
            logger.info("Extracting experience...")
            profile.experience = extract_experience_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract experience: {e}")

        # Extract Education using improved method
        try:
            logger.info("Extracting education...")
            profile.education = extract_education_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract education: {e}")

        # Extract Skills using improved method
        try:
            logger.info("Extracting skills...")
            profile.skills = extract_skills_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract skills: {e}")

        # Extract Certifications using improved method
        try:
            logger.info("Extracting certifications...")
            profile.certifications = extract_certifications_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract certifications: {e}")

        return profile

    def _extract_experience_fallback(self, soup, profile: ProfileData) -> None:
        """Fallback method to extract experience using BeautifulSoup."""
        try:
            exp_section = soup.find("section", {"id": re.compile(".*experience.*", re.I)}) or \
                         soup.find("section", {"data-section": "experience"}) or \
                         soup.find("div", {"id": "experience"})

            if exp_section:
                experience_items = exp_section.find_all("li", class_=re.compile(".*pvs-list.*|.*pvs-entity.*", re.I))
                if not experience_items:
                    experience_items = exp_section.find_all("li", limit=10)

                for item in experience_items:
                    title = self.extract_text_safe(item, "span.t-bold span[aria-hidden='true']") or \
                           self.extract_text_safe(item, "h3 span[aria-hidden='true']") or ""
                    company = self.extract_text_safe(item, "span.t-normal span[aria-hidden='true']") or ""
                    duration = self.extract_text_safe(item, "span.t-black--light span[aria-hidden='true']") or ""
                    description = self.extract_text_safe(item, "div.inline-show-more-text span[aria-hidden='true']") or ""

                    if title or company:
                        profile.experience.append({
                            "title": title,
                            "company": company,
                            "duration": duration,
                            "description": description
                        })
        except Exception as e:
            logger.debug(f"Fallback experience extraction failed: {e}")

    def _extract_education_fallback(self, soup, profile: ProfileData) -> None:
        """Fallback method to extract education using BeautifulSoup."""
        try:
            edu_section = soup.find("section", {"id": re.compile(".*education.*", re.I)}) or \
                         soup.find("section", {"data-section": "education"}) or \
                         soup.find("div", {"id": "education"})

            if edu_section:
                education_items = edu_section.find_all("li", class_=re.compile(".*pvs-list.*|.*pvs-entity.*", re.I))
                if not education_items:
                    education_items = edu_section.find_all("li", limit=10)

                for item in education_items:
                    school = self.extract_text_safe(item, "span.t-bold span[aria-hidden='true']") or \
                           self.extract_text_safe(item, "h3 span[aria-hidden='true']") or ""
                    degree = self.extract_text_safe(item, "span.t-normal span[aria-hidden='true']") or ""
                    duration = self.extract_text_safe(item, "span.t-black--light span[aria-hidden='true']") or ""

                    if school:
                        profile.education.append({
                            "school": school,
                            "degree": degree,
                            "duration": duration
                        })
        except Exception as e:
            logger.debug(f"Fallback education extraction failed: {e}")

    def generate_summary(self, profile: ProfileData) -> str:
        """
        Generate executive summary using Claude API.

        Args:
            profile: ProfileData object with extracted information

        Returns:
            Generated executive summary text
        """
        logger.info("Generating comprehensive executive summary with Claude API...")

        # Prepare ALL profile data for Claude - comprehensive view
        experience_text = "\n".join([
            f"- {exp['title']} at {exp['company']} ({exp['duration']})"
            + (f"\n  Description: {exp['description'][:200]}..." if exp['description'] and len(exp['description']) > 200
               else f"\n  {exp['description']}" if exp['description'] else "")
            for exp in profile.experience  # ALL experiences with years
        ])

        education_text = "\n".join([
            f"- {edu['degree']} from {edu['school']} ({edu['duration'] if edu['duration'] else 'Dates not specified'})"
            for edu in profile.education
        ])

        skills_text = ", ".join(profile.skills)  # ALL skills

        certifications_text = "\n".join([
            f"- {cert['name']} - {cert['issuer']} ({cert['date'] if cert['date'] else 'Date not specified'})"
            for cert in profile.certifications
        ])

        prompt = f"""Analyze this comprehensive LinkedIn profile data and create a detailed executive summary (4-5 paragraphs) suitable for a recruiter, hiring manager, or business partner.

PROFILE OVERVIEW:
━━━━━━━━━━━━━━━━
Name: {profile.name}
Headline: {profile.headline}
Location: {profile.location}
Total Roles: {len(profile.experience)}
Total Skills: {len(profile.skills)}
Education Background: {len(profile.education)} institutions

PROFESSIONAL SUMMARY:
━━━━━━━━━━━━━━━━
{profile.about}

COMPLETE WORK EXPERIENCE (with years/durations):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{experience_text}

EDUCATION (with years):
━━━━━━━━━━━━━━━━━━━━
{education_text}

COMPLETE SKILLS INVENTORY:
━━━━━━━━━━━━━━━━━━━━━━
{skills_text}

CERTIFICATIONS & LICENSES:
━━━━━━━━━━━━━━━━━━━━━━━━
{certifications_text}

Based on this COMPLETE profile information, create a comprehensive executive summary that:

1. **Current Position & Expertise**: Describe their current role, years of experience, and primary areas of expertise
2. **Career Progression**: Highlight the trajectory of their career, noting key transitions and growth (mentioning specific durations/years)
3. **Core Competencies**: Detail their technical and professional skills, emphasizing breadth and depth
4. **Educational Foundation**: Mention relevant degrees, institutions, and years
5. **Notable Achievements**: Call out any standout accomplishments, certifications, or unique qualifications

Write 4-5 substantive paragraphs that give a complete picture of this professional's background, emphasizing specific time periods and durations to show longevity and commitment. Be specific about years of experience and career timeline."""

        try:
            # Try configured model, fallback to stable version
            model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
            try:
                message = self.anthropic_client.messages.create(
                    model=model_name,
                    max_tokens=1500,
                    temperature=0.7,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
            except Exception as e:
                # Fallback to stable model version
                if "404" in str(e) or "not_found" in str(e).lower():
                    logger.warning(f"Model {model_name} not found, trying fallback model...")
                    model_name = "claude-sonnet-4-20250514"
                    message = self.anthropic_client.messages.create(
                        model=model_name,
                        max_tokens=1500,
                        temperature=0.7,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    )
                else:
                    raise

            summary = message.content[0].text
            logger.info("Summary generated successfully")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary with Claude API: {e}")
            return self._generate_fallback_summary(profile)

    def _generate_fallback_summary(self, profile: ProfileData) -> str:
        """Generate a basic fallback summary if API fails."""
        summary_parts = [
            f"PROFILE SUMMARY: {profile.name}",
            f"\nHeadline: {profile.headline}",
            f"Location: {profile.location}",
        ]

        if profile.about:
            summary_parts.append(f"\nAbout:\n{profile.about}")

        if profile.experience:
            summary_parts.append("\nRecent Experience:")
            for exp in profile.experience[:3]:
                summary_parts.append(f"- {exp['title']} at {exp['company']}")

        if profile.skills:
            summary_parts.append(f"\nKey Skills: {', '.join(profile.skills[:10])}")

        return "\n".join(summary_parts)

    def save_summary(self, profile: ProfileData, summary: str, output_dir: Path) -> Path:
        """
        Save the generated summary to a comprehensively formatted text file.

        Args:
            profile: ProfileData object
            summary: Generated summary text
            output_dir: Directory to save the file

        Returns:
            Path to the saved file
        """
        # Create safe filename from name
        name_parts = profile.name.lower().split()
        if len(name_parts) >= 2:
            filename = f"{name_parts[0]}_{name_parts[-1]}_linkedin_summary.txt"
        else:
            filename = f"{profile.name.lower().replace(' ', '_')}_linkedin_summary.txt"

        # Remove any invalid filename characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        output_path = output_dir / filename

        # Prepare comprehensive, well-structured output
        output_content = [
            "="*80,
            "LINKEDIN PROFILE - COMPREHENSIVE SUMMARY",
            "="*80,
            f"\nFull Name:     {profile.name}",
            f"Headline:      {profile.headline}",
            f"Location:      {profile.location}",
            f"Total Roles:   {len(profile.experience)}",
            f"Total Skills:  {len(profile.skills)}",
            f"Education:     {len(profile.education)} institutions",
            "\n" + "="*80,
            "AI-GENERATED EXECUTIVE SUMMARY",
            "="*80,
            f"\n{summary}",
        ]

        # ABOUT SECTION
        if profile.about:
            output_content.extend([
                "\n" + "="*80,
                "ABOUT / PROFESSIONAL SUMMARY",
                "="*80,
                f"\n{profile.about}",
            ])

        # EXPERIENCE SECTION - Comprehensive with all details
        if profile.experience:
            output_content.extend([
                "\n" + "="*80,
                f"PROFESSIONAL EXPERIENCE ({len(profile.experience)} Roles)",
                "="*80,
            ])

            for i, exp in enumerate(profile.experience, 1):
                output_content.extend([
                    f"\n{'─'*80}",
                    f"[{i}] {exp['title']}",
                    f"{'─'*80}",
                ])

                if exp['company']:
                    output_content.append(f"Company:      {exp['company']}")

                if exp['duration']:
                    output_content.append(f"Duration:     {exp['duration']}")

                if exp['description']:
                    output_content.extend([
                        f"\nResponsibilities & Achievements:",
                        f"{exp['description']}",
                    ])

                output_content.append("")  # Blank line between entries

        # EDUCATION SECTION - With all years
        if profile.education:
            output_content.extend([
                "\n" + "="*80,
                f"EDUCATION ({len(profile.education)} Institutions)",
                "="*80,
            ])

            for i, edu in enumerate(profile.education, 1):
                output_content.extend([
                    f"\n{'─'*80}",
                    f"[{i}] {edu['school']}",
                    f"{'─'*80}",
                ])

                if edu['degree']:
                    output_content.append(f"Degree:       {edu['degree']}")

                if edu['duration']:
                    output_content.append(f"Years:        {edu['duration']}")

                output_content.append("")  # Blank line

        # SKILLS SECTION - ALL skills in organized format
        if profile.skills:
            output_content.extend([
                "\n" + "="*80,
                f"SKILLS & COMPETENCIES ({len(profile.skills)} Total)",
                "="*80,
                "",
            ])

            # Format skills in columns for better readability
            skills_per_line = 3
            for i in range(0, len(profile.skills), skills_per_line):
                skill_batch = profile.skills[i:i+skills_per_line]
                numbered_skills = [f"{i+j+1}. {skill}" for j, skill in enumerate(skill_batch)]
                output_content.append("  " + " | ".join(f"{s:<25}" for s in numbered_skills))

        # CERTIFICATIONS SECTION
        if profile.certifications:
            output_content.extend([
                "\n" + "="*80,
                f"LICENSES & CERTIFICATIONS ({len(profile.certifications)} Total)",
                "="*80,
            ])

            for i, cert in enumerate(profile.certifications, 1):
                output_content.extend([
                    f"\n[{i}] {cert['name']}",
                ])

                if cert['issuer']:
                    output_content.append(f"    Issued by: {cert['issuer']}")

                if cert['date']:
                    output_content.append(f"    Date: {cert['date']}")

        # FOOTER
        output_content.extend([
            "\n" + "="*80,
            "END OF PROFILE SUMMARY",
            "="*80,
            f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Profile: {profile.name}",
            f"Powered by Claude AI (Anthropic)",
            "="*80,
        ])

        # Write to file
        output_path.write_text("\n".join(output_content), encoding='utf-8')
        logger.info(f"Comprehensive summary saved to: {output_path}")

        return output_path

    def cleanup(self) -> None:
        """Clean up resources and close the browser."""
        if self.driver:
            logger.info("Closing browser...")
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")
            finally:
                self.driver = None

    def scrape_profile_to_dict(self, profile_url: str) -> Optional[Dict]:
        """
        Scrape a LinkedIn profile and return structured data as a dict.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            Dict with profile data + AI summary, or None if failed
        """
        try:
            self.setup_driver()
            if not self.automated_login():
                logger.error("Login failed")
                return None

            if not self.navigate_to_profile(profile_url):
                logger.error("Failed to load profile")
                return None

            time.sleep(2)
            self.scroll_to_load_content()
            profile_data = self.extract_profile_data()

            if not profile_data.name:
                logger.error("Could not extract profile name")
                return None

            # Get detailed experience
            detailed_exp_soup = self.scrape_detailed_experience(profile_url)
            if detailed_exp_soup:
                detailed_exp = extract_experience_improved(detailed_exp_soup)
                if detailed_exp and len(detailed_exp) >= len(profile_data.experience):
                    profile_data.experience = detailed_exp

            # Get detailed skills
            detailed_skills_soup = self.scrape_detailed_skills(profile_url)
            if detailed_skills_soup:
                detailed_skills = extract_skills_improved(detailed_skills_soup)
                if detailed_skills and len(detailed_skills) >= len(profile_data.skills):
                    profile_data.skills = detailed_skills

            summary = self.generate_summary(profile_data)

            return {
                "name": profile_data.name,
                "headline": profile_data.headline,
                "location": profile_data.location,
                "about": profile_data.about,
                "experience": profile_data.experience,
                "education": profile_data.education,
                "skills": profile_data.skills,
                "certifications": profile_data.certifications,
                "summary": summary,
                "profile_url": profile_url,
                "scraped_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            }

        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}", exc_info=True)
            return None
        finally:
            self.cleanup()

    def scrape_profile(self, profile_url: str, output_dir: Path) -> Optional[Path]:
        """
        Main method to scrape a LinkedIn profile and generate summary.

        Args:
            profile_url: LinkedIn profile URL
            output_dir: Directory to save output

        Returns:
            Path to saved summary file, or None if failed
        """
        try:
            # Setup
            self.setup_driver()

            # Login (automated if credentials provided, otherwise manual)
            if not self.automated_login():
                logger.error("Login failed")
                return None

            # Navigate to profile
            logger.info("Waiting for profile page to load...")
            if not self.navigate_to_profile(profile_url):
                logger.error("Failed to load profile")
                return None

            # Wait a bit more for dynamic content
            time.sleep(2)

            # Load all content automatically
            logger.info("Loading all profile content...")
            self.scroll_to_load_content()

            # Extract basic profile data first
            profile_data = self.extract_profile_data()

            if not profile_data.name:
                logger.error("Could not extract profile name. Scraping may have failed.")
                return None

            # Navigate to detailed experience page to get ALL experiences
            logger.info("Fetching detailed experience data...")
            detailed_experience_soup = self.scrape_detailed_experience(profile_url)
            if detailed_experience_soup:
                # Extract from detailed page (overwrites basic extraction)
                detailed_experience = extract_experience_improved(detailed_experience_soup)
                if detailed_experience and len(detailed_experience) > len(profile_data.experience):
                    logger.info(f"Detailed experience page yielded {len(detailed_experience)} entries (vs {len(profile_data.experience)} from main page)")
                    profile_data.experience = detailed_experience
                elif detailed_experience:
                    logger.info(f"Using detailed experience data: {len(detailed_experience)} entries")
                    profile_data.experience = detailed_experience

            # Navigate to detailed skills page to get ALL skills
            logger.info("Fetching detailed skills data...")
            detailed_skills_soup = self.scrape_detailed_skills(profile_url)
            if detailed_skills_soup:
                # Extract from detailed page (overwrites basic extraction)
                detailed_skills = extract_skills_improved(detailed_skills_soup)
                if detailed_skills and len(detailed_skills) > len(profile_data.skills):
                    logger.info(f"Detailed skills page yielded {len(detailed_skills)} skills (vs {len(profile_data.skills)} from main page)")
                    profile_data.skills = detailed_skills
                elif detailed_skills:
                    logger.info(f"Using detailed skills data: {len(detailed_skills)} skills")
                    profile_data.skills = detailed_skills

            logger.info(f"Final profile data: {len(profile_data.experience)} experiences, {len(profile_data.skills)} skills")

            # Generate summary
            summary = self.generate_summary(profile_data)

            # Display summary
            print("\n" + "="*70)
            print("GENERATED SUMMARY")
            print("="*70)
            print(summary)
            print("="*70)

            # Save to file
            output_path = self.save_summary(profile_data, summary, output_dir)

            return output_path

        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}", exc_info=True)
            return None
        finally:
            self.cleanup()


def main() -> int:
    """Main entry point for the CLI."""
    import json as json_lib

    parser = argparse.ArgumentParser(
        description="LinkedIn Profile Scraper and Summarizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --url https://linkedin.com/in/satyanadella/
  %(prog)s --url https://linkedin.com/in/satyanadella/ --json
  %(prog)s --serve --port 8585
  %(prog)s  (interactive mode)
        """
    )

    parser.add_argument("--url", type=str, help="LinkedIn profile URL to scrape")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output structured JSON to stdout")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--output", "-o", type=Path, default=Path.cwd(), help="Output directory for summary file")
    parser.add_argument("--timeout", type=int, default=30, help="Page load timeout in seconds")
    parser.add_argument("--serve", action="store_true", help="Start as HTTP API server")
    parser.add_argument("--port", type=int, default=8585, help="Server port (default: 8585)")
    parser.add_argument("--debug", action="store_true", help="Save debug HTML files")

    args = parser.parse_args()

    if args.debug:
        os.environ["DEBUG_SCRAPER"] = "1"

    # Server mode
    if args.serve:
        from services.linkedin_scraper.server import start_server
        start_server(port=args.port)
        return 0

    # Get profile URL
    if args.url:
        profile_url = args.url.strip()
    else:
        print("\n" + "=" * 70)
        print("LinkedIn Profile Scraper")
        print("=" * 70)
        profile_url = input("\nEnter LinkedIn profile URL to scrape: ").strip()

    if not profile_url:
        logger.error("No URL provided")
        return 1

    if "linkedin.com/in/" not in profile_url:
        logger.error("Invalid LinkedIn profile URL. Must contain 'linkedin.com/in/'")
        return 1

    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not found. Set it in .env or environment.")
        return 1

    linkedin_email = os.getenv("LINKEDIN_EMAIL")
    linkedin_password = os.getenv("LINKEDIN_PASSWORD")
    user_data_dir = os.getenv("CHROME_USER_DATA_DIR")

    scraper = LinkedInScraper(
        api_key=api_key,
        headless=args.headless,
        page_timeout=args.timeout,
        linkedin_email=linkedin_email,
        linkedin_password=linkedin_password,
        user_data_dir=user_data_dir,
    )

    # JSON output mode
    if args.json_output:
        result = scraper.scrape_profile_to_dict(profile_url)
        if result:
            print(json_lib.dumps(result, indent=2, ensure_ascii=False))
            return 0
        else:
            print(json_lib.dumps({"error": "Failed to scrape profile"}))
            return 1

    # File output mode
    args.output.mkdir(parents=True, exist_ok=True)
    output_file = scraper.scrape_profile(profile_url, args.output)

    if output_file:
        print(f"\n✓ Success! Summary saved to: {output_file}")
        return 0
    else:
        print("\n✗ Failed to scrape profile")
        return 1


if __name__ == "__main__":
    sys.exit(main())
