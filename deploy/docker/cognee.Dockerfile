# Imagen delgada sobre la version fijada: solo prepara el directorio del
# modelo de embeddings con el dueño correcto para que el volumen nombrado
# (agents_model_cache) sea escribible por el usuario `cognee`.
FROM cognee/cognee:1.6.5
USER root
RUN mkdir -p /models && chown cognee:cognee /models
USER cognee
