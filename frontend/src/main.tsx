import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import { GuestOnly, RequireAuth, RequireWorkspace } from "./components/guards";
import { AuthProvider } from "./lib/auth";
import { WorkspaceProvider } from "./lib/workspace";
import AcceptInvite from "./pages/AcceptInvite";
import ComingSoon from "./pages/ComingSoon";
import Dashboard from "./pages/Dashboard";
import ForgotPassword from "./pages/ForgotPassword";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Members from "./pages/Members";
import NotFound from "./pages/NotFound";
import Onboarding from "./pages/Onboarding";
import Register from "./pages/Register";
import ResetPassword from "./pages/ResetPassword";
import VerifyEmail from "./pages/VerifyEmail";
import WorkspaceSettings from "./pages/WorkspaceSettings";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <WorkspaceProvider>
          <Routes>
            <Route path="/" element={<Home />} />
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
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/domains" element={<ComingSoon title="Domains" description="Every domain this workspace monitors." when="the next release" />} />
                  <Route path="/alerts" element={<ComingSoon title="Alerts" description="Problems that need someone to act." when="a later release" />} />
                  <Route path="/settings/members" element={<Members />} />
                  <Route path="/settings/workspace" element={<WorkspaceSettings />} />
                  <Route path="/settings" element={<Navigate to="/settings/workspace" replace />} />
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
