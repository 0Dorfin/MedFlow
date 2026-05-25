import type { NextConfig } from "next";

const ingesta = process.env.API_GATEWAY_INGESTA_URL ?? "http://localhost:8000";
const consulta = process.env.API_GATEWAY_CONSULTA_URL ?? "http://localhost:8001";
const transcripcion = process.env.TRANSCRIPCION_URL ?? "http://localhost:9100";
const preprocessing = process.env.PREPROCESSING_URL ?? "http://localhost:9101";
const extraction = process.env.LLM_EXTRACTION_URL ?? "http://localhost:9110";
const normalization = process.env.LLM_NORMALIZATION_URL ?? "http://localhost:9111";
const labeling = process.env.LLM_LABELING_URL ?? "http://localhost:9112";
const anxiety = process.env.ANXIETY_SCORE_URL ?? "http://localhost:9113";
const prediction = process.env.ML_PREDICTION_URL ?? "http://localhost:9122";
const audit = process.env.AUDIT_ETHICS_URL ?? "http://localhost:9124";
const n8n = process.env.N8N_WEBHOOK_BASE ?? "http://localhost:5678/webhook";

const proxyTimeoutMs = Number(process.env.NEXT_PROXY_TIMEOUT_MS ?? 600_000);

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    proxyTimeout: proxyTimeoutMs,
  },
  async rewrites() {
    return [
      { source: "/api/ingesta/:path*", destination: `${ingesta}/:path*` },
      { source: "/api/consulta/:path*", destination: `${consulta}/:path*` },
      { source: "/api/transcripcion/:path*", destination: `${transcripcion}/:path*` },
      { source: "/api/preprocessing/:path*", destination: `${preprocessing}/:path*` },
      { source: "/api/extraction/:path*", destination: `${extraction}/:path*` },
      { source: "/api/normalization/:path*", destination: `${normalization}/:path*` },
      { source: "/api/labeling/:path*", destination: `${labeling}/:path*` },
      { source: "/api/anxiety/:path*", destination: `${anxiety}/:path*` },
      { source: "/api/prediction/:path*", destination: `${prediction}/:path*` },
      { source: "/api/audit/:path*", destination: `${audit}/:path*` },
      { source: "/api/n8n/:path*", destination: `${n8n}/:path*` },
    ];
  },
};

export default nextConfig;
