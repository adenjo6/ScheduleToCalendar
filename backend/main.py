import os
import uuid
import base64
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import demjson3
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from ics import Calendar, Event
from openai import OpenAI

# -----------------------------------------------------------------------------
# 1. Environment and Initialization
# -----------------------------------------------------------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in .env file.")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg"}
UPLOAD_DIR = "uploads"
ICS_DIR = "ics_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(ICS_DIR, exist_ok=True)

# Mapping for day abbreviations to weekday numbers (Monday = 0)
DAY_MAP = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4}

# -----------------------------------------------------------------------------
# 2. FastAPI Application Setup
# -----------------------------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000","http://adenjo6.github.io/ScheduleToCalendar", "https://adenjo6.github.io/ScheduleToCalendar"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# 3. Route Definitions
# -----------------------------------------------------------------------------
@app.get("/")
def read_root():
    """Health-check endpoint."""
    return {"message": "Schedule to Calendar Backend is running."}

@app.post("/upload-schedule")
async def upload_schedule(image: UploadFile = File(...)) -> FileResponse:
    """
    Main endpoint:
      - Validates the image's MIME type.
      - Saves the uploaded image.
      - Processes the image via OpenAI.
      - Parses schedule JSON.
      - Generates an ICS file.
      - Returns the ICS file.
    """
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400, detail="Invalid image type. Only JPEG and PNG are allowed."
        )

    unique_id = str(uuid.uuid4())
    file_extension = image.filename.split(".")[-1]
    file_path = os.path.join(UPLOAD_DIR, f"{unique_id}.{file_extension}")

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await image.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")

    try:
        formatted_schedule = call_openai_api(file_path)
    except Exception as e:
        logging.error("Error calling OpenAI API", exc_info=True)
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

    try:
        events = parse_schedule(formatted_schedule)
        logging.info("Parsed events: %s", json.dumps(events, indent=2))
    except Exception as e:
        logging.error("Error parsing schedule", exc_info=True)
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

    try:
        ics_path = generate_ics(events)
    except Exception as e:
        logging.error("Error generating ICS file", exc_info=True)
        os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

    os.remove(file_path)  # Cleanup uploaded image

    return FileResponse(ics_path, media_type="text/calendar", filename="schedule.ics")

# -----------------------------------------------------------------------------
# 4. Helper Functions
# -----------------------------------------------------------------------------
def call_openai_api(image_path: str) -> str:
    """Reads an image, encodes it in base64, builds a prompt and message payload,
       and calls OpenAI's API to get a formatted JSON schedule as a string."""
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    ext = os.path.splitext(image_path)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        img_type = "image/jpeg"
    elif ext == ".png":
        img_type = "image/png"
    else:
        raise ValueError("Unsupported image type.")

    img_b64_str = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Use this image of a college class schedule and output the schedule in valid JSON format. "
        "Each event should include 'title', 'start', 'end', 'days', 'location', 'end_date', and 'notes'. "
        "In the image, the days correspond to: M = Monday, T = Tuesday, W = Wednesday, R = Thursday, F = Friday "
        "Dates should be in 'YYYY-MM-DDTHH:MM:SS' for start and end, and 'YYYY-MM-DD' for end_date. Use today's date as starting date and use 11 weeks after today's date for ending date"
        "Output only the JSON data. Do not include any explanations or additional text."
        "Return only valid JSON. Do not include triple backticks or any Markdown formatting."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{img_type};base64,{img_b64_str}"}}
            ],
        }
    ]

    response = openai_client.chat.completions.create(
        model="chatgpt-4o-latest",
        messages=messages,
        max_tokens=1500,
        temperature=0,
    )

    if not response or not response.choices:
        raise ValueError("Invalid response from OpenAI API.")

    formatted_schedule = response.choices[0].message.content.strip()
    logging.info("Formatted Schedule: %s", formatted_schedule)
    return formatted_schedule

def clean_response(response_str: str) -> str:
    # Trim whitespace
    cleaned = response_str.strip()
    
    # Remove triple backticks if present
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
    
    # Remove a leading language identifier like 'json' (case-insensitive)
    # For example, if the string starts with "json" or "json:" then remove it.
    lower_cleaned = cleaned.lower()
    if lower_cleaned.startswith("json"):
        # Remove the "json" word
        cleaned = cleaned[len("json"):].strip()
        # If it starts with a colon, remove that too
        if cleaned.startswith(":"):
            cleaned = cleaned[1:].strip()
    
    # Remove any stray backticks that may remain
    cleaned = cleaned.replace("`", "")
    
    return cleaned
def parse_schedule(formatted_schedule: str) -> List[Dict[str, Any]]:
    try:
        cleaned_schedule = clean_response(formatted_schedule)
        schedule_dict = demjson3.decode(cleaned_schedule)
        events = schedule_dict.get("events", [])
        if not isinstance(events, list):
            raise ValueError("'events' key does not contain a list.")
        return events
    except Exception as e:
        raise ValueError(f"Failed to parse schedule JSON: {e}")
    
def generate_ics(events: List[Dict[str, Any]]) -> str:
    """Generates an ICS calendar file from the list of events and returns its file path."""
    cal = Calendar()

    for idx, event_data in enumerate(events, start=1):
        try:
            title = event_data["title"]
            start_str = event_data["start"]
            end_str = event_data["end"]
            days = event_data["days"]
            location = event_data["location"]
            instructor = event_data["notes"]
            end_date_str = event_data["end_date"]

            start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%S")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

            for day in days:
                weekday = DAY_MAP.get(day.upper())
                if weekday is None:
                    logging.warning(f"Event {idx}: Unrecognized day abbreviation: {day}. Skipping.")
                    continue

                # Calculate first occurrence for this weekday
                days_ahead = (weekday - start_dt.weekday()) % 7
                first_event_date = start_dt.date() + timedelta(days=days_ahead)

                event = Event()
                event.name = title
                event.begin = datetime.combine(first_event_date, start_dt.time())
                event.end = datetime.combine(first_event_date, end_dt.time())
                event.location = location
                event.description = instructor
                event.rrule = {"freq": "WEEKLY", "until": end_date.strftime("%Y-%m-%d")}
                cal.events.add(event)
        except KeyError as e:
            logging.error(f"Event {idx}: Missing key {e}. Skipping event.")
        except Exception as e:
            logging.error(f"Event {idx}: Unexpected error: {e}. Skipping event.")

    ics_filename = f"schedule_{uuid.uuid4()}.ics"
    ics_path = os.path.join(ICS_DIR, ics_filename)
    with open(ics_path, "w") as f:
        f.write(str(cal))
    logging.info("ICS file created at: %s", ics_path)
    return ics_path
