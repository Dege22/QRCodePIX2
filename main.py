from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime
import hashlib
from pixqrcodegen import Payload
import sys
import io
import qrcode
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

class PixData(BaseModel):
    chave_aleatoria: str
    nome_beneficiario: str
    cidade_beneficiario: str
    valor_transferencia: float

counter_file_path = 'counter.txt'

def read_counter():
    if not os.path.exists(counter_file_path):
        with open(counter_file_path, 'w') as file:
            file.write('0')
    with open(counter_file_path, 'r') as file:
        return int(file.read())

def increment_counter():
    count = read_counter() + 1
    with open(counter_file_path, 'w') as file:
        file.write(str(count))
    return count

app = FastAPI()

# Serve Static Files, used for QR code image access
print("Diretório atual:", os.getcwd())
if not os.path.exists('static'):
    os.makedirs('static')
    print("Diretório 'static' criado em:", os.path.abspath('static'))
else:
    print("Diretório 'static' já existe em:", os.path.abspath('static'))
app.mount("/static", StaticFiles(directory="static"), name="static")

def generate_txid() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    hash_digest = hashlib.sha1(timestamp.encode()).hexdigest()[:10]
    txid = f"{timestamp}{hash_digest}"
    return txid

@app.get("/generate-pix/{chave_aleatoria}/{nome_beneficiario}/{cidade_beneficiario}/{valor_transferencia:float}")
async def generate_pix(request: Request, chave_aleatoria: str, nome_beneficiario: str, cidade_beneficiario: str, valor_transferencia: float):
    increment_counter()
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout

    try:
        txid = generate_txid()
        cidade_beneficiario_formatada = cidade_beneficiario.lower().replace(" ", "")
        valor_em_string = f"{valor_transferencia:.2f}"
        payload = Payload(nome_beneficiario, chave_aleatoria, valor_em_string, cidade_beneficiario_formatada, txid)
        codigo_pix = payload.gerarPayload()

        output = new_stdout.getvalue().strip()
        sys.stdout = old_stdout

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(output if codigo_pix is None else codigo_pix)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        qr_code_filename = f"{txid}.png"
        img.save(f"static/{qr_code_filename}")

        return JSONResponse(content={
            "message": "Pix Copia e Cola gerado com sucesso!",
            "pix_code": output if codigo_pix is None else codigo_pix,
            "qr_code_url": f"{request.url_for('static', path=qr_code_filename)}"
        })

    except Exception as e:
        sys.stdout = old_stdout
        return JSONResponse(status_code=500, content={
            "message": "Erro ao gerar o Pix Copia e Cola",
            "error": str(e),
            "Console Output": new_stdout.getvalue().strip()
        })

@app.get("/download/{filename}")
async def download_qr_code(filename: str):
    file_path = f"static/{filename}"
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=filename, media_type='image/png')
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/pix/gerados")
async def get_total_pix_generated():
    total_pix_generated = read_counter()
    return JSONResponse(content={"Total de pix gerados": total_pix_generated})
