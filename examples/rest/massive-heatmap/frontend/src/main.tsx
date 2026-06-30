import { createRoot } from "react-dom/client";
import { App } from "./App.js";
import { SettingsProvider } from "./settings.js";
import "./styles.css";
createRoot(document.getElementById("root")!).render(<SettingsProvider><App /></SettingsProvider>);
