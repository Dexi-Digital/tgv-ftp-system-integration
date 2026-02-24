import os
import re
import ftplib
import pyzipper
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from apscheduler.schedulers.background import BackgroundScheduler

# ==============================
# CONFIGURAÇÕES
# ==============================

FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_PATH = "/"

API_KEY = os.getenv("API_KEY")

LOCAL_DOWNLOAD_DIR = "downloads"
LOCAL_EXTRACT_DIR = "extracted"

os.makedirs(LOCAL_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(LOCAL_EXTRACT_DIR, exist_ok=True)

app = FastAPI()
scheduler = BackgroundScheduler()

ultimo_xml_extraido = None


# ==============================
# AUTENTICAÇÃO
# ==============================

api_key_header = APIKeyHeader(name="X-API-Key")

def verificar_api_key(x_api_key: str = Depends(api_key_header)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")


# ==============================
# FUNÇÕES PRINCIPAIS
# ==============================

def gerar_senha():
    now = datetime.now()
    return f"TGV@{now.year}{str(now.month).zfill(2)}#"


def conectar_ftp():
    ftp = ftplib.FTP_TLS(FTP_HOST)
    ftp.login(FTP_USER, FTP_PASS)
    ftp.prot_p()  # Ativa criptografia no canal de dados
    ftp.cwd(FTP_PATH)
    return ftp


def listar_zip_mais_recente():
    ftp = conectar_ftp()
    arquivos = ftp.nlst()
    ftp.quit()

    regex = re.compile(r"Tgv(\d{8})\.zip", re.IGNORECASE)
    zips = [f for f in arquivos if regex.match(f)]

    if not zips:
        return None

    zips.sort(reverse=True)
    return zips[0]


def baixar_arquivo(nome_arquivo):
    ftp = conectar_ftp()
    caminho_local = os.path.join(LOCAL_DOWNLOAD_DIR, nome_arquivo)

    with open(caminho_local, "wb") as f:
        ftp.retrbinary(f"RETR {nome_arquivo}", f.write)

    ftp.quit()
    return caminho_local


def extrair_zip(caminho_zip, senha):
    global ultimo_xml_extraido

    with pyzipper.AESZipFile(caminho_zip) as zf:
        zf.setpassword(senha.encode())
        zf.extractall(LOCAL_EXTRACT_DIR)

        arquivos_extraidos = zf.namelist()
        xmls = [f for f in arquivos_extraidos if f.lower().endswith(".xml")]

        if not xmls:
            raise Exception("Nenhum XML encontrado dentro do ZIP")

        ultimo_xml_extraido = os.path.join(LOCAL_EXTRACT_DIR, xmls[0])

    return ultimo_xml_extraido


def rotina_principal():
    print("Iniciando rotina FTP...")

    zip_name = listar_zip_mais_recente()
    if not zip_name:
        print("Nenhum ZIP encontrado.")
        return

    print(f"ZIP encontrado: {zip_name}")

    senha = gerar_senha()
    print(f"Senha gerada: {senha}")

    caminho_zip = baixar_arquivo(zip_name)
    print("Download concluído.")

    caminho_xml = extrair_zip(caminho_zip, senha)
    print(f"XML extraído em: {caminho_xml}")


# ==============================
# AGENDAMENTO (cron 05:30)
# ==============================

scheduler.add_job(rotina_principal, "cron", hour=5, minute=30)
scheduler.start()


# ==============================
# API REST
# ==============================

@app.post("/executar", dependencies=[Depends(verificar_api_key)])
def executar_manual():
    try:
        rotina_principal()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/xml", dependencies=[Depends(verificar_api_key)])
def obter_xml():
    if not ultimo_xml_extraido or not os.path.exists(ultimo_xml_extraido):
        raise HTTPException(status_code=404, detail="Nenhum XML disponível")

    return FileResponse(
        ultimo_xml_extraido,
        media_type="application/xml",
        filename=os.path.basename(ultimo_xml_extraido),
    )
