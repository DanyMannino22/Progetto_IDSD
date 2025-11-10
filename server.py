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
from starlette.concurrency import run_in_threadpool  # Import per l'esecuzione asincrona

# Carica le variabili d'ambiente
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    # Solleva un'eccezione se la chiave API manca
    raise ValueError("La variabile d'ambiente GROQ_API_KEY non è stata impostata.")

# --- Costanti e Configurazione ---
OUTPUT_DIR = Path("generated_files")
JAVA_MAIN_DIR = Path("src") / "main" / "java"
JAVA_TEST_DIR = Path("src") / "test" / "java"

# Contenuto di un pom.xml minimalista per JUnit 5
POM_CONTENT = """
<project xmlns="http://maven.apache.org/POM/4.0.0"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.ai</groupId>
    <artifactId>generated-tests</artifactId>
    <version>1.0</version>
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <junit.jupiter.version>5.9.1</junit.jupiter.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>${junit.jupiter.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.0.0-M5</version>
            </plugin>
        </plugins>
    </build>
</project>
"""

app = FastAPI(
    title="Test Generation Service",
    description="Microservizio che utilizza un LLM per generare ed eseguire unit test.",
    version="1.0.0"
)
client = Groq(api_key=groq_api_key)

# --- Gestore di Shutdown per la pulizia ---
@app.on_event("shutdown")
def delete_output_directory():
    if OUTPUT_DIR.is_dir():
        try:
            shutil.rmtree(OUTPUT_DIR)
            print(f"\n[SHUTDOWN] Cartella di output rimossa: {OUTPUT_DIR.resolve()}")
        except Exception as e:
            print(f"\n[ERRORE SHUTDOWN] Impossibile rimuovere la cartella {OUTPUT_DIR}: {e}")

# --- Funzioni di Utility ---

def clean_generated_code(response: str) -> str:
    """Estrae il codice contenuto all'interno del primo blocco di codice (```) trovato."""
    code_block_pattern = re.compile(r"^\s*```[a-zA-Z0-9#+\s-]*\n(.*?)\n\s*```\s*$", re.DOTALL | re.MULTILINE)
    match = code_block_pattern.search(response)
    if match:
        return match.group(1).strip()
    return response.strip()

def extract_class_name(code: str) -> str:
    """Estrae il nome della classe dal codice sorgente o di test Java/Python."""
    # Pattern per Java (class Nome) o Python (class Nome(...))
    match = re.search(r'(?:public\s+)?class\s+(\w+)', code)
    if match:
        return match.group(1)
    return f"Target_{time.strftime('%H%M%S')}"

def clean_java_files(working_dir: Path):
    """Rimuove tutti i file .java e pom.xml dalla directory di lavoro."""
    # Rimuove pom.xml
    pom_file = working_dir / "pom.xml"
    if pom_file.exists():
        pom_file.unlink()

    # Rimuove i file .java in tutta la struttura Maven
    for root, _, files in os.walk(working_dir, topdown=False):
        for file in files:
            if file.endswith(".java"):
                try:
                    os.unlink(Path(root) / file)
                except OSError as e:
                    print(f"Errore rimozione file: {e}")
    # Tentativo di rimuovere le directory Maven vuote per pulizia
    try:
        if (working_dir / 'src').is_dir():
             shutil.rmtree(working_dir / 'src', ignore_errors=True)
        if (working_dir / 'target').is_dir():
             shutil.rmtree(working_dir / 'target', ignore_errors=True)
    except Exception:
        pass


def save_code_to_file(content: str, file_type: str, language: str, timestamp: str) -> str:
    """Salva il contenuto in un file temporaneo e restituisce il percorso assoluto."""
    extension_map = {"python": "py", "java": "java", "javascript": "js", "typescript": "ts", "c#": "cs"}
    lang_lower = language.lower().replace("#", "sharp") 
    
    if language.lower() == "python" and file_type == "source":
        # Nome fisso per il modulo Python da importare (corrisponde al prompt)
        filename = "target_module.py"
    else:
        ext = extension_map.get(lang_lower, "txt")
        filename = f"{timestamp}_{file_type}_{lang_lower}.{ext}"
        
    file_path = OUTPUT_DIR / filename
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(file_path.resolve())
    except Exception as e:
        print(f"Errore durante il salvataggio del file {filename}: {e}")
        return ""

