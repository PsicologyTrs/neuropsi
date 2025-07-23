import os
import json
import io
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from docxtpl import DocxTemplate
from pydantic import BaseModel
import tempfile
from datetime import datetime, timedelta
from google.auth.transport.requests import Request

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashing-concha-6e359a.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI')

TOKEN_FILE = "token.json"
SCOPES = ['https://www.googleapis.com/auth/drive']

CARPETA_ORIGEN = "18S6rYuwaS1pDuy100K9n4CvojEixFP0u"
CARPETA_DESTINO = "18hU5uw1WuvuOPAKpL_nNEiO5G7GR65hC"

class FormData(BaseModel):
    nombre_form: str
    born_date_form: str
    age_form: str
    cedula_form: str
    residencia_form: str
    escolaridad: str
    location_form: str
    ocupation_form: str
    entidad_form: str
    cel_form: str
    acompañante_form: str
    dx_ingre_form: str
    problem_actual_form: str
    actitud__form: str
    hist_form: str
    ant_lab_form: str
    ant_per_form: str
    ant_farma_form: str
    antecedente_form: str

@app.get('/login')
def login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, _ = flow.authorization_url(access_type='offline', prompt='consent')
    return RedirectResponse(authorization_url)

@app.get('/oauth2callback')
def oauth2callback(code: str):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    with open(TOKEN_FILE, 'w') as token:
        json.dump({
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_expiry": (datetime.now() + timedelta(seconds=creds.expiry.timestamp() - datetime.now().timestamp())).isoformat()
        }, token)

    return {"status": "Autenticación exitosa, tokens guardados."}

