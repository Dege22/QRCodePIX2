from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
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
from fastapi.middleware.cors import CORSMiddleware

class PixData(BaseModel):
    chave_aleatoria: str
    nome_beneficiario: str
    cidade_beneficiario: str
    valor_transferencia: float

counter_file_path = 'counter.txt'
fixed_key_file_path = 'fixed_key.txt'
url_counter_file_path = 'url_counter.txt'

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

def reset_pix_counter():
    with open(counter_file_path, 'w') as file:
        file.write('0')

def reset_url_counter():
    url_counter = read_url_counter()
    for url in url_counter.keys():
        url_counter[url] = 0
    write_url_counter(url_counter)

def read_fixed_key():
    if not os.path.exists(fixed_key_file_path):
        with open(fixed_key_file_path, 'w') as file:
            file.write('')
    with open(fixed_key_file_path, 'r') as file:
        return file.read().strip()

def write_fixed_key(chave_aleatoria: str):
    with open(fixed_key_file_path, 'w') as file:
        file.write(chave_aleatoria)

def read_url_counter():
    if not os.path.exists(url_counter_file_path):
        return {}
    with open(url_counter_file_path, 'r') as file:
        url_counter = {}
        for line in file:
            url, count = line.strip().split(',')
            url_counter[url] = int(count)
        return url_counter

def write_url_counter(url_counter):
    with open(url_counter_file_path, 'w') as file:
        for url, count in url_counter.items():
            file.write(f'{url},{count}\n')

def increment_url_counter(url):
    url_counter = read_url_counter()
    if url in url_counter:
        url_counter[url] += 1
    else:
        url_counter[url] = 1
    write_url_counter(url_counter)

app = FastAPI()

# Forçar HTTPS
app.add_middleware(HTTPSRedirectMiddleware)

# Adicionar middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todas as origens
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos
if not os.path.exists('static'):
    os.makedirs('static')
app.mount("/static", StaticFiles(directory="static"), name="static")

def generate_txid() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    hash_digest = hashlib.sha1(timestamp.encode()).hexdigest()[:10]
    txid = f"{timestamp}{hash_digest}"
    return txid

@app.get("/generate-pix/{chave_aleatoria}/{nome_beneficiario}/{cidade_beneficiario}/{valor_transferencia:float}")
async def generate_pix(request: Request, chave_aleatoria: str, nome_beneficiario: str, cidade_beneficiario: str,
                       valor_transferencia: float):
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

@app.get("/generate-pix-fixo/{valor_transferencia:float}")
async def generate_pix_fixo(request: Request, valor_transferencia: float):
    chave_aleatoria = read_fixed_key()
    if not chave_aleatoria:
        return JSONResponse(status_code=400, content={
            "message": "Chave aleatória não está definida. Por favor, defina uma chave primeiro."})

    increment_counter()
    nome_beneficiario = "Smokeria 021"
    cidade_beneficiario = "RIO DE JANEIRO"

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

@app.get("/trocar-chave/{chave_aleatoria}")
async def trocar_chave(chave_aleatoria: str):
    write_fixed_key(chave_aleatoria)
    return JSONResponse(content={"message": f"Chave aleatória substituída com sucesso! Nova chave: {chave_aleatoria}"})

@app.get("/consultar-dados-fixos")
async def consultar_dados_fixos():
    chave_aleatoria = read_fixed_key()
    if not chave_aleatoria:
        return JSONResponse(status_code=400, content={
            "message": "Chave aleatória não está definida. Por favor, defina uma chave primeiro."})

    nome_beneficiario = "Smokeria 021"
    cidade_beneficiario = "SAO PAULO"

    return JSONResponse(content={
        "Chave Aleatoria": chave_aleatoria,
        "Nome": nome_beneficiario,
        "Cidade": cidade_beneficiario
    })

@app.get("/zerar-contagem-pix")
async def zerar_contagem_pix():
    reset_pix_counter()
    return JSONResponse(content={"message": "Contagem de Pix gerados zerada com sucesso!"})

@app.get("/zerar-contagem-visitantes")
async def zerar_contagem_visitantes():
    reset_url_counter()
    return JSONResponse(content={"message": "Contagem de acessos zerada com sucesso!"})

@app.get("/contar-acesso/{var:path}")
async def contar_acesso_var(request: Request, var: str):
    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}/contar-acesso/{var}"
    increment_url_counter(url)
    return JSONResponse(content={"message": f"Acesso registrado para URL: {url}"})

@app.get("/acessos")
async def get_acessos():
    url_counter = read_url_counter()
    return JSONResponse(content=url_counter)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Pega a porta da variável de ambiente ou usa a porta 8000 como padrão
    uvicorn.run(app, host="0.0.0.0", port=port)
