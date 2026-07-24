import { startServer } from "./server.js";
const PORT = Number(process.env.PORT ?? 8787);
await startServer({ port: PORT });
console.log(`[massive-heatmap] backend listening on http://localhost:${PORT}`);
