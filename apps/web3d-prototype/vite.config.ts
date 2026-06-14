import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Web-native 3D configurator MVP (Option B). WebGL2 target.
export default defineConfig({
  plugins: [react()],
  // Force a single React/reconciler instance — avoids R3F "Invalid hook call"
  // when Vite pre-bundles a second copy for the @react-three/fiber renderer.
  // @react-three/postprocessing + drei MUST be deduped/pre-bundled too, or the
  // EffectComposer captures a second React/fiber and throws "Invalid hook call".
  resolve: {
    dedupe: [
      "react",
      "react-dom",
      "@react-three/fiber",
      "@react-three/drei",
      "@react-three/postprocessing",
      "three",
    ],
  },
  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "@react-three/fiber",
      "@react-three/drei",
      "@react-three/postprocessing",
    ],
  },
  server: { host: "127.0.0.1", port: 5181, strictPort: true },
});
