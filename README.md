### 🤖 Servizio AI per la Generazione di Unit Test

Il presente repository contiene un'applicazione composta da due componenti principali che cooperano: un **Backend** (implementato in FastAPI) responsabile dell'interazione con l'API LLM e un **Frontend** (basato su Gradio) che fornisce l'interfaccia utente. L'obiettivo del servizio è trasformare il codice sorgente fornito in unit test completi e validi.

Si prega di seguire attentamente i seguenti passaggi per la configurazione e l'avvio del servizio.

### 🛠️ Prerequisiti Operativi

Per l'esecuzione corretta del servizio, è necessario disporre dei seguenti elementi:

1. **Python 3.x:** L'interprete Python è la base per l'esecuzione dell'intero progetto.

2. **Accesso a un Terminale:** È richiesto l'utilizzo di una shell a riga di comando (es. Prompt dei Comandi, PowerShell, Terminale).

L'applicazione è configurata per caricare la chiave d'accesso in modo sicuro tramite variabili d'ambiente, utilizzando il file di configurazione denominato **`.env`**.

#### 1. Installazione delle Dipendenze di Progetto

Tutte le librerie Python necessarie (come FastAPI, Gradio, Groq, ecc.) sono elencate nel file `requirements.txt`<br> 
Per automatizzare l'installazione, è necessario eseguire il seguente comando nel terminale:<br> 
    <p style="text-align:center;">`pip install -r requirements.txt`</p>

> **Avvertenza:** Il processo di installazione può richiedere un breve lasso di tempo, a seconda della velocità della connessione e dello stato dell'ambiente virtuale.

#### 2. Avvio del Servizio (Esecuzione Parallela)

Il Backend e il Frontend sono processi indipendenti che operano in comunicazione tra loro; pertanto, devono essere avviati in sessioni di terminale separate.

##### Passo 2A: Avvio del Backend (Servizio LLM)
Aprire la **prima sessione di terminale** ed eseguire il file di backend usando il comando `python backend_facade.py`. <br>
Questo processo costituisce il servizio API che gestisce la logica LLM ed è in ascolto sulla porta `8000`.

È necessario mantenere questa sessione di terminale attiva e in esecuzione per tutta la durata dell'utilizzo del servizio.

##### Passo 2B: Avvio del Frontend (Interfaccia Utente)

Aprire la **seconda sessione di terminale** e avviare l'interfaccia Gradio usando il comando `python frontend_facade.py`.

Dopo l'avvio, il terminale fornirà un URL locale (tipicamente `http://127.0.0.1:7860`).

**Aprire il link fornito in un browser web.**

### 🚀 Istruzioni per l'Utilizzo del Servizio AI

1. **Inserimento Codice:** Incollare la funzione o la classe del codice sorgente nell'area etichettata "Codice da testare".

2. **Selezione Linguaggio:** Selezionare il linguaggio di programmazione corretto (Python, Java, C#, ecc.) tramite il menu a tendina "Linguaggio del Codice".

3. **Generazione:** Premere il pulsante **"Genera Test"**.

L'output, contenente gli unit test completi per la funzione fornita, verrà visualizzato nella finestra della chat in pochi secondi.

