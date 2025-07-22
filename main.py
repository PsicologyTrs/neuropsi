# main.py
import os
import json
import io
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from docxtpl import DocxTemplate
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import tempfile

app = FastAPI()

# Permitir peticiones desde cualquier origen (Netlify)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashing-concha-6e359a.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Configuración
CARPETA_ORIGEN = "18S6rYuwaS1pDuy100K9n4CvojEixFP0u"
CARPETA_DESTINO = "18hU5uw1WuvuOPAKpL_nNEiO5G7GR65hC"

# Cargar credenciales desde variable de entorno
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build("drive", "v3", credentials=creds)

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

@app.post("/generar")
async def generar_plantilla(data: FormData):
    cedula = data.cedula_form.strip()

    if data.antecedente_form.lower() == "true":
        data.hist_form = "04/2025 TAC de cráneo simple (NORMAL), seguimiento por neurología"
        data.ant_lab_form = "Empleada en oficios varios"
        data.ant_per_form = "Red de apoyo estable"
        data.ant_farma_form = "Eszoplicona, fluoxetina, vitamina b12, levotiroxina, e ibersartan"
    elif data.antecedente_form.lower() == "false":
        data.hist_form = data.ant_lab_form = data.ant_per_form = data.ant_farma_form = "N/A"

    resultados = drive_service.files().list(
        q=f"'{CARPETA_ORIGEN}' in parents and name contains '.docx' and trashed = false",
        fields="files(id, name)"
    ).execute()
    archivos = resultados.get("files", [])

    if not archivos:
        return JSONResponse(status_code=404, content={"error": "No se encontró plantilla base."})

    file_id = archivos[0]["id"]

    # Descargar
    fh = io.BytesIO()
    request = drive_service.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.seek(0)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(fh.read())
        temp_path = tmp.name

    doc = DocxTemplate(temp_path)
    doc.render(data.dict())

    salida = os.path.join(tempfile.gettempdir(), f"plantilla_{cedula}.docx")
    doc.save(salida)

    # Subir a Drive
    metadata = {
        'name': f"plantilla_{cedula}.docx",
        'parents': [CARPETA_DESTINO]
    }
    media = MediaFileUpload(salida, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    uploaded_file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()

    enlace = f"https://drive.google.com/file/d/{uploaded_file['id']}/preview"

    return {
        "mensaje": "✅ Plantilla generada correctamente",
        "cedula": cedula,
        "link": enlace
    }

