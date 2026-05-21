FROM node:22-alpine AS deps
WORKDIR /app
COPY services/frontend/package.json services/frontend/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY services/frontend/ ./
ARG API_GATEWAY_INGESTA_URL
ARG API_GATEWAY_CONSULTA_URL
ARG TRANSCRIPCION_URL
ARG PREPROCESSING_URL
ARG LLM_EXTRACTION_URL
ARG LLM_NORMALIZATION_URL
ARG LLM_LABELING_URL
ARG ANXIETY_SCORE_URL
ARG ML_PREDICTION_URL
ARG AUDIT_ETHICS_URL
ENV NEXT_TELEMETRY_DISABLED=1 \
    API_GATEWAY_INGESTA_URL=$API_GATEWAY_INGESTA_URL \
    API_GATEWAY_CONSULTA_URL=$API_GATEWAY_CONSULTA_URL \
    TRANSCRIPCION_URL=$TRANSCRIPCION_URL \
    PREPROCESSING_URL=$PREPROCESSING_URL \
    LLM_EXTRACTION_URL=$LLM_EXTRACTION_URL \
    LLM_NORMALIZATION_URL=$LLM_NORMALIZATION_URL \
    LLM_LABELING_URL=$LLM_LABELING_URL \
    ANXIETY_SCORE_URL=$ANXIETY_SCORE_URL \
    ML_PREDICTION_URL=$ML_PREDICTION_URL \
    AUDIT_ETHICS_URL=$AUDIT_ETHICS_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
