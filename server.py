from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
import os
from dotenv import load_dotenv
import time
from pathlib import Path
import shutil
import re
import subprocess
from starlette.concurrency import run_in_threadpool # Importato per threading

# Carica le variabili d'ambiente da un file .env
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

# --- Validazione della chiave API ---
if not groq_api_key:
    raise ValueError("La variabile d'ambiente GROQ_API_KEY non è stata impostata.")

# --- Configurazione del Salvataggio File ---
# La variabile globale che definisce il percorso della cartella
OUTPUT_DIR = Path("generated_files")

# Inizializza l'applicazione FastAPI
app = FastAPI(
    title="Test Generation Service",
    description="Un microservizio che utilizza un LLM per generare unit test da codice sorgente.",
    version="1.0.0"
)

# --- Gestore di Shutdown per la pulizia ---
@app.on_event("shutdown")
def delete_output_directory():
    """Rimuove la directory di output quando il server viene spento."""
    if OUTPUT_DIR.is_dir():
        try:
            shutil.rmtree(OUTPUT_DIR)
            print(f"\n[SHUTDOWN] Cartella di output rimossa con successo: {OUTPUT_DIR.resolve()}")
        except Exception as e:
            print(f"\n[ERRORE SHUTDOWN] Impossibile rimuovere la cartella {OUTPUT_DIR}: {e}")

# Inizializza il client Groq
client = Groq(api_key=groq_api_key)

# --- Funzione Ausiliaria per la Pulizia del Codice LLM ---
def clean_generated_code(response: str) -> str:
    """Estrae il codice contenuto all'interno del primo blocco di codice (```) trovato."""
    # Pattern corretto
    code_block_pattern = re.compile(r"^\s*```[a-zA-Z0-9#+\s-]*\n(.*?)\n\s*```\s*$", re.DOTALL | re.MULTILINE)
    
    match = code_block_pattern.search(response)
    
    if match:
        return match.group(1).strip()
    
    return response.strip()

# --- Funzione Ausiliaria per il Salvataggio File ---
def save_code_to_file(content: str, file_type: str, language: str, timestamp: str) -> str:
    """Salva il contenuto in un file locale e restituisce il percorso assoluto."""
    extension_map = {
        "python": "py", "java": "java", "javascript": "js", 
        "typescript": "ts", "c#": "cs"
    }
    lang_lower = language.lower().replace("#", "sharp") 
    ext = extension_map.get(lang_lower, "txt")
    
    # Per Python, il codice sorgente viene salvato come 'target_module' per l'importazione
    if language.lower() == "python" and file_type == "source":
        filename = "target_module.py"
    else:
        filename = f"{timestamp}_{file_type}_{lang_lower}.{ext}"
        
    file_path = OUTPUT_DIR / filename
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Salvataggio completato: {filename}")
        return str(file_path.resolve()) # Restituisce il percorso assoluto
    except Exception as e:
        print(f"Errore durante il salvataggio del file {filename}: {e}")
        return ""

# --- Funzione per l'Esecuzione dei Test (Sincrona) ---
def execute_tests(language: str, source_path_str: str, test_path_str: str) -> str:
    """
    Esegue i test sul codice fornito utilizzando subprocess.
    Questa funzione è sincrona e deve essere eseguita in un threadpool.
    """
    language = language.lower()
    working_dir = Path(source_path_str).parent
    
    if language == "python":
        
        # 1. Creiamo un file __init__.py per trattare la cartella come un modulo Python.
        init_file = working_dir / "__init__.py"
        init_file.touch()
        
        test_file_name = Path(test_path_str).name

        try:
            # Comando: python -m unittest -v <nome_file_test>
            command = ["python", "-m", "unittest", "-v", test_file_name]
            
            # Esecuzione del comando
            result = subprocess.run(
                command, 
                cwd=working_dir, 
                capture_output=True, 
                text=True, 
                timeout=15 
            )
            
            # Restituisce l'output combinato per mostrare successi e fallimenti
            output = result.stdout + result.stderr
            
            # Pulizia: rimuove il file __init__.py dopo l'esecuzione
            init_file.unlink()
            
            return output
        
        except subprocess.TimeoutExpired:
            return "Execution Error: Test execution timed out (max 15 seconds)."
        except FileNotFoundError:
            return "Execution Error: Python interpreter ('python' command) not found."
        except Exception as e:
            return f"Execution Error: An unexpected error occurred during execution: {e}"

    elif language in ["java", "c#", "javascript", "typescript"]:
        return f"Test execution not fully implemented for {language}."
    
    else:
        return f"Language {language} not supported for execution."

# --- Modello di Richiesta Strutturata ---
class TestGenerationRequest(BaseModel):
    code: str
    language: str

# --- Implementazione del Pattern Remote Facade (Asincrono) ---
@app.post("/generate-tests", summary="Genera Unit Test per il codice fornito")
async def generate_tests(request: TestGenerationRequest):
    """Genera, salva ed esegue i test sul codice sorgente."""
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    prompt = f"""
    Sei un ingegnere del software esperto specializzato in testing.
    Il tuo compito è scrivere unit test chiari, concisi e completi.
    Scrivi gli unit test per la seguente classe in linguaggio {request.language}.
    Assicurati di coprire i casi principali e i casi limite (edge cases).
    Fornisci **SOLO** il codice del test. Non includere spiegazioni, introduzioni, conclusioni, o delimitatori del blocco di codice (come ```python o ```).
    Per i test in Python, includi l'istruzione 'import unittest' e fai riferimento al codice da testare come se fosse importato da un modulo chiamato 'target_module' (ad esempio: 'from target_module import NomeDellaTuaClasse').

    Codice da testare:
    ```{request.language}
    {request.code}
    ```
    """

    try:
        # 1. Chiamata LLM
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.2,
            max_tokens=2048
        )
        
        raw_generated_code = chat_completion.choices[0].message.content
        generated_test_code = clean_generated_code(raw_generated_code)

        # 2. POST-PROCESSING: GARANTISCI L'IMPORT DI UNITTEST PER PYTHON
        if request.language.lower() == "python":
            if "import unittest" not in generated_test_code:
                # Inserisce l'import all'inizio
                generated_test_code = "import unittest\n" + generated_test_code

        # 3. Logica di SALVATAGGIO LOCALE
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        source_path_str = save_code_to_file(
            content=request.code, file_type="source", language=request.language, timestamp=timestamp
        )
        test_path_str = save_code_to_file(
            content=generated_test_code, file_type="test", language=request.language, timestamp=timestamp
        )

        test_result = "Execution skipped: Files not saved successfully."
        
        if source_path_str and test_path_str:
            # 4. ESECUZIONE DEI TEST IN THREADPOOL
            # run_in_threadpool sposta la funzione sincrona (execute_tests) in un thread
            test_result = await run_in_threadpool(
                execute_tests, 
                request.language, 
                source_path_str, 
                test_path_str
            )

        # 5. Ritorna il risultato al frontend
        return {
            "test_code": generated_test_code,
            "execution_result": test_result
        }

    except Exception as e:
        # Gestione robusta degli errori
        print(f"ERRORE DETTAGLIATO: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante la comunicazione con l'LLM: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Esegui il server sulla porta 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)