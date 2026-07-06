import { AuthCard } from "../components/auth/AuthCard";
import { useRegister } from "../hooks/useAuth";

export function RegisterPage() {
  const register = useRegister();

  return (
    <AuthCard
      mode="register"
      loading={register.isPending}
      error={register.error}
      onSubmit={(values) =>
        register.mutate({
          fullName: values.fullName,
          email: values.email,
          password: values.password,
          confirmPassword: values.confirmPassword
        })
      }
    />
  );
}
