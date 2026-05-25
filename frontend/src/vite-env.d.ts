/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RAG_API_URL?: string;
  readonly VITE_DEV_API_PROXY?: string;
  readonly VITE_DEMO_UI?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
