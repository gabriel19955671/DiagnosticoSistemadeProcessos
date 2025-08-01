import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# --- Configuração da Página ---
st.set_page_config(
    page_title="Diagnóstico de Ferramentas Contábeis",
    page_icon="📊",
    layout="wide"
)

# --- Funções de Processamento e Análise ---

def padronizar_gclick(df):
    """Converte um DataFrame do G-Click para o formato padrão."""
    df_padronizado = df.rename(columns={
        'Task ID': 'id_tarefa',
        'Task Name': 'nome_tarefa',
        'Client Name': 'cliente',
        'Assignee': 'responsavel',
        'Due Date': 'data_prevista_conclusao',
        'Completion Date': 'data_real_conclusao'
    })
    df_padronizado['origem_ferramenta'] = 'G-Click'
    return df_padronizado

def padronizar_onvio(df):
    """Converte um DataFrame do Onvio para o formato padrão."""
    df_padronizado = df.rename(columns={
        'ProcessoID': 'id_tarefa',
        'Descricao': 'nome_tarefa',
        'NomeCliente': 'cliente',
        'Executor': 'responsavel',
        'PrazoFatal': 'data_prevista_conclusao',
        'DataFinalizacao': 'data_real_conclusao'
    })
    df_padronizado['origem_ferramenta'] = 'Onvio'
    return df_padronizado

def categorizar_tarefa(nome_tarefa):
    """
    Categoriza a tarefa com base em palavras-chave.
    !!! IMPORTANTE: Ajuste estas regras para a sua realidade !!!
    """
    nome_tarefa = str(nome_tarefa).lower()
    if any(keyword in nome_tarefa for keyword in ['dctf', 'sped', 'fiscal', 'imposto', 'das']):
        return 'Fiscal'
    elif any(keyword in nome_tarefa for keyword in ['balancete', 'contábil', 'conciliação']):
        return 'Contábil'
    elif any(keyword in nome_tarefa for keyword in ['folha', 'admissão', 'rescisão', 'esocial']):
        return 'Depto. Pessoal'
    else:
        return 'Outros'

def calcular_metricas(df):
    """Calcula novas colunas para análise."""
    df['data_prevista_conclusao'] = pd.to_datetime(df['data_prevista_conclusao'], errors='coerce')
    df['data_real_conclusao'] = pd.to_datetime(df['data_real_conclusao'], errors='coerce')

    df['status_prazo'] = 'No Prazo'
    df.loc[df['data_real_conclusao'] > df['data_prevista_conclusao'], 'status_prazo'] = 'Em Atraso'
    df.loc[df['data_real_conclusao'].isna(), 'status_prazo'] = 'Pendente'

    df['dias_de_atraso'] = (df['data_real_conclusao'] - df['data_prevista_conclusao']).dt.days
    df.loc[df['dias_de_atraso'] < 0, 'dias_de_atraso'] = 0

    # Adiciona colunas de tipo de tarefa e mês de conclusão
    df['tipo_tarefa'] = df['nome_tarefa'].apply(categorizar_tarefa)
    df['mes_conclusao'] = df['data_real_conclusao'].dt.to_period('M').astype(str)

    return df

# Função para converter DataFrame para CSV (para download)
@st.cache_data
def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# --- Interface (UI) ---

st.title("📊 Sistema de Diagnóstico de Gestores de Tarefas")
st.markdown("Faça o upload da sua planilha para analisar a performance e identificar gargalos.")

# --- Barra Lateral para Upload e Filtros ---
with st.sidebar:
    st.header("Configurações")
    ferramenta_selecionada = st.selectbox("1. Selecione a ferramenta", ["G-Click", "Onvio Processos", "Acessórias"])
    arquivo_carregado = st.file_uploader("2. Carregue seu arquivo", type=["csv", "xlsx"])
    st.info("O sistema espera colunas como 'Cliente', 'Responsável', 'Data Prevista' e 'Data de Conclusão'.")

