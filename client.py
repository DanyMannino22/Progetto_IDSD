import gradio as gr
import requests

# L'URL del nostro backend con l'endpoint specifico della Facade
BACKEND_URL = "http://127.0.0.1:8000/generate-tests"

# --- Funzione che interagisce con la Facade Remota ---
def get_unit_tests(code, language, history):
    """
    Invia il codice e il linguaggio al backend per la generazione e l'esecuzione dei test.
    """
    if not code or not language:
        history = history or []
        history.append(("Mancano dati", "Per favore, inserisci sia il codice che il linguaggio prima di inviare."))
        return history, ""

    try:
        payload = {"code": code, "language": language}
        response = requests.post(BACKEND_URL, json=payload)
        
        # Controlla se la richiesta ha avuto successo
        response.raise_for_status() 
        
        response_data = response.json()
        
        # Estrazione di entrambi i campi
        test_code = response_data.get("test_code", "Nessun codice di test ricevuto.")
        execution_result = response_data.get("execution_result", "Nessun risultato di esecuzione ricevuto.")
        
        # Formattazione del messaggio per il client
        bot_message = (
            f"**Codice Test Generato ({language}):**\n"
            f"```{language}\n{test_code}\n```\n\n"
            f"**Risultato dell'Esecuzione:**\n"
            f"```text\n{execution_result}\n```"
        )
        
        # Aggiunge l'input dell'utente e la risposta del bot alla cronologia della chat
        history = history or []
        history.append((f"Codice sorgente ({language}):\n```\n{code}\n```", bot_message))
        
        # Ritorna la cronologia aggiornata e pulisce la textbox del codice
        return history, ""

    except requests.exceptions.RequestException as e:
        # Gestisce errori di connessione o HTTP
        error_detail = e.response.json().get('detail', 'Nessun dettaglio errore.') if e.response is not None and e.response.content else str(e)
        error_message = f"Errore di comunicazione con il backend: {error_detail}"
        print(f"ERRORE FRONTEND: {error_message}")
        history = history or []
        history.append((code, error_message))
        return history, ""
    except Exception as e:
        # Gestisce altri errori imprevisti
        error_message = f"Si è verificato un errore: {str(e)}"
        print(f"ERRORE GENERICO: {error_message}")
        history = history or []
        history.append((code, error_message))
        return history, ""

# --- Interfaccia Utente con Gradio ---
with gr.Blocks(theme=gr.themes.Glass(), css=".example { padding: 8px; } .gr-chatbot { height: 400px !important; }") as demo:
    gr.Markdown("# 🤖 Assistente AI per la Generazione di Unit Test")
    gr.Markdown("Inserisci una classe o una funzione e seleziona il linguaggio. L'AI genererà gli unit test per te.")

    with gr.Row():
        chatbot = gr.Chatbot(label="Conversazione", bubble_full_width=False, height=400)

    with gr.Row():
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
