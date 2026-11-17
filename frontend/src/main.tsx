import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import { GuestOnly, RequireAuth, RequireWorkspace } from "./components/guards";
import { AuthProvider } from "./lib/auth";
import { WorkspaceProvider } from "./lib/workspace";
import AcceptInvite from "./pages/AcceptInvite";
import Checker from "./pages/Checker";
import Alerts from "./pages/Alerts";
import Billing from "./pages/Billing";
import Certificates from "./pages/Certificates";
import ClientReports from "./pages/ClientReports";
import DmarcReports from "./pages/DmarcReports";
import DomainDetail from "./pages/DomainDetail";
import Domains from "./pages/Domains";
import Overview from "./pages/Overview";
import ForgotPassword from "./pages/ForgotPassword";
import Home from "./pages/Home";
import LegalPage from "./pages/LegalPage";
import ToolPage from "./pages/tools/ToolPage";
import ToolsIndex from "./pages/tools/ToolsIndex";
import Login from "./pages/Login";
import Members from "./pages/Members";
import NotFound from "./pages/NotFound";
import Onboarding from "./pages/Onboarding";
import Register from "./pages/Register";
import Staff, { StaffWorkspace } from "./pages/Staff";
import ResetPassword from "./pages/ResetPassword";
import VerifyEmail from "./pages/VerifyEmail";
import WorkspaceSettings from "./pages/WorkspaceSettings";
import { applyTheme, initialTheme } from "./lib/theme";
import "./index.css";

applyTheme(initialTheme());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <WorkspaceProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/tools" element={<ToolsIndex />} />
            <Route path="/tools/:slug" element={<ToolPage />} />
            <Route path="/legal" element={<Navigate to="/legal/terms" replace />} />
            <Route path="/legal/:slug" element={<LegalPage />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route element={<GuestOnly />}>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
            </Route>
            <Route element={<RequireAuth />}>
              <Route path="/onboarding" element={<Onboarding />} />
              <Route path="/invite/accept" element={<AcceptInvite />} />
              <Route element={<RequireWorkspace />}>
                <Route element={<AppLayout />}>
                  <Route path="/dashboard" element={<Overview />} />
                  <Route path="/domains" element={<Domains />} />
                  <Route path="/domains/:id" element={<DomainDetail />} />
                  <Route path="/tools/checker" element={<Checker />} />
                  <Route path="/alerts" element={<Alerts />} />
                  <Route path="/reports/dmarc" element={<DmarcReports />} />
                  <Route path="/reports/tls" element={<Certificates />} />
                  <Route path="/reports/client" element={<ClientReports />} />
                  <Route path="/settings/billing" element={<Billing />} />
                  <Route path="/settings/members" element={<Members />} />
                  <Route path="/settings/workspace" element={<WorkspaceSettings />} />
                  <Route path="/settings" element={<Navigate to="/settings/workspace" replace />} />
                  <Route path="/staff" element={<Staff />} />
                  <Route path="/staff/workspaces/:id" element={<StaffWorkspace />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </WorkspaceProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
