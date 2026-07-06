import { Navigate, Outlet } from "react-router-dom";
import { tokenStore } from "../../lib/auth";

export function ProtectedRoute() {
  return tokenStore.isAuthenticated() ? <Outlet /> : <Navigate to="/login" replace />;
}