# --- Lógica Principal do App ---
if arquivo_carregado is not None:
    try:
        df_bruto = pd.read_excel(arquivo_carregado) if arquivo_carregado.name.endswith('.xlsx') else pd.read_csv(arquivo_carregado)

        if ferramenta_selecionada == "G-Click":
            df_padronizado = padronizar_gclick(df_bruto)
        elif ferramenta_selecionada == "Onvio Processos":
            df_padronizado = padronizar_onvio(df_bruto)
        else:
            st.error("Função de padronização não implementada.")
            st.stop()

        df_analise = calcular_metricas(df_padronizado)
        st.success(f"Arquivo '{arquivo_carregado.name}' processado! Análise abaixo:")

        with st.sidebar:
            st.header("Filtros de Análise")
            cliente_filtro = st.multiselect("Filtrar por Cliente:", options=df_analise['cliente'].unique(), default=df_analise['cliente'].unique())
            responsavel_filtro = st.multiselect("Filtrar por Responsável:", options=df_analise['responsavel'].unique(), default=df_analise['responsavel'].unique())
            
            df_filtrado = df_analise[df_analise['cliente'].isin(cliente_filtro) & df_analise['responsavel'].isin(responsavel_filtro)]

        # --- Exibição dos Relatórios ---
        st.header("Dashboard de Performance")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Tarefas", f"{df_filtrado.shape[0]:,}")
        taxa_no_prazo = (df_filtrado[df_filtrado['status_prazo'] == 'No Prazo'].shape[0] / df_filtrado.shape[0]) * 100 if df_filtrado.shape[0] > 0 else 0
        col2.metric("Tarefas no Prazo", f"{taxa_no_prazo:.2f}%")
        media_atraso = df_filtrado[df_filtrado['dias_de_atraso'] > 0]['dias_de_atraso'].mean()
        col3.metric("Média de Dias de Atraso", f"{media_atraso:.1f} dias" if pd.notna(media_atraso) else "N/A")
        
        st.markdown("---")

        # --- NOVAS ANÁLISES ---

        # 1. Performance por Colaborador
        st.header("Desempenho por Colaborador")
        col_resp1, col_resp2 = st.columns(2)
        
        with col_resp1:
            df_tarefas_resp = df_filtrado.groupby('responsavel').size().reset_index(name='contagem').sort_values('contagem', ascending=False)
            fig_resp_total = px.bar(df_tarefas_resp, x='responsavel', y='contagem', title='Volume de Tarefas por Responsável', labels={'responsavel': 'Responsável', 'contagem': 'Nº de Tarefas'})
            st.plotly_chart(fig_resp_total, use_container_width=True)

        with col_resp2:
            df_prazo_resp = df_filtrado[df_filtrado['status_prazo'] != 'Pendente'].groupby('responsavel')['status_prazo'].apply(lambda x: (x == 'No Prazo').sum() / len(x) * 100).reset_index(name='taxa_no_prazo').sort_values('taxa_no_prazo', ascending=False)
            fig_resp_prazo = px.bar(df_prazo_resp, x='responsavel', y='taxa_no_prazo', title='Taxa de Entrega no Prazo por Responsável (%)', labels={'responsavel': 'Responsável', 'taxa_no_prazo': '% no Prazo'})
            st.plotly_chart(fig_resp_prazo, use_container_width=True)

        # 2. Análise por Tipo de Tarefa
        st.header("Análise por Tipo de Tarefa")
        df_atraso_tipo = df_filtrado[df_filtrado['status_prazo'] == 'Em Atraso'].groupby('tipo_tarefa').size().reset_index(name='contagem').sort_values('contagem', ascending=False)
        fig_atraso_tipo = px.pie(df_atraso_tipo, names='tipo_tarefa', values='contagem', title='Tipos de Tarefa com Mais Atrasos')
        st.plotly_chart(fig_atraso_tipo, use_container_width=True)
        st.warning("A categorização de tarefas é uma estimativa. Ajuste a função `categorizar_tarefa` no código para refletir suas necessidades.")

        # 3. Evolução Temporal
        st.header("Evolução Temporal")
        df_temporal = df_filtrado[df_filtrado['status_prazo'] != 'Pendente'].copy()
        df_temporal = df_temporal.sort_values('mes_conclusao')
        df_evolucao = df_temporal.groupby('mes_conclusao')['status_prazo'].apply(lambda x: (x == 'No Prazo').sum() / len(x) * 100).reset_index(name='taxa_no_prazo')
        fig_evolucao = px.line(df_evolucao, x='mes_conclusao', y='taxa_no_prazo', title='Evolução da Taxa de Entrega no Prazo', markers=True, labels={'mes_conclusao': 'Mês', 'taxa_no_prazo': 'Taxa no Prazo (%)'})
        fig_evolucao.update_yaxes(range=[0, 105]) # Fixa o eixo Y de 0 a 105%
        st.plotly_chart(fig_evolucao, use_container_width=True)

        # 4. Tabela de dados e Botão de Exportação
        with st.expander("Ver dados detalhados e exportar"):
            st.dataframe(df_filtrado)
            
            csv = to_csv(df_filtrado)
            st.download_button(
                label="📥 Baixar dados como CSV",
                data=csv,
                file_name='diagnostico_tarefas.csv',
                mime='text/csv',
            )

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
else:
    st.info("Aguardando o carregamento de um arquivo para iniciar a análise.")

# --- Diagnóstico com Inteligência Artificial (GPT-4) ---
import openai

openai.api_key = st.secrets["OPENAI_API_KEY"]

st.markdown("---")
st.subheader("📌 Diagnóstico Automático com IA")

if st.button("Gerar Diagnóstico com IA"):
    with st.spinner("Gerando análise com inteligência artificial..."):
        resumo = df_filtrado[['cliente', 'responsavel', 'status_prazo', 'tipo_tarefa', 'dias_de_atraso']].head(50).to_csv(index=False)
        prompt = f"""Você é um analista contábil. Avalie os dados a seguir e gere um diagnóstico sobre gargalos, atrasos e oportunidades de melhoria:
{resumo}"""
        try:
            resposta = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Você é um analista contábil especialista em produtividade."},
                    {"role": "user", "content": prompt}
                ]
            )
            st.success("✅ Diagnóstico gerado com sucesso!")
            st.markdown(resposta["choices"][0]["message"]["content"])
        except Exception as e:
            st.error(f"Erro ao gerar diagnóstico com IA: {e}")
