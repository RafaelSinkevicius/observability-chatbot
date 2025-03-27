from flask import Flask, request, render_template, jsonify, session
from flask_session import Session
import requests
from prometheus_client import start_http_server
from groq import Groq
import re
from dotenv import load_dotenv
import os

# Configuração do Flask
app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'super_secret_key'
Session(app)

# Configuração do Groq API
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

MIXTRAL_MODEL = "mixtral-8x7b-32768"

# Endpoint da API do Prometheus
PROMETHEUS_URL = "http://prometheus:9090/api/v1/query"
LOKI_URL = "http://loki:3100/loki/api/v1/query"
TEMPO_URL = "http://tempo:3200/api/traces"

# Funções auxiliares para consultas
def query_loki(log_query):
    """Consulta logs no Loki."""
    response = requests.get(LOKI_URL, params={"query": log_query}, timeout=5)
    if response.status_code == 200:
        return response.json()
    return {"error": "Erro ao consultar Loki."}

def query_tempo(trace_id):
    """Consulta traces no Tempo."""
    response = requests.get(f"{TEMPO_URL}/{trace_id}", timeout=5)
    if response.status_code == 200:
        return response.json()
    return {"error": "Erro ao consultar Tempo."}

def query_prometheus(metric_name):
    """Consulta métricas no Prometheus."""
    response = requests.get(PROMETHEUS_URL, params={"query": metric_name}, timeout=5)
    if response.status_code == 200:
        return response.json()
    return {"error": "Erro ao consultar Prometheus."}

