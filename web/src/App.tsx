import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ChatPanel from "./components/ChatPanel";
import TranscriptPanel from "./components/TranscriptPanel";
import ProtocolViewer from "./components/ProtocolViewer";
import PacketDialog from "./components/PacketDialog";
import PacketStatusPanel from "./components/PacketStatusPanel";

/** The same set of page routes, used both at the root (single-project mode)
 *  and under /p/:projectId (launcher mode). */
function PageRoutes() {
  return (
    <>
      <Route index element={<ChatPanel />} />
      <Route path="history" element={<TranscriptPanel />} />
      <Route path="protocol" element={<ProtocolViewer />} />
      <Route path="packet" element={<PacketDialog />} />
      <Route path="packet-status" element={<PacketStatusPanel />} />
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Single-project mode (flat routes) */}
        {PageRoutes()}

        {/* Launcher mode: project-scoped routes */}
        <Route path="p/:projectId">{PageRoutes()}</Route>

      </Route>
    </Routes>
  );
}
