import os
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import create_retrieval_chain, ConversationalRetrievalChain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.memory import ConversationBufferMemory
from langchain import hub
from langchain_core.messages import HumanMessage, AIMessage
from langchain_ollama import OllamaLLM, OllamaEmbeddings
import chromadb
import tempfile
from pathlib import Path

# Configuration de la page Streamlit
st.set_page_config(page_title="Assistant RAG Multi-Modèles", layout="wide")

# Initialisation des variables de session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_memory" not in st.session_state:
    st.session_state.chat_memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer"
    )

def check_relevance(question, docs, threshold=0.3):
    """Vérifie la pertinence des documents par rapport à la question"""
    if not docs:
        return False, 0
    
    doc_texts = [doc.page_content.lower() for doc in docs]
    question_words = [word.lower() for word in question.split() if len(word) > 3]
    
    matches = sum(1 for word in question_words for text in doc_texts if word in text)
    relevance_score = matches / len(question_words) if question_words else 0
    
    return relevance_score >= threshold, relevance_score

@st.cache_resource
def load_document(file):
    """Charge un document avec gestion du cache"""
    name, extension = os.path.splitext(file.name)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_file_path = tmp_file.name

    try:
        if extension.lower() == '.pdf':
            loader = PyPDFLoader(tmp_file_path)
        elif extension.lower() == '.txt':
            loader = TextLoader(tmp_file_path)
        elif extension.lower() in ['.docx', '.doc']:
            loader = Docx2txtLoader(tmp_file_path)
        else:
            raise ValueError(f"Extension de fichier non supportée: {extension}")
        
        documents = loader.load()
        return documents
    finally:
        os.remove(tmp_file_path)

def initialize_rag_components(model_name="llama3.1", persist_dir=None):
    """Initialise les composants RAG"""
    llm = OllamaLLM(model=model_name, base_url="http://localhost:11434")
    embeddings = OllamaEmbeddings(model=model_name, base_url="http://localhost:11434")
    
    if persist_dir:
        chroma_client = chromadb.PersistentClient(path=persist_dir)
    else:
        chroma_client = chromadb.Client()
    
    return llm, embeddings, chroma_client

# Interface utilisateur
st.title("💬 Assistant RAG Multi-Modèles")

# Sidebar pour la configuration
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # Sélection du modèle
    model_name = st.selectbox(
        "Choisir le modèle LLM",
        ["llama3.1", "mistral","llama3.2", "gemma:7b", "llama2:13b"],
        index=0
    )
    
    # Configuration de la pertinence
    relevance_threshold = st.slider(
        "Seuil de pertinence",
        min_value=0.0,
        max_value=1.0,
        value=0.3,
        step=0.1
    )
    
    # Upload de documents
    uploaded_files = st.file_uploader(
        "Charger des documents",
        accept_multiple_files=True,
        type=['pdf', 'txt', 'docx']
    )
    
    process_docs = st.button("Traiter les documents")

# Traitement des documents
if process_docs and uploaded_files:
    with st.spinner("Traitement des documents en cours..."):
        persist_dir = Path("./rag_database")
        persist_dir.mkdir(exist_ok=True)
        
        llm, embeddings, chroma_client = initialize_rag_components(
            model_name=model_name,
            persist_dir=str(persist_dir)
        )
        
        # Chargement et traitement des documents
        all_documents = []
        for file in uploaded_files:
            try:
                documents = load_document(file)
                all_documents.extend(documents)
                st.success(f"📄 {file.name} chargé avec succès")
            except Exception as e:
                st.error(f"❌ Erreur lors du chargement de {file.name}: {str(e)}")
        
        # Splitting des documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            length_function=len
        )
        splits = text_splitter.split_documents(all_documents)
        
        # Création du vectorstore
        vectorstore = Chroma(
            persist_directory=str(persist_dir),
            embedding_function=embeddings,
            client=chroma_client,
            collection_name=f"rag_collection_{model_name}"
        )
        
        vectorstore.add_documents(splits)
        st.session_state.vectorstore = vectorstore
        st.session_state.llm = llm
        st.success("✅ Documents traités avec succès!")

# Interface de chat
for message in st.session_state.messages:
    with st.chat_message("user" if isinstance(message, HumanMessage) else "assistant"):
        st.markdown(message.content)

# Zone de saisie
if prompt := st.chat_input("Posez votre question ici..."):
    st.session_state.messages.append(HumanMessage(content=prompt))
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        if hasattr(st.session_state, 'vectorstore') and hasattr(st.session_state, 'llm'):
            # Récupération des documents pertinents
            retriever = st.session_state.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 3}
            )
            
            retrieved_docs = retriever.get_relevant_documents(prompt)
            is_relevant, confidence = check_relevance(prompt, retrieved_docs, relevance_threshold)
            
            if is_relevant:
                # Utilisation du RAG pour les questions pertinentes
                chain = ConversationalRetrievalChain.from_llm(
                    llm=st.session_state.llm,
                    retriever=retriever,
                    memory=st.session_state.chat_memory,
                    return_source_documents=True
                )
                
                with st.spinner("🤔 Réflexion en cours..."):
                    response = chain({"question": prompt})
                    st.markdown(response["answer"])
                    
                    # Affichage des sources
                    with st.expander("📚 Sources"):
                        for i, doc in enumerate(response["source_documents"], 1):
                            st.markdown(f"**Source {i}:**\n{doc.page_content}\n")
                    
                    # Affichage des métriques
                    st.info(f"🎯 Score de pertinence: {confidence:.2f}")
            else:
                # Utilisation directe du LLM pour les questions hors contexte
                with st.spinner("🤔 Génération de la réponse..."):
                    response = st.session_state.llm.invoke(prompt)
                    st.markdown(response)
                    st.warning("⚠️ Réponse générée sans contexte documentaire")
            
            # Mise à jour de l'historique
            st.session_state.messages.append(AIMessage(content=response["answer"] if is_relevant else response))
        else:
            st.warning("⚠️ Veuillez d'abord charger et traiter des documents.")

# Bouton pour effacer l'historique
if st.sidebar.button("🗑️ Effacer l'historique"):
    st.session_state.messages = []
    st.session_state.chat_memory.clear()