# --- Funzione per l'Esecuzione dei Test (Sincrona) ---

def execute_tests(language: str, source_path_str: str, test_path_str: str) -> str:
    """
    Esegue i test sul codice fornito (Python o Java). 
    Questa funzione è sincrona e viene eseguita in un threadpool.
    """
    language = language.lower()
    working_dir = Path(source_path_str).parent
    
    # Assicurati di leggere dal disco i contenuti salvati in caso di modifica del post-processing
    source_content = Path(source_path_str).read_text(encoding="utf-8")
    test_content = Path(test_path_str).read_text(encoding="utf-8")
    
    # --- LOGICA PYTHON ---
    if language == "python":
        
        init_file = working_dir / "__init__.py"
        init_file.touch() # Rende la cartella un pacchetto Python per l'importazione
        test_file_name = Path(test_path_str).name

        try:
            # Esegui unittest sulla cartella (che contiene i file sorgente e test)
            command = ["python", "-m", "unittest", "-v", test_file_name] 
            result = subprocess.run(
                command, cwd=working_dir, capture_output=True, text=True, timeout=15 
            )
            
            output = result.stdout + result.stderr
            init_file.unlink()
            return output
        
        except subprocess.TimeoutExpired:
            return "Execution Error: Python execution timed out (max 15 seconds)."
        except FileNotFoundError:
            return "Execution Error: Python interpreter ('python' command) not found."
        except Exception as e:
            return f"Execution Error: An unexpected error occurred during Python execution: {e}"

    # --- LOGICA JAVA (Maven) ---
    elif language == "java":
        
        # 1. Setup Struttura Maven
        main_dir = working_dir / JAVA_MAIN_DIR
        test_dir = working_dir / JAVA_TEST_DIR
        main_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Scrittura dei file nei percorsi Maven
        source_class_name = extract_class_name(source_content)
        test_class_name = extract_class_name(test_content)
        
        # Sovrascrive i file nella struttura Maven (importante)
        (main_dir / f"{source_class_name}.java").write_text(source_content, encoding="utf-8")
        (test_dir / f"{test_class_name}.java").write_text(test_content, encoding="utf-8")
        
        # 3. Scrittura pom.xml
        (working_dir / "pom.xml").write_text(POM_CONTENT, encoding="utf-8")
        
        # 4. Esecuzione Maven
        try:
            command = "mvn test" 
            
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=45,
                shell=True
            )
            
            output = result.stdout + result.stderr
            
            # Parsing dell'output di Maven
            if "BUILD SUCCESS" in output:
                return "Maven BUILD SUCCESS. Output completo dell'esecuzione:\n\n" + output
            
            elif "BUILD FAILURE" in output:
                 # Troncamento dell'output per non sovraccaricare il frontend
                 return "Maven BUILD FAILURE. Compilazione o fallimento dei test.\n\n" + output[-3000:] 
                 
            return output 
            
        except subprocess.TimeoutExpired:
            return "Execution Error: Maven execution timed out (max 45 seconds)."
        except FileNotFoundError:
            return "Execution Error: Maven ('mvn' command) non trovato. Assicurati che Maven sia installato e nel tuo PATH."
        except Exception as e:
            return f"Execution Error: Errore imprevisto durante l'esecuzione Maven: {e}"

    # --- Altri Linguaggi ---
    elif language in ["c#", "javascript", "typescript"]:
        return f"Test execution non implementata per {language}."
    else:
        return f"Linguaggio {language} non supportato per l'esecuzione."

# --- Modello di Richiesta Strutturata ---
class TestGenerationRequest(BaseModel):
    code: str
    language: str

# --- Implementazione del Pattern Remote Facade (Asincrono) ---

