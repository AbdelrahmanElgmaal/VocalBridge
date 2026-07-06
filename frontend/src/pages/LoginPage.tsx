import { AuthCard } from "../components/auth/AuthCard";
import { useLogin } from "../hooks/useAuth";

export function LoginPage() {
  const login = useLogin();

  return (
    <AuthCard
      mode="login"
      loading={login.isPending}
      error={login.error}
      onSubmit={(values) => login.mutate({ email: values.email, password: values.password })}
    />
  );
}
