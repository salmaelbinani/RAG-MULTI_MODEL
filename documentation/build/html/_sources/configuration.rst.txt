=============
Configuration
=============

Paramètres Principaux
--------------------

Modèles LLM
^^^^^^^^^^^

Sélectionnez parmi :

- llama3.1
- mistral
- llama3.2
- gemma:7b
- llama2:13b

Seuil de Pertinence
------------------

- Plage : 0.0 à 1.0
- Défaut : 0.3
- Influence la sélection des documents pertinents

Configuration Avancée
--------------------

Vectorisation
^^^^^^^^^^^^^

- Utilisation de Chroma pour la création de vectorstore
- Chunk size configurable
- Gestion des chevauchements de texte

Mémoire de Conversation
----------------------

- Historique de conversation conservé
- Limite configurable (à développer)

Personnalisation
---------------

Variables d'Environnement
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Exemple de configuration
   export OLLAMA_BASE_URL=http://localhost:11434
   export LLM_MODEL=llama3.1

Exemple de Configuration
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Configuration programmatique
   from multi_model_rag import initialize_rag_components

   llm, embeddings, chroma_client = initialize_rag_components(
       model_name="llama3.1",
       persist_dir="./rag_database"
   )