"""
LinkedIn Profile Scraper Service.

Adapted from the standalone LinkedIn Profile Scraper for use as a service
within the Rover Network Agent. Scrapes LinkedIn profiles using browser
automation and returns structured profile data.

Key differences from standalone version:
- No AI summary generation (the calling agent handles analysis)
- No file output (returns data directly)
- Defaults to headless mode
- No manual login fallback (requires credentials)
"""

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from services.linkedin_scraper.extraction import (
    extract_experience_improved,
    extract_education_improved,
    extract_skills_improved,
    extract_certifications_improved
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class LinkedInProfileData:
    """Structured storage for LinkedIn profile data."""
    name: str = ""
    headline: str = ""
    about: str = ""
    location: str = ""
    experience: List[Dict[str, str]] = field(default_factory=list)
    education: List[Dict[str, str]] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    certifications: List[Dict[str, str]] = field(default_factory=list)


class LinkedInScraperService:
    """
    LinkedIn profile scraper service using browser automation.

    Uses undetected-chromedriver to avoid bot detection and extracts
    comprehensive profile data including experience, education, skills,
    and certifications.
    """

    LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"

    def __init__(
        self,
        headless: bool = True,
        page_timeout: int = 30,
        element_timeout: int = 10,
        linkedin_email: Optional[str] = None,
        linkedin_password: Optional[str] = None,
        user_data_dir: Optional[str] = None,
    ):
        """
        Initialize the LinkedIn scraper service.

        Args:
            headless: Run browser in headless mode (default True for agent use)
            page_timeout: Page load timeout in seconds
            element_timeout: Element wait timeout in seconds
            linkedin_email: LinkedIn email for automated login
            linkedin_password: LinkedIn password for automated login
            user_data_dir: Chrome user data directory for session persistence
        """
        self.headless = headless
        self.page_timeout = page_timeout
        self.element_timeout = element_timeout
        self.driver = None
        self.linkedin_email = linkedin_email
        self.linkedin_password = linkedin_password
        self.user_data_dir = user_data_dir or str(Path.home() / ".linkedin_scraper_chrome")

    def setup_driver(self) -> None:
        """Initialize undetected Chrome driver with appropriate options."""
        import undetected_chromedriver as uc
        from selenium.common.exceptions import WebDriverException

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
        from selenium.common.exceptions import NoSuchElementException

        if not self.driver:
            return False

        try:
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(3)

            current_url = self.driver.current_url

            if "login" in current_url or "challenge" in current_url:
                return False

            if "feed" in current_url or "mynetwork" in current_url:
                return True

            logged_in_indicators = [
                "nav__button-secondary",
                "global-nav",
                "feed-container",
                "search-global-typeahead"
            ]

            from selenium.webdriver.common.by import By
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

        Returns:
            True if login successful, False otherwise
        """
        from selenium.common.exceptions import (
            NoSuchElementException,
            TimeoutException,
        )
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        if not self.driver:
            raise RuntimeError("Driver not initialized. Call setup_driver() first.")

        # Check if already logged in
        if self.is_logged_in():
            logger.info("Session already active, skipping login")
            return True

        if not self.linkedin_email or not self.linkedin_password:
            logger.error("No LinkedIn credentials provided")
            return False

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
                logger.error("Could not find email field")
                if self.is_logged_in():
                    return True
                return False

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
                return False

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
                return False

            login_button.click()
            time.sleep(3)

            # Check for 2FA or verification challenge
            current_url = self.driver.current_url
            if "challenge" in current_url or "checkpoint" in current_url:
                logger.warning("2FA/Verification challenge detected. Waiting briefly...")
                # In headless/agent mode, we can only wait for session-based auth
                max_wait = 30
                start_time = time.time()
                while time.time() - start_time < max_wait:
                    time.sleep(2)
                    current_url = self.driver.current_url
                    if "challenge" not in current_url and "checkpoint" not in current_url:
                        if self.is_logged_in():
                            logger.info("Verification completed")
                            return True
                logger.error(
                    "2FA/verification challenge could not be completed automatically. "
                    "Try setting CHROME_USER_DATA_DIR and logging in manually once first."
                )
                return False

            # Verify login
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
                logger.error("Could not verify login")
                return False

        except Exception as e:
            logger.error(f"Error during automated login: {e}")
            return False

    def navigate_to_profile(self, profile_url: str) -> bool:
        """
        Navigate to target LinkedIn profile and wait for it to fully load.

        Args:
            profile_url: Full LinkedIn profile URL

        Returns:
            True if navigation successful
        """
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        if not self.driver:
            raise RuntimeError("Driver not initialized")

        logger.info(f"Navigating to profile: {profile_url}")

        try:
            self.driver.get(profile_url)
            time.sleep(2)

            # Wait for profile main section to load
            try:
                WebDriverWait(self.driver, self.element_timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "main"))
                )
            except TimeoutException:
                try:
                    WebDriverWait(self.driver, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except TimeoutException:
                    pass

            # Wait for profile content to be visible
            content_selectors = [
                "section[id*='experience']",
                "section[data-section='experience']",
                "h1",
                ".pv-text-details__left-panel",
                "div.profile-photo-edit__preview",
            ]

            profile_loaded = False
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

            time.sleep(2)
            logger.info("Profile page loaded successfully")
            return True

        except TimeoutException:
            logger.error("Timeout waiting for profile page to load")
            return False
        except WebDriverException as e:
            logger.error(f"Error navigating to profile: {e}")
            return False

    def scrape_detailed_experience(self, base_profile_url: str):
        """
        Navigate to the detailed experience page to get ALL experience entries.

        Args:
            base_profile_url: Base LinkedIn profile URL

        Returns:
            BeautifulSoup object of the detailed experience page, or None if failed
        """
        from bs4 import BeautifulSoup
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        if not self.driver:
            return None

        experience_url = base_profile_url.rstrip('/') + '/details/experience/'
        logger.info(f"Navigating to detailed experience page: {experience_url}")

        try:
            self.driver.get(experience_url)
            time.sleep(3)

            WebDriverWait(self.driver, self.element_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )

            # Scroll to load all content
            logger.info("Scrolling to load all experience entries...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            for _ in range(5):
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

    def scrape_detailed_skills(self, base_profile_url: str):
        """
        Navigate to the detailed skills page to get ALL skills.

        Args:
            base_profile_url: Base LinkedIn profile URL

        Returns:
            BeautifulSoup object of the detailed skills page, or None if failed
        """
        from bs4 import BeautifulSoup
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        if not self.driver:
            return None

        skills_url = base_profile_url.rstrip('/') + '/details/skills/'
        logger.info(f"Navigating to detailed skills page: {skills_url}")

        try:
            self.driver.get(skills_url)
            time.sleep(3)

            WebDriverWait(self.driver, self.element_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )

            # Scroll to load all content
            logger.info("Scrolling to load all skills...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            for _ in range(3):
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
        """Scroll through the entire profile to load all lazy-loaded sections."""
        if not self.driver:
            return

        logger.info("Scrolling through profile to load all content...")

        # Click all "Show more" buttons to expand sections
        try:
            self.driver.execute_script("""
                var buttons = document.querySelectorAll(
                    'button[aria-label*="Show more"], '
                    + 'button[aria-label*="show more"], '
                    + 'button.inline-show-more-text__button, '
                    + 'span.show-more-less-text__text--more'
                );
                buttons.forEach(function(btn) {
                    if (btn.offsetParent !== null) {
                        btn.click();
                    }
                });
            """)
            time.sleep(1)
        except Exception as e:
            logger.debug(f"Could not click 'Show more' buttons: {e}")

        # Get initial height
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        scroll_attempts = 0
        max_attempts = 15

        while scroll_attempts < max_attempts:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Try clicking "Show more" buttons again as we scroll
            try:
                self.driver.execute_script("""
                    var buttons = document.querySelectorAll(
                        'button[aria-label*="Show more"], '
                        + 'button[aria-label*="show more"], '
                        + 'button.inline-show-more-text__button'
                    );
                    buttons.forEach(function(btn) {
                        if (btn.offsetParent !== null) {
                            btn.click();
                        }
                    });
                """)
            except Exception:
                pass

            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                # Try smaller increments
                for i in range(3):
                    self.driver.execute_script(f"window.scrollBy(0, {500 * (i + 1)});")
                    time.sleep(1)
                    current_height = self.driver.execute_script("return document.body.scrollHeight")
                    if current_height > new_height:
                        new_height = current_height
                        break

                if new_height == last_height:
                    break

            last_height = new_height
            scroll_attempts += 1

        # Scroll back to top
        self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
        time.sleep(2)

        logger.info("Finished loading all content")

    def _extract_text_safe(self, element, selector: str, attribute: str = "text") -> str:
        """Safely extract text from an element."""
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

    def _extract_with_selenium(self, selectors: List[str], timeout: int = 5) -> str:
        """Try to extract text using Selenium with multiple selector fallbacks."""
        from selenium.common.exceptions import NoSuchElementException, TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

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

    def extract_profile_data(self) -> LinkedInProfileData:
        """
        Extract all relevant data from the loaded LinkedIn profile.

        Returns:
            LinkedInProfileData object with extracted information
        """
        from bs4 import BeautifulSoup

        if not self.driver:
            raise RuntimeError("Driver not initialized")

        logger.info("Extracting profile data...")

        profile = LinkedInProfileData()
        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        # Extract name
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
                profile.name = self._extract_text_safe(soup, selector)
                if profile.name:
                    logger.info(f"Found name: {profile.name}")
                    break

            if not profile.name:
                profile.name = self._extract_with_selenium(name_selectors)

            # Fallback: extract from page title
            if not profile.name:
                try:
                    page_title = self.driver.title
                    if "|" in page_title:
                        profile.name = page_title.split("|")[0].strip()
                    elif "/in/" in self.driver.current_url:
                        url_part = self.driver.current_url.split("/in/")[1].split("/")[0]
                        profile.name = url_part.replace("-", " ").title()
                except Exception:
                    pass

            if not profile.name:
                logger.warning("Could not extract name with any method")
        except Exception as e:
            logger.warning(f"Could not extract name: {e}")

        # Extract headline
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
                profile.headline = self._extract_text_safe(soup, selector)
                if profile.headline:
                    break
        except Exception as e:
            logger.warning(f"Could not extract headline: {e}")

        # Extract location
        try:
            location_selectors = [
                "span.text-body-small.inline",
                "span[class*='text-body-small'][class*='inline']",
                "div.top-card-layout__first-subline span",
                "span.text-body-small",
                "div.pv-text-details__left-panel span.text-body-small"
            ]
            for selector in location_selectors:
                profile.location = self._extract_text_safe(soup, selector)
                if profile.location:
                    break
        except Exception as e:
            logger.warning(f"Could not extract location: {e}")

        # Extract About section
        try:
            about_section = soup.find("section", {"data-section": "summary"}) or \
                          soup.find("section", class_=re.compile(".*summary.*", re.I))

            if about_section:
                about_text = self._extract_text_safe(about_section, "div.display-flex.ph5.pv3") or \
                           self._extract_text_safe(about_section, "div.inline-show-more-text") or \
                           self._extract_text_safe(about_section, "span[aria-hidden='true']")

                if about_text:
                    profile.about = about_text
        except Exception as e:
            logger.warning(f"Could not extract about section: {e}")

        # Extract Experience
        try:
            profile.experience = extract_experience_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract experience: {e}")

        # Extract Education
        try:
            profile.education = extract_education_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract education: {e}")

        # Extract Skills
        try:
            profile.skills = extract_skills_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract skills: {e}")

        # Extract Certifications
        try:
            profile.certifications = extract_certifications_improved(soup)
        except Exception as e:
            logger.warning(f"Could not extract certifications: {e}")

        return profile

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

    def scrape_profile_data(self, profile_url: str) -> LinkedInProfileData:
        """
        Main method to scrape a LinkedIn profile and return structured data.

        Args:
            profile_url: Full LinkedIn profile URL (e.g., https://linkedin.com/in/username)

        Returns:
            LinkedInProfileData with all extracted fields

        Raises:
            RuntimeError: If scraping fails (driver setup, login, navigation)
        """
        try:
            # Setup
            self.setup_driver()

            # Login
            if not self.automated_login():
                raise RuntimeError(
                    "LinkedIn login failed. Check LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env. "
                    "If 2FA is required, set CHROME_USER_DATA_DIR and log in manually once first."
                )

            # Navigate to profile
            if not self.navigate_to_profile(profile_url):
                raise RuntimeError(f"Failed to load profile: {profile_url}")

            time.sleep(2)

            # Load all content
            self.scroll_to_load_content()

            # Extract basic profile data
            profile_data = self.extract_profile_data()

            if not profile_data.name:
                raise RuntimeError(
                    "Could not extract profile data. The page may not have loaded correctly."
                )

            # Fetch detailed experience page for ALL roles
            logger.info("Fetching detailed experience data...")
            detailed_exp_soup = self.scrape_detailed_experience(profile_url)
            if detailed_exp_soup:
                detailed_exp = extract_experience_improved(detailed_exp_soup)
                if detailed_exp and len(detailed_exp) >= len(profile_data.experience):
                    logger.info(
                        f"Detailed experience: {len(detailed_exp)} entries "
                        f"(vs {len(profile_data.experience)} from main page)"
                    )
                    profile_data.experience = detailed_exp

            # Fetch detailed skills page for ALL skills
            logger.info("Fetching detailed skills data...")
            detailed_skills_soup = self.scrape_detailed_skills(profile_url)
            if detailed_skills_soup:
                detailed_skills = extract_skills_improved(detailed_skills_soup)
                if detailed_skills and len(detailed_skills) >= len(profile_data.skills):
                    logger.info(
                        f"Detailed skills: {len(detailed_skills)} "
                        f"(vs {len(profile_data.skills)} from main page)"
                    )
                    profile_data.skills = detailed_skills

            logger.info(
                f"Scraping complete: {profile_data.name} - "
                f"{len(profile_data.experience)} experiences, "
                f"{len(profile_data.skills)} skills"
            )

            return profile_data

        except KeyboardInterrupt:
            logger.info("Scraping interrupted")
            raise RuntimeError("Scraping was interrupted")
        finally:
            self.cleanup()
