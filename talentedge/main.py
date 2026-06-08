from fastapi import FastAPI, Request
from api.custom_assessments import router as custom_assessments_router
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import settings
from database import create_tables
from auth.router import router as auth_router
from api.candidates import router as candidates_router
from api.assessments import router as assessments_router
from api.assess import router as assess_router
from api.logs import router as logs_router
from api.emails import router as emails_router
from api.interviews import router as interviews_router
from api.analytics import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    print(f"\U0001f680 {settings.APP_NAME} started at {settings.APP_URL}")
    yield

app = FastAPI(title=settings.APP_NAME, version="2.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)
app.include_router(candidates_router)
app.include_router(assessments_router)
app.include_router(assess_router)
app.include_router(logs_router)
app.include_router(emails_router)
app.include_router(custom_assessments_router)
app.include_router(interviews_router)
app.include_router(analytics_router)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "landing.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(request, "signup.html")

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html")

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    from auth.utils import get_current_user_from_cookie
    user = get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})

@app.get("/assess", response_class=HTMLResponse)
async def assess_page(request: Request, token: str = ""):
    return templates.TemplateResponse(request, "assessment_portal.html", {"token": token})


if __name__ == "__main__":
    import uvicorn
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
