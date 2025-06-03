import requests
import json
import base64
import logging
import pickle
import os
from datetime import datetime, timedelta
import time

# Configure logging - output to console for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Replace the hardcoded constants with environment variables
AUTH_URL = os.environ.get("AUTH_URL")
API_URL = os.environ.get("API_URL")

# Authentication details
EMAIL = os.environ.get("EMAIL")
USER_ID = os.environ.get("USER_ID")

# Configuration for checking
DAYS_TO_LOOK_AHEAD = 30   # How many days in the future to check
CUTOFF_DATE = datetime(2025, 6, 19)  # Only process appointments until June 19th, 2025

# Mailgun Configuration
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN")
MAILGUN_FROM_EMAIL = os.environ.get("MAILGUN_FROM_EMAIL")
MAILGUN_TO_EMAIL = os.environ.get("MAILGUN_TO_EMAIL")
MAILGUN_API_URL = os.environ.get("MAILGUN_API_URL")

# Replace in your script
MAIL_TEMPLATE_LINK = os.environ.get("MAIL_TEMPLATE_LINK")

# File to store previously notified dates
PREVIOUS_NOTIFIED_FILE = "previous_notified.pkl"

class EmailService:
    def __init__(self):
        self.api_key = MAILGUN_API_KEY
        self.domain = MAILGUN_DOMAIN
        self.from_email = MAILGUN_FROM_EMAIL
        self.api_url = MAILGUN_API_URL
        
    def send_email(self, to, subject, html, text=None):
        """Send email using Mailgun API"""
        url = f"{self.api_url}/v3/{self.domain}/messages"
        
        data = {
            "from": self.from_email,
            "to": to,
            "subject": subject,
            "html": html
        }
        
        if text:
            data["text"] = text
            
        try:
            response = requests.post(
                url,
                auth=("api", self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                logger.info(f"Email sent successfully to {to}")
                return response.json()
            else:
                logger.error(f"Failed to send email. Status: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return None

def appointment_available_template(available_dates):
    """Create email template for available appointments"""
    count = len(available_dates)
    
    subject = f"Kapper Afspraak Beschikbaar! ({count} nieuwe tijden)"
    
    # Get booking link from environment variable
    booking_link = MAIL_TEMPLATE_LINK  # Using the environment variable
    
    # Create HTML version
    html = f"""
    <h1>Goed nieuws! Er zijn nieuwe afspraken beschikbaar bij je kapper!</h1>
    <p>De volgende nieuwe tijdsloten zijn beschikbaar:</p>
    <ul>
    """
    
    for i, date in enumerate(sorted(available_dates), 1):
        html += f"<li><strong>{date}</strong></li>\n"
    
    html += f"""
    </ul>
    <br>
    <p><a href="{booking_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Boek Nu Je Afspraak</a></p>
    <br>
    <p>Met vriendelijke groet,</p>
    <p>De BillCollector</p>
    """
    
    # Create text version
    text = f"Goede nieuws! Er zijn {count} nieuwe afspraken beschikbaar bij je kapper!\n\n"
    text += "De volgende nieuwe tijdsloten zijn beschikbaar:\n\n"
    
    for i, date in enumerate(sorted(available_dates), 1):
        text += f"{i}. {date}\n"
    
    text += f"\nBoek je afspraak op: {booking_link}\n\n"
    text += "Met vriendelijke groet,\nDe BillCollector"
    
    return {
        "subject": subject,
        "html": html,
        "text": text
    }

def load_previous_notified():
    """Load the set of previously notified appointment dates"""
    if os.path.exists(PREVIOUS_NOTIFIED_FILE):
        try:
            # Check if file is not empty
            if os.path.getsize(PREVIOUS_NOTIFIED_FILE) > 0:
                with open(PREVIOUS_NOTIFIED_FILE, 'rb') as f:
                    return pickle.load(f)
            else:
                logger.warning("Previous notified file exists but is empty")
                return set()
        except Exception as e:
            logger.error(f"Error loading previous notified dates: {e}")
            return set()
    logger.info("No previous notified file found, creating new")
    return set()

def save_previous_notified(notified_dates):
    """Save the set of previously notified appointment dates"""
    try:
        with open(PREVIOUS_NOTIFIED_FILE, 'wb') as f:
            pickle.dump(notified_dates, f)
        logger.info(f"Saved {len(notified_dates)} notified dates to {PREVIOUS_NOTIFIED_FILE}")
    except Exception as e:
        logger.error(f"Error saving notified dates: {e}")

def send_email_notification(available_dates):
    """Send email notification with available appointment dates"""
    if not available_dates:
        return
    
    # Load previously notified dates
    previous_notified = load_previous_notified()
    
    # Only notify about new dates we haven't seen before
    new_dates = set(available_dates) - previous_notified
    if not new_dates:
        logger.info("No new available dates to notify about")
        return
    
    logger.info(f"Sending notification about {len(new_dates)} new available slots")
    
    try:
        email_service = EmailService()
        email_template = appointment_available_template(list(new_dates))
        
        result = email_service.send_email(
            to=MAILGUN_TO_EMAIL,
            subject=email_template["subject"],
            html=email_template["html"],
            text=email_template["text"]
        )
        
        if result:
            logger.info(f"Email notification sent for {len(new_dates)} available slots")
            # Update our record of what we've notified about
            previous_notified.update(new_dates)
            save_previous_notified(previous_notified)
        else:
            logger.error("Failed to send email notification")
            
    except Exception as e:
        logger.error(f"Error in email notification process: {e}")


def get_auth_token():
    """Get a fresh authentication token"""
    # Base64 encode the credentials
    email_encoded = base64.b64encode(EMAIL.encode()).decode()
    id_encoded = base64.b64encode(USER_ID.encode()).decode()
    
    logger.info(f"Encoded email: {email_encoded}")
    logger.info(f"Encoded id: {id_encoded}")
    
    # Prepare the payload
    payload = {
        "email": email_encoded,
        "id": id_encoded
    }
    
    headers = {
        "Content-Type": "application/json",
        "Origin": os.environ.get("ORIGIN"),
        "Referer": os.environ.get("REFERER"),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    }
    
    logger.info("Sending authentication request...")
    try:
        response = requests.post(AUTH_URL, json=payload, headers=headers)
        logger.info(f"Auth status code: {response.status_code}")
        
        # Debug response
        logger.info(f"Auth response text: {response.text[:200]}...")  # Show first 200 chars
        
        response.raise_for_status()
        token_data = response.json()
        
        if "token" in token_data:
            token = token_data["token"]
            logger.info(f"Successfully obtained token: {token[:20]}...{token[-20:] if len(token) > 40 else token}")
            return token
        else:
            logger.error("Token not found in response")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Authentication request failed: {e}")
        return None

def get_available_appointments(token):
    """Make API call to check for available appointments"""
    today = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=DAYS_TO_LOOK_AHEAD)).strftime("%Y-%m-%d")
    
    logger.info(f"Checking appointments from {today} to {end_date}")
    
    # Use pre-encoded strings to match exactly what the browser sends
    params = {
        "StartDate": today,
        "EndDate": end_date,
        "Services": '[{"servicesId":5049,"order":1,"employeeId":322350}]',
        "CombinationServices": '[]',
        "EmployeeId": 322350
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": os.environ.get("ORIGIN"),
        "Referer": os.environ.get("REFERER"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "nl-NL,nl;q=0.8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    }
    
    logger.info("Sending appointment request...")
    try:
        response = requests.get(API_URL, params=params, headers=headers)
        logger.info(f"Appointment API status code: {response.status_code}")
        
        # Print out complete response for debugging
        response_text = response.text
        logger.info(f"Response length: {len(response_text)} characters")
        logger.info(f"Response preview: {response_text[:500]}...")  # Show more of the response
        
        if response.status_code != 200:
            logger.error(f"Error response: {response.text}")
            return None
            
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Raw response: {response.text[:500]}...")
        return None

def process_appointments(data):
    """Process appointment data and check if any are available"""
    if not data:
        logger.warning("No appointment data received")
        return []
    
    # NEW: Handle the correct response format which is an array of date objects
    if not isinstance(data, list):
        logger.warning(f"Unexpected response format. Expected list, got {type(data)}")
        logger.warning(f"Data preview: {str(data)[:200]}...")
        return []
    
    available_dates = []
    available_count = 0
    total_days = len(data)
    filtered_count = 0
    
    logger.info(f"Processing {total_days} days of appointment data (filtering until {CUTOFF_DATE.strftime('%Y-%m-%d')})")
    
    for day_data in data:
        # Check if this day has available times
        if "date" in day_data and "availableTimes" in day_data and day_data["availableTimes"]:
            date_str = day_data["date"]
            
            # Parse the date and check if it's before our cutoff
            try:
                day_date = datetime.strptime(date_str, "%Y-%m-%d")
                if day_date > CUTOFF_DATE:
                    filtered_count += 1
                    continue  # Skip dates after June 13th, 2025
            except ValueError:
                logger.warning(f"Could not parse date: {date_str}")
                continue
            
            for time_slot in day_data["availableTimes"]:
                if "availableTime" in time_slot:
                    available_count += 1
                    time_str = time_slot["availableTime"]
                    
                    try:
                        # Combine date and time
                        full_datetime_str = f"{date_str}T{time_str}:00"
                        date_obj = datetime.fromisoformat(full_datetime_str)
                        formatted_date = date_obj.strftime("%A, %d %B %Y at %H:%M")
                        available_dates.append(formatted_date)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Date parsing error: {e} for date: {date_str} time: {time_str}")
                        available_dates.append(f"{date_str} at {time_str}")
    
    if filtered_count > 0:
        logger.info(f"Filtered out {filtered_count} days after cutoff date")
    logger.info(f"Found {available_count} available time slots (within date range)")
    return available_dates

def main():
    """Main function to check appointments and display results"""
    logger.info("Starting appointment availability check")
    
    # Get a fresh authentication token
    token = get_auth_token()
    if not token:
        logger.error("Failed to get authentication token. Aborting check.")
        return
    
    # Get available appointments
    data = get_available_appointments(token)
    if data:
        available_dates = process_appointments(data)
        if available_dates:
            logger.info(f"Found {len(available_dates)} available appointment slots")
            logger.info("Available appointments:")
            for i, date in enumerate(available_dates, 1):
                logger.info(f"  {i}. {date}")
            
            # Send email notification for new available slots
            send_email_notification(available_dates)
        else:
            logger.info("No available appointments found within the specified date range")
    else:
        logger.warning("Failed to retrieve appointment data")


if __name__ == "__main__":
    # Retry mechanism in case of temporary failures
    max_retries = 3
    for attempt in range(max_retries):
        try:
            main()  
            break  # Exit the loop if successful
        except Exception as e:
            logger.error(f"Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Waiting 30 seconds before retry...")
                time.sleep(30)
            else:
                logger.error("All retry attempts failed")
