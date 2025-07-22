import os
import json
import io
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from docxtpl import DocxTemplate
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import tempfile

app = FastAPI()

# Permitir peticiones desde Netlify
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashing-concha-6e359a.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

CARPETA_ORIGEN = "18S6rYuwaS1pDuy100K9n4CvojEixFP0u"
CARPETA_DESTINO = "18hU5uw1WuvuOPAKpL_nNEiO5G7GR65hC"

# Cargar credenciales
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

    # Variables extra con su propio nombre
    extra_variables = {
        "PD": {
            "Tiempo": "{{PD.Tiempo}}",
            "Lugar": "{{PD.Lugar}}",
            "Persona": "{{PD.Persona}}",
            "Espontanea": "{{PD.Espontanea}}",
            "Por_categorias": "{{PD.Por_categorias}}",
            "Reconocimiento": "{{PD.Reconocimiento}}",
            "Digitos": "{{PD.Digitos}}",
            "Deteccion_visual": "{{PD.Deteccion_visual}}",
            "Veinte": "{{PD.Veinte}}",
            "Fluidez_verbal_semantica": "{{PD.Fluidez_verbal_semantica}}",
            "Fluidez_verbal_fonologica": "{{PD.Fluidez_verbal_fonologica}}",
            "Denominacion": "{{PD.Denominacion}}",
            "Comprension": "{{PD.Comprension}}",
            "Repeticion": "{{PD.Repeticion}}",
            "Semejanzas": "{{PD.Semejanzas}}",
            "Calculo": "{{PD.Calculo}}"
        },
        "DATOS_GENERALES": {
            "lectura": "{{DATOS_GENERALES.lectura}}",
            "dictado": "{{DATOS_GENERALES.dictado}}",
            "secuenciacion": "{{DATOS_GENERALES.secuenciacion}}"
        },
        "Suma": {
            "Motoras": "{{Suma.Motoras}}"
        },
        "RESULTADO_Orientacion": "{{RESULTADO_Orientacion}}",
        "RESULTADO_Espontanea": "{{RESULTADO_Espontanea}}",
        "RESULTADO_categorias": "{{RESULTADO_categorias}}",
        "RESULTADO_Reconocimiento": "{{RESULTADO_Reconocimiento}}",
        "RESULTADO_Digitos": "{{RESULTADO_Digitos}}",
        "RESULTADO_Deteccion_visual": "{{RESULTADO_Deteccion_visual}}",
        "RESULTADO_Veinte": "{{RESULTADO_Veinte}}",
        "RESULTADO_Fluidez_verbal_semantica": "{{RESULTADO_Fluidez_verbal_semantica}}",
        "RESULTADO_Fluidez_verbal_fonologica": "{{RESULTADO_Fluidez_verbal_fonologica}}",
        "RESULTADO_Denominacion": "{{RESULTADO_Denominacion}}",
        "RESULTADO_Compresion": "{{RESULTADO_Compresion}}",
        "RESULTADO_Repeticion": "{{RESULTADO_Repeticion}}",
        "RESULTADO_Lectura": "{{RESULTADO_Lectura}}",
        "RESULTADO_dictado": "{{RESULTADO_dictado}}",
        "RESULTADO_Semejanzas": "{{RESULTADO_Semejanzas}}",
        "RESULTADO_Calculo": "{{RESULTADO_Calculo}}",
        "RESULTADO_secuenciacion": "{{RESULTADO_secuenciacion}}",
        "RESULTADO_Suma_Motoras": "{{RESULTADO_Suma_Motoras}}"
    }

    # Descargar plantilla
    resultados = drive_service.files().list(
        q=f"'{CARPETA_ORIGEN}' in parents and name contains '.docx' and trashed = false",
        fields="files(id, name)"
    ).execute()
    archivos = resultados.get("files", [])
    if not archivos:
        return JSONResponse(status_code=404, content={"error": "No se encontró plantilla base."})

    file_id = archivos[0]["id"]
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
    context = {**extra_variables, **data.dict()}
    doc.render(context)

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