def list_metrics():
    """Lista todas as métricas disponíveis no Prometheus através do Grafana."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/label/__name__/values", timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                return data["data"]  # Lista de métricas
        return []
    except Exception as e:
        return {"error": f"Erro ao listar métricas: {str(e)}"}

# Rotas Flask
@app.route("/", methods=["GET"])
def welcome():
    return render_template("index.html")

@app.route("/metrics", methods=["GET"])
def get_metrics():
    """Retorna a lista de métricas disponíveis."""
    metrics = list_metrics()
    if isinstance(metrics, list):
        return jsonify({"metrics": metrics})
    return jsonify(metrics)

@app.route("/ask", methods=["POST"])
def ask_question():
    try:
        user_input = request.json.get("question", "").strip().lower()

        available_metrics = list_metrics()
        if isinstance(available_metrics, list) and any(user_input in metric for metric in available_metrics):
            query = next(metric for metric in available_metrics if user_input in metric)
            metric_description = f"Métrica correspondente encontrada: {query}"

        if 'conversation' not in session:
            session['conversation'] = []

        session['conversation'].append({"role": "user", "content": user_input})

        # Contexto para o modelo Groq
        
        context = (
            "Você é um Especialista em Métricas Prometheus, Logs Loki e Traces Tempo"

            "Sua principal função é interpretar perguntas e solicitações sobre métricas (Prometheus), logs (Loki) e" 
            "traces (Tempo), traduzindo-as em consultas precisas e fornecendo respostas detalhadas e acionáveis" 
            "com base nos resultados obtidos."

            "Objetivo Principal"
            "- Auxiliar os usuários a acessar e entender dados específicos relacionados ao desempenho de" 
            "sistemas, infraestrutura e eventos monitorados por Prometheus, Loki e Tempo."

            "- Oferecer insights claros e explicativos com base nos dados extraídos das métricas, logs ou traces."

            "Instruções"
            "1. Criação de Consultas Dinâmicas"
                "- Sempre que o usuário solicitar informações, interprete as perguntas e gere consultas" 
                "específicas para:"
                    "- Prometheus: Para métricas quantitativas e séries temporais."
                    "- Loki: Para consultas baseadas em logs."
                    "- Tempo: Para análise de traces (distribuição de eventos e latência)."

            "2. Extração de Parâmetros do Prompt"
                "- Sempre que possível, extraia os seguintes parâmetros do que o usuário informar:"
                    "- Tipo de fonte de dados: Identifique se o usuário está solicitando dados de métricas" 
                    "(Prometheus), logs (Loki) ou traces (Tempo)."
                    "- Intervalo de tempo: Período de análise para métricas ou logs (e.g., últimos 5 minutos," 
                    "1 hora, etc.)."
                    "- Filtros adicionais: Exemplo: namespaces, pods, endpoints, ou identificadores específicos."

            "3. Estruturação de Consultas"
                "- Utilize a sintaxe adequada para cada sistema:"
                    "- Prometheus: PromQL para métricas temporais."
                    "- Loki: Filtros e expressões para logs."
                    "- Tempo: Filtros e spans específicos para traces de latência."

            "4. Análises e Respostas Detalhadas"
                "- Após realizar a consulta, forneça:"
                    "- Resumo dos Resultados: Apresente os dados ou logs de forma clara e legível."
                    "- Análise Contextual: Explique o que os resultados significam para a performance ou" 
                    "comportamento do sistema."
                    "- Recomendações: Sugira ações corretivas ou melhorias, se aplicável."

            "5. Recomendações e Ajustes"
                "- Caso os parâmetros fornecidos pelo usuário sejam insuficientes, peça mais informações de maneira" 
                "objetiva, como o intervalo de tempo desejado, o tipo de métrica, ou quaisquer filtros específicos."
        
            "Métricas Disponíveis por Categoria (Prometheus)"
            "1. CPU:"
                "- Métricas disponíveis: cpu_usage_seconds_total, node_cpu_seconds_total, process_cpu_seconds_total."

            "2. Rede:"
                "- Métricas disponíveis: node_network_receive_bytes_total, node_network_transmit_bytes_total," 
                "node_network_receive_errors_total."

            "3. Memória:"
                "- Métricas disponíveis: node_memory_MemAvailable_bytes, node_memory_MemFree_bytes," 
                "node_memory_Active_bytes."

            "Logs (Loki):"
            "- As consultas baseiam-se em padrões ou termos específicos, como:"
                "- Identificar erros em um serviço: level=""error""."
                "- Filtrar logs por namespace ou pod: {namespace=""example", "pod=""pod-name""}."

            "Traces (Tempo)"
            "- As análises de traces incluem spans e latências específicas:"
                "- Identificar spans com maior tempo de execução."
                "- Traçar dependências e gargalos em serviços distribuídos."

            "Exemplo de Uso"
            "1. Métricas (Prometheus)"
                "- Pergunta: ""Quais foram os picos de uso de CPU nos últimos 10 minutos?" 
                    "- Interprete o recurso (CPU) e o intervalo de tempo (10 minutos)."
                    "- Construa uma consulta PromQL:"
                    "max(rate(node_cpu_seconds_total[10m]))"
                    "- Responda com os resultados, identificando os momentos de maior uso."

            "2. Logs (Loki)"
            "- Pergunta:" "Mostre todos os logs de erro do serviço X no namespace Y."
                "- Construa uma consulta Loki:"
                "{namespace=""Y"", service=""X""} |= ""error"
                "- Filtre os resultados e resuma os logs encontrados."

            "3.Traces (Tempo)"
            "Pergunta:" "Quais spans apresentam a maior latência em um serviço específico?"
                "- Filtre por spans e latências no Tempo, identificando os gargalos principais."

            "Seja claro e objetivo ao gerar consultas e interpretar os resultados. Certifique-se de alinhar as" 
            "respostas às necessidades do usuário e às especificidades do Prometheus, Loki e Tempo."
        )

        # Variáveis para consulta
        query = None
        metric_description = None
        is_loki_query = False  # Flag para identificar se a consulta é sobre o Loki

        time_pattern = r"(\d+)\s*(segundos|minutos|horas|dias)"
        match = re.search(time_pattern, user_input)
        time_interval = None
        if match:
            value, unit = match.groups()
            unit_abbreviation = {
                "segundos": "s",
                "minutos": "m",
                "horas": "h",
                "dias": "d",
            }
            time_interval = f"{value}{unit_abbreviation[unit]}"

        # Identificar a consulta baseada nas palavras-chave
        if "cpu" in user_input:
            if time_interval:
                query = f"rate(process_cpu_seconds_total[{time_interval}])"
                metric_description = f"uso médio de CPU nos últimos {match.group(0)}"
            elif "loki" in user_input:
                is_loki_query = True  # A consulta é para Loki
                query = 'process_cpu_seconds_total{job="loki"}' # Ajuste conforme seu nome de job
                metric_description = "uso de CPU do Loki"
            else:
                query = "sum(process_cpu_seconds_total)"
                metric_description = "tempo total de uso de CPU"

        elif "memória" in user_input:
            query = "process_resident_memory_bytes"
            metric_description = "uso atual de memória residente"
        
        elif "disco" in user_input:
            query = "node_filesystem_avail_bytes"
            metric_description = "espaço disponível em disco"
        
        elif "rede" in user_input:
            query = "rate(node_network_receive_bytes_total)"
            metric_description = "taxa de recebimento de dados na rede"

        # Caso haja uma consulta válida
        if query:
            if is_loki_query:
                # Consultar Loki, se a flag for verdadeira
                loki_response = requests.get(
                    LOKI_URL, params={"query": query}, timeout=5
                )

                if loki_response.status_code != 200:
                    return jsonify(
                        {"answer": f"Erro ao acessar métricas do Loki. Status code: {loki_response.status_code}. Detalhes: {loki_response.text}"}
                    )

                try:
                    loki_data = loki_response.json()
                    if "data" in loki_data and "result" in loki_data["data"]:
                        results = loki_data["data"]["result"]
                        if results:
                            # Formatar os dados para enviar ao Groq
                            metric_values = [
                                {
                                    "metric": item["metric"],
                                    "value": item["value"][1],
                                }
                                for item in results
                            ]
                            groq_input = f"""
                            {context}

                            O usuário perguntou: "{user_input}"

                            Dados Loki obtidos para a métrica "{metric_description}":
                            {metric_values}

                            Gere uma resposta detalhada com base nesses dados.
                            """

                            # Consultar o modelo Groq para gerar a resposta
                            groq_response = client.chat.completions.create(
                                model=MIXTRAL_MODEL,
                                messages=[{"role": "system", "content": groq_input}],
                                temperature=1,
                                max_tokens=1024,
                                top_p=1,
                            )

                            return jsonify({"answer": groq_response.choices[0].message.content.strip()})

                        else:
                            return jsonify(
                                {"answer": f"Não há dados disponíveis para a métrica '{metric_description}' no momento."}
                            )
                    else:
                        return jsonify({"answer": "Erro ao processar a resposta do Loki: dados ausentes."})
                except Exception as e:
                    return jsonify({"answer": f"Erro ao processar os dados do Loki: {str(e)}"})

            else:
                # Consultar Prometheus se não for uma consulta Loki
                prometheus_response = requests.get(
                    PROMETHEUS_URL, params={"query": query}, timeout=5
                )

                if prometheus_response.status_code != 200:
                    return jsonify(
                        {"answer": f"Erro ao acessar métricas do Prometheus. Status code: {prometheus_response.status_code}. Detalhes: {prometheus_response.text}"}
                    )   

                try:
                    prometheus_data = prometheus_response.json()
                    if "data" in prometheus_data and "result" in prometheus_data["data"]:
                        results = prometheus_data["data"]["result"]
                        if results:
                            # Formatar os dados para enviar ao Groq
                            metric_values = [
                                {
                                    "metric": item["metric"],
                                    "value": item["value"][1],
                                }
                                for item in results
                            ]
                            groq_input = f"""
                            {context}

                            O usuário perguntou: "{user_input}"

                            Dados Prometheus obtidos para a métrica "{metric_description}":
                            {metric_values}

                            Gere uma resposta detalhada com base nesses dados.
                            """

                            # Consultar o modelo Groq para gerar a resposta
                            groq_response = client.chat.completions.create(
                                model=MIXTRAL_MODEL,
                                messages=[{"role": "system", "content": groq_input}],
                                temperature=1,
                                max_tokens=1024,
                                top_p=1,
                            )

                            return jsonify({"answer": groq_response.choices[0].message.content.strip()})

                        else:
                            return jsonify(
                                {"answer": f"Não há dados disponíveis para a métrica '{metric_description}' no momento."}
                            )
                    else:
                        return jsonify({"answer": "Erro ao processar a resposta do Prometheus: dados ausentes."})
                except Exception as e:
                    return jsonify({"answer": f"Erro ao processar os dados do Prometheus: {str(e)}"})

        # Caso não seja uma pergunta relacionada a métricas
        groq_response = client.chat.completions.create(
            model=MIXTRAL_MODEL,
            messages=session['conversation'],
            temperature=1,
            max_tokens=1024,
            top_p=1,
        )

        answer = groq_response.choices[0].message.content.strip()
        session['conversation'].append({"role": "assistant", "content": answer})

        return jsonify({"answer": groq_response.choices[0].message.content.strip()})

    except requests.exceptions.ConnectionError:
        return jsonify({"answer": "Erro: Não foi possível se conectar aos serviços."})
    except Exception as e:
        return jsonify({"answer": f"Erro ao processar a consulta: {str(e)}"})

if __name__ == "__main__":
    # Iniciar servidor de métricas na porta 8000
    start_http_server(8000)

    # Iniciar a aplicação Flask
    app.run(host="0.0.0.0", port=5000)