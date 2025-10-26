# frontend_facade.py
import gradio as gr
import requests

# L'URL del nostro backend con l'endpoint specifico della Facade
BACKEND_URL = "http://127.0.0.1:8000/generate-tests"

# --- Funzione che interagisce con la Facade Remota ---
# Questa funzione ora è molto più semplice. Raccoglie i dati strutturati
# dall'interfaccia utente e li invia all'endpoint corretto.
def get_unit_tests(code, language, history):
    """
    Invia il codice e il linguaggio al backend per la generazione dei test.
    """
    if not code or not language:
        # Aggiunge un messaggio di errore alla chat se i campi non sono compilati
        history = history or []
        history.append(("Mancano dati", "Per favore, inserisci sia il codice che il linguaggio prima di inviare."))
        return history, ""

    try:
        # La richiesta ora invia un JSON strutturato, come richiesto dalla Pydantic model del backend.
        payload = {"code": code, "language": language}
        response = requests.post(BACKEND_URL, json=payload)
        
        # Controlla se la richiesta ha avuto successo
        response.raise_for_status() 
        
        bot_message = response.json().get("test_code", "Nessun codice di test ricevuto.")
        
        # Aggiunge l'input dell'utente e la risposta del bot alla cronologia della chat
        history = history or []
        history.append((f"Codice ({language}):\n```\n{code}\n```", bot_message))
        
        # Ritorna la cronologia aggiornata e pulisce la textbox del codice
        return history, ""

    except requests.exceptions.RequestException as e:
        # Gestisce errori di connessione o HTTP
        error_message = f"Errore di comunicazione con il backend: {str(e)}"
        print(error_message)
        history = history or []
        history.append((code, error_message))
        return history, ""
    except Exception as e:
        # Gestisce altri errori imprevisti
        error_message = f"Si è verificato un errore: {str(e)}"
        print(error_message)
        history = history or []
        history.append((code, error_message))
        return history, ""

# --- Interfaccia Utente con Gradio ---
with gr.Blocks(theme=gr.themes.Glass(), css=".example { padding: 8px; } .gr-chatbot { height: 400px !important; }") as demo:
    gr.Markdown("# 🤖 Assistente AI per la Generazione di Unit Test")
    gr.Markdown("Inserisci una classe o una funzione e seleziona il linguaggio. L'AI genererà gli unit test per te.")

    with gr.Row():
        # Il chatbot ora occupa più spazio per una migliore leggibilità
        chatbot = gr.Chatbot(label="Conversazione", bubble_full_width=False, height=400)

    with gr.Row():
        # Input strutturati: un'area di testo per il codice e un menu a tendina per il linguaggio
        code_input = gr.Code(label="Codice da testare", language=None, lines=10)
    
    with gr.Row():
        language_input = gr.Dropdown(
            ["Java", "Python", "JavaScript", "TypeScript", "C#"], 
            label="Linguaggio del Codice"
        )
        submit_btn = gr.Button("🚀 Genera Test", variant="primary")

    def clear_chat():
        return [], "", ""

    clear_btn = gr.Button("Pulisci Chat", variant="stop")

    # Associazione degli eventi ai componenti dell'interfaccia
    submit_btn.click(
        fn=get_unit_tests, 
        inputs=[code_input, language_input, chatbot], 
        outputs=[chatbot, code_input]
    )
    
    clear_btn.click(
        fn=clear_chat, 
        inputs=None, 
        outputs=[chatbot, code_input, language_input]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
