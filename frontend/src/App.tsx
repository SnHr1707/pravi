import { Navigate, Route, Routes } from "react-router-dom";
import StaffLayout from "./components/StaffLayout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Report from "./pages/Report";
import Track from "./pages/Track";
import Dashboard from "./pages/Dashboard";
import Assets from "./pages/Assets";
import AssetDetail from "./pages/AssetDetail";
import Complaints from "./pages/Complaints";
import Works from "./pages/Works";
import Documents from "./pages/Documents";
import Planner from "./pages/Planner";
import Contractors from "./pages/Contractors";
import Settings from "./pages/Settings";
import Offices from "./pages/Offices";
import Digging from "./pages/Digging";
import Performance from "./pages/Performance";

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<Landing />} />
      <Route path="/report" element={<Report />} />
      <Route path="/track" element={<Track />} />
      <Route path="/login" element={<Login />} />
      <Route path="/performance" element={<Performance />} />
      {/* Staff (JWT cookie) */}
      <Route path="/app" element={<StaffLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="assets" element={<Assets />} />
        <Route path="assets/:id" element={<AssetDetail />} />
        <Route path="complaints" element={<Complaints />} />
        <Route path="works" element={<Works />} />
        <Route path="documents" element={<Documents />} />
        <Route path="planner" element={<Planner />} />
        <Route path="contractors" element={<Contractors />} />
        <Route path="settings" element={<Settings />} />
        <Route path="offices" element={<Offices />} />
        <Route path="digging" element={<Digging />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
