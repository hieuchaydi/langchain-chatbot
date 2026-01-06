# Markdown Chatbot using Gemini API and BM25

This project is a **Markdown-based document chatbot** that allows users to ask questions directly about the content of `.md` files.

The chatbot works by first retrieving the most relevant text sections from the uploaded Markdown documents using the **BM25 information retrieval algorithm (`BM25Okapi`)**. These retrieved sections are then passed as context to a **large language model accessed via the Gemini API**, which generates clear and context-aware answers grounded in the original documents.

By combining classical information retrieval with modern language models, this project follows a **Retrieval-Augmented Generation (RAG)** approach without relying on embeddings or vector databases. This makes the system lightweight, fast, and easy to understand, while still delivering accurate document-aware responses.

The project is well suited for use cases such as:
- Exploring technical documentation
- Querying README files and wikis
- Building lightweight knowledge base chatbots
- Learning or prototyping RAG systems with BM25

Overall, this repository provides a simple and practical example of how BM25 can be integrated with the Gemini API to build an efficient document-based chatbot for Markdown content.
