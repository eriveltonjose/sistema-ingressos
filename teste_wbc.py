import requests

url = "http://189.90.139.178:2020/AMBR/wsCpfValidos.rule?sys=WBC"

payload = {
    "cpf": "26193841687",
    "tipo": "01"
}

try:
    r = requests.get(
        url,
        json=payload,
        timeout=30
    )

    print("STATUS:", r.status_code)
    print("RESPOSTA:")
    print(r.text)

except Exception as e:
    print("ERRO:")
    print(e)