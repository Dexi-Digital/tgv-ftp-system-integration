# FTP System Integration — API REST

Serviço que realiza download automático de arquivos ZIP via FTP-TLS, extrai XMLs com senha dinâmica e os disponibiliza via API REST.

---

## Base URL

```
http://<host>:8000
```

---

## Documentação Interativa (Swagger / OpenAPI)

FastAPI gera automaticamente a documentação interativa da API. Com o serviço em execução, acesse:

| Interface  | URL                              | Descrição                                              |
|------------|----------------------------------|--------------------------------------------------------|
| Swagger UI | `http://<host>:8000/docs`        | Interface interativa para explorar e testar os endpoints |
| ReDoc      | `http://<host>:8000/redoc`       | Documentação em formato de leitura                     |
| OpenAPI JSON | `http://<host>:8000/openapi.json` | Schema bruto em formato OpenAPI 3.x                  |

> O schema OpenAPI pode ser importado em ferramentas como Postman, Insomnia ou qualquer cliente compatível com OpenAPI 3.

---

## Autenticação

Nenhuma autenticação é exigida nos endpoints da API. O acesso ao FTP é configurado via variáveis de ambiente no servidor.

---

## Variáveis de Ambiente

| Variável   | Descrição                        | Obrigatório |
|------------|----------------------------------|-------------|
| `FTP_HOST` | Endereço do servidor FTP         | Sim         |
| `FTP_USER` | Usuário de login no FTP          | Sim         |
| `FTP_PASS` | Senha de login no FTP            | Sim         |

---

## Endpoints

### POST /executar

Dispara manualmente a rotina de integração: conecta ao FTP, localiza o ZIP mais recente com o padrão `TgvYYYYMMDD.zip`, faz o download, descompacta com a senha gerada dinamicamente e armazena o XML extraído em memória.

> A rotina também é executada automaticamente todos os dias às **05:30**.

#### Requisição

```
POST /executar
```

Sem corpo de requisição.

#### Resposta de sucesso

**Status:** `200 OK`

```json
{
  "status": "ok"
}
```

#### Respostas de erro

**Caso 1 — Nenhum ZIP disponível no FTP**

**Status:** `200 OK`

```json
{
  "status": "ok"
}
```

> **Atenção:** a rotina retorna `200 OK` mesmo quando não há ZIP no FTP. Nesse caso, nenhum XML é armazenado. Uma chamada subsequente a `GET /xml` retornará `404`. Consulte a seção [GET /xml — Erros](#respostas-de-erro-1) para tratar esse cenário.

---

**Caso 2 — Falha durante a execução**

**Status:** `500 Internal Server Error`

```json
{
  "detail": "<mensagem de erro>"
}
```

| Causa                                        | Valor de `detail`                                  | O que fazer                                                    |
|----------------------------------------------|----------------------------------------------------|----------------------------------------------------------------|
| Host FTP inacessível ou variável não definida | `"[Errno 11001] getaddrinfo failed"` ou similar   | Verificar `FTP_HOST` e conectividade de rede                   |
| Credenciais FTP inválidas                    | `"530 Login incorrect"` ou similar                 | Verificar `FTP_USER` e `FTP_PASS`                              |
| Falha ao baixar o arquivo do FTP             | Mensagem de erro do protocolo FTP                  | Verificar permissões do usuário FTP no diretório               |
| Senha do ZIP incorreta (data errada)         | `"Bad password for file"` ou similar               | Verificar se o relógio do servidor está correto                |
| ZIP corrompido ou inválido                   | Mensagem da lib `pyzipper`                         | Verificar integridade do arquivo no FTP                        |
| ZIP sem arquivo XML interno                  | `"Nenhum XML encontrado dentro do ZIP"`            | Verificar o conteúdo do ZIP na origem                          |

#### Exemplo com cURL

```bash
curl -X POST http://<host>:8000/executar
```

#### Exemplo com Python

```python
import requests

response = requests.post("http://<host>:8000/executar")

if response.status_code == 200:
    print("Rotina executada.")
    # Não garante que um XML esteja disponível — verifique GET /xml em seguida
elif response.status_code == 500:
    print(f"Falha na execução: {response.json()['detail']}")
```

---

### GET /xml

Retorna o arquivo XML extraído na última execução bem-sucedida da rotina (seja manual via `/executar` ou automática pelo agendador).

Como a resposta usa `Content-Disposition: attachment`, o arquivo pode ser baixado diretamente — via browser, `wget`, `curl` ou qualquer cliente HTTP — sem nenhum processamento adicional.

#### Requisição

```
GET /xml
```

Sem parâmetros.

#### Resposta de sucesso

**Status:** `200 OK`
**Content-Type:** `application/xml`
**Content-Disposition:** `attachment; filename="<nome-do-arquivo>.xml"`

O corpo da resposta é o conteúdo binário do arquivo XML.

#### Respostas de erro

**Status:** `404 Not Found`

```json
{
  "detail": "Nenhum XML disponível"
}
```

| Causa                                                          | O que fazer                                                                            |
|----------------------------------------------------------------|----------------------------------------------------------------------------------------|
| O serviço foi iniciado mas `POST /executar` ainda não rodou   | Chamar `POST /executar` antes de tentar obter o XML                                    |
| A última execução não encontrou nenhum ZIP no FTP             | Aguardar o próximo ciclo (05:30) ou acionar `POST /executar` quando o arquivo estiver disponível |
| O serviço foi reiniciado (variável em memória foi resetada)   | Chamar `POST /executar` para recarregar o XML                                          |
| O arquivo foi deletado do disco após a extração               | Chamar `POST /executar` para baixar e extrair novamente                                |

> **Importante:** o XML é armazenado apenas em memória durante o ciclo de vida do processo. Reiniciar o serviço sem chamar `/executar` novamente tornará o XML indisponível até a próxima execução da rotina.

#### Download direto via browser

Acesse a URL abaixo diretamente no navegador. O browser iniciará o download automaticamente com o nome original do arquivo:

```
http://<host>:8000/xml
```

#### Exemplo com wget

```bash
wget http://<host>:8000/xml
```

O arquivo será salvo com o nome original extraído do ZIP.

#### Exemplo com cURL

```bash
curl -O -J http://<host>:8000/xml
```

#### Exemplo com Python

```python
import requests

response = requests.get("http://<host>:8000/xml")

if response.status_code == 200:
    filename = response.headers["Content-Disposition"].split("filename=")[-1].strip('"')
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"XML salvo em: {filename}")
elif response.status_code == 404:
    print("XML não disponível. Execute POST /executar para carregar o arquivo.")
```

---

## Fluxo de integração recomendado

```
1. POST /executar   →  dispara o download e extração do XML
2. GET  /xml        →  obtém o arquivo XML extraído
```

Em produção, `/executar` normalmente **não precisa ser chamado manualmente**, pois a rotina roda automaticamente às 05:30. Chame-o apenas para forçar uma atualização fora do horário agendado.

---

## Execução local com Docker

```bash
docker build -t ftp-system-integration .

docker run -p 8000:8000 \
  -e FTP_HOST=ftp.exemplo.com \
  -e FTP_USER=usuario \
  -e FTP_PASS=senha \
  ftp-system-integration
```

---

## Execução local sem Docker

```bash
pip install -r requirements.txt
FTP_HOST=ftp.exemplo.com FTP_USER=usuario FTP_PASS=senha uvicorn app:app --host 0.0.0.0 --port 8000
```
