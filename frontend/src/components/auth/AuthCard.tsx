import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { Input } from "../ui/Input";
import { Button } from "../ui/Button";
import { getApiError } from "../../lib/api";

interface AuthCardProps {
  mode: "login" | "register";
  loading: boolean;
  onSubmit: (values: Record<string, string>) => void;
  error?: unknown;
}

export function AuthCard({ mode, loading, onSubmit, error }: AuthCardProps) {
  const [values, setValues] = useState<Record<string, string>>({
    fullName: "",
    email: "",
    password: "",
    confirmPassword: ""
  });

  const errors = useMemo(() => {
    const next: Record<string, string> = {};
    if (values.email && !/^\S+@\S+\.\S+$/.test(values.email)) next.email = "Use a valid email address.";
    if (values.password && values.password.length < 8) next.password = "Password must be at least 8 characters.";
    if (mode === "register" && values.confirmPassword && values.password !== values.confirmPassword) {
      next.confirmPassword = "Passwords do not match.";
    }
    return next;
  }, [mode, values]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (Object.keys(errors).length) return;
    onSubmit(values);
  }

  const isRegister = mode === "register";

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <motion.form
        onSubmit={submit}
        className="glass w-full max-w-md rounded-lg p-6 shadow-violet sm:p-8"
        initial={{ y: 18, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
      >
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-electric/15 text-electric shadow-glow">
            <Sparkles className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">{isRegister ? "Create workspace" : "Welcome back"}</h1>
            <p className="text-sm text-slate-400">Vocal Bridge AI dubbing studio</p>
          </div>
        </div>

        <div className="space-y-4">
          {isRegister && (
            <Input
              label="Full name"
              value={values.fullName}
              onChange={(event) => setValues({ ...values, fullName: event.target.value })}
              required
            />
          )}
          <Input
            label="Email"
            type="email"
            value={values.email}
            error={errors.email}
            onChange={(event) => setValues({ ...values, email: event.target.value })}
            required
          />
          <Input
            label="Password"
            type="password"
            value={values.password}
            error={errors.password}
            onChange={(event) => setValues({ ...values, password: event.target.value })}
            required
          />
          {isRegister && (
            <Input
              label="Confirm password"
              type="password"
              value={values.confirmPassword}
              error={errors.confirmPassword}
              onChange={(event) => setValues({ ...values, confirmPassword: event.target.value })}
              required
            />
          )}
        </div>

        {Boolean(error) && <p className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">{getApiError(error)}</p>}

        <Button className="mt-6 w-full" loading={loading}>
          {isRegister ? "Register" : "Login"}
        </Button>

        <p className="mt-6 text-center text-sm text-slate-400">
          {isRegister ? "Already have an account?" : "New to Vocal Bridge?"}{" "}
          <Link className="font-semibold text-electric hover:text-cyan-200" to={isRegister ? "/login" : "/register"}>
            {isRegister ? "Login" : "Create account"}
          </Link>
        </p>
      </motion.form>
    </div>
  );
}
