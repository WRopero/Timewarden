# Thin image over the pinned version: it only prepares the embeddings
# model directory with the correct owner so that the named volume
# (agents_model_cache) is writable by the `cognee` user.
FROM cognee/cognee:1.6.5
USER root
RUN mkdir -p /models && chown cognee:cognee /models
USER cognee
