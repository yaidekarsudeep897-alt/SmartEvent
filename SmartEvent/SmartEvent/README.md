# SmartEvent

SmartEvent is a simple, human-made style Flask web application for event owners, workers, guests, caterers and administrators.

## Main features

- Worker registration/login and profile
- Worker skills, availability and expected payment
- Event owner registration/login
- Create and manage events
- Catering/caterer listing
- Create worker jobs for an event
- Workers browse and apply for jobs
- Admin worker verification
- Application accept/reject
- Worker payment records
- Guest management and RSVP fields
- Event location/map-ready data
- Role-based dashboards
- SQLite database

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run:

```bash
pip install -r requirements.txt
python app.py
```

4. Open http://127.0.0.1:5000

## Demo accounts

Admin:
admin@smartevent.local / admin123

Event owner:
owner@smartevent.local / owner123

Worker:
worker@smartevent.local / worker123

The SQLite database is created automatically on first run.

## Notes

This is a college-project starter implementation. Before production use, change the Flask secret key, add CSRF protection, stronger validation, HTTPS, real payment integration and a proper map API.
