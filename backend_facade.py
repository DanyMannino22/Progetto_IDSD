# backend_facade.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente da un file .env
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

# --- Validazione della chiave API ---
if not groq_api_key:
    raise ValueError("La variabile d'ambiente GROQ_API_KEY non è stata impostata.")

app = FastAPI(
    title="Test Generation Service",
    description="Un microservizio che utilizza un LLM per generare unit test da codice sorgente.",
    version="1.0.0"
)

# Inizializza il client Groq
client = Groq(api_key=groq_api_key)

# --- Modello di Richiesta Strutturata ---
# Invece di una stringa generica, definiamo un modello di dati
# specifico per la nostra operazione. Questo rende l'API più chiara e robusta.
class TestGenerationRequest(BaseModel):
    code: str
    language: str

# --- Implementazione del Pattern Remote Facade ---
# Questo endpoint agisce come una "facciata remota".
# Nasconde la complessità della costruzione del prompt e dell'interazione con l'LLM.
# Il client (frontend) deve solo conoscere questa interfaccia semplice e specifica.
@app.post("/generate-tests", summary="Genera Unit Test per il codice fornito")
async def generate_tests(request: TestGenerationRequest):
    """
    Prende in input codice sorgente e un linguaggio, costruisce un prompt
    specifico per la generazione di test e interroga l'LLM.

    - **request**: Un oggetto JSON con i campi 'code' and 'language'.
    - **return**: Il codice dei test generato dall'LLM.
    """
    # 1. La logica di costruzione del prompt è incapsulata qui, nel backend.
    #    Il frontend non ha bisogno di sapere come formulare questa richiesta.
    prompt = f"""
    Sei un ingegnere del software esperto specializzato in testing.
    Il tuo compito è scrivere unit test chiari, concisi e completi.
    Scrivi gli unit test per la seguente classe in linguaggio {request.language}.
    Assicurati di coprire i casi principali e i casi limite (edge cases).
    Fornisci solo il codice del test, senza spiegazioni aggiuntive.

    Codice da testare:
    ```{request.language}
    {request.code}
    ```
    """

    try:
        # 2. Interazione con il servizio complesso (LLM)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2, # Bassa temperatura per risposte più deterministiche e focalizzate sul codice
            max_tokens=2048  # Imposta un limite ragionevole per il codice generato
        )
        
        generated_test_code = chat_completion.choices[0].message.content
        return {"test_code": generated_test_code}

    except Exception as e:
        # Gestione robusta degli errori
        print(f"ERRORE DETTAGLIATO: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante la comunicazione con l'LLM: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Esegui il server sulla porta 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