@app.post("/generate-tests", summary="Genera Unit Test per il codice fornito")
async def generate_tests(request: TestGenerationRequest):
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Pulizia preliminare in base al linguaggio
    if request.language.lower() == "java":
        clean_java_files(OUTPUT_DIR)
    
    # Estrae il nome della classe per l'uso nel prompt e nel post-processing
    source_class_name = extract_class_name(request.code)
    
    prompt = f"""
    Sei un ingegnere del software esperto specializzato in testing. Il tuo compito è scrivere unit test chiari, concisi e completi per il codice fornito, utilizzando il linguaggio **{request.language}**.

    **REGOLE GENERALI:**
    1. Fornisci SOLO il codice del test. Non includere spiegazioni, introduzioni, conclusioni, o delimitatori del blocco di codice (come ```java o ```python).
    2. Il valore atteso nell'asserzione DEVE essere matematicamente CORRETTO.

    **REGOLE SPECIFICHE PER LINGUAGGIO ({request.language}):**
    
    [IF JAVA]:
    - **JUnit 5:** Utilizza sempre JUnit 5. Includi l'importazione per l'annotazione @Test. Includi l'import statico completo: `import static org.junit.jupiter.api.Assertions.*;`.
    - **Getter:** Assumi l'esistenza di un metodo **getter pubblico standard** (es. `getNome()`) per accedere ai campi privati.
    - **Output:** Non creare asserzioni su metodi che scrivono solo su console (`System.out.println`).
    
    [IF PYTHON]:
    - **Unittest:** Utilizza il modulo standard `unittest`.
    - **Importazione:** Devi importare il codice da testare usando l'esatta sintassi: `from target_module import {source_class_name}`. **È CRUCIALE usare 'target\_module', non il nome della classe.**
    - **Mocking:** Usa `unittest.mock.patch` per catturare l'output su console (`sys.stdout`) se necessario per testare metodi che usano `print()`.

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

        # 2. POST-PROCESSING (Correzioni per robustezza)
        
        if request.language.lower() == "python":
            
            # 2.1. Assicura l'import unittest
            if "import unittest" not in generated_test_code:
                generated_test_code = "import unittest\n" + generated_test_code

            if "import io" not in generated_test_code and "StringIO" in generated_test_code:
                # Aggiunge 'import io' subito dopo le altre importazioni standard
                generated_test_code = generated_test_code.replace("import unittest", "import unittest\nimport io", 1)
                
            # 2.2. CORREZIONE CRUCIALE: Assicura l'importazione della classe da target_module
            correct_import_statement = f"from target_module import {source_class_name}"
            
            # Pattern per trovare import [qualcosa] import [NomeClasse]
            import_pattern = re.compile(r"from\s+\w+\s+import\s+" + re.escape(source_class_name), re.IGNORECASE)
            
            if import_pattern.search(generated_test_code):
                # Se c'è un import esistente (corretto o errato), lo sostituiamo con l'import corretto
                generated_test_code = import_pattern.sub(correct_import_statement, generated_test_code, 1)
            else:
                # Se manca del tutto, lo aggiungiamo subito dopo 'import unittest'
                generated_test_code = generated_test_code.replace("import unittest", f"import unittest\n{correct_import_statement}", 1)

            
        elif request.language.lower() == "java":
            # Correzione Java: assicura l'import @Test
            junit_test_import = "import org.junit.jupiter.api.Test;"
            if junit_test_import not in generated_test_code:
                generated_test_code = junit_test_import + "\n" + generated_test_code

        # 3. Logica di SALVATAGGIO LOCALE
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Salviamo il codice sorgente (che in Python sarà target_module.py)
        source_path_str = save_code_to_file(
            content=request.code, file_type="source", language=request.language, timestamp=timestamp
        )
        # Salviamo il codice di test (che potrebbe essere stato modificato dal post-processing)
        test_path_str = save_code_to_file(
            content=generated_test_code, file_type="test", language=request.language, timestamp=timestamp
        )

        test_result = "Execution skipped: Files not saved successfully."
        
        if source_path_str and test_path_str:
            # 4. ESECUZIONE DEI TEST IN THREADPOOL
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
        print(f"ERRORE DETTAGLIATO: {e}")
        raise HTTPException(status_code=500, detail=f"Errore durante la comunicazione con l'LLM: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Avviare il backend sulla porta 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
