import ReactDOM from "react-dom/client";
import App from "./App";
import { useStore } from "./state/store";
import "./index.css";

// Dev-only: expose the Zustand store on window for debugging / QA from the console
// (e.g. window.useStore.getState().heroCaptureFn(...)). Stripped from prod builds.
if (import.meta.env.DEV) (window as unknown as { useStore: typeof useStore }).useStore = useStore;

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
