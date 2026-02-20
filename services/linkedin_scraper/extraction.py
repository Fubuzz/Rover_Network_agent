"""
Improved extraction methods for LinkedIn profiles.

Based on HTML structure analysis, these methods use the correct selectors
to extract profile data from modern LinkedIn profiles.
"""

import logging
import re
from typing import Dict, List
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def find_section_by_heading(soup: BeautifulSoup, heading_text: str) -> Tag:
    """
    Find a section by its H2 heading text.

    Args:
        soup: BeautifulSoup object
        heading_text: Text to search for in H2 headings (case-insensitive)

    Returns:
        Section element or None
    """
    headings = soup.find_all("h2")
    for h2 in headings:
        if heading_text.lower() in h2.get_text().lower():
            # Get the parent section
            section = h2.find_parent("section")
            if section:
                logger.info(f"Found '{heading_text}' section via H2 heading")
                return section
    return None


def extract_experience_improved(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extract experience data using improved selectors.

    LinkedIn structure:
    - Section identified by H2 with text "Experience"
    - Contains <li> items with class 'artdeco-list__item'
    - Each item can contain multiple positions at same company:
      Format: Company (bold), Total Duration (normal), Title1 (bold), Duration1 (light), Title2 (bold), Duration2 (light), ...

    Returns:
        List of experience dictionaries
    """
    experience_list = []

    # Find experience section by H2 heading
    exp_section = find_section_by_heading(soup, "experience")

    if not exp_section:
        logger.warning("Could not find experience section")
        return experience_list

    # Find all list items
    list_items = exp_section.find_all("li", class_="artdeco-list__item")
    logger.info(f"Found {len(list_items)} experience list items")

    for item in list_items:
        # Find all spans with aria-hidden="true" - these contain the actual text
        spans = item.find_all("span", {"aria-hidden": "true"})

        if not spans:
            continue

        # Extract all text with their styling info
        text_elements = []
        for span in spans:
            text = span.get_text(strip=True)
            if text and len(text) > 1:
                parent_classes = span.parent.get("class", []) if span.parent else []
                parent_class_str = " ".join(parent_classes)

                text_elements.append({
                    "text": text,
                    "is_bold": "t-bold" in parent_class_str,
                    "is_light": "t-black--light" in parent_class_str or "t-black" in parent_class_str,
                    "is_normal": "t-normal" in parent_class_str
                })

        if not text_elements:
            continue

        # Pattern recognition:
        # If first element is bold and second is normal/light, first might be company name
        # Then alternating bold (titles) and light (durations)

        company_name = None
        i = 0

        # Check if first element is a company name
        if text_elements[0]["is_bold"]:
            first_text = text_elements[0]["text"]

            # Job title keywords - if present, it's a position not a company
            job_keywords = ["manager", "engineer", "director", "analyst", "specialist", "coordinator",
                           "developer", "designer", "consultant", "head of", "vp", "ceo", "cto", "cfo",
                           "lead", "senior", "junior", "intern", "associate", "assistant", "product", "software"]

            is_job_title = any(keyword in first_text.lower() for keyword in job_keywords)

            # If second element exists and is normal (likely total duration), first is company
            has_total_duration = (len(text_elements) > 1 and
                                text_elements[1]["is_normal"] and
                                any(word in text_elements[1]["text"].lower() for word in ["yr", "mo", "full-time", "part-time"]))

            if not is_job_title and has_total_duration:
                # First element is company name
                company_name = first_text
                i = 2  # Skip company name and total duration
                logger.debug(f"Found company: {company_name}")
            else:
                # First element is a position title
                i = 0

        # Extract positions
        while i < len(text_elements):
            elem = text_elements[i]

            if elem["is_bold"]:
                # This is a position title
                title = elem["text"]
                duration = ""
                company = company_name if company_name else ""
                description = ""

                # Look for company and duration in next elements
                if i + 1 < len(text_elements):
                    next_elem = text_elements[i + 1]

                    # Check if next element is company info (normal text, not a date range)
                    if not company and next_elem["is_normal"] and not next_elem["is_light"]:
                        # Check if it looks like a company (not a duration)
                        next_text = next_elem["text"]
                        # Duration indicators: year ranges (2020-2024), "yr", "mo", "present"
                        is_duration = any(word in next_text.lower() for word in ["yr", "mo", "present"]) or \
                                     re.search(r'\d{4}.*-.*\d{4}|\d{4}.*present', next_text.lower())

                        if not is_duration:
                            # This is company info
                            company = next_text
                            i += 1  # Skip company

                            # Now look for duration in the element after company
                            if i + 1 < len(text_elements):
                                potential_duration = text_elements[i + 1]
                                if potential_duration["is_light"] or \
                                   any(word in potential_duration["text"].lower() for word in ["yr", "mo", "present", "-"]):
                                    duration = potential_duration["text"]
                                    i += 1  # Skip duration
                        else:
                            # This element is actually the duration (no separate company)
                            duration = next_text
                            i += 1
                    # If next element is light text, it's definitely duration
                    elif next_elem["is_light"]:
                        duration = next_elem["text"]
                        i += 1

                # Look for description (long text)
                if i + 1 < len(text_elements):
                    next_elem = text_elements[i + 1]
                    if len(next_elem["text"]) > 100:
                        description = next_elem["text"]
                        i += 1

                experience_list.append({
                    "title": title,
                    "company": company,
                    "duration": duration,
                    "description": description
                })

                logger.debug(f"Extracted: {title} at {company} ({duration})")

            i += 1

    logger.info(f"Extracted {len(experience_list)} experience entries")
    return experience_list


def extract_education_improved(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extract education data using improved selectors.

    LinkedIn structure:
    - Section identified by H2 with text "Education"
    - Contains <li> items with spans containing:
      1. School name (first bold span)
      2. Degree (normal span)
      3. Duration (light span)

    Returns:
        List of education dictionaries
    """
    education_list = []

    # Find education section by H2 heading
    edu_section = find_section_by_heading(soup, "education")

    if not edu_section:
        logger.warning("Could not find education section")
        return education_list

    # Find all list items
    list_items = edu_section.find_all("li", class_="artdeco-list__item")
    logger.info(f"Found {len(list_items)} education items")

    for item in list_items:
        # Find all spans with aria-hidden="true"
        spans = item.find_all("span", {"aria-hidden": "true"})

        if len(spans) < 2:
            continue

        # Extract text
        texts = [span.get_text(strip=True) for span in spans if span.get_text(strip=True)]

        if len(texts) >= 2:
            school = texts[0]
            degree = texts[1] if len(texts) > 1 else ""
            duration = texts[2] if len(texts) > 2 else ""

            education_list.append({
                "school": school,
                "degree": degree,
                "duration": duration
            })

            logger.debug(f"Extracted education: {degree} from {school}")

    logger.info(f"Extracted {len(education_list)} education entries")
    return education_list


def extract_skills_improved(soup: BeautifulSoup) -> List[str]:
    """
    Extract ALL skills using improved selectors.

    LinkedIn structure:
    - Section identified by H2 with text "Skills"
    - Contains <li> items
    - Skill names are in bold spans
    - Filter out endorsement text

    Returns:
        List of ALL skill names
    """
    skills_list = []
    seen_skills = set()

    # Find skills section by H2 heading
    skills_section = find_section_by_heading(soup, "skills")

    if not skills_section:
        logger.warning("Could not find skills section")
        return skills_list

    # Find all list items
    list_items = skills_section.find_all("li", class_="artdeco-list__item")
    logger.info(f"Found {len(list_items)} skill items")

    for item in list_items:
        # Find bold elements (skill names) - these are typically the first bold element in each item
        bold_elements = item.find_all(class_=re.compile(".*t-bold.*"))

        if not bold_elements:
            continue

        # Take the first bold element as it's usually the skill name
        first_bold = bold_elements[0]
        text = first_bold.get_text(strip=True)

        # Clean up duplicated text (LinkedIn sometimes duplicates)
        # e.g., "PythonPython" -> "Python"
        if len(text) % 2 == 0:
            half = len(text) // 2
            if text[:half] == text[half:]:
                text = text[:half]

        # Filter out non-skill text
        exclude_terms = [
            "endorsement", "endorsed",  "person", "people", "month", "year", "last 6 months"
        ]

        # Check if it's a reasonable skill name
        if (text and
            len(text) >= 2 and
            len(text) < 80 and
            not any(term in text.lower() for term in exclude_terms) and
            text.lower() not in seen_skills):

            skills_list.append(text)
            seen_skills.add(text.lower())
            logger.debug(f"Extracted skill: {text}")

    logger.info(f"Extracted {len(skills_list)} skills total")
    return skills_list  # Return ALL skills, no limit


def extract_certifications_improved(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extract certifications using improved selectors.

    Returns:
        List of certification dictionaries
    """
    cert_list = []
    cert_section = None

    # Try multiple heading variations
    for heading in ["licenses", "certifications", "licenses & certifications"]:
        cert_section = find_section_by_heading(soup, heading)
        if cert_section:
            break

    if not cert_section:
        logger.info("No certifications section found")
        return cert_list

    # Find all list items
    list_items = cert_section.find_all("li", class_="artdeco-list__item")
    logger.info(f"Found {len(list_items)} certification items")

    for item in list_items:
        spans = item.find_all("span", {"aria-hidden": "true"})
        texts = [span.get_text(strip=True) for span in spans if span.get_text(strip=True)]

        if len(texts) >= 1:
            name = texts[0]
            issuer = texts[1] if len(texts) > 1 else ""
            date = texts[2] if len(texts) > 2 else ""

            cert_list.append({
                "name": name,
                "issuer": issuer,
                "date": date
            })

            logger.debug(f"Extracted cert: {name}")

    logger.info(f"Extracted {len(cert_list)} certifications")
    return cert_list
