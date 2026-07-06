import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { tokenStore } from "./lib/auth";
import { Skeleton } from "./components/ui/Skeleton";

const LandingPage = lazy(() => import("./pages/LandingPage").then((module) => ({ default: module.LandingPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const CreateTranslationPage = lazy(() => import("./pages/CreateTranslationPage").then((module) => ({ default: module.CreateTranslationPage })));
const TranslationDetailsPage = lazy(() => import("./pages/TranslationDetailsPage").then((module) => ({ default: module.TranslationDetailsPage })));
const HistoryPage = lazy(() => import("./pages/HistoryPage").then((module) => ({ default: module.HistoryPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })));
const RegisterPage = lazy(() => import("./pages/RegisterPage").then((module) => ({ default: module.RegisterPage })));

function PageFallback() {
  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center gap-4 px-6">
      <Skeleton className="h-12 w-72" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

export function App() {
  const defaultRoute = tokenStore.isAuthenticated() ? "/dashboard" : "/login";

  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/translate" element={<CreateTranslationPage />} />
          <Route path="/translations/:id" element={<TranslationDetailsPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Route>
        <Route path="*" element={<Navigate to={defaultRoute} replace />} />
      </Routes>
    </Suspense>
  );
}
