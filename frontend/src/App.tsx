import { HashRouter, Routes, Route } from "react-router-dom";
import Shell from "./components/Shell";
import { SessionProvider } from "./state/session";
import Dashboard from "./screens/Dashboard";
import Intake from "./screens/Intake";
import Analysis from "./screens/Analysis";
import Neural from "./screens/Neural";
import OriginTrace from "./screens/OriginTrace";
import Recapture from "./screens/Recapture";
import Entities from "./screens/Entities";
import GraphScreen from "./screens/Graph";
import CrossCase from "./screens/CrossCase";
import Stress from "./screens/Stress";
import Timeline from "./screens/Timeline";
import Audit from "./screens/Audit";
import Packet from "./screens/Packet";
import Benchmark from "./screens/Benchmark";

export default function App() {
  return (
    <SessionProvider>
      <HashRouter>
        <Shell>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Intake />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/neural" element={<Neural />} />
            <Route path="/origin" element={<OriginTrace />} />
            <Route path="/recapture" element={<Recapture />} />
            <Route path="/entities" element={<Entities />} />
            <Route path="/graph" element={<GraphScreen />} />
            <Route path="/cross-case" element={<CrossCase />} />
            <Route path="/stress" element={<Stress />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/benchmark" element={<Benchmark />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/packet" element={<Packet />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </Shell>
      </HashRouter>
    </SessionProvider>
  );
}