def get_credentials():
    if not os.path.exists(TOKEN_FILE):
        raise HTTPException(401, "Debes iniciar sesión primero (/login).")

    with open(TOKEN_FILE, 'r') as token:
        token_data = json.load(token)

    creds = Credentials(
        token=token_data['access_token'],
        refresh_token=token_data['refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES
    )

    if datetime.fromisoformat(token_data['token_expiry']) <= datetime.now():
        creds.refresh(Request())
        with open(TOKEN_FILE, 'w') as token:
            json.dump({
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_expiry": (datetime.now() + timedelta(seconds=creds.expiry.timestamp() - datetime.now().timestamp())).isoformat()
            }, token)

    return creds

@app.post("/generar")
async def generar_plantilla(data: FormData):
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    cedula = data.cedula_form.strip()

    if data.antecedente_form.lower() == "true":
        data.hist_form = "04/2025 TAC de cráneo simple (NORMAL), seguimiento por neurología"
        data.ant_lab_form = "Empleada en oficios varios"
        data.ant_per_form = "Red de apoyo estable"
        data.ant_farma_form = "Eszoplicona, fluoxetina, vitamina b12, levotiroxina, e ibersartan"
    else:
        data.hist_form = data.ant_lab_form = data.ant_per_form = data.ant_farma_form = "N/A"

    extra_variables = {
    "PD": {
        "Tiempo": "{% raw %}{{PD.Tiempo}}{% endraw %}",
        "Lugar": "{% raw %}{{PD.Lugar}}{% endraw %}",
        "Persona": "{% raw %}{{PD.Persona}}{% endraw %}",
        "Espontanea": "{% raw %}{{PD.Espontanea}}{% endraw %}",
        "Por_categorias": "{% raw %}{{PD.Por_categorias}}{% endraw %}",
        "Reconocimiento": "{% raw %}{{PD.Reconocimiento}}{% endraw %}",
        "Digitos": "{% raw %}{{PD.Digitos}}{% endraw %}",
        "Deteccion_visual": "{% raw %}{{PD.Deteccion_visual}}{% endraw %}",
        "Veinte": "{% raw %}{{PD.Veinte}}{% endraw %}",
        "Fluidez_verbal_semantica": "{% raw %}{{PD.Fluidez_verbal_semantica}}{% endraw %}",
        "Fluidez_verbal_fonologica": "{% raw %}{{PD.Fluidez_verbal_fonologica}}{% endraw %}",
        "Denominacion": "{% raw %}{{PD.Denominacion}}{% endraw %}",
        "Comprension": "{% raw %}{{PD.Comprension}}{% endraw %}",
        "Repeticion": "{% raw %}{{PD.Repeticion}}{% endraw %}",
        "Semejanzas": "{% raw %}{{PD.Semejanzas}}{% endraw %}",
        "Calculo": "{% raw %}{{PD.Calculo}}{% endraw %}"
    },
    "DATOS_GENERALES": {
        "lectura": "{% raw %}{{DATOS_GENERALES.lectura}}{% endraw %}",
        "dictado": "{% raw %}{{DATOS_GENERALES.dictado}}{% endraw %}",
        "secuenciacion": "{% raw %}{{DATOS_GENERALES.secuenciacion}}{% endraw %}"
    },
    "Suma": {
        "Motoras": "{% raw %}{{Suma.Motoras}}{% endraw %}"
    },
    "RESULTADO_Orientacion": "{% raw %}{{RESULTADO_Orientacion}}{% endraw %}",
    "RESULTADO_Espontanea": "{% raw %}{{RESULTADO_Espontanea}}{% endraw %}",
    "RESULTADO_categorias": "{% raw %}{{RESULTADO_categorias}}{% endraw %}",
    "RESULTADO_Reconocimiento": "{% raw %}{{RESULTADO_Reconocimiento}}{% endraw %}",
    "RESULTADO_Digitos": "{% raw %}{{RESULTADO_Digitos}}{% endraw %}",
    "RESULTADO_Deteccion_visual": "{% raw %}{{RESULTADO_Deteccion_visual}}{% endraw %}",
    "RESULTADO_Veinte": "{% raw %}{{RESULTADO_Veinte}}{% endraw %}",
    "RESULTADO_Fluidez_verbal_semantica": "{% raw %}{{RESULTADO_Fluidez_verbal_semantica}}{% endraw %}",
    "RESULTADO_Fluidez_verbal_fonologica": "{% raw %}{{RESULTADO_Fluidez_verbal_fonologica}}{% endraw %}",
    "RESULTADO_Denominacion": "{% raw %}{{RESULTADO_Denominacion}}{% endraw %}",
    "RESULTADO_Compresion": "{% raw %}{{RESULTADO_Compresion}}{% endraw %}",
    "RESULTADO_Repeticion": "{% raw %}{{RESULTADO_Repeticion}}{% endraw %}",
    "RESULTADO_Lectura": "{% raw %}{{RESULTADO_Lectura}}{% endraw %}",
    "RESULTADO_dictado": "{% raw %}{{RESULTADO_dictado}}{% endraw %}",
    "RESULTADO_Semejanzas": "{% raw %}{{RESULTADO_Semejanzas}}{% endraw %}",
    "RESULTADO_Calculo": "{% raw %}{{RESULTADO_Calculo}}{% endraw %}",
    "RESULTADO_secuenciacion": "{% raw %}{{RESULTADO_secuenciacion}}{% endraw %}",
    "RESULTADO_Suma_Motoras": "{% raw %}{{RESULTADO_Suma_Motoras}}{% endraw %}"
}


    resultados = drive_service.files().list(
        q=f"'{CARPETA_ORIGEN}' in parents and name contains '.docx' and trashed = false",
        fields="files(id, name)"
    ).execute()

    archivos = resultados.get("files", [])
    if not archivos:
        return JSONResponse(status_code=404, content={"error": "No se encontró plantilla base."})

    file_id = archivos[0]["id"]
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, drive_service.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(fh.read())
        temp_path = tmp.name

    doc = DocxTemplate(temp_path)
    context = {**extra_variables, **data.dict()}
    doc.render(context)

    salida = os.path.join(tempfile.gettempdir(), f"plantilla_{cedula}.docx")
    doc.save(salida)

    metadata = {'name': f"plantilla_{cedula}.docx", 'parents': [CARPETA_DESTINO]}
    media = MediaFileUpload(salida, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    uploaded_file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()

    enlace = f"https://drive.google.com/file/d/{uploaded_file['id']}/preview"

    os.remove(salida)
    os.remove(temp_path)

    return {"mensaje":"✅ Plantilla generada correctamente","cedula":cedula,"link":enlace}

@app.get("/")
def read_root():
    return {"status": "Servidor funcionando correctamente!"}
