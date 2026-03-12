import uvicorn
import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.admin import setup_panel
from app.config import setup_logging

log = setup_logging(logging.getLogger(__name__))

app = FastAPI(title="My Settlement - Admin Panel")

@app.get("/")
async def root():
    return RedirectResponse(url="/admin")

setup_panel(app)

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="0.0.0.0", port=3480)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.critical(e, exc_info=True)
