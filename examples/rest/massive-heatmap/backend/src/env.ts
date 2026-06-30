import { config } from "dotenv";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Load the demo-root .env regardless of the process cwd. `npm run dev` runs the
// backend with its cwd in backend/, but the .env (and .env.example) live at the
// demo root, one level up from backend/.
const HERE = dirname(fileURLToPath(import.meta.url)); // backend/src
config({ path: join(HERE, "..", "..", ".env") });

export function apiKey(): string {
  const k = process.env.MASSIVE_API_KEY;
  if (!k) {
    throw new Error(
      "MASSIVE_API_KEY not set. Copy .env.example to .env (in the massive-heatmap root) and add your key.",
    );
  }
  return k;
}
