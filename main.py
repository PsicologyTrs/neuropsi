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
from google.auth.transport.requests import Request as GoogleRequest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    ant_acade_form: str     # <--- ¡AQUÍ ESTÁ LA VARIABLE FALTANTE!
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
        creds.refresh(GoogleRequest())
        with open(TOKEN_FILE, 'w') as token:
            json.dump({
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_expiry": (datetime.now() + timedelta(seconds=creds.expiry.timestamp() - datetime.now().timestamp())).isoformat()
            }, token)

    return creds

CARPETA_MAGISTERIO = "14q4GX6WssQjIoZiHDWWW1UTWdiSe0Unw"  # MAGISTERIO
CARPETA_SONRISAS = "18S6rYuwaS1pDuy100K9n4CvojEixFP0u"    # SONRISAS DE ESPERANZA (antes PGP)

@app.post("/generar")
async def generar_plantilla(data: FormData):
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    cedula = data.cedula_form.strip()

    # Mapeo de entidad_form a carpeta y a lo que va en el Word
    entidad = (data.entidad_form or "").strip()
    if entidad == "Magisterio_Norte":
        carpeta_origen = CARPETA_MAGISTERIO
        entidad_plantilla = "MAGISTERIO"
    elif entidad == "Cetin_Norte":
        carpeta_origen = CARPETA_MAGISTERIO
        entidad_plantilla = "MAGISTERIO/ CETIN"
    elif entidad == "PGP_Norte":
        carpeta_origen = CARPETA_MAGISTERIO
        entidad_plantilla = "PGP SUMIMEDICAL"
    elif entidad == "Sonrisa_esperanza":
        carpeta_origen = CARPETA_SONRISAS
        entidad_plantilla = "SONRISAS DE ESPERANZA"
    else:
        carpeta_origen = CARPETA_MAGISTERIO
        entidad_plantilla = "MAGISTERIO"

    extra_variables = {
        "PD": {
            "Tiempo": "{{PD.Tiempo}}",
            "Lugar": "{{PD.Lugar}}",
            "Persona": "{{PD.Persona}}",
            "Espontanea": "{{PD.Espontanea}}",
            "Por_categorias": "{{PD.Por_categorias}}",
            "Reconocimiento": " {{PD.Reconocimiento}}",
            "Digitos": " {{PD.Digitos}}",
            "Deteccion_visual": " {{PD.Deteccion_visual}}",
            "Veinte": " {{PD.Veinte}}",
            "Fluidez_verbal_semantica": " {{PD.Fluidez_verbal_semantica}}",
            "Fluidez_verbal_fonologica": " {{PD.Fluidez_verbal_fonologica}}",
            "Denominacion": " {{PD.Denominacion}}",
            "Comprension": " {{PD.Comprension}}",
            "Repeticion": " {{PD.Repeticion}}",
            "Semejanzas": " {{PD.Semejanzas}}",
            "Calculo": " {{PD.Calculo}}"
        },
        "DATOS_GENERALES": {
            "lectura": " {{DATOS_GENERALES.lectura}}",
            "dictado": " {{DATOS_GENERALES.dictado}}",
            "secuenciacion": " {{DATOS_GENERALES.secuenciacion}}"
        },
        "Suma": {
            "Motoras": " {{Suma.Motoras}}"
        },
        "RESULTADO_Orientacion": " {{RESULTADO_Orientacion}}",
        "RESULTADO_Espontanea": " {{RESULTADO_Espontanea}}",
        "RESULTADO_categorias": " {{RESULTADO_categorias}}",
        "RESULTADO_Reconocimiento": " {{RESULTADO_Reconocimiento}}",
        "RESULTADO_Digitos": " {{RESULTADO_Digitos}}",
        "RESULTADO_Deteccion_visual": " {{RESULTADO_Deteccion_visual}}",
        "RESULTADO_Veinte": " {{RESULTADO_Veinte}}",
        "RESULTADO_Fluidez_verbal_semantica": " {{RESULTADO_Fluidez_verbal_semantica}}",
        "RESULTADO_Fluidez_verbal_fonologica": " {{RESULTADO_Fluidez_verbal_fonologica}}",
        "RESULTADO_Denominacion": " {{RESULTADO_Denominacion}}",
        "RESULTADO_Compresion": " {{RESULTADO_Compresion}}",
        "RESULTADO_Repeticion": " {{RESULTADO_Repeticion}}",
        "RESULTADO_Lectura": " {{RESULTADO_Lectura}}",
        "RESULTADO_dictado": " {{RESULTADO_dictado}}",
        "RESULTADO_Semejanzas": " {{RESULTADO_Semejanzas}}",
        "RESULTADO_Calculo": " {{RESULTADO_Calculo}}",
        "RESULTADO_secuenciacion": " {{RESULTADO_secuenciacion}}",
        "RESULTADO_Suma_Motoras": " {{RESULTADO_Suma_Motoras}}"
    }

    # Mezcla los datos y sobreescribe entidad_form para la plantilla Word
    context = {**extra_variables, **data.dict()}
    context["entidad_form"] = entidad_plantilla

    resultados = drive_service.files().list(
        q=f"'{carpeta_origen}' in parents and name contains '.docx' and trashed = false",
        fields="files(id, name)"
    ).execute()

    archivos = resultados.get("files", [])
    if not archivos:
        return JSONResponse(status_code=404, content={"error": "No se encontró plantilla base para esta entidad."})

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
    doc.render(context)

    salida = os.path.join(tempfile.gettempdir(), f"plantilla_{cedula}.docx")
    doc.save(salida)

    metadata = {'name': f"plantilla_{cedula}.docx", 'parents': [CARPETA_DESTINO]}
    media = MediaFileUpload(salida, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    uploaded_file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()

    enlace = f"https://drive.google.com/file/d/{uploaded_file['id']}/preview"

    # Sube el JSON con entidad y nombre
    datos_json = {
        "cedula_form": data.cedula_form,
        "entidad_form": data.entidad_form,
        "nombre_form": data.nombre_form
    }
    json_path = os.path.join(tempfile.gettempdir(), f"plantilla_{cedula}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(datos_json, f, ensure_ascii=False)
    metadata_json = {
        'name': f"plantilla_{cedula}.json",
        'parents': [CARPETA_DESTINO]
    }
    media_json = MediaFileUpload(json_path, mimetype="application/json")
    drive_service.files().create(body=metadata_json, media_body=media_json, fields="id").execute()
    os.remove(json_path)

    os.remove(salida)
    os.remove(temp_path)

    return {"mensaje": "✅ Plantilla generada correctamente", "cedula": cedula, "link": enlace}
