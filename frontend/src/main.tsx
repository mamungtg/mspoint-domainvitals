import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import { GuestOnly, RequireAuth, RequireWorkspace } from "./components/guards";
import { AuthProvider } from "./lib/auth";
import { WorkspaceProvider } from "./lib/workspace";
import AcceptInvite from "./pages/AcceptInvite";
import Checker from "./pages/Checker";
import ComingSoon from "./pages/ComingSoon";
import DomainDetail from "./pages/DomainDetail";
import Domains from "./pages/Domains";
import Overview from "./pages/Overview";
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
                  <Route path="/alerts" element={<ComingSoon title="Alerts" description="Problems that need someone to act."
                    what={["A new failing check or a DNS record that changed", "Certificates close to expiry", "Mail and in-app notifications, with who acknowledged them"]} />} />
                  <Route path="/reports/dmarc" element={<ComingSoon title="DMARC reports" description="Who sends mail as your domains, and whether it passes."
                    what={["Aggregate reports from Google, Microsoft, Yahoo and others", "Sending sources with SPF and DKIM alignment", "Pass rate trends per domain"]} />} />
                  <Route path="/reports/tls" element={<ComingSoon title="SSL/TLS certificates" description="Certificate health for every monitored hostname."
                    what={["Days until expiry, with alerts at 30, 15, 7, 3 and 1 days", "Hostname, chain and TLS version checks", "Renewal history"]} />} />
                  <Route path="/settings/billing" element={<ComingSoon title="Plan and billing" description="Your plan, usage and invoices."
                    what={["Plans by number of domains", "Card payments and invoices through Stripe", "Self-service upgrades and cancellation"]} />} />
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
